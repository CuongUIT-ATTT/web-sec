"""Verified-imported-Context OWASP ZAP Access Control lifecycle.

This runner is deliberately not a generic scanner. It accepts only the local
VAmPI manifest, imports a manually reviewed Context, validates non-secret
attestation facts, and starts the Access Control add-on only after each gate
passes. Any gate failure produces a fresh, redacted ``NOT_RUN`` artifact.
"""

from __future__ import annotations

import os
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from vampi_authz_lab.common import write_redacted_json

from .zap_context_builder import (
    TARGET_BASE,
    ZapContextError,
    _zap_api,
    allowed_paths,
    capture_history_snapshot,
    history_baseline_summary,
    import_reviewed_context,
    load_allowlist_v2,
    load_context_attestation,
    seed_reviewed_paths,
    verify_history_delta,
    wait_for_history_quiescence,
    verify_imported_context,
    verify_preloaded_context,
    verify_imported_users,
    verify_seed_delta,
    verify_site_tree_containment,
    verify_user_authentication_state,
)

ZAP_REPORT_PATH = Path("results/zap/zap_access_control_report.json")
ZAP_STATUS_PATH = Path("results/zap/zap_run_status.json")
ZAP_BOOTSTRAP_PATH = Path("results/zap/zap_bootstrap_readiness.json")
POLL_INTERVAL_SECONDS = 2
DEFAULT_TIMEOUT_SECONDS = 120


class _AccessControlHtmlParser(HTMLParser):
    """Extract only exact reviewed rows from ZAP's Access Control report table."""

    _OUTCOMES = frozenset({"ILLEGAL", "VALID", "UNKNOWN"})

    def __init__(self, paths: set[str], users: set[str]) -> None:
        super().__init__(convert_charrefs=True)
        self._paths = paths
        self._users = users
        self._in_result_row = False
        self._cells: list[dict[str, str]] = []
        self._header_cells: list[str] = []
        self._current_cell: dict[str, str] | None = None
        self._current_header_cell: list[str] | None = None
        self._header_users: list[str] | None = None
        self.records: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        attributes = {name.lower(): value or "" for name, value in attrs}
        if normalized_tag == "tr":
            self._in_result_row = False
            self._cells = []
            self._header_cells = []
        elif normalized_tag == "td":
            self._in_result_row = True
            self._current_cell = {"class": attributes.get("class", ""), "text": ""}
        elif normalized_tag == "th":
            self._current_header_cell = []
        elif normalized_tag == "a" and self._current_cell is not None:
            self._current_cell["href"] = attributes.get("href", "")

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell["text"] += data
        elif self._current_header_cell is not None:
            self._current_header_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "td" and self._current_cell is not None:
            self._cells.append(self._current_cell)
            self._current_cell = None
        elif normalized_tag == "th" and self._current_header_cell is not None:
            self._header_cells.append("".join(self._current_header_cell).strip())
            self._current_header_cell = None
        elif normalized_tag == "tr":
            if self._in_result_row:
                self._record_row()
            else:
                self._record_header_users()
            self._in_result_row = False
            self._cells = []
            self._header_cells = []

    def _record_header_users(self) -> None:
        """Bind result columns to exact reviewed display names from the header."""
        candidates = [value for value in self._header_cells if value in self._users]
        if len(candidates) == len(self._users) and set(candidates) == self._users:
            self._header_users = candidates

    def _record_row(self) -> None:
        """Read the documented fixed table layout without retaining raw cells."""
        if self._header_users is None or len(self._cells) != 2 + (2 * len(self._header_users)):
            return
        if self._cells[0]["text"].strip().upper() != "GET":
            return
        href = self._cells[1].get("href", "")
        parsed = urlsplit(href)
        if (
            parsed.scheme != "http"
            or parsed.netloc != "127.0.0.1:5000"
            or parsed.query
            or parsed.fragment
            or parsed.path not in self._paths
        ):
            return
        path = parsed.path
        for offset, user in enumerate(self._header_users):
            result_cell = self._cells[3 + (offset * 2)]
            outcome = result_cell["class"].strip().upper()
            if outcome in self._OUTCOMES:
                self.records.append({"path": path, "user": user, "result": outcome})


def _version_metadata(api_key: str) -> dict[str, str | None]:
    version = _zap_api("core", "view", "version", api_key=api_key).get("version")
    if not isinstance(version, str) or not version:
        raise ZapContextError("ZAP did not return a version string.")
    addons = _zap_api("autoupdate", "view", "installedAddons", api_key=api_key).get("installedAddons")
    if not isinstance(addons, list):
        raise ZapContextError("ZAP did not return installed add-on metadata.")
    access_control_version: str | None = None
    for addon in addons:
        if not isinstance(addon, dict):
            continue
        identifier = str(addon.get("id", "")).lower()
        name = str(addon.get("name", "")).lower()
        if identifier == "accesscontrol" or "access control" in name:
            addon_version = addon.get("version")
            if isinstance(addon_version, str) and addon_version:
                access_control_version = addon_version
                break
    if access_control_version is None:
        raise ZapContextError("ZAP Access Control Testing add-on is not installed.")
    return {"zap_version": version, "access_control_addon_version": access_control_version}


def _build_not_run_report(
    reason: str,
    *,
    details: dict[str, Any] | None = None,
    version_metadata: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Build a bounded, credential-free report for a safely blocked run."""
    metadata = version_metadata or {}
    return {
        "schema_version": 3,
        "assessment_id": "zap-access-control-v2",
        "target": TARGET_BASE,
        "zap_version": metadata.get("zap_version"),
        "access_control_addon_version": metadata.get("access_control_addon_version"),
        "status": "NOT_RUN",
        "reason": reason,
        "details": details or {},
        "findings": [],
        "comparison_with_known_bola": None,
        "credential_or_response_bodies_exported": False,
    }


def _build_scan_report(
    scan_results: list[dict[str, str]],
    manifest: dict[str, Any],
    version_metadata: dict[str, str | None],
    *,
    scan_metadata: dict[str, Any],
) -> dict[str, Any]:
    """Build a redacted result summary from whitelisted transient HTML rows."""
    known_bola_paths = {
        "/books/v1/week1-userA-book",
        "/books/v1/week1-userB-book",
    }
    illegal = [record for record in scan_results if record["result"] == "ILLEGAL"]
    detected_bola_paths = {record["path"] for record in illegal if record["path"] in known_bola_paths}
    return {
        "schema_version": 3,
        "assessment_id": "zap-access-control-v2",
        "target": TARGET_BASE,
        "zap_version": version_metadata["zap_version"],
        "access_control_addon_version": version_metadata["access_control_addon_version"],
        "status": "COMPLETED",
        "allowed_request_count": len(manifest["allowed_requests"]),
        "scan_result_count": len(scan_results),
        "unauthorized_access_findings": illegal,
        "comparison_with_known_bola": {
            "known_bola_count": 2,
            "known_bola_paths": sorted(known_bola_paths),
            "zap_detected_unauthorized_access_count": len(illegal),
            "zap_detected_known_bola_paths": sorted(detected_bola_paths),
            "zap_missed_known_bola_paths": sorted(known_bola_paths - detected_bola_paths),
            "note": "ZAP results assess reviewed access rules only; they do not prove sensitive-field baseline equality.",
        },
        "scan_metadata": scan_metadata,
        "credential_or_response_bodies_exported": False,
    }


def _write_run_artifacts(report_path: Path, status_path: Path, report: dict[str, Any]) -> None:
    """Write fresh report and status objects to exactly caller-selected paths."""
    write_redacted_json(report_path, report)
    status = {
        "schema_version": 3,
        "assessment_id": report["assessment_id"],
        "target": report["target"],
        "status": report["status"],
        "reason": report.get("reason"),
        "zap_version": report.get("zap_version"),
        "access_control_addon_version": report.get("access_control_addon_version"),
        "credential_or_response_bodies_exported": False,
    }
    write_redacted_json(status_path, status)


def _start_access_control_scan(api_key: str, context_id: str, users: list[dict[str, str]]) -> None:
    """Start the documented context/user based scan; there is no scan ID."""
    user_ids = ",".join(user["id"] for user in users)
    result = _zap_api(
        "accessControl", "action", "scan",
        {
            "contextId": context_id,
            "userId": user_ids,
            "scanAsUnAuthUser": "false",
            "raiseAlert": "false",
            "alertRiskLevel": "High",
        },
        api_key=api_key,
    )
    if result.get("Result") != "OK":
        raise ZapContextError("ZAP did not confirm Access Control scan start.")


def _poll_scan_status(api_key: str, context_id: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, int | str]:
    """Poll documented context-based progress/status until clean completion."""
    deadline = time.monotonic() + timeout
    last_progress = -1
    while time.monotonic() < deadline:
        progress_result = _zap_api(
            "accessControl", "view", "getScanProgress", {"contextId": context_id}, api_key=api_key
        )
        status_result = _zap_api(
            "accessControl", "view", "getScanStatus", {"contextId": context_id}, api_key=api_key
        )
        try:
            progress = int(progress_result.get("getScanProgress"))
        except (TypeError, ValueError) as error:
            raise ZapContextError("ZAP returned malformed Access Control scan progress.") from error
        status = status_result.get("getScanStatus")
        if not isinstance(status, str) or not status:
            raise ZapContextError("ZAP returned malformed Access Control scan status.")
        if progress < last_progress or not 0 <= progress <= 100:
            raise ZapContextError("ZAP returned an invalid Access Control scan progress value.")
        last_progress = progress
        normalized = status.strip().upper()
        if normalized in {"INTERRUPTED", "PAUSED"}:
            raise ZapContextError(f"Access Control scan ended as {normalized}.")
        if progress == 100 and normalized in {"NOT RUNNING", "COMPLETED", "FINISHED"}:
            return {"progress": progress, "status": normalized}
        if normalized not in {"RUNNING", "NOT RUNNING", "COMPLETED", "FINISHED"}:
            raise ZapContextError("ZAP returned an unknown Access Control scan state.")
        time.sleep(POLL_INTERVAL_SECONDS)
    raise ZapContextError(f"Access Control scan timed out after {timeout}s.")


def _is_html_report_write_response(result: Any) -> bool:
    """Accept only the documented opaque report-write acknowledgement.

    The Access Control add-on returns ``{"writeHTMLreport": "OK"}``, unlike
    scan-start's generic ``{"Result": "OK"}``. The report's existence is
    still verified before any whitelist-only parsing begins.
    """
    return (
        isinstance(result, dict)
        and set(result) == {"writeHTMLreport"}
        and result["writeHTMLreport"] == "OK"
    )


def _extract_transient_html_summary(
    host_report_path: str | Path,
    manifest: dict[str, Any],
    users: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Parse a mounted temporary report and retain only whitelisted fields."""
    report_path = Path(host_report_path)
    if not report_path.is_file():
        raise ZapContextError("ZAP did not create the mounted transient HTML report.")
    try:
        contents = report_path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as error:
        raise ZapContextError("Transient ZAP HTML report cannot be safely read.") from error
    parser = _AccessControlHtmlParser(allowed_paths(manifest), {user["name"] for user in users})
    try:
        parser.feed(contents)
        parser.close()
    except Exception as error:
        raise ZapContextError("Transient ZAP HTML report could not be parsed.") from error
    if not parser.records:
        raise ZapContextError("Transient ZAP HTML report has no complete reviewed result rows.")
    return parser.records


def _write_and_return(
    report_path: Path,
    status_path: Path,
    reason: str,
    *,
    details: dict[str, Any] | None = None,
    version_metadata: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    report = _build_not_run_report(reason, details=details, version_metadata=version_metadata)
    _write_run_artifacts(report_path, status_path, report)
    return report


def _build_bootstrap_readiness(
    *,
    context_mode: str,
    context_metadata: dict[str, Any],
    users: list[dict[str, str]],
    version_metadata: dict[str, str | None],
) -> dict[str, Any]:
    """Record the static Desktop handoff before operator authentication/quiescence."""
    return {
        "schema_version": 1,
        "assessment_id": "zap-access-control-v2",
        "target": TARGET_BASE,
        "zap_version": version_metadata["zap_version"],
        "access_control_addon_version": version_metadata["access_control_addon_version"],
        "status": "BOOTSTRAP_REQUIRES_OPERATOR_AUTH_AND_QUIESCE",
        "context_mode": context_mode,
        "context": {
            "context_name": context_metadata["context_name"],
            "include_count": context_metadata["include_count"],
        },
        "reviewed_user_names": [user["name"] for user in users],
        "operator_next_step": "Authenticate and poll each reviewed user in ZAP Desktop, then quiesce target traffic without restarting ZAP. The ordinary runner captures its own private post-auth history baseline.",
        "credential_or_response_bodies_exported": False,
    }


def run_zap_authentication_bootstrap(
    *,
    api_key: str = "",
    context_mode: str = "preloaded-desktop",
    allowlist_path: str | Path = "zap/allowlist-v2.json",
    context_path: str | Path | None = None,
    context_attestation_path: str | Path = "zap/imported-context-attestation.json",
    bootstrap_path: str | Path = ZAP_BOOTSTRAP_PATH,
) -> dict[str, Any]:
    """Verify a preloaded Desktop Context before operator authentication.

    This phase is read-only. It never starts authentication, polling, seeding,
    scanning, report creation, Context import, or history mutation.
    """
    destination = Path(bootstrap_path)
    version_metadata: dict[str, str | None] | None = None
    gate = "zap_addon"
    try:
        if context_mode != "preloaded-desktop":
            raise ZapContextError("Authentication bootstrap requires preloaded Desktop Context mode.")
        version_metadata = _version_metadata(api_key)
        gate = "allowlist"
        manifest = load_allowlist_v2(allowlist_path)
        gate = "input_contract"
        if not context_path:
            raise ZapContextError("Authentication bootstrap requires a private reviewed Context.")
        gate = "local_context_attestation"
        attestation = load_context_attestation(context_attestation_path, manifest, context_path)
        gate = "preloaded_context_metadata"
        context_metadata = verify_preloaded_context(api_key, manifest, attestation)
        gate = "reviewed_users"
        users = verify_imported_users(api_key, context_metadata["context_id"], attestation)
        readiness = _build_bootstrap_readiness(
            context_mode=context_mode,
            context_metadata=context_metadata,
            users=users,
            version_metadata=version_metadata,
        )
    except (ZapContextError, OSError, ValueError) as error:
        readiness = {
            "schema_version": 1,
            "assessment_id": "zap-access-control-v2",
            "target": TARGET_BASE,
            "zap_version": (version_metadata or {}).get("zap_version"),
            "access_control_addon_version": (version_metadata or {}).get("access_control_addon_version"),
            "status": "BOOTSTRAP_NOT_READY",
            "context_mode": context_mode,
            "details": {"failure_class": type(error).__name__, "gate": gate},
            "credential_or_response_bodies_exported": False,
        }
    write_redacted_json(destination, readiness)
    return readiness


def run_zap_access_control(
    *,
    api_key: str = "",
    context_mode: str = "import",
    allowlist_path: str | Path = "zap/allowlist-v2.json",
    context_path: str | Path | None = None,
    zap_context_path: str | None = None,
    context_attestation_path: str | Path = "zap/imported-context-attestation.json",
    host_report_path: str | Path | None = None,
    zap_report_path: str | None = None,
    report_path: str | Path = ZAP_REPORT_PATH,
    status_path: str | Path = ZAP_STATUS_PATH,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run a constrained assessment or return a redacted ``NOT_RUN`` report.

    ``context_path`` is always the local private file used for fingerprint
    verification. ``context_mode='import'`` requires ``zap_context_path`` as
    the explicit absolute path visible to a Docker ZAP process. With
    ``context_mode='preloaded-desktop'`` ZAP must already contain the reviewed
    Context; no Context path is passed to the API. ``host_report_path`` and
    ``zap_report_path`` name the same disposable report file from the caller
    and ZAP-process viewpoints.
    """
    destination = Path(report_path)
    status_destination = Path(status_path)
    version_metadata: dict[str, str | None] | None = None
    transient_host_report = Path(host_report_path) if host_report_path else None
    transient_report_owned = False
    gate = "zap_addon"
    try:
        version_metadata = _version_metadata(api_key)
        gate = "allowlist"
        manifest = load_allowlist_v2(allowlist_path)
        gate = "input_contract"
        if context_mode not in {"import", "preloaded-desktop"}:
            raise ZapContextError("ZAP Context mode is invalid.")
        if not context_path or not transient_host_report or not zap_report_path:
            raise ZapContextError("Private reviewed Context and transient-report paths are required.")
        if not isinstance(zap_report_path, str) or not zap_report_path.startswith("/"):
            raise ZapContextError("ZAP transient-report path must be an absolute ZAP-visible path.")
        resolved_destinations = {destination.resolve(), status_destination.resolve()}
        if len(resolved_destinations) != 2 or transient_host_report.resolve() in resolved_destinations:
            raise ZapContextError("ZAP report, status, and transient-report paths must be distinct.")
        if transient_host_report.exists() or transient_host_report.is_symlink():
            raise ZapContextError("Transient ZAP report path must not already exist.")
        if context_mode == "import" and not zap_context_path:
            raise ZapContextError("Import mode requires an absolute ZAP-visible Context path.")
        if context_mode == "preloaded-desktop" and zap_context_path:
            raise ZapContextError("Preloaded Desktop mode does not accept a ZAP Context path.")
        gate = "local_context_attestation"
        attestation = load_context_attestation(context_attestation_path, manifest, context_path)
        if context_mode == "import":
            gate = "context_import"
            context_id = import_reviewed_context(api_key, zap_context_path)
            gate = "imported_context_metadata"
            context_metadata = verify_imported_context(api_key, context_id, manifest, attestation)
        else:
            gate = "preloaded_context_metadata"
            context_metadata = verify_preloaded_context(api_key, manifest, attestation)
            context_id = context_metadata["context_id"]
        gate = "reviewed_users"
        users = verify_imported_users(api_key, context_id, attestation)
        gate = "authentication_state"
        authentication_states = verify_user_authentication_state(api_key, context_id, users)
        gate = "post_auth_quiescence"
        quiescence = wait_for_history_quiescence(api_key)
        gate = "post_auth_baseline"
        post_auth_baseline = capture_history_snapshot(api_key, manifest)
        gate = "reviewed_seed"
        seed_metadata = seed_reviewed_paths(api_key, manifest)
        gate = "site_tree_diagnostics"
        _, site_tree_diagnostics = verify_site_tree_containment(api_key, manifest)
        gate = "pre_scan_delta"
        post_seed_snapshot = capture_history_snapshot(api_key, manifest)
        seed_contained, seed_delta = verify_seed_delta(
            post_auth_baseline, post_seed_snapshot, manifest
        )
        if not seed_contained:
            return _write_and_return(
                destination, status_destination, "Pre-scan target history delta violates the exact reviewed request scope.",
                details={
                    "baseline": history_baseline_summary(post_auth_baseline),
                    "seed_delta": seed_delta,
                    "site_tree_diagnostics": site_tree_diagnostics,
                },
                version_metadata=version_metadata,
            )
        if seed_delta["new_message_count"] != seed_metadata["seeded_request_count"]:
            return _write_and_return(
                destination, status_destination, "Pre-scan target history delta has an unexpected reviewed seed count.",
                details={
                    "baseline": history_baseline_summary(post_auth_baseline),
                    "seed_delta": seed_delta,
                    "site_tree_diagnostics": site_tree_diagnostics,
                },
                version_metadata=version_metadata,
            )
        gate = "scan_start"
        _start_access_control_scan(api_key, context_id, users)
        gate = "scan_completion"
        scan_status = _poll_scan_status(api_key, context_id, timeout=timeout)
        gate = "transient_report_write"
        transient_report_owned = True
        report_write_result = _zap_api(
            "accessControl", "action", "writeHTMLreport",
            {"contextId": context_id, "fileName": zap_report_path}, api_key=api_key,
        )
        if not _is_html_report_write_response(report_write_result):
            raise ZapContextError("ZAP did not confirm transient Access Control report creation.")
        gate = "transient_report_parse"
        scan_rows = _extract_transient_html_summary(transient_host_report, manifest, users)
        gate = "post_scan_delta"
        post_scan_snapshot = capture_history_snapshot(api_key, manifest)
        post_contained, scan_delta = verify_history_delta(
            post_seed_snapshot, post_scan_snapshot, manifest
        )
        if not post_contained:
            return _write_and_return(
                destination, status_destination, "Post-scan target history delta violates the exact reviewed request scope.",
                details={
                    "baseline": history_baseline_summary(post_auth_baseline),
                    "seed_delta": seed_delta,
                    "scan_delta": scan_delta,
                    "site_tree_diagnostics": site_tree_diagnostics,
                },
                version_metadata=version_metadata,
            )
        report = _build_scan_report(
            scan_rows,
            manifest,
            version_metadata,
            scan_metadata={
                "context": {
                    "context_name": context_metadata["context_name"],
                    "include_count": context_metadata["include_count"],
                },
                "authenticated_users": authentication_states,
                "quiescence": quiescence,
                "baseline": history_baseline_summary(post_auth_baseline),
                "seed_delta": seed_delta,
                "scan_delta": scan_delta,
                "site_tree_diagnostics": site_tree_diagnostics,
                "completion": scan_status,
            },
        )
        _write_run_artifacts(destination, status_destination, report)
        return report
    except (ZapContextError, OSError, ValueError) as error:
        reason = f"Safety gate stopped the Access Control assessment: {type(error).__name__}."
        if (
            gate == "post_auth_quiescence"
            and str(error) == "ZAP target history did not quiesce before the safe timeout."
        ):
            reason = "Post-auth target history quiescence timed out."
        return _write_and_return(
            destination,
            status_destination,
            reason,
            details={"context_mode": context_mode, "failure_class": type(error).__name__, "gate": gate},
            version_metadata=version_metadata,
        )
    finally:
        if transient_report_owned and transient_host_report is not None:
            try:
                os.remove(transient_host_report)
            except FileNotFoundError:
                pass
