"""Verified-imported-Context OWASP ZAP Access Control lifecycle.

This runner is deliberately not a generic scanner. It accepts only the local
VAmPI manifest, imports a manually reviewed Context, validates non-secret
attestation facts, and starts the Access Control add-on only after each gate
passes. Any gate failure produces a fresh, redacted ``NOT_RUN`` artifact.
"""

from __future__ import annotations

import os
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from vampi_authz_lab.common import write_redacted_json

from .zap_context_builder import (
    TARGET_BASE,
    ZapContextError,
    _zap_api,
    allowed_paths,
    import_reviewed_context,
    load_allowlist_v2,
    load_context_attestation,
    seed_reviewed_paths,
    verify_imported_context,
    verify_imported_users,
    verify_message_containment,
    verify_site_tree_containment,
    verify_user_authentication_state,
)

ZAP_REPORT_PATH = Path("results/zap/zap_access_control_report.json")
ZAP_STATUS_PATH = Path("results/zap/zap_run_status.json")
POLL_INTERVAL_SECONDS = 2
DEFAULT_TIMEOUT_SECONDS = 120


class _AccessControlHtmlParser(HTMLParser):
    """Extract only reviewed URL/user/result cells from transient HTML."""

    def __init__(self, paths: set[str], users: set[str]) -> None:
        super().__init__(convert_charrefs=True)
        self._paths = paths
        self._users = users
        self._in_row = False
        self._row_parts: list[str] = []
        self.records: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "tr":
            self._in_row = True
            self._row_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_row:
            self._row_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "tr" or not self._in_row:
            return
        self._in_row = False
        row = " ".join(self._row_parts)
        path = next((value for value in self._paths if value in row), None)
        user = next((value for value in self._users if re.search(rf"\b{re.escape(value)}\b", row)), None)
        upper = row.upper()
        outcome = next((value for value in ("ILLEGAL", "VALID", "UNKNOWN") if value in upper), None)
        if path and user and outcome:
            self.records.append({"path": path, "user": user, "result": outcome})
        self._row_parts = []


def _version_metadata(api_key: str) -> dict[str, str | None]:
    version = _zap_api("core", "view", "version", api_key=api_key).get("version")
    if not isinstance(version, str) or not version:
        raise ZapContextError("ZAP did not return a version string.")
    addons = _zap_api("autoupdate", "view", "installedAddons", api_key=api_key).get("addons")
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
        "schema_version": 2,
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
        "schema_version": 2,
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
        "schema_version": 2,
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


def run_zap_access_control(
    *,
    api_key: str = "",
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

    ``context_path`` is the local private file used for fingerprint verification;
    ``zap_context_path`` is its explicit absolute path mounted inside the ZAP
    container. ``host_report_path`` and ``zap_report_path`` likewise refer to
    the same disposable mounted report file from host and container viewpoints.
    """
    destination = Path(report_path)
    status_destination = Path(status_path)
    version_metadata: dict[str, str | None] | None = None
    transient_host_report = Path(host_report_path) if host_report_path else None
    try:
        version_metadata = _version_metadata(api_key)
        manifest = load_allowlist_v2(allowlist_path)
        if not context_path or not zap_context_path or not transient_host_report or not zap_report_path:
            raise ZapContextError("Verified imported Context and mounted transient-report paths are required.")
        attestation = load_context_attestation(context_attestation_path, manifest, context_path)
        context_id = import_reviewed_context(api_key, zap_context_path)
        context_metadata = verify_imported_context(api_key, context_id, manifest, attestation)
        users = verify_imported_users(api_key, context_id, attestation)
        authentication_states = verify_user_authentication_state(api_key, context_id, users)
        empty_history, empty_history_details = verify_message_containment(api_key, manifest, expected_count=0)
        if not empty_history:
            return _write_and_return(
                destination, status_destination, "Fresh ZAP session already contains target history outside the reviewed baseline.",
                details={"history": empty_history_details},
                version_metadata=version_metadata,
            )
        seed_metadata = seed_reviewed_paths(api_key, manifest)
        _, site_tree_diagnostics = verify_site_tree_containment(api_key, manifest)
        pre_contained, pre_history = verify_message_containment(
            api_key, manifest, expected_count=seed_metadata["seeded_request_count"]
        )
        if not pre_contained:
            return _write_and_return(
                destination, status_destination, "Pre-scan target history violates the exact reviewed request scope.",
                details={"history": pre_history, "site_tree_diagnostics": site_tree_diagnostics},
                version_metadata=version_metadata,
            )
        _start_access_control_scan(api_key, context_id, users)
        scan_status = _poll_scan_status(api_key, context_id, timeout=timeout)
        _zap_api(
            "accessControl", "action", "writeHTMLreport",
            {"contextId": context_id, "fileName": zap_report_path}, api_key=api_key,
        )
        scan_rows = _extract_transient_html_summary(transient_host_report, manifest, users)
        post_contained, post_history = verify_message_containment(api_key, manifest)
        if not post_contained:
            return _write_and_return(
                destination, status_destination, "Post-scan target history violates the exact reviewed request scope.",
                details={"history": post_history, "site_tree_diagnostics": site_tree_diagnostics},
                version_metadata=version_metadata,
            )
        report = _build_scan_report(
            scan_rows,
            manifest,
            version_metadata,
            scan_metadata={
                "context": context_metadata,
                "authenticated_users": authentication_states,
                "pre_scan_history": pre_history,
                "post_scan_history": post_history,
                "site_tree_diagnostics": site_tree_diagnostics,
                "completion": scan_status,
            },
        )
        _write_run_artifacts(destination, status_destination, report)
        return report
    except (ZapContextError, OSError, ValueError) as error:
        return _write_and_return(
            destination,
            status_destination,
            f"Safety gate stopped the Access Control assessment: {type(error).__name__}.",
            details={"failure_class": type(error).__name__},
            version_metadata=version_metadata,
        )
    finally:
        if transient_host_report is not None:
            try:
                os.remove(transient_host_report)
            except FileNotFoundError:
                pass
