import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BundleComparison, ComparePanel } from "./App";
import { api, type ComparisonBundle, type Comparison, type Run } from "./api";
beforeEach(() => { vi.spyOn(api, "comparisonBundles").mockResolvedValue([]); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const runs: Run[] = [1, 2].map(id => ({ id, project_id: 1, status: "COMPLETED", snapshot: {}, execution_summary: null }));
function data(run = 1): Comparison {
  return { run_id: run, cases: [{ run_id: run, case_key: "resource:1:actor:2", methods: [
    { method: "MANUAL", execution_status: "NOT_RUN", observation: null, provenance: "UNAVAILABLE", artifact: "UNAVAILABLE", timing_status: "TIMING_NOT_AVAILABLE" },
    { method: "T18", execution_status: "COMPLETED_RESPONSE", observation: { case_key: "resource:1:actor:2", execution_status: "COMPLETED_RESPONSE", authorization_conclusion: "CONFIRMED_VIOLATION", reason_codes: [], http_status: 403, response_metadata: { evidence: null } }, provenance: `run:${run}:result:10`, artifact: "UNAVAILABLE", timing_status: "TIMING_NOT_AVAILABLE" },
    { method: "ZAP", execution_status: "NOT_RUN", observation: null, provenance: "UNAVAILABLE", artifact: "UNAVAILABLE", timing_status: "TIMING_NOT_AVAILABLE" },
  ] }] };
}
function choose(id: string) { fireEvent.change(screen.getByLabelText("Lượt chạy để so sánh"), { target: { value: id } }); }
it("reads persisted run only and displays unavailable metadata and methods", async () => {
  const spy = vi.spyOn(api, "comparison").mockResolvedValue(data());
  render(<ComparePanel projectId={1} runs={runs} />);
  expect(spy).not.toHaveBeenCalled(); choose("1");
  await screen.findByText(/CONFIRMED_VIOLATION/);
  expect(spy).toHaveBeenCalledWith(1, 1);
  expect(screen.getByText(/HTTP 403/)).toBeTruthy();
  expect(screen.getAllByText(/^NOT_RUN/).length).toBe(2);
  expect(screen.getByText(/Evidence metadata: UNAVAILABLE/)).toBeTruthy();
  expect(screen.getByText(/run:1:result:10/)).toBeTruthy();
  expect(screen.getAllByText("TIMING_NOT_AVAILABLE").length).toBe(3);
});
it("does not show a late response from a previous run", async () => {
  let resolve!: (value: Comparison) => void;
  vi.spyOn(api, "comparison").mockImplementation((_project, run) => run === 1 ? new Promise(r => { resolve = r; }) : Promise.resolve({ run_id: 2, cases: [] }));
  render(<ComparePanel projectId={1} runs={runs} />); choose("1"); choose("2");
  await screen.findByText(/chưa có observation/); resolve(data());
  await waitFor(() => expect(screen.queryByText(/CONFIRMED_VIOLATION/)).toBeNull());
});
it("rejects mismatched run and reports read failure without NOT_RUN fabrication", async () => {
  vi.spyOn(api, "comparison").mockResolvedValue(data(2));
  render(<ComparePanel projectId={1} runs={runs} />); choose("1");
  await screen.findByRole("alert"); expect(screen.queryByText(/CONFIRMED_VIOLATION/)).toBeNull();
});
it("reports an empty run without inventing cases", async () => {
  vi.spyOn(api, "comparison").mockResolvedValue({ run_id: 1, cases: [] });
  render(<ComparePanel projectId={1} runs={runs} />); choose("1");
  await screen.findByText(/chưa có observation/);
  expect(screen.queryByText("resource:1:actor:2")).toBeNull();
});
it.each([true, false])("uses only matching historical policy, binding=%s", async matches => {
  const payload = data();
  const observation = payload.cases[0].methods[1].observation!;
  observation.response_metadata.evidence = { schema_version: 1, run_id: matches ? 1 : 2, case_key: observation.case_key, actor_identity_id: 2, owner_identity_id: 1, owner_control_valid: true, owner_http_status: 200, owner_execution_status: "COMPLETED_RESPONSE", policy_id: 5, policy_version: 7, policy_decision: "DENY", policy_resolution: "RESOLVED", actor_resource_matches: true, restricted_fields_match_owner: true };
  Object.assign(observation.response_metadata, { raw_body: "SECRET-CANARY" });
  vi.spyOn(api, "comparison").mockResolvedValue(payload);
  render(<ComparePanel projectId={1} runs={runs} />); choose("1");
  await screen.findByText(/CONFIRMED_VIOLATION/);
  expect(Boolean(screen.queryByText(/Policy 5 \/ v7/))).toBe(matches);
  expect(screen.queryByText(/SECRET-CANARY/)).toBeNull();
});

const bundleCase = { case_id: "historical-case", method: "GET", operation_template: "/objects/{id}", actor_role: "userA", owner_category: "OTHER", policy_id: "cross-user", policy_version: "v1", expected_decision: "DENY" };
function bundle(digest = "history", version: 1 | 2 = 2): ComparisonBundle {
  return { content_digest: digest, attestation_status: "UNVERIFIED", schema_version: version,
    manifest: { content_digest: "cohort", version: "sha256:cohort", cases: [bundleCase] },
    selections: [{ method: "MANUAL", execution_id: "historical" }, { method: "T18", execution_id: "current" }],
    observations: [{ method: "MANUAL", execution_id: "historical", manifest_digest: "cohort", manifest_version: "sha256:cohort", case_revision: bundleCase, execution_status: "COMPLETED", signal: "ACCESS_DENIED", provenance: null }],
    legacy: [{ method: "ZAP", source_alias: "legacy-source", linkage_status: "UNLINKED", conclusion: "UNKNOWN", provenance: null }], artifacts: [] };
}
async function chooseBundle(digest = "history") {
  await screen.findByRole("option", { name: digest });
  fireEvent.change(screen.getByLabelText("Bundle để so sánh"), { target: { value: digest } });
}
it.each([1, 2] as const)("renders schema %s historical completed independently from current unexecuted", async version => {
  vi.mocked(api.comparisonBundles).mockResolvedValue([{ content_digest: "history", attestation_status: "UNVERIFIED" }]);
  vi.spyOn(api, "comparisonBundle").mockResolvedValue(bundle("history", version));
  render(<BundleComparison projectId={1} />); await chooseBundle();
  await screen.findByText("COMPLETED");
  expect(screen.getByText("MANUAL: 1/1")).toBeTruthy();
  expect(screen.getByText("T18: 0/1")).toBeTruthy();
  expect(screen.getByText(/Conclusion: UNKNOWN/)).toBeTruthy();
  expect(screen.getByText(/UNLINKED · UNKNOWN/)).toBeTruthy();
  expect(screen.getAllByText(/TIMING_NOT_AVAILABLE/)).toHaveLength(3);
  expect(screen.getByText("Reason: NO_OBSERVATION")).toBeTruthy();
});
it("never renders receipt bytes or unknown metadata", async () => {
  const payload = bundle(); payload.observations[0].provenance = { artifact_ref: "artifact", artifact_hash: "hash", producer_kind: "HUMAN", producer_version: "v1", operator_alias: "operator" };
  payload.artifacts = [Object.assign({ artifact_ref: "artifact", artifact_hash: "hash", integrity_status: "HASH_MATCHED", attestation_status: "UNVERIFIED" }, { receipt_base64_chunks: ["SECRET-CANARY"], raw_body: "SECRET-CANARY" })];
  vi.mocked(api.comparisonBundles).mockResolvedValue([{ content_digest: "history", attestation_status: "UNVERIFIED" }]);
  vi.spyOn(api, "comparisonBundle").mockResolvedValue(payload);
  render(<BundleComparison projectId={1} />); await chooseBundle(); await screen.findByText(/HASH_MATCHED/);
  expect(screen.queryByText(/SECRET-CANARY/)).toBeNull(); expect(screen.getByText(/SOURCE_RECORDED/)).toBeTruthy();
});
it("ignores stale bundle and project responses", async () => {
  let resolve!: (value: ComparisonBundle) => void;
  vi.mocked(api.comparisonBundles).mockResolvedValue([{ content_digest: "history", attestation_status: "UNVERIFIED" }, { content_digest: "new", attestation_status: "UNVERIFIED" }]);
  vi.spyOn(api, "comparisonBundle").mockImplementation((_project, digest) => digest === "history" ? new Promise(r => { resolve = r; }) : Promise.resolve({ ...bundle("new"), manifest: { content_digest: "new-cohort", version: "new-cohort", cases: [] } }));
  const view = render(<BundleComparison projectId={1} />); await chooseBundle(); await chooseBundle("new");
  await screen.findByText(/Cohort rỗng/); resolve(bundle());
  await waitFor(() => expect(screen.queryByText("COMPLETED")).toBeNull());
  await chooseBundle(); view.rerender(<BundleComparison projectId={2} />); resolve(bundle());
  await waitFor(() => expect(screen.queryByText("historical-case")).toBeNull());
});
it("ignores a previous project's late inventory", async () => {
  let resolve!: (value: {content_digest: string; attestation_status: "UNVERIFIED"}[]) => void;
  vi.mocked(api.comparisonBundles).mockImplementation(project => project === 1 ? new Promise(r => { resolve = r; }) : Promise.resolve([]));
  const view = render(<BundleComparison projectId={1} />); view.rerender(<BundleComparison projectId={2} />);
  await screen.findByText(/Chưa có bundle/); resolve([{ content_digest: "old-project", attestation_status: "UNVERIFIED" }]);
  await waitFor(() => expect(screen.queryByRole("option", {name: "old-project"})).toBeNull());
});
it("shows inventory and detail errors without fabricating results", async () => {
  vi.mocked(api.comparisonBundles).mockRejectedValueOnce(new Error("secret"));
  const view = render(<BundleComparison projectId={1} />); await screen.findByRole("alert");
  expect(screen.queryByText("NOT_RUN")).toBeNull();
  vi.mocked(api.comparisonBundles).mockResolvedValue([{content_digest: "history", attestation_status: "UNVERIFIED"}]);
  vi.spyOn(api, "comparisonBundle").mockResolvedValue(bundle("wrong"));
  view.rerender(<BundleComparison projectId={2} />); await chooseBundle(); await screen.findByRole("alert");
  expect(screen.queryByText("COMPLETED")).toBeNull();
});

it("uses project-scoped GET inventory and detail endpoints", async () => {
  vi.mocked(api.comparisonBundles).mockRestore();
  const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 200, json: async () => [] } as unknown as Response);
  await api.comparisonBundles(7, 100); await api.comparisonBundle(7, "digest");
  expect(fetchSpy.mock.calls.map(call => call[0])).toEqual(["/api/projects/7/comparisons?offset=100&limit=100", "/api/projects/7/comparisons/digest"]);
  expect(fetchSpy.mock.calls.every(call => !call[1]?.method || call[1].method === "GET")).toBe(true);
});


function inventoryPage(prefix: string, count = 100) {
  return Array.from({ length: count }, (_, index) => ({ content_digest: `${prefix}-${index}`, attestation_status: "UNVERIFIED" as const }));
}
it.each([0, 1])("loads full inventory followed by a terminal page of %s rows", async tail => {
  const first = inventoryPage("first");
  vi.mocked(api.comparisonBundles).mockImplementation(async (project, offset) => {
    expect(project).toBe(1);
    if (offset === 0) return first;
    if (offset === 100) return inventoryPage("tail", tail);
    throw new Error("Unexpected extra page");
  });
  const detail = vi.spyOn(api, "comparisonBundle").mockResolvedValue(bundle(tail ? "tail-0" : "first-99"));
  render(<BundleComparison projectId={1} />);
  await chooseBundle(tail ? "tail-0" : "first-99");
  await screen.findByText("COMPLETED");
  expect(screen.getAllByRole("option")).toHaveLength(101 + tail);
  expect(vi.mocked(api.comparisonBundles).mock.calls).toEqual([[1, 0], [1, 100]]);
  expect(detail).toHaveBeenCalledExactlyOnceWith(1, tail ? "tail-0" : "first-99");
});
it("rejects the whole inventory when the next page fails", async () => {
  vi.mocked(api.comparisonBundles).mockResolvedValueOnce(inventoryPage("partial")).mockRejectedValueOnce(new Error("SECRET-PAGE-ERROR"));
  const detail = vi.spyOn(api, "comparisonBundle");
  render(<BundleComparison projectId={1} />);
  await screen.findByRole("alert");
  expect(vi.mocked(api.comparisonBundles).mock.calls).toEqual([[1, 0], [1, 100]]);
  expect(screen.queryByRole("option", { name: "partial-0" })).toBeNull();
  expect(screen.queryByText(/SECRET-PAGE-ERROR|COMPLETED|NOT_RUN/)).toBeNull();
  expect(detail).not.toHaveBeenCalled();
});
it.each(["resolve", "reject"] as const)("ignores a stale next-page %s after switching project", async outcome => {
  let resolve!: (value: ReturnType<typeof inventoryPage>) => void;
  let reject!: (reason: Error) => void;
  const pending = new Promise<ReturnType<typeof inventoryPage>>((yes, no) => { resolve = yes; reject = no; });
  vi.mocked(api.comparisonBundles).mockImplementation(async (project, offset) => {
    if (project === 2) return inventoryPage("current", 1);
    if (offset === 0) return inventoryPage("old");
    if (offset === 100) return pending;
    throw new Error("Stale pagination continued");
  });
  vi.spyOn(api, "comparisonBundle").mockResolvedValue(bundle("current-0"));
  const view = render(<BundleComparison projectId={1} />);
  await waitFor(() => expect(api.comparisonBundles).toHaveBeenCalledWith(1, 100));
  view.rerender(<BundleComparison projectId={2} />);
  await chooseBundle("current-0"); await screen.findByText("COMPLETED");
  if (outcome === "resolve") resolve(inventoryPage("stale"));
  else reject(new Error("SECRET-STALE-ERROR"));
  await pending.catch(() => undefined);
  await waitFor(() => {
    expect(screen.getAllByRole("option")).toHaveLength(2);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("option", { name: "old-0" })).toBeNull();
    expect(screen.queryByRole("option", { name: "stale-0" })).toBeNull();
    expect(screen.getByText("COMPLETED")).toBeTruthy();
    expect(vi.mocked(api.comparisonBundles).mock.calls).toEqual([[1, 0], [1, 100], [2, 0]]);
  });
});
