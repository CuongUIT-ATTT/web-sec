import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { api, type Result, type Finding } from "./api";
import { App, CaseMatrix } from "./App";
vi.mock("./api", async (original) => {
  const actual = await original<typeof import("./api")>();
  return { ...actual, api: Object.fromEntries(Object.keys(actual.api).map(key => [key, vi.fn().mockResolvedValue([])])) };
});
const mock = vi.mocked(api);
const run = (id: number, status = "COMPLETED") => ({ id, project_id: 1, status, snapshot: {}, execution_summary: null });
const result = (key: string): Result => ({ case_key: key, execution_status: "COMPLETED", authorization_conclusion: "INCONCLUSIVE", reason_codes: [], http_status: 200, response_metadata: { evidence: null } });
function deferred<T>() { let resolve!: (v: T) => void; const promise = new Promise<T>(r => { resolve = r; }); return { promise, resolve }; }
async function open() {
  render(<App legacy />);
  fireEvent.change(screen.getByLabelText("Mật khẩu quản trị"), { target: { value: "synthetic-password" } });
  fireEvent.click(screen.getByRole("button", { name: "Vào trạm kiểm thử" }));
  await screen.findAllByRole("option", { name: "Owner fixture" });
}
function change(label: string, value: string) { fireEvent.change(screen.getByLabelText(label), { target: { value } }); }
afterEach(cleanup);
beforeEach(() => {
  vi.resetAllMocks();
  for (const method of Object.values(mock)) method.mockResolvedValue([] as never);
  mock.projects.mockResolvedValue([{ id: 1, name: "QA synthetic", description: "mock only" }]);
  mock.targets.mockResolvedValue([{ id: 1, project_id: 1, base_url: "http://127.0.0.1:5000", timeout_seconds: 2, request_limit: 100, verification_path: "/me" }]);
  mock.identities.mockResolvedValue([{ id: 4, display_name: "Owner fixture", role: "reader", principal_pointer: "/id", expected_principal: "4", has_secret: true }]);
  mock.operations.mockResolvedValue([{ id: 7, operation_key: "get-item", method: "GET", path: "/items/{id}", selected: true }]);
  mock.resourceTypes.mockResolvedValue([{ id: 8, name: "Item fixture", resource_id_pointer: "/id", restricted_pointers: ["/private"] }]);
  mock.resources.mockResolvedValue([{ id: 9, resource_type_id: 8, external_id: "item-9", owner_identity_id: 4, path_parameter: "id" }]);
  mock.batchMatrix.mockResolvedValue({ identity_count: 3, concrete_target_count: 1, actor_case_count: 3, identity_verifications: 3, owner_baselines: 1, planned_attempts: 7, maximum_http_requests: 7, request_limit: 100, within_request_limit: true, targets: [] });
});
it("creates role policy with resource scope and identity XOR role", async () => {
  await open(); change("Operation", "7"); change("Loại resource", "8"); change("Chủ thể policy", "role"); change("Role áp dụng", "reader"); change("Phạm vi resource", "9"); change("Quyết định", "UNKNOWN");
  fireEvent.click(screen.getByRole("button", { name: "Tạo policy" }));
  expect(mock.createPolicy).toHaveBeenCalledWith(1, { operation_id: 7, resource_type_id: 8, resource_id: 9, identity_id: null, role: "reader", decision: "UNKNOWN" });
});
it("preserves role/resource edit and switches exclusively to identity", async () => {
  mock.policies.mockResolvedValue([{ id: 10, version: 3, operation_id: 7, resource_type_id: 8, resource_id: 9, identity_id: null, role: "reader", decision: "DENY" }]);
  await open(); change("Policy đang sửa", "10");
  expect(screen.getByLabelText("Role áp dụng")).toHaveValue("reader"); expect(screen.getByLabelText("Phạm vi resource")).toHaveValue("9");
  change("Chủ thể policy", "identity"); change("Danh tính áp dụng", "4"); fireEvent.click(screen.getByRole("button", { name: "Lưu policy" }));
  expect(mock.updatePolicy).toHaveBeenCalledWith(10, { operation_id: 7, resource_type_id: 8, resource_id: 9, identity_id: 4, role: null, decision: "DENY" });
});
it("renders resolved matrix fields from response", async () => {
  mock.matrix.mockResolvedValue([{ case_key: "matrix-case", control_type: "CROSS_USER", actor_identity_id: 5, owner_identity_id: 4, resource_id: 9, operation_id: 7, resolved_decision: "DENY", policy_id: 10, policy_version: 3, policy_status: "RESOLVED", warnings: [] }]);
  await open(); change("Operation", "7"); change("Loại resource", "8"); change("Resource cho ma trận", "9"); fireEvent.click(screen.getByRole("button", { name: "Lập ma trận" }));
  expect(await screen.findByText("DENY")).toBeInTheDocument(); expect(screen.getByText(/RESOLVED/)).toBeInTheDocument(); expect(screen.getByRole("region", { name: "Ma trận phân quyền" })).toHaveTextContent("Owner: identity-4"); expect(screen.getByRole("region", { name: "Ma trận phân quyền" })).toHaveTextContent("Policy 10 / v3");
});
it("requests run-scoped findings, reports missing evidence and ignores stale other-run response", async () => {
  mock.runs.mockResolvedValue([run(1), run(2)]);
  const old = deferred<Result[]>(); mock.results.mockImplementation(id => id === 1 ? old.promise : Promise.resolve([result("new-case")]));
  await open(); const buttons = screen.getAllByRole("button", { name: "Xem kết quả" }); fireEvent.click(buttons[0]); fireEvent.click(buttons[1]);
  expect(await screen.findByText("new-case")).toBeInTheDocument(); expect(mock.findings).toHaveBeenCalledWith(1, 2); expect(screen.getByText(/UNAVAILABLE/)).toBeInTheDocument();
  await act(async () => old.resolve([result("old-case")])); expect(screen.queryByText("old-case")).not.toBeInTheDocument();
});
it("blocks duplicate batch queue while request is pending", async () => {
  const pending = deferred<ReturnType<typeof run>>(); mock.createBatchRun.mockReturnValue(pending.promise);
  await open(); const button = screen.getByRole("button", { name: "Queue all selected GET mappings" }); await waitFor(() => expect(button).toBeEnabled()); fireEvent.click(button); fireEvent.click(button);
  expect(mock.createBatchRun).toHaveBeenCalledTimes(1); expect(button).toBeDisabled(); await act(async () => pending.resolve(run(3)));
});
it("blocks duplicate cancellation while request is pending", async () => {
  mock.runs.mockResolvedValue([run(1, "RUNNING")]); const pending = deferred<void>(); mock.cancelRun.mockReturnValue(pending.promise);
  await open(); const button = screen.getByRole("button", { name: "Dừng" }); fireEvent.click(button); fireEvent.click(button); expect(mock.cancelRun).toHaveBeenCalledTimes(1); expect(button).toBeDisabled(); await act(async () => pending.resolve());
});
it("does not display previous-project results after project switch", async () => {
  mock.projects.mockResolvedValue([{ id: 1, name: "QA synthetic", description: "" }, { id: 2, name: "Other project", description: "" }]);
  mock.runs.mockResolvedValue([run(1)]);
  const pending = deferred<Result[]>(); mock.results.mockReturnValue(pending.promise);
  await open(); fireEvent.click(screen.getByRole("button", { name: "Xem kết quả" }));
  fireEvent.click(screen.getByRole("button", { name: "Other project" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Other project" })).toHaveClass("active"));
  await screen.findAllByRole("option", { name: "Owner fixture" });
  await act(async () => pending.resolve([result("previous-project-case")]));
  expect(screen.queryByText("previous-project-case")).not.toBeInTheDocument();
});

const finding = (path: string): Finding => ({ id: 1, fingerprint: path, conclusion: "CONFIRMED_BOLA", operation: { method: "GET", path }, policy: { id: 10, version: 1 }, reproduction_count: 1 });
it("does not publish pending findings after project switch", async () => {
  mock.projects.mockResolvedValue([{ id: 1, name: "QA synthetic", description: "" }, { id: 2, name: "Other project", description: "" }]);
  mock.runs.mockResolvedValue([run(1)]);
  const pending = deferred<Finding[]>(); mock.findings.mockImplementation((_project, runId) => runId ? pending.promise : Promise.resolve([]));
  await open(); fireEvent.click(screen.getByRole("button", { name: "Xem kết quả" }));
  expect(mock.findings).toHaveBeenCalledWith(1, 1);
  fireEvent.click(screen.getByRole("button", { name: "Other project" }));
  await screen.findAllByRole("option", { name: "Owner fixture" });
  await act(async () => pending.resolve([finding("/previous-project-finding")]));
  expect(screen.queryByText("GET /previous-project-finding")).not.toBeInTheDocument();
});
it.each(["results", "findings"] as const)("ignores late %s errors after project switch", async (method) => {
  mock.projects.mockResolvedValue([{ id: 1, name: "QA synthetic", description: "" }, { id: 2, name: "Other project", description: "" }]);
  mock.runs.mockResolvedValue([run(1)]);
  let reject!: (error: Error) => void;
  const pending = new Promise<never>((_, fail) => { reject = fail; });
  if (method === "findings") mock.findings.mockImplementation((_project, runId) => runId ? pending : Promise.resolve([]));
  else mock.results.mockReturnValue(pending);
  await open(); fireEvent.click(screen.getByRole("button", { name: "Xem kết quả" }));
  fireEvent.click(screen.getByRole("button", { name: "Other project" }));
  await screen.findAllByRole("option", { name: "Owner fixture" });
  await act(async () => reject(new Error("stale-project-error")));
  expect(screen.queryByText("stale-project-error")).not.toBeInTheDocument();
});
it.each([false, true])("keeps newest same-run request when older request rejects=%s", async (rejectOld) => {
  mock.runs.mockResolvedValue([run(1)]);
  let reject!: (error: Error) => void; let resolve!: (value: Result[]) => void;
  const old = new Promise<Result[]>((ok, fail) => { resolve = ok; reject = fail; });
  const oldFindings = deferred<Finding[]>();
  mock.results.mockReturnValueOnce(old).mockResolvedValue([result("newest-same-run")]);
  let findingCalls = 0;
  mock.findings.mockImplementation((_project, runId) => !runId ? Promise.resolve([]) : ++findingCalls === 1 ? oldFindings.promise : Promise.resolve([finding("/newest-finding")]));
  await open(); const button = screen.getByRole("button", { name: "Xem kết quả" });
  fireEvent.click(button); fireEvent.click(button);
  expect(await screen.findByText("newest-same-run")).toBeInTheDocument();
  expect(screen.getByText("GET /newest-finding")).toBeInTheDocument();
  await act(async () => { oldFindings.resolve([finding("/obsolete-finding")]); if (rejectOld) reject(new Error("obsolete-error")); else resolve([result("obsolete-result")]); });
  expect(screen.getByText("newest-same-run")).toBeInTheDocument();
  expect(screen.getByText("GET /newest-finding")).toBeInTheDocument();
  expect(screen.queryByText("obsolete-result")).not.toBeInTheDocument();
  expect(screen.queryByText("GET /obsolete-finding")).not.toBeInTheDocument();
  expect(screen.queryByText("obsolete-error")).not.toBeInTheDocument();
});

it("keeps redacted resource ID out of edits unless a replacement is entered", async () => {
  mock.resources.mockResolvedValue([{ id: 9, resource_type_id: 8, external_id: "[REDACTED]", resource_alias: "resource-9", owner_identity_id: 4, path_parameter: "id" }]);
  await open(); change("Chọn loại resource", "8"); change("Resource đang sửa", "9");
  const input = screen.getByLabelText("Resource ID thay thế (để trống để giữ ID cũ)"); expect(input).toHaveValue("");
  fireEvent.click(screen.getByRole("button", { name: "Lưu resource" }));
  expect(mock.updateResource).toHaveBeenCalledWith(9, { owner_identity_id: 4, path_parameter: "id" });
  await waitFor(() => expect(screen.getByLabelText("Resource đang sửa")).toHaveValue(""));
  change("Chọn loại resource", "8"); change("Resource đang sửa", "9");
  change("Resource ID thay thế (để trống để giữ ID cũ)", "replacement-synthetic");
  fireEvent.click(screen.getByRole("button", { name: "Lưu resource" }));
  expect(mock.updateResource).toHaveBeenLastCalledWith(9, { external_id: "replacement-synthetic", owner_identity_id: 4, path_parameter: "id" });
});

it.each([3, 5])("shows and filters every case in a %i-account matrix", count => {
  const cases = Array.from({ length: count }, (_, index) => ({ case_key: `operation:7:resource:9:actor:${index + 1}`, control_type: "POLICY", actor_alias: `identity-${index + 1}`, actor_role: index === 0 ? "admin" : "user", owner_alias: "identity-2", owner_role: "user", resource_alias: "resource-9", ownership_category: index === 1 ? "OWNER" : "CROSS_USER", expected_decision: index === 1 ? "ALLOW" : "DENY", method: "GET", path_template: "/items/{id}", actor_identity_id: index + 1, owner_identity_id: 2, resource_id: 9, operation_id: 7, resolved_decision: null, policy_id: 10, policy_version: 2, policy_status: "RESOLVED", warnings: [] }));
  render(<CaseMatrix cases={cases} />);
  expect(screen.getAllByRole("row")).toHaveLength(count + 1);
  expect(screen.getByText(/NOT_RUN/)).toBeInTheDocument();
  change("Lọc quyền dự kiến", "ALLOW"); expect(screen.getAllByRole("row")).toHaveLength(2);
  expect(screen.getByText("operation:7:resource:9:actor:2")).toBeInTheDocument();
  change("Lọc tài khoản", "1"); expect(screen.getByText("Không có case khớp bộ lọc.")).toBeInTheDocument();
});

it("renders batch cases from the selected batch preview without queueing", async () => {
  const plan = await mock.batchMatrix(1, 1);
  mock.batchMatrix.mockClear();
  mock.batchMatrix.mockResolvedValue({ ...plan, cases: [{ case_key: "operation:7:resource:9:actor:4", control_type: "OWNER", actor_alias: "identity-4", actor_role: "reader", owner_alias: "identity-4", owner_role: "reader", resource_alias: "resource-9", ownership_category: "OWNER", expected_decision: "UNKNOWN", method: "GET", path_template: "/items/{id}", actor_identity_id: 4, owner_identity_id: 4, resource_id: 9, operation_id: 7, resolved_decision: null, policy_id: null, policy_version: null, policy_status: "MISSING", warnings: ["POLICY_MISSING"] }] });
  await open();
  expect(await screen.findByText("operation:7:resource:9:actor:4")).toBeInTheDocument();
  expect(screen.getByText("POLICY_MISSING")).toBeInTheDocument();
  expect(mock.createBatchRun).not.toHaveBeenCalled();
});
it("links persisted reproduction to the exact selected run and case", async () => {
  const key = "operation:7:resource:9:actor:4";
  mock.runs.mockResolvedValue([run(2)]);
  mock.results.mockResolvedValue([result(key)]);
  mock.findings.mockImplementation(async (_project, runId) => runId === 2 ? [{ id: 1, fingerprint: "synthetic", conclusion: "CONFIRMED_VIOLATION", operation: { method: "GET", path: "/items/{id}" }, policy: { id: 1, version: 1 }, reproduction_count: 1, reproductions: [{ run_id: 2, run_result_id: 12, case_key: key }, { run_id: 99, run_result_id: 13, case_key: "foreign" }] }] : []);
  await open();
  fireEvent.click(screen.getByRole("button", { name: "Xem kết quả" }));
  const link = await screen.findByRole("link", { name: `Run #2 · ${key}` });
  expect(link.getAttribute("href")).toBe(`#analysis-2-${key}`);
  expect(document.getElementById(`analysis-2-${key}`)).toBeTruthy();
  expect(screen.queryByRole("link", { name: /Run #99/ })).toBeNull();
});

it("reports configured roles separately from account counts and web administration", async () => {
  await open();
  expect(screen.getByText(/1 tài khoản · 1 role đã cấu hình/)).toHaveTextContent("Gate 3 role: CHƯA ĐỦ; gate 5 role: CHƯA ĐỦ");
});
it("shows matrix loading and error without queueing", async () => {
  const pending = deferred<never>(); mock.matrix.mockReturnValue(pending.promise);
  await open(); change("Operation", "7"); change("Loại resource", "8"); change("Resource cho ma trận", "9"); fireEvent.click(screen.getByRole("button", { name: "Lập ma trận" }));
  expect(screen.getByRole("button", { name: "Đang lập ma trận…" })).toBeDisabled();
  await act(async () => pending.resolve(Promise.reject(new Error("matrix-preview-failed")) as never));
  expect(await screen.findByRole("alert")).toHaveTextContent("matrix-preview-failed");
  expect(mock.createBatchRun).not.toHaveBeenCalled();
});

it("keeps multi-operation keys and unknown policy conflicts visible", () => {
  const rows = [7, 8].map(operation => ({ case_key: `operation:${operation}:resource:9:actor:4`, operation_id: operation, method: "GET", path_template: operation === 7 ? "/items/{id}" : "/items/{id}/details", control_type: "OWNER", actor_identity_id: 4, resource_id: 9, owner_identity_id: 4, actor_role: null, owner_role: null, ownership_category: "OWNER", expected_decision: "UNKNOWN", resolved_decision: null, policy_id: null, policy_version: null, policy_status: "CONFLICT", warnings: ["POLICY_CONFLICT"] }));
  render(<CaseMatrix cases={rows} />);
  expect(screen.getAllByRole("row")).toHaveLength(3);
  for (const row of rows) expect(screen.getByText(row.case_key)).toBeInTheDocument();
  expect(screen.getAllByText("UNKNOWN")).toHaveLength(3);
  expect(screen.getAllByText("POLICY_CONFLICT")).toHaveLength(2);
  expect(screen.getAllByText(/Role: Chưa gán/)).toHaveLength(4);
});
