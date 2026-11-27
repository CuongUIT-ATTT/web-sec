import { useEffect, useRef, useState } from "react";
import { api, type ResourceInspection as Inspection } from "./api";

export function ResourceInspection({ projectId, resourceId }: { projectId: number; resourceId: number }) {
  const [value, setValue] = useState<Inspection | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  useEffect(() => () => { ++generation.current; }, []);
  function hide() { ++generation.current; setValue(null); setError(""); setPending(false); }
  useEffect(() => {
    const onHide = () => { if (document.hidden) hide(); };
    document.addEventListener("visibilitychange", onHide);
    return () => document.removeEventListener("visibilitychange", onHide);
  }, []);
  async function reveal() {
    const current = ++generation.current;
    setPending(true); setError("");
    try {
      const result = await api.inspectResource(projectId, resourceId);
      if (current === generation.current) setValue(result);
    } catch {
      if (current === generation.current) setError("Không xem được ID. Kiểm tra phiên đăng nhập rồi thử lại.");
    } finally { if (current === generation.current) setPending(false); }
  }
  return <div className="resource-inspection">
    <button type="button" className="quiet" aria-expanded={value !== null} disabled={pending}
      onClick={() => value ? hide() : void reveal()}>{pending ? "Đang đọc ID…" : value ? "Ẩn ID" : "Xem ID đã lưu"}</button>
    {error && <p role="alert">{error}</p>}
    {value && <div>
      <p>ID tài nguyên: <code>{value.external_id}</code></p>
      <p>Path parameter: <code>{value.path_parameter}</code></p>
      <p>Request preview từ dữ liệu đã lưu; chưa gửi tới lab.</p>
      {value.request_previews.length ? <ul>{value.request_previews.map(p => <li key={p.operation_id}><code>{p.method} {p.path}</code></li>)}</ul> : <p>Chưa có operation GET được chọn khớp path parameter.</p>}
    </div>}
  </div>;
}
