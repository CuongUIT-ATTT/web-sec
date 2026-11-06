import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

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
    runs: vi.fn().mockResolvedValue([]),
    findings: vi.fn().mockResolvedValue([]),
  },
}));

const mockedApi = vi.mocked(api);

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
  mockedApi.runs.mockResolvedValue([]);
  mockedApi.findings.mockResolvedValue([]);
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
