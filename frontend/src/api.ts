export type Project = { id: number; name: string; description: string };
export type Target = { id: number; project_id: number; base_url: string; timeout_seconds: number; request_limit: number; verification_path: string };
export type Identity = { id: number; display_name: string; role: string | null; principal_pointer: string | null; expected_principal: string | null; has_secret: boolean };
export type Operation = { id: number; operation_key: string; method: string; path: string; selected: boolean };
export type ResourceType = { id: number; name: string; resource_id_pointer: string; restricted_pointers: string[] };
export type Resource = { id: number; resource_type_id: number; external_id: string; owner_identity_id: number; path_parameter: string };
export type Policy = { id: number; version: number; operation_id: number; resource_type_id: number; decision: "ALLOW" | "DENY" | "UNKNOWN"; identity_id: number | null; role: string | null; resource_id: number | null };
export type MatrixCase = { case_key: string; control_type: string; actor_identity_id: number; resource_id: number; policy_status: string; warnings: string[] };
export type Run = { id: number; project_id: number; status: string; snapshot: Record<string, unknown> };
export type Result = { case_key: string; execution_status: string; authorization_conclusion: string; reason_codes: string[]; http_status: number | null; response_metadata: Record<string, unknown> };
export type Finding = { id: number; fingerprint: string; conclusion: string; operation: { method: string; path: string }; policy: { id: number; version: number }; reproduction_count: number };

export type TargetInput = Omit<Target, "id" | "project_id">;
export type IdentityInput = { display_name: string; role?: string | null; principal_pointer?: string | null; expected_principal?: string | null; bearer_token?: string };
export type ResourceTypeInput = Omit<ResourceType, "id">;
export type ResourceInput = Omit<Resource, "id" | "resource_type_id">;
export type PolicyInput = Omit<Policy, "id" | "version">;

let csrfToken: string | null = null;

function message(body: unknown): string {
  if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") return body.detail;
  return "Yêu cầu không thể hoàn tất.";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (init.method && init.method !== "GET" && csrfToken) headers.set("X-CSRF-Token", csrfToken);
  const response = await fetch(path, { ...init, headers, credentials: "same-origin" });
  if (response.status === 204) return undefined as T;
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new Error(message(body));
  return body as T;
}

function patch<T>(path: string, value: unknown) {
  return request<T>(path, { method: "PATCH", body: JSON.stringify(value) });
}

export const api = {
  async login(password: string) {
    const response = await request<{ csrf_token: string }>("/api/auth/login", { method: "POST", body: JSON.stringify({ password }) });
    csrfToken = response.csrf_token;
  },
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  projects: () => request<Project[]>("/api/projects"),
  createProject: (name: string, description: string) => request<Project>("/api/projects", { method: "POST", body: JSON.stringify({ name, description }) }),
  updateProject: (projectId: number, value: Omit<Project, "id">) => patch<Project>(`/api/projects/${projectId}`, value),
  createTarget: (projectId: number, value: TargetInput) => request<Target>(`/api/projects/${projectId}/targets`, { method: "POST", body: JSON.stringify(value) }),
  updateTarget: (targetId: number, value: TargetInput) => patch<Target>(`/api/targets/${targetId}`, value),
  targets: (projectId: number) => request<Target[]>(`/api/projects/${projectId}/targets`),
  connectionTest: (targetId: number) => request<{ execution_status: string; http_status: number | null; reason_codes: string[] }>(`/api/targets/${targetId}/connection-test`, { method: "POST" }),
  identities: (projectId: number) => request<Identity[]>(`/api/projects/${projectId}/identities`),
  createIdentity: (projectId: number, value: Required<IdentityInput>) => request<Identity>(`/api/projects/${projectId}/identities`, { method: "POST", body: JSON.stringify(value) }),
  updateIdentity: (identityId: number, value: IdentityInput) => patch<Identity>(`/api/identities/${identityId}`, value),
  verifyIdentity: (identityId: number, targetId: number) => request<{ authentication_passed: boolean; principal_matched: boolean; principal_confirmed: boolean; execution_status: string; reason_codes: string[] }>(`/api/identities/${identityId}/verify?target_id=${targetId}`, { method: "POST" }),
  importOpenApi: (projectId: number, document: Record<string, unknown>) => request<Operation[]>(`/api/projects/${projectId}/openapi`, { method: "POST", body: JSON.stringify({ document }) }),
  operations: (projectId: number) => request<Operation[]>(`/api/projects/${projectId}/operations`),
  updateOperation: (operationId: number, selected: boolean) => patch<Operation>(`/api/operations/${operationId}`, { selected }),
  createResourceType: (projectId: number, value: ResourceTypeInput) => request<ResourceType>(`/api/projects/${projectId}/resource-types`, { method: "POST", body: JSON.stringify(value) }),
  updateResourceType: (resourceTypeId: number, value: ResourceTypeInput) => patch<ResourceType>(`/api/resource-types/${resourceTypeId}`, value),
  resourceTypes: (projectId: number) => request<ResourceType[]>(`/api/projects/${projectId}/resource-types`),
  resources: (projectId: number) => request<Resource[]>(`/api/projects/${projectId}/resources`),
  createResource: (typeId: number, value: ResourceInput) => request<Resource>(`/api/resource-types/${typeId}/resources`, { method: "POST", body: JSON.stringify(value) }),
  updateResource: (resourceId: number, value: ResourceInput) => patch<Resource>(`/api/resources/${resourceId}`, value),
  policies: (projectId: number) => request<Policy[]>(`/api/projects/${projectId}/policies`),
  createPolicy: (projectId: number, value: PolicyInput) => request<Policy>(`/api/projects/${projectId}/policies`, { method: "POST", body: JSON.stringify(value) }),
  updatePolicy: (policyId: number, value: PolicyInput) => patch<Policy>(`/api/policies/${policyId}`, value),
  matrix: (projectId: number, operationId: number, resourceId: number) => request<MatrixCase[]>(`/api/projects/${projectId}/matrix?operation_id=${operationId}&resource_id=${resourceId}`),
  createRun: (projectId: number, value: { target_id: number; resource_id: number; operation_id: number }) => request<Run>(`/api/projects/${projectId}/runs`, { method: "POST", body: JSON.stringify(value) }),
  runs: (projectId: number) => request<Run[]>(`/api/projects/${projectId}/runs`),
  results: (runId: number) => request<Result[]>(`/api/runs/${runId}/results`),
  findings: (projectId: number) => request<Finding[]>(`/api/projects/${projectId}/findings`),
  cancelRun: (runId: number) => request<void>(`/api/runs/${runId}/cancel`, { method: "POST" }),
};
