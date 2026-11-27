import { AuthorizationConfigEditor } from "./AuthorizationConfigEditor";
import { ToastViewport, useToastStore, type Notice } from "./Toast";
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { api, type AuthorizationCase, type AuthorizationPreview, type AuthorizationResult, type Run, type Target, type Operation, type ResourceType, type Resource, type Identity, type SnapshotIdentityLabel } from './api';

export function selectionBudget(rows: AuthorizationCase[]) {
  const baselines = new Set(rows.map(c => `${c.operation_id}:${c.resource_id}:${c.baseline_identity_id}`));
  const identities = new Set(rows.flatMap(c => [c.actor_identity_id, c.baseline_identity_id]).filter(x => x !== null));
  return rows.length + baselines.size + identities.size;
}
const evidenceLabels: Record<string,string> = {baseline_authorized:'Baseline được policy cho phép',baseline_valid:'Baseline hợp lệ',baseline_http_status:'HTTP baseline',actor_principal_matches:'Danh tính actor đã khớp',baseline_resource_matches:'Baseline đúng tài nguyên/kết quả',actor_resource_matches:'Actor nhận đúng tài nguyên/kết quả',protected_fields_match_baseline:'Dữ liệu bảo vệ khớp baseline',actor_body_truncated:'Body actor bị cắt',actor_json_parse_error:'Lỗi JSON actor',baseline_body_truncated:'Body baseline bị cắt',baseline_json_parse_error:'Lỗi JSON baseline'};
const explanations: Record<string,string> = {CONFIRMED_VIOLATION:'Policy cấm nhưng dữ liệu bảo vệ khớp đối chứng được phép.',SUSPECTED_VIOLATION:'Có dấu hiệu tiết lộ, bằng chứng chưa đủ để xác nhận.',POLICY_CONSISTENT_CASE:'Hành vi quan sát phù hợp policy.',INVALID_TEST:'Danh tính hoặc đối chứng không hợp lệ.',INSUFFICIENT_EVIDENCE:'Chưa đủ bằng chứng để kết luận.',NOT_RUN:'Chưa có kết quả thực thi.'};
export function historicalIdentity(label: SnapshotIdentityLabel | undefined, id: number | null) {
  if (label?.display_name) return `${label.display_name} (${label.role ?? 'Chưa gán role'}) · #${label.id}`;
  return id == null ? 'Chưa có / không áp dụng' : `Danh tính #${id}${label?.role ? ` (${label.role})` : ''} · thiếu nhãn snapshot lịch sử`;
}
const steps = ['Setup', 'Matrix', 'Run', 'Results', 'Comparison'];
export function AuthorizationWorkflow({ projectId, targets, setup, legacy, operations = [], types = [], resources = [], identities = [], onNotice }: {projectId: number; targets: Target[]; setup: ReactNode; legacy: ReactNode; operations?: Operation[]; types?: ResourceType[]; resources?: Resource[]; identities?: Identity[]; onNotice?: (notice: Notice) => void}) {
  const [step, setStep] = useState('Setup');
  const [target, setTarget] = useState('');
  const [config, setConfig] = useState('');
  const [dirty, setDirty] = useState(false);
  const [preview, setPreview] = useState<AuthorizationPreview | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [runs, setRuns] = useState<Run[]>([]);
  const [runId, setRunId] = useState('');
  const [results, setResults] = useState<AuthorizationResult[]>([]);
  const localToastStore = useToastStore();
  const pushNotice = onNotice ?? localToastStore.notify;
  const [busy, setBusy] = useState(false);
  const [conclusion, setConclusion] = useState('');
  const [resultPage, setResultPage] = useState(0);
  useEffect(() => {setResultPage(0);}, [runId, conclusion]);
  const lock = useRef(false);
  async function perform(work: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true);
    try { await work(); } catch (e) { pushNotice({ kind: 'error', text: e instanceof Error ? e.message : 'Yêu cầu thất bại' }); }
    finally { lock.current = false; setBusy(false); }
  }
  useEffect(() => { let live = true; api.authorizationConfig(projectId).then(v => { if (live) setConfig(JSON.stringify(v.configuration, null, 2)); }).catch(e => {if(live) pushNotice({ kind: 'error', text: String(e) });}); return () => {live = false;}; }, [projectId, pushNotice]);
  // Any setup change invalidates the preview and explicit selection.
  useEffect(() => {setPreview(null); setSelected([]);}, [targets, setup, target]);
  useEffect(() => {
    let live = true; let timer: number;
    async function poll() {
      try {
        const list = await api.runs(projectId);
        if (!live) return;
        setRuns(list);
        if (runId) {const response = await api.authorizationResults(projectId, Number(runId)); if(live) setResults(response.cases);}
      } catch(e) {if(live) pushNotice({ kind: 'error', text: String(e) });}
      if(live) timer = window.setTimeout(poll, 2000);
    }
    if (['Run','Results','Comparison'].includes(step)) void poll();
    return () => {live = false; window.clearTimeout(timer);};
  }, [step, projectId, runId, pushNotice]);
  const identityName = (id: number | null) => {
    const i = identities.find(i => i.id === id);
    return i ? `${i.display_name} (${i.role ?? 'Chưa gán role'}) · #${i.id}` : id == null ? 'Không áp dụng' : `Identity #${id}`;
  };
  const resourceName = (id: number | null) => id == null ? 'Chức năng' : resources.find(r => r.id === id)?.resource_alias ?? `resource-${id}`;
  const caseTitle = (c: AuthorizationCase) => `${identityName(c.actor_identity_id)} → ${c.method} ${c.path_template} → ${resourceName(c.resource_id)} · chủ sở hữu ${identityName(c.owner_identity_id)}`;
  const rows = preview?.cases ?? [];
  const filteredResults = results.filter(r => !conclusion || r.conclusion === conclusion);
  const pageCount = Math.max(1, Math.ceil(filteredResults.length / 50));
  const safePage = Math.min(resultPage, pageCount - 1);
  const picked = rows.filter(c => selected.includes(c.case_id));
  const budget = selectionBudget(picked);
  const visible = rows.filter(c => Object.entries(filters).every(([key,value]) => !value || String(c[key as keyof AuthorizationCase] ?? '') === value));
  async function refresh() {const next = await api.authorizationPreview(projectId, Number(target)); setPreview(next); setSelected([]); pushNotice({ kind: 'success', text: `Đã tạo preview ma trận: ${next.actor_case_count} cases (${next.executable_case_count} khả thi).` });}
  return <section className="authorization-workflow">
    <nav className="workflow-nav" aria-label="Năm bước kiểm thử">{steps.map(s => <button key={s} aria-current={step === s ? 'step' : undefined} onClick={() => setStep(s)}>{s}</button>)}</nav>
    <h2>{step}</h2><p>Ma trận tự động BOLA / BFLA · chỉ thực thi GET đã phê duyệt.</p>
    {step === 'Setup' && <>{setup}<article className="station"><h3>Quy tắc quyền dùng lại</h3><p>Chọn operation và loại BOLA/BFLA, xác nhận mapping; khai báo owner/shared/role và evidence chức năng. DENY thắng UNKNOWN, rồi ALLOW. Không khớp là UNKNOWN.</p><AuthorizationConfigEditor value={config} operations={operations} types={types} resources={resources} identities={identities} onNotice={pushNotice} onChange={value => {setConfig(value); setDirty(true); setPreview(null); setSelected([]);}} /><button disabled={busy || !dirty} onClick={() => void perform(async () => {await api.saveAuthorizationConfig(projectId, JSON.parse(config)); setDirty(false); pushNotice({ kind: 'success', text: 'Đã lưu revision mới. Mở Matrix để xem toàn bộ case.' });})}>Lưu quy tắc</button></article></>}
    {step === 'Matrix' && <>
      <label>API đích cho ma trận<select value={target} onChange={e => setTarget(e.target.value)}><option value="">Chọn API</option>{targets.map(t => <option key={t.id} value={t.id}>{t.base_url}</option>)}</select></label>
      <button disabled={!target || dirty || busy} onClick={() => void perform(refresh)}>Tạo lại preview</button>
      {!preview && <p role="status">Preview chưa có hoặc đã cũ. Lưu cấu hình rồi tạo lại trước khi chọn case.</p>}
      {preview && <><p>{preview.identity_count} identities · {preview.actor_case_count} cases · {preview.executable_case_count} executable · {preview.exclusions.length} exclusions</p><p>Revision <code>{preview.policy_revision}</code></p>
        <ul aria-label="Coverage theo danh tính">{identities.map(i=><li key={i.id}>{i.display_name} / {i.role ?? "Chưa gán role"}: {rows.filter(c=>c.actor_identity_id===i.id).length} cases{preview.exclusions.filter(e=>e.identity_id===i.id).map(e=>` · ${e.reason}`)}</li>)}</ul>{!rows.length && <p>Chưa có case: kiểm tra identity verification, resources, operation được chọn/phê duyệt và mapping.</p>}<ul aria-label="Identity exclusions">{preview.exclusions.map((e,i) => <li key={i}>Identity #{e.identity_id}: {e.reason}</li>)}</ul><ul aria-label="Cảnh báo mapping">{preview.warnings.map((w,i) => <li key={i}>Operation #{w.operation_id}: {w.reason}</li>)}</ul>
        <div className="matrix-filters">{[['actor_identity_id','Identity'],['actor_role','Role'],['operation_id','Operation'],['resource_id','Resource'],['expected_decision','Quyền dự kiến']].map(([key,label]) => <label key={key}>{label}<select value={filters[key] ?? ''} onChange={e => setFilters({...filters,[key]:e.target.value})}><option value="">Tất cả</option>{[...new Set(rows.map(c => String(c[key as keyof AuthorizationCase] ?? '')))].filter(Boolean).map(v => <option key={v} value={v}>{key === 'actor_identity_id' ? identityName(Number(v)) : key === 'resource_id' ? resourceName(Number(v)) : key === 'operation_id' ? (() => {const o=operations.find(o=>o.id===Number(v)); return o ? `${o.method} ${o.path}` : `Operation #${v}`;})() : v}</option>)}</select></label>)}</div>
        <p>{visible.length}/{rows.length} hiển thị · {selected.length} được chọn · budget {budget}/{preview.request_limit} requests (actor + baseline + xác minh). Toàn ma trận: {preview.planned_attempts}.</p>
        <button onClick={() => { if (selected.length) { setSelected([]); pushNotice({ kind: 'info', text: 'Đã bỏ chọn tất cả case.' }); } }}>Bỏ chọn tất cả</button>
        <div className="case-table"><table><thead><tr><th>Chọn</th><th>Case / operation</th><th>Actor / role</th><th>Resource / owner</th><th>Policy / baseline</th><th>Trạng thái</th></tr></thead><tbody>{visible.map(c => <tr key={c.case_id}><td><span className="matrix-mobile-label">Chọn</span><input aria-label={`Chọn ${c.case_id}`} type="checkbox" disabled={!c.execution_eligible || c.method !== 'GET'} checked={selected.includes(c.case_id)} onChange={e => setSelected(e.target.checked ? [...selected,c.case_id] : selected.filter(id => id !== c.case_id))}/></td><td><span className="matrix-mobile-label">Case / operation</span><b>{c.method} {c.path_template}</b><p>{c.kind}</p><details><summary>Case ID</summary><code>{c.case_id}</code></details></td><td><span className="matrix-mobile-label">Actor / role</span>{identityName(c.actor_identity_id)}</td><td><span className="matrix-mobile-label">Resource / owner</span><b>{resourceName(c.resource_id)}</b><p>Chủ sở hữu: {identityName(c.owner_identity_id)}</p><p>{c.relationship}</p></td><td><span className="matrix-mobile-label">Policy / baseline</span>{c.expected_decision}<p>{c.matched_rule_keys.join(', ')}</p>Baseline dự kiến: {identityName(c.baseline_identity_id)}</td><td><span className="matrix-mobile-label">Trạng thái</span>NOT_RUN<p>{c.reasons.join(', ')}</p></td></tr>)}</tbody></table></div>
        <button disabled={!selected.length || busy || budget > preview.request_limit} onClick={() => setStep('Run')}>Xem lựa chọn trước khi chạy</button></>}
    </>}
    {step === 'Run' && <><article className="selection-summary"><h3>Lựa chọn hiện tại</h3><ul aria-label="Các case được chọn">{picked.map(c => <li key={c.case_id}>{caseTitle(c)} · {c.expected_decision} · baseline dự kiến {identityName(c.baseline_identity_id)}</li>)}</ul><p>{picked.length} case được chọn · {budget} requests dự kiến / budget {preview?.request_limit ?? "—"}. Revision {preview?.policy_revision ?? 'chưa có'}. Snapshot được cố định lúc queue.</p><button disabled={!preview || dirty || !picked.length || busy || budget > (preview?.request_limit ?? 0)} onClick={() => void perform(async () => {
      if(!preview) return;
      const current = await api.authorizationPreview(projectId, Number(target));
      if(JSON.stringify(current) !== JSON.stringify(preview)) {setPreview(current); setSelected([]); throw new Error('STALE_PREVIEW: cấu hình đã đổi. Chọn lại case ở Matrix.');}
      const run = await api.queueAuthorization(projectId, Number(target), preview.policy_revision, selected);
      setRunId(String(run.id)); setSelected([]); pushNotice({ kind: 'success', text: `Đã queue Run #${run.id}` });
    })}>Queue các case GET đã chọn</button><p>Requests dự kiến gồm xác minh danh tính, baseline được phép và requests của actor. Lựa chọn hiện tại độc lập với run đã queue.</p></article><h3>Run đã queue và lịch sử</h3>
    {runs.map(r => <article key={r.id}><b>Run #{r.id} · {r.status}</b><p>{String((r.snapshot.request_plan as {actor_cases?: number} | undefined)?.actor_cases ?? r.snapshot.concrete_target_count ?? "Không có metadata")} cases đã queue</p><p>Snapshot: {String(r.snapshot.run_kind ?? "LEGACY")} · revision {String(r.snapshot.policy_revision ?? "lịch sử")}</p>{r.execution_summary && <p>Planned {r.execution_summary.planned_attempts} · transport {r.execution_summary.transport_attempts} · responses {r.execution_summary.completed_responses} · errors {r.execution_summary.transport_errors} · scope blocked {r.execution_summary.scope_blocked} · cancelled {r.execution_summary.cancelled_cases}</p>}<details><summary>Danh tính và baseline dự kiến trong snapshot Run #{r.id}</summary><ul>{((r.snapshot.case_summaries ?? []) as {case_id:string; actor:SnapshotIdentityLabel; owner:SnapshotIdentityLabel; baseline:SnapshotIdentityLabel; method:string; path:string; resource_name:string|null; resource_id:number|null}[]).map(c=><li key={c.case_id}>{historicalIdentity(c.actor,c.actor.id)} → {c.method} {c.path} → {c.resource_name ?? (c.resource_id == null ? 'Chức năng' : `resource-${c.resource_id}`)} · chủ sở hữu {historicalIdentity(c.owner,c.owner.id)} · baseline dự kiến {historicalIdentity(c.baseline,c.baseline.id)}</li>)}</ul><p>Baseline thực thi quan sát được nằm trong Results; không suy ra từ lựa chọn hiện tại.</p></details>{['QUEUED','RUNNING','CANCEL_REQUESTED'].includes(r.status) && <button disabled={busy || r.status === 'CANCEL_REQUESTED'} onClick={() => void perform(async () => {await api.cancelRun(r.id); setRuns(await api.runs(projectId)); pushNotice({ kind: 'info', text: `Đã gửi yêu cầu hủy Run #${r.id}.` });})}>Hủy Run #{r.id}</button>}</article>)}</>}
    {['Results','Comparison'].includes(step) && <><label>Run tự động<select value={runId} onChange={e => {setRunId(e.target.value); setResults([]);}}><option value="">Chọn run</option>{runs.filter(r => r.snapshot.run_kind === 'AUTOAUTH_SELECTED').map(r => <option key={r.id} value={r.id}>Run #{r.id} · {r.status}</option>)}</select></label>
    {step === 'Results' ? <><label>Lọc kết luận<select value={conclusion} onChange={e=>setConclusion(e.target.value)}><option value="">Tất cả</option>{['CONFIRMED_VIOLATION','SUSPECTED_VIOLATION','POLICY_CONSISTENT_CASE','INVALID_TEST','INSUFFICIENT_EVIDENCE','NOT_RUN'].map(c=><option key={c}>{c}</option>)}</select></label><p>Kết luận dựa trên policy và bằng chứng baseline; HTTP thành công riêng lẻ không chứng minh vi phạm. Chỉ metadata rút gọn được hiển thị.</p><p>{filteredResults.length} kết quả · Trang {safePage+1}/{pageCount}</p><button disabled={safePage===0} onClick={()=>setResultPage(safePage-1)}>Trang kết quả trước</button><button disabled={safePage+1>=pageCount} onClick={()=>setResultPage(safePage+1)}>Trang kết quả sau</button><div className="results-list" aria-label="Kết quả kiểm thử"><div className="result-columns" aria-hidden="true"><b>Người gọi</b><b>Tài nguyên / chức năng</b><b>Policy dự kiến</b><b>HTTP quan sát</b><b>Kết luận</b></div>{filteredResults.slice(safePage*50, (safePage+1)*50).map(r => <article className="result-item" key={r.case_id}>
      <dl className="result-columns result-fields"><div><dt className="mobile-label">Người gọi</dt><dd><b>{historicalIdentity(r.presentation?.actor,r.actor_identity_id)}</b></dd></div><div><dt className="mobile-label">Tài nguyên / chức năng</dt><dd><b>{r.presentation?.method ?? 'GET'} {r.presentation?.path ?? `Operation #${r.operation_id ?? '—'} · thiếu snapshot`}</b><p>{r.resource_id == null ? 'Chức năng' : r.presentation?.resource_name ?? `resource-${r.resource_id} · thiếu nhãn snapshot`}</p><p>Chủ sở hữu: {historicalIdentity(r.presentation?.owner,r.presentation?.owner.id ?? null)}</p></dd></div><div><dt className="mobile-label">Policy dự kiến</dt><dd>{r.expected_decision}</dd></div><div><dt className="mobile-label">HTTP quan sát</dt><dd>{r.http_status ?? '—'}<p>{r.execution_status} · HTTP {r.http_status ?? '—'}</p></dd></div><div><dt className="mobile-label">Kết luận</dt><dd><strong>{r.conclusion}</strong><p>{explanations[r.conclusion] ?? "Chưa có giải thích"}</p></dd></div></dl>
      <p>Baseline thực thi: {historicalIdentity(r.presentation?.actual_baseline,r.presentation?.actual_baseline.id ?? null)} · {r.presentation?.baseline_provenance ?? 'Thiếu provenance lịch sử'}{r.presentation?.actual_baseline.id != null && r.presentation.actual_baseline.id !== r.baseline_identity_id && <strong> · KHÁC BASELINE DỰ KIẾN — cần kiểm tra provenance</strong>}</p>
      <details><summary aria-label={`Đối chiếu và evidence ${r.case_id}`}>Đối chiếu và evidence</summary><div className="evidence-details"><p>Baseline dự kiến trong snapshot: {historicalIdentity(r.presentation?.planned_baseline,r.baseline_identity_id)} · {r.presentation?.baseline_kind ?? 'Thiếu lý do snapshot'}</p><p>Baseline thực thi lấy từ evidence đã lưu; không thay bằng cấu hình hiện tại. OWNER ưu tiên nếu policy ALLOW; nếu không, dùng danh tính ALLOW có ID nhỏ nhất.</p><p>{r.reason_codes.join(', ')}</p><p>Độ đầy đủ bằng chứng: {r.conclusion === 'INSUFFICIENT_EVIDENCE' || r.conclusion === 'NOT_RUN' ? 'Chưa đủ / chưa quan sát' : 'Xem kết luận và đối chiếu bên dưới'}</p><dl>{Object.entries(r.evidence ?? {}).map(([k,v])=><div key={k}><dt>{evidenceLabels[k] ?? k}</dt><dd>{v === null ? 'UNAVAILABLE' : typeof v === 'boolean' ? (v ? 'Có' : 'Không') : String(v)}</dd></div>)}</dl><p>Revision {r.policy_revision}</p><p>{r.matched_rule_keys.join(', ')}</p><p>Run #{r.run_id} · result #{r.result_id ?? '—'}</p><code>{r.case_id}</code><p>{r.finding_id}</p><p>{r.artifact_ref ?? 'UNAVAILABLE'}</p></div></details>
    </article>)}</div></> : <><p>Manual và OWASP ZAP: NOT_RUN · provenance/artifact UNAVAILABLE. Chưa có ground truth được xác minh để tính TP/FP/TN/FN.</p><div className="case-table"><table><thead><tr><th>Người gọi / tài nguyên</th><th>T18</th><th>Manual</th><th>OWASP ZAP</th></tr></thead><tbody>{results.map(r => <tr key={r.case_id}><td><b>{historicalIdentity(r.presentation?.actor,r.actor_identity_id)}</b><p>{r.presentation?.method} {r.presentation?.path}</p><p>{r.presentation?.resource_name ?? "Chức năng"}</p><details><summary>Case ID</summary><code>{r.case_id}</code></details></td><td>{r.execution_status} / {r.conclusion}<p>{r.artifact_ref ?? 'UNAVAILABLE'}</p></td><td>NOT_RUN / UNAVAILABLE</td><td>NOT_RUN / UNAVAILABLE</td></tr>)}</tbody></table></div></>}
    <details><summary>Lịch sử và bundle so sánh đã lưu</summary>{legacy}</details></>}
    {!onNotice && <ToastViewport store={localToastStore} />}
  </section>;
}
