import { ResourceInspection } from "./ResourceInspection";
import { AuthorizationWorkflow } from "./AuthorizationWorkflow";
import { ToastViewport, useToastStore, type Notice } from "./Toast";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { api, type ComparisonBundle, type BundleMethod, type Comparison, type BatchMatrix, type ExternalLabJob, type Finding, type Identity, type MatrixCase, type Operation, type OperationResourceMapping, type Policy, type Project, type Resource, type ResourceType, type Result, type Run, type Target } from "./api";

function useAction() {
  const toastStore = useToastStore();
  async function perform(work: () => Promise<void>) {
    try { await work(); } catch (error) { toastStore.notify({ kind: "error", text: error instanceof Error ? error.message : "Lỗi không xác định." }); }
  }
  return { toastStore, setNotice: toastStore.notify, perform };
}

function errorNotice(error: unknown): Exclude<Notice, null> { return { kind: "error", text: error instanceof Error ? error.message : "Lỗi không xác định." }; }
function optional(value: string): string | null { return value.trim() || null; }

export function App({ legacy = false }: { legacy?: boolean } = {}) {
  const [authenticated, setAuthenticated] = useState(false);
  const [password, setPassword] = useState("");
  const [seedingDemo, setSeedingDemo] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<number | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);
  const [identities, setIdentities] = useState<Identity[]>([]);
  const [operations, setOperations] = useState<Operation[]>([]);
  const [resourceTypes, setResourceTypes] = useState<ResourceType[]>([]);
  const [resources, setResources] = useState<Resource[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [mappings, setMappings] = useState<OperationResourceMapping[]>([]);
  const [matrix, setMatrix] = useState<MatrixCase[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [results, setResults] = useState<Result[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [externalLabJobs, setExternalLabJobs] = useState<ExternalLabJob[]>([]);
  const { toastStore, setNotice, perform } = useAction();
  const projectGeneration = useRef(0);
  const activeProject = projects.find((project) => project.id === activeProjectId) ?? null;
  const target = targets[0] ?? null;

  async function refreshProject(projectId: number) {
    const generation = ++projectGeneration.current;
    const [nextTargets, nextIdentities, nextOperations, nextTypes, nextResources, nextPolicies, nextMappings, nextRuns, nextFindings, nextExternalLabJobs] = await Promise.all([
      api.targets(projectId), api.identities(projectId), api.operations(projectId), api.resourceTypes(projectId), api.resources(projectId), api.policies(projectId), api.operationResourceMappings(projectId), api.runs(projectId), api.findings(projectId), api.externalLabJobs(projectId),
    ]);
    if (generation !== projectGeneration.current) return;
    setTargets(nextTargets); setIdentities(nextIdentities); setOperations(nextOperations); setResourceTypes(nextTypes); setResources(nextResources); setPolicies(nextPolicies); setMappings(nextMappings); setRuns(nextRuns); setFindings(nextFindings); setExternalLabJobs(nextExternalLabJobs);
  }

  async function refreshProjects(activeId = activeProjectId) {
    const loaded = await api.projects();
    setProjects(loaded);
    if (activeId && loaded.some((project) => project.id === activeId)) return;
    setActiveProjectId(loaded[0]?.id ?? null);
  }

  useEffect(() => {
    if (!authenticated) return;
    refreshProjects().catch(() => setAuthenticated(false));
  }, [authenticated]);

  useEffect(() => {
    ++projectGeneration.current;
    setTargets([]); setIdentities([]); setOperations([]); setResourceTypes([]); setResources([]); setPolicies([]); setMappings([]); setMatrix([]); setRuns([]); setResults([]); setFindings([]); setExternalLabJobs([]);
    if (!activeProjectId) return;
    refreshProject(activeProjectId).catch((error: unknown) => setNotice(errorNotice(error)));
  }, [activeProjectId]);

  if (!authenticated) return <><main className="gate"><section className="gate-card"><p className="signal">PHẠM VI CÓ KIỂM SOÁT</p><h1>Trạm kiểm thử<br />phân quyền REST</h1><p>Đăng nhập quản trị để cấu hình lab IP allowlist, chạy GET read-only và xem bằng chứng đã được rút gọn.</p><form onSubmit={(event) => { event.preventDefault(); void perform(async () => { await api.login(password); setPassword(""); setAuthenticated(true); setNotice({ kind: "success", text: "Đăng nhập thành công." }); }); }}><label>Mật khẩu quản trị<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required /></label><button>Vào trạm kiểm thử</button></form></section></main><ToastViewport store={toastStore} /></>;

  return <><main className="shell"><header className="masthead"><div><p className="signal">CONTROLLED AUTHORIZATION TESTING</p><h1>Trạm kiểm thử phân quyền</h1></div><div className="scope-note"><b>GET-only MVP</b><span>Bearer · JSON · IP allowlist</span><button className="quiet" onClick={() => void perform(async () => { await api.logout(); setAuthenticated(false); setNotice({ kind: "info", text: "Đã đăng xuất khỏi phiên quản trị." }); })}>Đăng xuất</button></div></header>
    <aside className="rail"><h2>Dự án</h2><ProjectForm onCreated={(project) => { setProjects((current) => [...current, project]); setActiveProjectId(project.id); setNotice({ kind: "success", text: `Đã tạo dự án ${project.name}.` }); }} onNotice={setNotice} />
      <button disabled={seedingDemo} onClick={() => { setSeedingDemo(true); void perform(async () => {
        const demo = await api.seedSshDemo();
        setProjects(await api.projects());
        setActiveProjectId(demo.project_id);
        await refreshProject(demo.project_id);
        setNotice({kind: "success", text: "Đã chọn dữ liệu mẫu lab SSH. Nhập token lab và xác minh userA, userB, admin trong Setup. Policy cross-owner/admin cần được cấu hình theo kịch bản lab."});
      }).finally(() => setSeedingDemo(false)); }}>{seedingDemo ? "Đang nạp mẫu…" : "Nạp dữ liệu mẫu"}</button>
      <p>Lab SSH 100.106.64.21:5003 · 3 tài khoản · 4 sách. Cần nhập token lab riêng. Không tự chạy kiểm thử. Nạp lại giữ nguyên cấu hình và lịch sử.</p>
      <div className="project-list">{projects.map((project) => <button className={project.id === activeProjectId ? "project active" : "project"} key={project.id} onClick={() => setActiveProjectId(project.id)}>{project.name}</button>)}</div>
      <p className="rail-foot">Thông tin bí mật chỉ được gửi trong biểu mẫu, mã hoá ở server và không được trả về giao diện.</p>
    </aside>
    <section className="workspace">{!activeProject ? <Empty title="Chưa có dự án" text="Tạo dự án để bắt đầu thiết lập lab." /> : <>
      <DeleteProject key={activeProject.id} project={activeProject} onNotice={setNotice} onDeleted={() => { ++projectGeneration.current; setProjects(current => current.filter(p => p.id !== activeProject.id)); setActiveProjectId(null); setNotice({ kind: "success", text: "Đã xóa dự án và dữ liệu lưu trong ứng dụng." }); }} />
      <ProjectHeading project={activeProject} onNotice={setNotice} onSaved={async (next) => { await refreshProjects(next.id); setNotice({ kind: "success", text: "Đã cập nhật dự án. Các lượt chạy lịch sử không thay đổi." }); }} />
{legacy ? <>      <div className="station-grid">
        <TargetPanel projectId={activeProject.id} targets={targets} onChanged={async () => {await refreshProject(activeProject.id); setMatrix([]);}} onNotice={setNotice}/>
        <IdentityPanel projectId={activeProject.id} target={target} identities={identities} onChanged={async () => {await refreshProject(activeProject.id); setMatrix([]);}} onNotice={setNotice}/>
        <ResourcePanel key={activeProject.id} projectId={activeProject.id} identities={identities} types={resourceTypes} resources={resources} onChanged={async () => {await refreshProject(activeProject.id); setMatrix([]);}} onNotice={setNotice}/>
        <MatrixPanel projectId={activeProject.id} operations={operations} types={resourceTypes} resources={resources} identities={identities} policies={policies} mappings={mappings} matrix={matrix} onMatrix={setMatrix} onChanged={async () => {await refreshProject(activeProject.id); setMatrix([]);}} onNotice={setNotice}/>
        <RunPanel projectId={activeProject.id} targets={targets} mappings={mappings} runs={runs} results={results} findings={findings} onRuns={setRuns} onResults={setResults} onFindings={setFindings} onNotice={setNotice}/>
        <article><ExternalLabPanel projectId={activeProject.id} jobs={externalLabJobs} onJobs={setExternalLabJobs} onNotice={setNotice}/></article>
      </div></> : <>      <AuthorizationWorkflow key={activeProject.id} projectId={activeProject.id} targets={targets} operations={operations} types={resourceTypes} resources={resources} identities={identities} onNotice={setNotice} setup={<div className="station-grid">        <Station number="01" title="API đích có phạm vi" detail="Chỉ chấp nhận IP/CIDR, port và đường dẫn đã allowlist."><TargetPanel projectId={activeProject.id} targets={targets} onChanged={async () => { await refreshProject(activeProject.id); setMatrix([]); }} onNotice={setNotice} /></Station>
        <Station number="02" title="Danh tính độc lập" detail="Mỗi bearer token dùng một context riêng; anonymous không kế thừa gì."><IdentityPanel projectId={activeProject.id} target={target} identities={identities} onChanged={async () => { await refreshProject(activeProject.id); setMatrix([]); }} onNotice={setNotice} /></Station>
        <Station number="03" title="OpenAPI operations" detail="Tải OpenAPI JSON cục bộ. Chỉ operation GET được chọn mới có thể chạy."><OpenApiPanel projectId={activeProject.id} operations={operations} onChanged={async () => { await refreshProject(activeProject.id); setMatrix([]); }} onNotice={setNotice} /></Station>
        <Station number="04" title="Tài nguyên và mapping" detail="Khai báo resource có owner; dùng JSON Pointer tuyệt đối RFC 6901."><ResourcePanel key={activeProject.id} projectId={activeProject.id} identities={identities} types={resourceTypes} resources={resources} onChanged={async () => { await refreshProject(activeProject.id); setMatrix([]); }} onNotice={setNotice} /></Station>
</div>} legacy={<ComparePanel projectId={activeProject.id} runs={runs} />} /></>}
    </>}</section>
  </main><ToastViewport store={toastStore} /></>;
}

function Empty({ title, text }: { title: string; text: string }) { return <div className="empty"><h2>{title}</h2><p>{text}</p></div>; }
function Station({ number, title, detail, children }: { number: string; title: string; detail: string; children: ReactNode }) { return <article id={`station-${number}`} className="station"><header><span>{number}</span><div><h3>{title}</h3><p>{detail}</p></div></header>{children}</article>; }

function ProjectForm({ onCreated, onNotice }: { onCreated: (project: Project) => void; onNotice?: (notice: Notice) => void }) {
  const [name, setName] = useState(""); const [description, setDescription] = useState("");
  return <form className="compact-form" onSubmit={(event) => { event.preventDefault(); api.createProject(name, description).then((project) => { onCreated(project); setName(""); setDescription(""); }).catch((reason: unknown) => onNotice?.(errorNotice(reason))); }}><label>Tên dự án<input value={name} onChange={(event) => setName(event.target.value)} required /></label><label>Mô tả<textarea value={description} onChange={(event) => setDescription(event.target.value)} /></label><button>Tạo dự án</button></form>;
}

function ProjectHeading({ project, onSaved, onNotice }: { project: Project; onSaved: (project: Project) => Promise<void>; onNotice?: (notice: Notice) => void }) {
  const [editing, setEditing] = useState(false); const [name, setName] = useState(project.name); const [description, setDescription] = useState(project.description);
  useEffect(() => { setName(project.name); setDescription(project.description); }, [project]);
  if (!editing) return <div className="project-heading"><div><p className="signal">DỰ ÁN ĐANG MỞ</p><h2>{project.name}</h2><p>{project.description || "Chưa có mô tả."}</p></div><button className="quiet" onClick={() => setEditing(true)}>Sửa dự án</button></div>;
  return <form className="project-heading compact-form edit-form" onSubmit={(event) => { event.preventDefault(); api.updateProject(project.id, { name, description }).then(async (next) => { await onSaved(next); setEditing(false); }).catch((error: unknown) => onNotice?.(errorNotice(error))); }}><label>Tên dự án<input value={name} onChange={(event) => setName(event.target.value)} required /></label><label>Mô tả<textarea value={description} onChange={(event) => setDescription(event.target.value)} /></label><div className="actions"><button>Lưu thay đổi</button><button type="button" className="quiet" onClick={() => { setName(project.name); setDescription(project.description); setEditing(false); }}>Huỷ</button></div></form>;
}

function TargetPanel({ projectId, targets, onChanged, onNotice }: { projectId: number; targets: Target[]; onChanged: () => Promise<void>; onNotice: (notice: Notice) => void }) {
  const [editingId, setEditingId] = useState<number | null>(null); const selected = targets.find((item) => item.id === editingId) ?? null;
  const [testingId, setTestingId] = useState<number | null>(null);
  const [baseUrl, setBaseUrl] = useState(""); const [verificationPath, setVerificationPath] = useState("/me"); const [timeout, setTimeout] = useState("5"); const [limit, setLimit] = useState("100");
  useEffect(() => { if (selected) { setBaseUrl(selected.base_url); setVerificationPath(selected.verification_path); setTimeout(String(selected.timeout_seconds)); setLimit(String(selected.request_limit)); } }, [selected]);
  function reset() { setEditingId(null); setBaseUrl(""); setVerificationPath("/me"); setTimeout("5"); setLimit("100"); }
  const value = { base_url: baseUrl, verification_path: verificationPath, timeout_seconds: Number(timeout), request_limit: Number(limit) };
  return <div className="panel-content"><form className="compact-form" onSubmit={(event) => { event.preventDefault(); const request = selected ? api.updateTarget(selected.id, value) : api.createTarget(projectId, value); request.then(async () => { await onChanged(); reset(); onNotice({ kind: "success", text: `Đã ${selected ? "cập nhật" : "lưu"} API đích; thay đổi chỉ áp dụng lượt chạy mới.` }); }).catch((error: unknown) => onNotice(errorNotice(error))); }}><label>Base URL IP lab<input placeholder="http://127.0.0.1:5000/api" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} required /></label><label>Đường dẫn kiểm tra principal<input value={verificationPath} onChange={(event) => setVerificationPath(event.target.value)} required /></label><label>Timeout (giây)<input type="number" min="0.1" max="30" step="0.1" value={timeout} onChange={(event) => setTimeout(event.target.value)} required /></label><label>Giới hạn request<input type="number" min="1" max="1000" value={limit} onChange={(event) => setLimit(event.target.value)} required /></label><div className="actions"><button>{selected ? "Lưu API đích" : "Thêm API đích"}</button>{selected && <button type="button" className="quiet" onClick={reset}>Huỷ</button>}</div></form><ul className="evidence-list">{targets.map((item) => <li key={item.id}><div><b>{item.base_url}</b><span>{item.verification_path} · timeout {item.timeout_seconds}s · limit {item.request_limit}</span></div><div className="actions"><button className="quiet" onClick={() => { setEditingId(item.id); onNotice({ kind: "info", text: `Đang chỉnh sửa API đích ${item.base_url}.` }); }}>Sửa</button><button className="quiet" disabled={testingId === item.id} onClick={() => { setTestingId(item.id); api.connectionTest(item.id).then((result) => onNotice({ kind: "info", text: `Connection test: ${result.execution_status}${result.http_status ? ` · HTTP ${result.http_status}` : ""}` })).catch((error: unknown) => onNotice(errorNotice(error))).finally(() => setTestingId((current) => current === item.id ? null : current)); }}>{testingId === item.id ? "Đang kiểm tra…" : "Kiểm tra"}</button></div></li>)}</ul></div>;
}

function IdentityPanel({ projectId, target, identities, onChanged, onNotice }: { projectId: number; target: Target | null; identities: Identity[]; onChanged: () => Promise<void>; onNotice: (notice: Notice) => void }) {
  const [editingId, setEditingId] = useState<number | null>(null); const selected = identities.find((item) => item.id === editingId) ?? null;
  const [verifyingId, setVerifyingId] = useState<number | null>(null);
  const [displayName, setDisplayName] = useState(""); const [role, setRole] = useState(""); const [pointer, setPointer] = useState("/data/username"); const [principal, setPrincipal] = useState(""); const [token, setToken] = useState("");
  useEffect(() => { if (selected) { setDisplayName(selected.display_name); setRole(selected.role ?? ""); setPointer(selected.principal_pointer ?? ""); setPrincipal(selected.expected_principal ?? ""); setToken(""); } }, [selected]);
  const configuredRoles = new Set(identities.map(identity => identity.role?.trim()).filter(Boolean)).size;
  function reset() { setEditingId(null); setDisplayName(""); setRole(""); setPointer("/data/username"); setPrincipal(""); setToken(""); }
  return <div className="panel-content"><p>Role tài khoản lab độc lập với quyền quản trị web. {identities.length} tài khoản · {configuredRoles} role đã cấu hình. Gate 3 role: {configuredRoles >= 3 ? "ĐỦ CẤU HÌNH" : "CHƯA ĐỦ"}; gate 5 role: {configuredRoles >= 5 ? "ĐỦ CẤU HÌNH" : "CHƯA ĐỦ"}. Chưa xác minh thực nghiệm.</p><form className="compact-form" onSubmit={(event) => { event.preventDefault(); const metadata = { display_name: displayName, role: optional(role), principal_pointer: optional(pointer), expected_principal: optional(principal) }; const request = selected ? api.updateIdentity(selected.id, token ? { ...metadata, bearer_token: token } : metadata) : api.createIdentity(projectId, { ...metadata, bearer_token: token }); request.then(async () => { const replaced = Boolean(selected && token); await onChanged(); reset(); onNotice({ kind: "success", text: replaced ? "Đã cập nhật danh tính; bearer token đã thay thế và không thể hiển thị lại." : `Đã ${selected ? "cập nhật" : "lưu"} danh tính.` }); }).catch((error: unknown) => onNotice(errorNotice(error))); }}><label>Tên hiển thị<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} required /></label><label>Vai trò<input value={role} onChange={(event) => setRole(event.target.value)} /></label><label>Principal pointer<input value={pointer} onChange={(event) => setPointer(event.target.value)} required /></label><label>Principal mong đợi<input value={principal} onChange={(event) => setPrincipal(event.target.value)} required /></label><label>{selected ? "Bearer token thay thế (để trống để giữ token cũ)" : "Bearer token"}<input type="password" value={token} onChange={(event) => setToken(event.target.value)} autoComplete="off" required={!selected} /></label><div className="actions"><button>{selected ? "Lưu danh tính" : "Thêm danh tính"}</button>{selected && <button type="button" className="quiet" onClick={reset}>Huỷ</button>}</div></form><ul className="evidence-list">{identities.map((identity) => <li key={identity.id}><div><b>{identity.display_name}</b><span>identity-{identity.id}</span><span>{identity.role || "Không gán role"} · token {identity.has_secret ? "đã mã hoá" : "thiếu"}</span></div><div className="actions"><button className="quiet" onClick={() => { setEditingId(identity.id); onNotice({ kind: "info", text: `Đang chỉnh sửa danh tính ${identity.display_name}.` }); }}>Sửa</button>{target && <button className="quiet" disabled={verifyingId === identity.id} onClick={() => { setVerifyingId(identity.id); api.verifyIdentity(identity.id, target.id).then((result) => onNotice({ kind: result.principal_confirmed ? "success" : "error", text: `${identity.display_name}: auth=${result.authentication_passed ? "pass" : "fail"}, principal=${result.principal_matched ? "match" : "mismatch"}` })).catch((error: unknown) => onNotice(errorNotice(error))).finally(() => setVerifyingId((current) => current === identity.id ? null : current)); }}>{verifyingId === identity.id ? "Đang xác minh…" : "Xác minh"}</button>}</div></li>)}</ul></div>;
}

function OpenApiPanel({ projectId, operations, onChanged, onNotice }: { projectId: number; operations: Operation[]; onChanged: () => Promise<void>; onNotice: (notice: Notice) => void }) {
  const [spec, setSpec] = useState("{\n  \"openapi\": \"3.0.3\",\n  \"paths\": {\n    \"/books/{id}\": {\n      \"parameters\": [{ \"name\": \"id\", \"in\": \"path\" }],\n      \"get\": { \"operationId\": \"readBook\" }\n    }\n  }\n}");
  return <div className="panel-content"><form className="compact-form" onSubmit={(event) => { event.preventDefault(); try { const document = JSON.parse(spec) as Record<string, unknown>; api.importAuthorizationOpenApi(projectId, document).then(async () => { await onChanged(); onNotice({ kind: "success", text: "Đã phân tích OpenAPI JSON và lưu inventory operation." }); }).catch((error: unknown) => onNotice(errorNotice(error))); } catch { onNotice({ kind: "error", text: "OpenAPI phải là JSON hợp lệ." }); } }}><label>OpenAPI JSON<textarea className="code-input" value={spec} onChange={(event) => setSpec(event.target.value)} required /></label><button>Nhập OpenAPI</button></form><ul className="operation-list">{operations.map((operation) => <li key={operation.id}><b>{operation.method}</b><code>{operation.path}</code><span>{operation.operation_key}</span><label className="inline-check"><input type="checkbox" checked={operation.selected} onChange={(event) => api.updateOperation(operation.id, event.target.checked).then(async () => { await onChanged(); onNotice({ kind: "success", text: `Đã ${event.target.checked ? "chọn" : "bỏ chọn"} operation; chỉ run mới bị ảnh hưởng.` }); }).catch((error: unknown) => onNotice(errorNotice(error)))} /> Chọn vào ma trận</label></li>)}</ul></div>;
}

function ResourcePanel({ projectId, identities, types, resources, onChanged, onNotice }: { projectId: number; identities: Identity[]; types: ResourceType[]; resources: Resource[]; onChanged: () => Promise<void>; onNotice: (notice: Notice) => void }) {
  const [typeId, setTypeId] = useState(""); const selectedType = types.find((item) => item.id === Number(typeId)) ?? null;
  const [typeName, setTypeName] = useState("book"); const [idPointer, setIdPointer] = useState("/data/id"); const [restricted, setRestricted] = useState("/data/secret");
  const [resourceId, setResourceId] = useState(""); const selectedResource = resources.find((item) => item.id === Number(resourceId)) ?? null;
  const [externalId, setExternalId] = useState(""); const [ownerId, setOwnerId] = useState(""); const [parameter, setParameter] = useState("id");
  useEffect(() => { if (!typeId && types[0]) setTypeId(String(types[0].id)); }, [types, typeId]);
  useEffect(() => { if (selectedType) { setTypeName(selectedType.name); setIdPointer(selectedType.resource_id_pointer); setRestricted(selectedType.restricted_pointers.join(", ")); } }, [selectedType]);
  useEffect(() => { if (selectedResource) { setExternalId(""); setOwnerId(String(selectedResource.owner_identity_id)); setParameter(selectedResource.path_parameter); } }, [selectedResource]);
  function resetType() { setTypeId(""); setTypeName("book"); setIdPointer("/data/id"); setRestricted("/data/secret"); }
  function resetResource() { setResourceId(""); setExternalId(""); setOwnerId(""); setParameter("id"); }
  const [resourceInspectionRevision, setResourceInspectionRevision] = useState(0);
  useEffect(() => { setResourceInspectionRevision(n => n + 1); }, [resources]);
  const typeValue = { name: typeName, resource_id_pointer: idPointer, restricted_pointers: restricted.split(",").map((item) => item.trim()).filter(Boolean) };
  return <div className="panel-content"><h4>Tài nguyên thuộc tài khoản nào</h4><p>resource-N là nhãn nội bộ. Bấm Xem ID đã lưu để đối chiếu ID gửi tới lab; ID được ẩn khi rời màn hình.</p>{resources.length ? <ul className="evidence-list">{resources.map(resource => <li className="resource-config-row" key={resource.id}><b>{resource.resource_alias || `resource-${resource.id}`}</b><span>{types.find(type => type.id === resource.resource_type_id)?.name} · Owner: identity-{resource.owner_identity_id} · {identities.find(identity => identity.id === resource.owner_identity_id)?.display_name} · Role: {identities.find(identity => identity.id === resource.owner_identity_id)?.role ?? "Chưa gán"} · Path parameter: {resource.path_parameter}</span><ResourceInspection key={`${projectId}:${resource.id}:${resource.owner_identity_id}:${resource.path_parameter}:${resourceInspectionRevision}`} projectId={projectId} resourceId={resource.id} /></li>)}</ul> : <p>Chưa cấu hình tài nguyên và owner.</p>}<form className="compact-form divided" onSubmit={(event) => { event.preventDefault(); const request = selectedType ? api.updateResourceType(selectedType.id, typeValue) : api.createResourceType(projectId, typeValue); request.then(async () => { await onChanged(); resetType(); onNotice({ kind: "success", text: `Đã ${selectedType ? "cập nhật" : "lưu"} mapping resource; thay đổi áp dụng run mới.` }); }).catch((error: unknown) => onNotice(errorNotice(error))); }}><label>Chọn loại resource<select value={typeId} onChange={(event) => setTypeId(event.target.value)}><option value="">Tạo loại mới</option>{types.map((type) => <option key={type.id} value={type.id}>{type.name}</option>)}</select></label><label>Loại tài nguyên<input value={typeName} onChange={(event) => setTypeName(event.target.value)} required /></label><label>Resource ID pointer<input value={idPointer} onChange={(event) => setIdPointer(event.target.value)} required /></label><label>Restricted pointers, phân cách dấu phẩy<input value={restricted} onChange={(event) => setRestricted(event.target.value)} required /></label><div className="actions"><button>{selectedType ? "Lưu mapping" : "Tạo loại resource"}</button>{selectedType && <button type="button" className="quiet" onClick={resetType}>Tạo loại khác</button>}</div></form>{selectedType && <form className="compact-form" onSubmit={(event) => { event.preventDefault(); const value = { ...(externalId ? { external_id: externalId } : {}), owner_identity_id: Number(ownerId), path_parameter: parameter }; const request = selectedResource ? api.updateResource(selectedResource.id, value) : api.createResource(selectedType.id, { ...value, external_id: externalId }); request.then(async () => { await onChanged(); resetResource(); onNotice({ kind: "success", text: `Đã ${selectedResource ? "cập nhật" : "lưu"} resource; thay đổi áp dụng run mới.` }); }).catch((error: unknown) => onNotice(errorNotice(error))); }}><label>Resource đang sửa<select value={resourceId} onChange={(event) => setResourceId(event.target.value)}><option value="">Tạo resource mới</option>{resources.filter((resource) => resource.resource_type_id === selectedType.id).map((resource) => <option key={resource.id} value={resource.id}>{resource.resource_alias || `resource-${resource.id}`}</option>)}</select></label><label>{selectedResource ? "Resource ID thay thế (để trống để giữ ID cũ)" : "Resource ID"}<input value={externalId} onChange={(event) => setExternalId(event.target.value)} required={!selectedResource} autoComplete="off" /></label><label>Owner<select value={ownerId} onChange={(event) => setOwnerId(event.target.value)} required><option value="">Chọn danh tính</option>{identities.map((identity) => <option key={identity.id} value={identity.id}>{identity.display_name}</option>)}</select></label><label>Path parameter<input value={parameter} onChange={(event) => setParameter(event.target.value)} required /></label><div className="actions"><button>{selectedResource ? "Lưu resource" : "Tạo resource"}</button>{selectedResource && <button type="button" className="quiet" onClick={resetResource}>Tạo resource khác</button>}</div></form>}</div>;
}


export function CaseMatrix({ cases, identities = [], operations = [] }: { cases: MatrixCase[]; identities?: Identity[]; operations?: Operation[] }) {
  const [actor, setActor] = useState(""); const [decision, setDecision] = useState("");
  const visible = cases.filter(row => (!actor || String(row.actor_identity_id) === actor) && (!decision || (row.expected_decision ?? row.resolved_decision ?? "UNKNOWN") === decision));
  const alias = (id: number) => identities.find(item => item.id === id)?.display_name;
  if (!cases.length) return <p>Chưa có case ma trận trong phạm vi đã chọn. NOT_RUN — chưa có kết quả thực nghiệm.</p>;
  return <section aria-label="Ma trận phân quyền"><h4>Ma trận tài khoản × API × tài nguyên</h4><p>{visible.length}/{cases.length} cases · Quyền dự kiến từ policy; NOT_RUN — preview chưa phải kết quả thực nghiệm. Role admin không tự động có quyền.</p>
    <div className="compact-form"><label>Lọc tài khoản<select value={actor} onChange={e => setActor(e.target.value)}><option value="">Tất cả tài khoản</option>{[...new Map(cases.map(row => [row.actor_identity_id, row])).values()].map(row => <option key={row.actor_identity_id} value={row.actor_identity_id}>{row.actor_alias ?? `identity-${row.actor_identity_id}`}</option>)}</select></label><label>Lọc quyền dự kiến<select value={decision} onChange={e => setDecision(e.target.value)}><option value="">Tất cả quyền</option>{["ALLOW", "DENY", "UNKNOWN"].map(value => <option key={value}>{value}</option>)}</select></label></div>
    <div className="case-table"><table><caption>Case ID ổn định để nối kết quả Analyze và Compare</caption><thead><tr><th>Case ID / API</th><th>Tài khoản / role</th><th>Tài nguyên / owner</th><th>Quan hệ</th><th>Quyền dự kiến</th><th>Policy / căn cứ</th></tr></thead><tbody>{visible.map(row => <tr key={row.case_key}><td><code>{row.case_key}</code><br />{row.method ?? "GET"} {row.path_template ?? operations.find(op => op.id === row.operation_id)?.path ?? `operation-${row.operation_id}`}</td><td>{row.actor_alias ?? `identity-${row.actor_identity_id}`} {alias(row.actor_identity_id)}<br />Role: {row.actor_role ?? identities.find(i => i.id === row.actor_identity_id)?.role ?? "Chưa gán"}</td><td>{row.resource_alias ?? `resource-${row.resource_id}`}<br />Owner: {row.owner_alias ?? `identity-${row.owner_identity_id}`} {alias(row.owner_identity_id)}<br />Role: {row.owner_role ?? identities.find(i => i.id === row.owner_identity_id)?.role ?? "Chưa gán"}</td><td>{row.ownership_category ?? row.control_type}</td><td><strong>{row.expected_decision ?? row.resolved_decision ?? "UNKNOWN"}</strong></td><td>Policy {row.policy_id ?? "—"} / v{row.policy_version ?? "—"}<br />{row.policy_status}{row.warnings.map(warning => <p key={warning}>{warning}</p>)}</td></tr>)}</tbody></table></div>{!visible.length && <p>Không có case khớp bộ lọc.</p>}</section>;
}

function MatrixPanel({ projectId, operations, types, resources, identities, policies, mappings, matrix, onMatrix, onChanged, onNotice }: { projectId: number; operations: Operation[]; types: ResourceType[]; resources: Resource[]; identities: Identity[]; policies: Policy[]; mappings: OperationResourceMapping[]; matrix: MatrixCase[]; onMatrix: (matrix: MatrixCase[]) => void; onChanged: () => Promise<void>; onNotice: (notice: Notice) => void }) {
  const [operationId, setOperationId] = useState(""); const [typeId, setTypeId] = useState(""); const [resourceId, setResourceId] = useState(""); const [policyId, setPolicyId] = useState(""); const selectedPolicy = policies.find((item) => item.id === Number(policyId)) ?? null;
  const selectedMapping = mappings.find((mapping) => mapping.operation_id === Number(operationId) && mapping.resource_type_id === Number(typeId));
  async function addMapping() { await api.createOperationResourceMapping(projectId, { operation_id: Number(operationId), resource_type_id: Number(typeId), selected: true }); await onChanged(); onNotice({ kind: "success", text: "Đã thêm mapping GET vào phạm vi batch." }); }
  async function toggleMapping() { if (!selectedMapping) return; await api.updateOperationResourceMapping(selectedMapping.id, !selectedMapping.selected); await onChanged(); onNotice({ kind: "success", text: `Đã ${selectedMapping.selected ? "tắt" : "bật"} mapping batch.` }); }
  const [subjectKind, setSubjectKind] = useState("identity"); const [policyResource, setPolicyResource] = useState("");
  const [decision, setDecision] = useState<Policy["decision"]>("ALLOW"); const [subject, setSubject] = useState("");
  const selectedType = types.find((item) => item.id === Number(typeId));
  useEffect(() => { if (!operationId && operations.find((item) => item.selected)) setOperationId(String(operations.find((item) => item.selected)?.id)); }, [operations, operationId]);
  useEffect(() => { if (!typeId && types[0]) setTypeId(String(types[0].id)); }, [types, typeId]);
  useEffect(() => { if (!resourceId && resources.find((item) => item.resource_type_id === Number(typeId))) setResourceId(String(resources.find((item) => item.resource_type_id === Number(typeId))?.id)); }, [resources, typeId, resourceId]);
  useEffect(() => { if (selectedPolicy) { setDecision(selectedPolicy.decision); setSubjectKind(selectedPolicy.role !== null ? "role" : "identity"); setSubject(selectedPolicy.role ?? String(selectedPolicy.identity_id ?? "")); setPolicyResource(String(selectedPolicy.resource_id ?? "")); setOperationId(String(selectedPolicy.operation_id)); setTypeId(String(selectedPolicy.resource_type_id)); } }, [selectedPolicy]);
  function resetPolicy() { setPolicyId(""); setDecision("ALLOW"); setSubject(""); setSubjectKind("identity"); setPolicyResource(""); }
  const previewGeneration = useRef(0);
  useEffect(() => { previewGeneration.current += 1; setMatrixPending(false); onMatrix([]); return () => { previewGeneration.current += 1; }; }, [projectId, operationId, resourceId]);
  const [matrixPending, setMatrixPending] = useState(false);
  const canMatrix = Boolean(operationId && resourceId);
  async function previewMatrix() {
    if (matrixPending) return;
    const generation = ++previewGeneration.current;
    setMatrixPending(true); onMatrix([]);
    try { const rows = await api.matrix(projectId, Number(operationId), Number(resourceId)); if (generation === previewGeneration.current) { onMatrix(rows); onNotice({ kind: "success", text: `Đã lập ma trận: ${rows.length} cases.` }); } }
    catch (error) { if (generation === previewGeneration.current) onNotice({ kind: "error", text: errorNotice(error).text || "Không thể lập ma trận." }); }
    finally { if (generation === previewGeneration.current) setMatrixPending(false); }
  }
  const canMap = Boolean(operationId && typeId);
  return <div className="panel-content"><div className="compact-form"><label>Batch operation-resource mapping<select value={operationId} onChange={(event) => setOperationId(event.target.value)}><option value="">Chọn operation GET</option>{operations.filter((operation) => operation.selected).map((operation) => <option key={operation.id} value={operation.id}>{operation.method} {operation.path}</option>)}</select></label><label>Loại resource cho batch<select value={typeId} onChange={(event) => setTypeId(event.target.value)}><option value="">Chọn loại resource</option>{types.map((type) => <option key={type.id} value={type.id}>{type.name}</option>)}</select></label><div className="actions">{selectedMapping ? <button disabled={!canMap} onClick={() => void toggleMapping()}>{selectedMapping.selected ? "Tắt mapping batch" : "Bật mapping batch"}</button> : <button disabled={!canMap} onClick={() => void addMapping()}>Thêm mapping batch</button>}</div></div>{mappings.length > 0 && <ul className="matrix-list">{mappings.map((mapping) => <li key={mapping.id}><b>{mapping.selected ? "BATCH ENABLED" : "BATCH DISABLED"}</b><span>{operations.find((operation) => operation.id === mapping.operation_id)?.path ?? `Operation #${mapping.operation_id}`}</span><span>{types.find((type) => type.id === mapping.resource_type_id)?.name ?? `Type #${mapping.resource_type_id}`}</span></li>)}</ul>}<div className="divider" /><form className="compact-form" onSubmit={(event) => { event.preventDefault(); const value = { operation_id: Number(operationId), resource_type_id: Number(typeId), decision, identity_id: subjectKind === "identity" ? Number(subject) : null, role: subjectKind === "role" ? subject : null, resource_id: policyResource ? Number(policyResource) : null }; const request = selectedPolicy ? api.updatePolicy(selectedPolicy.id, value) : api.createPolicy(projectId, value); request.then(async () => { await onChanged(); resetPolicy(); onNotice({ kind: "success", text: `Đã ${selectedPolicy ? "cập nhật" : "lưu"} policy; ma trận cần sinh lại và chỉ run mới dùng policy này.` }); }).catch((error: unknown) => onNotice(errorNotice(error))); }}><label>Policy đang sửa<select value={policyId} onChange={(event) => setPolicyId(event.target.value)}><option value="">Tạo policy mới</option>{policies.map((policy) => <option key={policy.id} value={policy.id}>#{policy.id} v{policy.version} · {policy.decision}</option>)}</select></label><label>Operation<select value={operationId} onChange={(event) => setOperationId(event.target.value)} required><option value="">Chọn operation</option>{operations.filter((operation) => operation.selected).map((operation) => <option key={operation.id} value={operation.id}>{operation.method} {operation.path}</option>)}</select></label><label>Loại resource<select value={typeId} onChange={(event) => { setTypeId(event.target.value); setResourceId(""); setPolicyResource(""); }} required><option value="">Chọn loại</option>{types.map((type) => <option key={type.id} value={type.id}>{type.name}</option>)}</select></label><label>Chủ thể policy<select value={subjectKind} onChange={(event) => { setSubjectKind(event.target.value); setSubject(""); }}><option value="identity">Danh tính</option><option value="role">Role</option></select></label>{subjectKind === "identity" ? <label>Danh tính áp dụng<select value={subject} onChange={(event) => setSubject(event.target.value)} required><option value="">Chọn danh tính</option>{identities.map((identity) => <option key={identity.id} value={identity.id}>{identity.display_name}</option>)}</select></label> : <label>Role áp dụng<input value={subject} onChange={(event) => setSubject(event.target.value)} required list="policy-roles" /><datalist id="policy-roles">{[...new Set(identities.map((identity) => identity.role).filter(Boolean))].map((role) => <option key={role} value={role!} />)}</datalist></label>}<label>Phạm vi resource<select value={policyResource} onChange={(event) => setPolicyResource(event.target.value)}><option value="">Toàn bộ loại resource</option>{resources.filter((resource) => resource.resource_type_id === Number(typeId)).map((resource) => <option key={resource.id} value={resource.id}>{resource.resource_alias || `resource-${resource.id}`}</option>)}</select></label><label>Quyết định<select value={decision} onChange={(event) => setDecision(event.target.value as Policy["decision"])}><option>ALLOW</option><option>DENY</option><option>UNKNOWN</option></select></label><div className="actions"><button>{selectedPolicy ? "Lưu policy" : "Tạo policy"}</button>{selectedPolicy && <button type="button" className="quiet" onClick={resetPolicy}>Tạo policy khác</button>}</div></form><div className="divider" /><label>Resource cho ma trận<select value={resourceId} onChange={(event) => setResourceId(event.target.value)} required><option value="">Chọn resource</option>{resources.filter((resource) => resource.resource_type_id === selectedType?.id).map((resource) => <option key={resource.id} value={resource.id}>{resource.resource_alias || `resource-${resource.id}`}</option>)}</select></label><button disabled={!canMatrix || matrixPending} onClick={() => void previewMatrix()}>{matrixPending ? "Đang lập ma trận…" : "Lập ma trận"}</button>{matrixPending && <p role="status">Đang đọc policy và các case trong phạm vi đã chọn.</p>}{!matrixPending && <CaseMatrix cases={matrix} identities={identities} operations={operations} />}</div>;
}

function ExternalLabPanel({ projectId, jobs, onJobs, onNotice }: { projectId: number; jobs: ExternalLabJob[]; onJobs: (jobs: ExternalLabJob[]) => void; onNotice: (notice: Notice) => void }) {
  const lock = useRef(false); const [pending, setPending] = useState(false);
  async function queue() { if (lock.current) return; lock.current = true; setPending(true); try { const job = await api.createReadOnlyExternalLabJob(projectId); onJobs([job, ...jobs]); onNotice({ kind: "info", text: "Đã xếp read-only external lab job cho bridge của operator." }); } catch (error) { onNotice(errorNotice(error)); } finally { lock.current = false; setPending(false); } }
  const active = jobs.some((job) => ["QUEUED", "DISPATCHING", "SUBMITTED", "RUNNING", "CANCEL_REQUESTED"].includes(job.status));
  useEffect(() => {
    if (!active) return;
    let current = true; let attempts = 0; let timer: number;
    async function poll() { try { const next = await api.externalLabJobs(projectId); if (current) onJobs(next); } catch (error) { if (current) onNotice(errorNotice(error)); } if (current && ++attempts < 300) timer = window.setTimeout(poll, 2000); }
    timer = window.setTimeout(poll, 2000);
    return () => { current = false; window.clearTimeout(timer); };
  }, [active, projectId, onJobs]);
  return <div className="panel-content"><section className="finding-groups"><h4>Operator-side bridge only</h4><p>Chỉ queue workflow VAmPI local read-only cố định. Không có command, target, token, log hay artifact path trong giao diện.</p><p>Nếu bridge chưa được operator cấu hình, yêu cầu queue sẽ bị từ chối an toàn và không có local fallback.</p><p>BFLA disposable, ZAP runtime và Docker vẫn là operator-only và không thể chạy tại đây.</p></section><button disabled={active || pending} onClick={() => void queue()}>Queue read-only verification</button>{jobs.length > 0 && <ul className="run-list">{jobs.map((job) => <li key={job.public_id}><div><b>Lab job {job.public_id.slice(0, 8)}</b><span className={`status ${job.status.toLowerCase()}`}>{job.status}</span></div><p className="run-summary">{job.failure_code ? `failure ${job.failure_code}` : "No raw output is retained."}{job.artifact_manifest_sha256 ? " · redacted manifest verified" : ""}</p>{Object.keys(job.result_summary).length > 0 && <p className="run-summary">{typeof job.result_summary.case_count === "number" ? `cases ${job.result_summary.case_count}` : "Summary received."}</p>}{["QUEUED", "DISPATCHING", "SUBMITTED", "RUNNING"].includes(job.status) && <button className="quiet" onClick={() => api.cancelExternalLabJob(job.public_id).then(() => api.externalLabJobs(projectId).then((next) => { onJobs(next); onNotice({ kind: "info", text: `Đã gửi yêu cầu dừng Lab job ${job.public_id.slice(0, 8)}.` }); })).catch((error: unknown) => onNotice(errorNotice(error)))}>Dừng</button>}</li>)}</ul>}</div>;
}

function RunPanel({ projectId, targets, mappings, runs, results, findings, onRuns, onResults, onFindings, onNotice }: { projectId: number; targets: Target[]; mappings: OperationResourceMapping[]; runs: Run[]; results: Result[]; findings: Finding[]; onRuns: (runs: Run[]) => void; onResults: (results: Result[]) => void; onFindings: (findings: Finding[]) => void; onNotice: (notice: Notice) => void }) {
  const selectedRun = useRef<number | null>(null); const [viewingRun, setViewingRun] = useState<number | null>(null); const actionLock = useRef(false); const [pending, setPending] = useState(false);
  async function guarded(work: () => Promise<void>) { if (actionLock.current) return; actionLock.current = true; setPending(true); try { await work(); } catch (error) { onNotice(errorNotice(error)); } finally { actionLock.current = false; setPending(false); } }
  const [targetId, setTargetId] = useState(""); const [plan, setPlan] = useState<BatchMatrix | null>(null); const latest = runs[0];
  useEffect(() => { if (!targetId && targets[0]) setTargetId(String(targets[0].id)); }, [targets, targetId]);
  useEffect(() => { let current = true; setPlan(null); if (targetId) api.batchMatrix(projectId, Number(targetId)).then((next) => { if (current) setPlan(next); }).catch((error: unknown) => { if (current) onNotice(errorNotice(error)); }); return () => { current = false; }; }, [projectId, targetId, mappings]);
  useEffect(() => { if (!latest || ["COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED"].includes(latest.status)) return; let current = true; let attempts = 0; let timer: number; async function poll() { if (!current) return; try { const next = await api.runs(projectId); if (current) onRuns(next); } catch (error) { if (current) onNotice(errorNotice(error)); } if (current && ++attempts < 300) timer = window.setTimeout(poll, 2000); } timer = window.setTimeout(poll, 2000); return () => { current = false; window.clearTimeout(timer); }; }, [latest?.id, latest?.status, projectId, onRuns]);
  const viewGeneration = useRef(0);
  useEffect(() => { return () => { ++viewGeneration.current; selectedRun.current = null; }; }, [projectId]);
  async function viewRun(runId: number) {
    const generation = ++viewGeneration.current;
    selectedRun.current = runId; setViewingRun(runId); onResults([]); onFindings([]);
    try {
      const [nextResults, nextFindings] = await Promise.all([api.results(runId), api.findings(projectId, runId)]);
      if (generation === viewGeneration.current && selectedRun.current === runId) { onResults(nextResults); onFindings(nextFindings); }
    } catch (error) { if (generation === viewGeneration.current) onNotice(errorNotice(error)); }
  }
  const ready = Boolean(targetId && plan?.within_request_limit && plan.concrete_target_count > 0);
  return <div className="panel-content"><div className="compact-form"><label>API đích<select value={targetId} onChange={(event) => setTargetId(event.target.value)}><option value="">Chọn API</option>{targets.map((target) => <option key={target.id} value={target.id}>{target.base_url}</option>)}</select></label></div>{plan ? <section className="finding-groups"><h4>Batch preview</h4><p>{plan.identity_count} danh tính · {plan.concrete_target_count} resource-operation · {plan.actor_case_count} actor cases</p><p>{plan.identity_verifications} xác minh + {plan.owner_baselines} owner baseline + {plan.actor_case_count} actor request = <b>{plan.planned_attempts}/{plan.request_limit}</b> planned attempts.</p>{plan.targets.map((item) => <p key={`${item.operation_id}-${item.resource_type_id}`}><code>GET {item.operation_path}</code> · {item.resource_type_name}: {item.resource_count} resource, {item.actor_case_count} case</p>)}<CaseMatrix cases={plan.cases ?? []} /></section> : <p>Chọn API đích và bật mapping GET để xem batch preview.</p>}<button disabled={!ready || pending} onClick={() => void guarded(async () => { await api.createBatchRun(projectId, Number(targetId)).then((run) => { onRuns([run, ...runs]); onNotice({ kind: "info", text: "Đã xếp batch run. Worker chỉ dùng mapping và resource đã snapshot." }); }).catch((error: unknown) => onNotice(errorNotice(error))); })}>Queue all selected GET mappings</button>{runs.length > 0 && <ul className="run-list">{runs.map((run) => <li key={run.id}><div><b>Run #{run.id}</b><span className={`status ${run.status.toLowerCase()}`}>{run.status}</span></div><div className="actions"><button className="quiet" onClick={() => void viewRun(run.id)}>Xem kết quả</button>{["QUEUED", "RUNNING"].includes(run.status) && <button disabled={pending} className="quiet" onClick={() => void guarded(async () => { await api.cancelRun(run.id).then(() => api.runs(projectId).then((next) => { onRuns(next); onNotice({ kind: "info", text: `Đã gửi yêu cầu dừng Run #${run.id}.` }); })).catch((error: unknown) => onNotice(errorNotice(error))); })}>Dừng</button>}</div>{run.execution_summary && <p className="run-summary">planned {run.execution_summary.planned_attempts} · transport {run.execution_summary.transport_attempts} · responses {run.execution_summary.completed_responses} · scope {run.execution_summary.scope_blocked} · errors {run.execution_summary.transport_errors} · cancelled {run.execution_summary.cancelled_cases}</p>}</li>)}</ul>}{viewingRun !== null && <p role="status">Kết quả run #{viewingRun} · {results.length} cases · {findings.length} nhóm findings</p>}{results.length > 0 && <table><thead><tr><th>Case</th><th>Execution</th><th>Kết luận</th><th>HTTP</th><th>Bằng chứng</th></tr></thead><tbody>{results.map((result) => <tr id={`analysis-${viewingRun}-${result.case_key}`} key={result.case_key}><td>{result.case_key}</td><td>{result.execution_status}</td><td>{result.authorization_conclusion}</td><td>{result.http_status ?? "—"}</td><td><Evidence result={result} /></td></tr>)}</tbody></table>}{findings.length > 0 && <section className="finding-groups" aria-labelledby="finding-groups-title"><h4 id="finding-groups-title">Nhóm phát hiện đã xác nhận</h4><p>Nhóm theo policy và mapping ổn định; không hiển thị danh tính, resource ID hoặc dữ liệu nhạy cảm.</p><ul>{findings.map((finding) => <li key={finding.id}><div><b>{finding.conclusion}</b><code>{finding.operation.method} {finding.operation.path}</code><span>Policy #{finding.policy.id} · phiên bản {finding.policy.version}</span></div><strong>{finding.reproduction_count} lần tái hiện</strong>{finding.reproductions?.filter((link) => link.run_id === viewingRun && link.case_key).map((link) => <a key={link.run_result_id} href={`#analysis-${link.run_id}-${link.case_key}`}>Run #{link.run_id} · {link.case_key}</a>)}{!finding.reproductions?.length && <span>UNAVAILABLE — chưa có liên kết case</span>}</li>)}</ul></section>}</div>;
}

export function Evidence({ result }: { result: Result }) {
  const evidence = result.response_metadata.evidence;
  if (!evidence) return <span>UNAVAILABLE — chưa có evidence hợp lệ · {result.reason_codes.join(", ") || "chưa có reason codes"}</span>;
  const explanations: Record<string, string> = {
    CONFIRMED_VIOLATION: "CONFIRMED — policy DENY và bằng chứng protected fields khớp owner hợp lệ.",
    POLICY_CONSISTENT_CASE: "POLICY-CONSISTENT — phù hợp policy; ALLOW sharing không phải vi phạm.",
    INVALID_TEST: "INVALID_TEST — danh tính hoặc owner baseline không hợp lệ.",
    BLOCKED_POLICY_CONFLICT: "BLOCKED — policy xung đột, chưa thể kết luận quyền.",
    INSUFFICIENT_EVIDENCE: "INSUFFICIENT_EVIDENCE — chưa đủ căn cứ xác nhận vi phạm.",
    NOT_EVALUATED: "NOT EVALUATED — chưa có quan sát đủ để đánh giá.",
  };
  return <details><summary>Run #{evidence.run_id} · {evidence.case_key}</summary><dl>
    <dt>Phân tích</dt><dd>{explanations[result.authorization_conclusion] ?? "UNAVAILABLE"} HTTP chỉ là quan sát transport.</dd>
    <dt>Actor / owner tại thời điểm chạy</dt><dd>identity-{evidence.actor_identity_id} / identity-{evidence.owner_identity_id} · role {evidence.actor_role ?? "UNAVAILABLE"} / {evidence.owner_role ?? "UNAVAILABLE"} · {evidence.ownership ?? "UNAVAILABLE"}</dd>
    <dt>Protected fields (không chứa values)</dt><dd>{evidence.protected_fields?.length ? evidence.protected_fields.map((field) => <p key={field.alias}>{field.alias}: owner {String(field.owner_present)} ({field.owner_type ?? "unavailable"}) · actor {String(field.actor_present)} ({field.actor_type ?? "unavailable"}) · khớp {String(field.matches_owner)}</p>) : "UNAVAILABLE — metadata lịch sử không có kiểm tra từng field"}</dd>
    <dt>Artifact</dt><dd>UNAVAILABLE — không có artifact đính kèm</dd>
    <dt>Owner control hợp lệ</dt><dd>{String(evidence.owner_control_valid)}</dd>
    <dt>Kiểm tra baseline</dt><dd>principal {String(evidence.owner_principal_matches ?? "UNAVAILABLE")} · resource {String(evidence.owner_resource_matches ?? "UNAVAILABLE")} · protected evidence {String(evidence.owner_restricted_evidence_valid ?? "UNAVAILABLE")} · truncated {String(evidence.owner_body_truncated ?? "UNAVAILABLE")} · parse error {String(evidence.owner_json_parse_error ?? "UNAVAILABLE")}</dd>
    <dt>Actor principal</dt><dd>{String(evidence.actor_principal_matches ?? "UNAVAILABLE")}</dd>
    <dt>Owner response</dt><dd>{evidence.owner_execution_status} · HTTP {evidence.owner_http_status ?? "—"}</dd>
    <dt>Policy</dt><dd>#{evidence.policy_id ?? "—"} v{evidence.policy_version ?? "—"} · {evidence.policy_decision ?? "—"} · {evidence.policy_resolution}</dd>
    <dt>Actor đúng resource / restricted fields khớp owner</dt><dd>{String(evidence.actor_resource_matches)} / {String(evidence.restricted_fields_match_owner)}</dd>
    <dt>Reason codes</dt><dd>{result.reason_codes.join(", ") || "—"}</dd>
  </dl></details>;
}


export function ComparePanel({ projectId, runs }: { projectId: number; runs: Run[] }) {
  const [runId, setRunId] = useState<number | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    let current = true;
    setComparison(null); setError(""); setLoading(false);
    if (runId === null || !runs.some(run => run.id === runId && run.project_id === projectId)) return;
    setLoading(true);
    api.comparison(projectId, runId).then(data => {
      if (current) {
        if (data.run_id === runId && data.cases.every(row => row.run_id === runId)) setComparison(data);
        else setError("Nguồn comparison không khớp run: UNAVAILABLE");
      }
    }).catch(() => { if (current) setError("Không đọc được comparison: UNAVAILABLE"); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [projectId, runId, runs]);
  return <section id="comparison" className="station"><BundleComparison key={projectId} projectId={projectId} /><h3>So sánh phương pháp theo case</h3>
    <p>Nguồn T18 là kết quả web đã lưu. Manual/ZAP chưa có nguồn được xác minh cho run/case này: NOT_RUN. Artifacts CLI lịch sử không được tự ghép. BFLA là thực nghiệm riêng.</p>
    <label>Lượt chạy để so sánh<select value={runId ?? ""} onChange={event => setRunId(event.target.value ? Number(event.target.value) : null)}><option value="">Chọn run đã lưu</option>{runs.filter(run => run.project_id === projectId).map(run => <option key={run.id} value={run.id}>Đối chiếu #{run.id} · {run.status}</option>)}</select></label>
    {loading && <p>Đang đọc kết quả đã lưu…</p>}{error && <p role="alert">{error}</p>}
    {!runId && <p>Chọn run để xem case thực tế; ma trận preview không phải kết quả thực thi.</p>}
    {comparison && !comparison.cases.length && <p>NOT_RUN — chưa có observation được lưu; provenance UNAVAILABLE.</p>}
    {comparison && <div className="case-table"><table><caption>Run #{comparison.run_id} · Không có ground truth để tính TP/FP/FN</caption><thead><tr><th>Run / case</th><th>Phương pháp</th><th>Policy lịch sử</th><th>Observation / conclusion</th><th>Provenance / artifact</th><th>Timing</th></tr></thead><tbody>{comparison.cases.flatMap((row, index) => row.methods.map(method => {
      const observation = method.observation;
      const candidate = observation?.response_metadata.evidence;
      const evidence = candidate?.run_id === row.run_id && candidate.case_key === row.case_key ? candidate : null;
      return <tr key={`${index}:${method.method}`}><td>Run #{row.run_id}<br /><code>{row.case_key ?? "UNAVAILABLE"}</code></td><td>{method.method === "ZAP" ? "OWASP ZAP" : method.method}</td><td>{evidence ? `Policy ${evidence.policy_id ?? "UNAVAILABLE"} / v${evidence.policy_version ?? "UNAVAILABLE"} · ${evidence.policy_decision ?? "UNAVAILABLE"} · ${evidence.policy_resolution}` : "UNAVAILABLE"}</td><td>{method.execution_status}<br />{observation ? <>HTTP {observation.http_status ?? "UNAVAILABLE"}<br />{observation.authorization_conclusion}</> : "UNAVAILABLE"}</td><td>{method.provenance}<br />Artifact: {method.artifact}{observation && !evidence && <p>Evidence metadata: UNAVAILABLE</p>}</td><td>{method.timing_status}</td></tr>;
    }))}</tbody></table></div>}
  </section>;
}


export function BundleComparison({ projectId }: { projectId: number }) {
  const [inventory, setInventory] = useState<{ project: number; digests: string[] } | null>(null);
  const [selected, setSelected] = useState<{ project: number; digest: string } | null>(null);
  const [loaded, setLoaded] = useState<{ project: number; bundle: ComparisonBundle } | null>(null);
  const [failure, setFailure] = useState<{ project: number; text: string } | null>(null);
  const [pending, setPending] = useState(false);
  useEffect(() => {
    let current = true;
    setInventory(null); setSelected(null); setLoaded(null); setFailure(null);
    async function read() {
      const digests: string[] = [];
      for (let offset = 0; ; offset += 100) {
        const page = await api.comparisonBundles(projectId, offset);
        if (!current) return;
        digests.push(...page.map(row => row.content_digest));
        if (page.length < 100) break;
      }
      if (current) setInventory({ project: projectId, digests });
    }
    read().catch(() => { if (current) setFailure({ project: projectId, text: "Không đọc được danh sách bundle: UNKNOWN" }); });
    return () => { current = false; };
  }, [projectId]);
  useEffect(() => {
    let current = true;
    setLoaded(null); setPending(false);
    if (!selected || selected.project !== projectId) return;
    setFailure(null); setPending(true);
    api.comparisonBundle(projectId, selected.digest).then(bundle => {
      if (!current) return;
      if (bundle.content_digest !== selected.digest || ![1, 2].includes(bundle.schema_version) || bundle.attestation_status !== "UNVERIFIED") throw new Error("Mismatch");
      setLoaded({ project: projectId, bundle });
    }).catch(() => { if (current) setFailure({ project: projectId, text: "Không đọc được bundle hợp lệ: UNKNOWN" }); })
      .finally(() => { if (current) setPending(false); });
    return () => { current = false; };
  }, [projectId, selected]);
  const bundle = loaded?.project === projectId && selected?.project === projectId && loaded.bundle.content_digest === selected.digest ? loaded.bundle : null;
  const digests = inventory?.project === projectId ? inventory.digests : null;
  const methods: BundleMethod[] = ["MANUAL", "T18", "ZAP"];
  function cell(caseId: string, method: BundleMethod) {
    const execution = bundle?.selections.find(item => item.method === method)?.execution_id;
    const candidates = bundle!.observations.filter(item => item.method === method && item.case_revision.case_id === caseId);
    const observation = candidates.find(item => item.execution_id === execution && item.manifest_digest === bundle!.manifest.content_digest && item.manifest_version === bundle!.manifest.version);
    const reason = !execution ? "NO_EXECUTION_SELECTION" : candidates.length ? "EXECUTION_MISMATCH" : "NO_OBSERVATION";
    const provenance = observation?.provenance;
    const artifact = provenance && bundle!.artifacts.find(item => item.artifact_ref === provenance.artifact_ref && item.artifact_hash === provenance.artifact_hash);
    const conclusion = observation?.execution_status === "COMPLETED" && provenance && ["ACCESS_ALLOWED", "ACCESS_DENIED"].includes(observation.signal) ? observation.signal : "UNKNOWN";
    return <td key={method}><strong>{observation?.execution_status ?? "NOT_RUN"}</strong><p>{observation ? `Signal: ${observation.signal} · Conclusion: ${conclusion}` : `Reason: ${reason}`}</p><code>{execution ?? "UNKNOWN"}</code><p className="comparison-badge">{provenance ? "SOURCE_RECORDED" : "UNVERIFIED"} · UNVERIFIED</p>{provenance && <p>{provenance.producer_kind} / {provenance.producer_version}<br />{provenance.operator_alias ?? "UNKNOWN"}<br /><code>{provenance.artifact_ref}</code><br /><code>{provenance.artifact_hash}</code><br />{artifact?.integrity_status ?? "UNKNOWN"}</p>}<p>TIMING_NOT_AVAILABLE — bundle không có timing.</p></td>;
  }
  return <div className="bundle-comparison"><h3>Bundle / cohort đã lưu</h3><p>Độc lập với run hiện tại. Hash kiểm tính nhất quán, không phải attestation. Không có ground truth để tính TP/FP/FN.</p>
    <label>Bundle để so sánh<select value={selected?.project === projectId ? selected.digest : ""} onChange={event => { setLoaded(null); setSelected(event.target.value ? { project: projectId, digest: event.target.value } : null); }}><option value="">Chọn bundle</option>{digests?.map(digest => <option key={digest} value={digest}>{digest}</option>)}</select></label>
    {failure?.project === projectId && <p role="alert">{failure.text}</p>}{pending && <p role="status">Đang đọc bundle…</p>}{!digests && !failure && <p>Đang đọc danh sách bundle…</p>}{digests?.length === 0 && <p>Chưa có bundle được lưu; coverage UNKNOWN.</p>}
    {bundle && <><p>Schema {bundle.schema_version} · UNVERIFIED · Cohort <code>{bundle.manifest.version}</code></p><p>Coverage: số observation COMPLETED trong execution được chọn / số case cohort; không phải coverage đã xác minh.</p>{methods.map(method => { const execution = bundle.selections.find(item => item.method === method)?.execution_id; const count = bundle.observations.filter(item => item.method === method && item.execution_id === execution && item.manifest_digest === bundle.manifest.content_digest && item.execution_status === "COMPLETED").length; return <p key={method}>{method}: {execution && bundle.manifest.cases.length ? `${count}/${bundle.manifest.cases.length}` : "UNKNOWN — thiếu execution hoặc cohort rỗng"}</p>; })}
    {!bundle.manifest.cases.length && <p>Cohort rỗng; không tạo case giả.</p>}<div className="case-table"><table><caption>Case × Manual / T18 / OWASP ZAP</caption><thead><tr><th>Case / policy</th><th>Manual</th><th>T18</th><th>OWASP ZAP</th></tr></thead><tbody>{bundle.manifest.cases.map(row => <tr key={row.case_id}><th scope="row"><code>{row.case_id}</code><p>{row.method} {row.operation_template}</p>{row.actor_role} / {row.owner_category}<p>{row.policy_id} / {row.policy_version} · {row.expected_decision}</p></th>{methods.map(method => cell(row.case_id, method))}</tr>)}</tbody></table></div>
    <h4>Nguồn lịch sử chưa liên kết</h4>{bundle.legacy.length ? bundle.legacy.map(row => <p key={`${row.method}:${row.source_alias}`}>{row.method} · {row.source_alias} · UNLINKED · UNKNOWN · UNVERIFIED{row.provenance && <><br />{row.provenance.producer_kind} / {row.provenance.producer_version}<br /><code>{row.provenance.artifact_ref}</code><br /><code>{row.provenance.artifact_hash}</code></>}</p>) : <p>Không có nguồn legacy trong bundle.</p>}</>}
  </div>;
}

export function DeleteProject({ project, onDeleted, onNotice }: { project: Project; onDeleted: () => void; onNotice?: (notice: Notice) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  if (!open) return <button className="quiet" onClick={() => setOpen(true)}>Xóa dự án</button>;
  return <form aria-label="Xác nhận xóa dự án" className="compact-form" onSubmit={async event => {
    event.preventDefault();
    if (lock.current || name !== project.name) return;
    lock.current = true; setPending(true); setError("");
    try { await api.deleteProject(project.id, name); onDeleted(); }
    catch (reason) {
      const text = reason instanceof Error ? reason.message : "Không thể xóa dự án.";
      if (onNotice) onNotice({ kind: "error", text });
      else setError(text);
    }
    finally { lock.current = false; setPending(false); }
  }}><p>Xóa vĩnh viễn dự án <strong>{project.name}</strong>, API đích, danh tính/token đã lưu, cấu hình, comparison và toàn bộ lịch sử/evidence trong ứng dụng. Không thể hoàn tác. Bản xuất bên ngoài và dữ liệu lab không bị xóa.</p>
    <label>Nhập đúng tên dự án để xóa<input value={name} onChange={event => setName(event.target.value)} disabled={pending} autoComplete="off" /></label>
    <div className="actions"><button disabled={pending || name !== project.name}>{pending ? "Đang xóa…" : "Xác nhận xóa vĩnh viễn"}</button><button type="button" className="quiet" disabled={pending} onClick={() => { setOpen(false); setName(""); setError(""); }}>Hủy xóa</button></div>
    {!onNotice && error && <p role="alert">{error}</p>}
  </form>;
}
