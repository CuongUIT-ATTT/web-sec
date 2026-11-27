import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastViewport, useToastStore } from "./Toast";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function Harness({ onRender }: { onRender?: () => void }) {
  onRender?.();
  const store = useToastStore();
  return (
    <div>
      <button onClick={() => store.notify({ kind: "success", text: "Lưu thành công" })}>
        Success
      </button>
      <button onClick={() => store.notify({ kind: "info", text: "Đang kiểm tra kết nối" })}>
        Info
      </button>
      <button onClick={() => store.notify({ kind: "error", text: "Xác minh thất bại" })}>
        Error
      </button>
      <ToastViewport store={store} />
    </div>
  );
}

describe("floating toast notifications", () => {
  it("renders floating toasts without re-rendering the parent component", () => {
    const renders = vi.fn();
    render(<Harness onRender={renders} />);
    expect(renders).toHaveBeenCalledTimes(1);
    expect(screen.queryByLabelText("Thông báo trạng thái")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Success" }));
    fireEvent.click(screen.getByRole("button", { name: "Error" }));

    expect(renders).toHaveBeenCalledTimes(1);
    const viewport = screen.getByLabelText("Thông báo trạng thái");
    expect(viewport).toHaveClass("toast-viewport");
    expect(screen.getByRole("status")).toHaveTextContent("Lưu thành công");
    expect(screen.getByRole("alert")).toHaveTextContent("Xác minh thất bại");
  });

  it("supports dismissing a single toast, Escape key, and clearing all", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Success" }));
    fireEvent.click(screen.getByRole("button", { name: "Info" }));
    fireEvent.click(screen.getByRole("button", { name: "Error" }));

    expect(screen.getByRole("button", { name: "Đóng tất cả (3)" })).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByText("Xác minh thất bại")).toBeNull();
    expect(screen.getByRole("button", { name: "Đóng tất cả (2)" })).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Đóng thông báo" })[0]);
    expect(screen.queryByText("Đang kiểm tra kết nối")).toBeNull();
    expect(screen.getByText("Lưu thành công")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Info" }));
    fireEvent.click(screen.getByRole("button", { name: "Đóng tất cả (2)" }));
    expect(screen.queryByLabelText("Thông báo trạng thái")).toBeNull();
  });

  it("auto-dismisses success toasts while pausing on hover and keeping errors persistent", () => {
    vi.useFakeTimers();
    render(<Harness />);

    fireEvent.click(screen.getByRole("button", { name: "Success" }));
    fireEvent.click(screen.getByRole("button", { name: "Error" }));

    const successToast = screen.getByRole("status");
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(screen.getByText("Lưu thành công")).toBeInTheDocument();

    fireEvent.mouseEnter(successToast);
    act(() => {
      vi.advanceTimersByTime(10000);
    });
    expect(screen.getByText("Lưu thành công")).toBeInTheDocument();

    fireEvent.mouseLeave(successToast);
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.queryByText("Lưu thành công")).toBeNull();
    expect(screen.getByRole("alert")).toHaveTextContent("Xác minh thất bại");
  });
});
