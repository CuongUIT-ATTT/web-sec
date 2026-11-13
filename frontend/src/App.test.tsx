import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { api } from "./api";
import { App } from "./App";

vi.mock("./api", () => ({
  api: {
    login: vi.fn().mockResolvedValue(undefined),
    projects: vi.fn().mockResolvedValue([]),
    logout: vi.fn().mockResolvedValue(undefined),
    targets: vi.fn().mockResolvedValue([]),
    identities: vi.fn().mockResolvedValue([]),
    operations: vi.fn().mockResolvedValue([]),
    resourceTypes: vi.fn().mockResolvedValue([]),
    resources: vi.fn().mockResolvedValue([]),
    policies: vi.fn().mockResolvedValue([]),
    operationResourceMappings: vi.fn().mockResolvedValue([]),
    batchMatrix: vi.fn().mockResolvedValue({ identity_count: 0, concrete_target_count: 0, actor_case_count: 0, identity_verifications: 0, owner_baselines: 0, planned_attempts: 0, maximum_http_requests: 0, request_limit: 100, within_request_limit: true, targets: [] }),
    runs: vi.fn().mockResolvedValue([]),
    findings: vi.fn().mockResolvedValue([]),
    externalLabJobs: vi.fn().mockResolvedValue([]),
    createReadOnlyExternalLabJob: vi.fn().mockResolvedValue({ public_id: "12345678-1234-1234-1234-123456789abc", project_id: 1, job_kind: "READ_ONLY_VAMPI_VERIFICATION_V1", protocol_version: 1, status: "QUEUED", requested_at: "2026-11-13T00:00:00Z", dispatched_at: null, started_at: null, finished_at: null, cancel_requested_at: null, result_summary: {}, artifact_manifest_sha256: null, failure_code: null }),
    cancelExternalLabJob: vi.fn().mockResolvedValue(undefined),
  },
}));

const mockedApi = vi.mocked(api);

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.login.mockResolvedValue(undefined);
  mockedApi.projects.mockResolvedValue([]);
  mockedApi.logout.mockResolvedValue(undefined);
  mockedApi.targets.mockResolvedValue([]);
  mockedApi.identities.mockResolvedValue([]);
  mockedApi.operations.mockResolvedValue([]);
  mockedApi.resourceTypes.mockResolvedValue([]);
  mockedApi.resources.mockResolvedValue([]);
  mockedApi.policies.mockResolvedValue([]);
  mockedApi.operationResourceMappings.mockResolvedValue([]);
  mockedApi.batchMatrix.mockResolvedValue({ identity_count: 0, concrete_target_count: 0, actor_case_count: 0, identity_verifications: 0, owner_baselines: 0, planned_attempts: 0, maximum_http_requests: 0, request_limit: 100, within_request_limit: true, targets: [] });
  mockedApi.runs.mockResolvedValue([]);
  mockedApi.findings.mockResolvedValue([]);
  mockedApi.externalLabJobs.mockResolvedValue([]);
  mockedApi.createReadOnlyExternalLabJob.mockResolvedValue({ public_id: "12345678-1234-1234-1234-123456789abc", project_id: 1, job_kind: "READ_ONLY_VAMPI_VERIFICATION_V1", protocol_version: 1, status: "QUEUED", requested_at: "2026-11-13T00:00:00Z", dispatched_at: null, started_at: null, finished_at: null, cancel_requested_at: null, result_summary: {}, artifact_manifest_sha256: null, failure_code: null });
  mockedApi.cancelExternalLabJob.mockResolvedValue(undefined);
});

describe("authorization testing workspace", () => {
  it("requires an admin password before configuration is visible", async () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: /trạm kiểm thử/i })).toBeInTheDocument();
    expect(screen.queryByText("Dự án đang mở")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Mật khẩu quản trị"), { target: { value: "password" } });
    fireEvent.click(screen.getByRole("button", { name: "Vào trạm kiểm thử" }));

    expect(await screen.findByText("Dự án")).toBeInTheDocument();
  });

  it("queues only the fixed external read-only workflow", async () => {
    mockedApi.projects.mockResolvedValue([{ id: 1, name: "Lab", description: "Edit test" }]);
    render(<App />);

    fireEvent.change(screen.getByLabelText("Mật khẩu quản trị"), { target: { value: "password" } });
    fireEvent.click(screen.getByRole("button", { name: "Vào trạm kiểm thử" }));
    const queue = await screen.findByRole("button", { name: "Queue read-only verification" });
    const panel = screen.getByText(/Không có command, target, token, log hay artifact path/i).closest("article");
    expect(panel).toBeTruthy();
    expect(panel).not.toHaveTextContent(/Base URL IP lab/i);

    fireEvent.click(queue);
    expect(mockedApi.createReadOnlyExternalLabJob).toHaveBeenCalledWith(1);
  });

  it("prefills safe identity fields but never its bearer token", async () => {
    mockedApi.projects.mockResolvedValue([{ id: 1, name: "Lab", description: "Edit test" }]);
    mockedApi.identities.mockResolvedValue([{ id: 4, display_name: "Alice", role: "reader", principal_pointer: "/data/name", expected_principal: "alice", has_secret: true }]);
    render(<App />);

    fireEvent.change(screen.getByLabelText("Mật khẩu quản trị"), { target: { value: "password" } });
    fireEvent.click(screen.getByRole("button", { name: "Vào trạm kiểm thử" }));
    expect((await screen.findAllByText("Alice")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getAllByRole("button", { name: "Sửa" })[0]);
    expect(screen.getByLabelText("Tên hiển thị")).toHaveValue("Alice");
    expect(screen.getByLabelText("Bearer token thay thế (để trống để giữ token cũ)")).toHaveValue("");
  });
});
