import { useEffect, useRef, useState, useSyncExternalStore } from "react";

export type NoticeKind = "error" | "success" | "info";
export type NoticeInput = { kind: NoticeKind; text: string };
export type Notice = NoticeInput | null;

export type ToastItem = NoticeInput & {
  id: number;
  createdAt: string;
  durationMs: number | null;
};

const MAX_TOASTS = 5;
const DEFAULT_AUTO_DISMISS_MS = 6500;

const KIND_LABELS: Record<NoticeKind, string> = {
  success: "THÀNH CÔNG",
  error: "LỖI",
  info: "THÔNG TIN",
};

function formatTime(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

export class ToastStore {
  private items: ToastItem[] = [];
  private nextId = 0;
  private listeners = new Set<() => void>();

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  getSnapshot = () => this.items;

  private emit() {
    for (const listener of this.listeners) {
      listener();
    }
  }

  notify = (notice: Notice) => {
    if (!notice) {
      if (this.items.length === 0) return;
      this.items = [];
      this.emit();
      return;
    }
    const id = ++this.nextId;
    const item: ToastItem = {
      id,
      kind: notice.kind,
      text: notice.text,
      createdAt: formatTime(new Date()),
      durationMs: notice.kind === "error" ? null : DEFAULT_AUTO_DISMISS_MS,
    };
    const withoutLatestDuplicate =
      this.items[0] &&
      this.items[0].kind === item.kind &&
      this.items[0].text === item.text
        ? this.items.slice(1)
        : this.items;
    this.items = [item, ...withoutLatestDuplicate].slice(0, MAX_TOASTS);
    this.emit();
  };

  dismiss = (id: number) => {
    const next = this.items.filter((item) => item.id !== id);
    if (next.length === this.items.length) return;
    this.items = next;
    this.emit();
  };

  clear = () => {
    if (this.items.length === 0) return;
    this.items = [];
    this.emit();
  };
}

export function useToastStore(): ToastStore {
  const [store] = useState(() => new ToastStore());
  return store;
}

function ToastCard({
  toast,
  onDismiss,
}: {
  toast: ToastItem;
  onDismiss: (id: number) => void;
}) {
  const [paused, setPaused] = useState(false);
  const remainingRef = useRef<number>(toast.durationMs ?? 0);
  const startedAtRef = useRef<number>(0);

  useEffect(() => {
    if (toast.durationMs === null || paused) return;
    if (remainingRef.current <= 0) {
      onDismiss(toast.id);
      return;
    }
    startedAtRef.current = Date.now();
    const timer = window.setTimeout(() => onDismiss(toast.id), remainingRef.current);
    return () => {
      window.clearTimeout(timer);
      const elapsed = Date.now() - startedAtRef.current;
      remainingRef.current = Math.max(0, remainingRef.current - elapsed);
    };
  }, [toast.id, toast.durationMs, paused, onDismiss]);

  return (
    <article
      className={`toast ${toast.kind}${paused ? " paused" : ""}`}
      role={toast.kind === "error" ? "alert" : "status"}
      aria-live={toast.kind === "error" ? "assertive" : "polite"}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div className="toast-header">
        <span className="toast-badge">
          <span className="toast-dot" aria-hidden="true" />
          {KIND_LABELS[toast.kind]}
        </span>
        <div className="toast-meta">
          <time className="toast-time">{toast.createdAt}</time>
          <button
            type="button"
            className="toast-close"
            aria-label="Đóng thông báo"
            onClick={() => onDismiss(toast.id)}
          >
            ×
          </button>
        </div>
      </div>
      <p className="toast-text">{toast.text}</p>
      {toast.durationMs !== null && (
        <span
          className="toast-progress"
          aria-hidden="true"
          style={{ animationDuration: `${toast.durationMs}ms` }}
        />
      )}
    </article>
  );
}

export function ToastViewport({ store }: { store: ToastStore }) {
  const toasts = useSyncExternalStore(store.subscribe, store.getSnapshot);

  useEffect(() => {
    if (!toasts.length) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        store.dismiss(toasts[0].id);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [toasts, store]);

  if (!toasts.length) return null;

  return (
    <aside className="toast-viewport" aria-label="Thông báo trạng thái">
      {toasts.length > 1 && (
        <div className="toast-toolbar">
          <button
            type="button"
            className="toast-clear-all"
            onClick={store.clear}
          >
            Đóng tất cả ({toasts.length})
          </button>
        </div>
      )}
      {toasts.map((toast) => (
        <ToastCard key={toast.id} toast={toast} onDismiss={store.dismiss} />
      ))}
    </aside>
  );
}
