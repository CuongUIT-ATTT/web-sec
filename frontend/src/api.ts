export type Project = { id: number; name: string; description: string };
export type Target = { id: number; project_id: number; base_url: string; timeout_seconds: number; request_limit: number; verification_path: string };
export type Identity = { id: number; display_name: string; role: string | null; principal_pointer: string | null; expected_principal: string | null; has_secret: boolean };
export type Operation = { id: number; operation_key: string; method: string; path: string; selected: boolean };
export type ResourceType = { id: number; name: string; resource_id_pointer: string; restricted_pointers: string[] };
export type Resource = { id: number; resource_type_id: number; external_id: string; resource_alias?: string; owner_identity_id: number; path_parameter: string };
export type ResourceInspection = Resource & { request_previews: { operation_id: number; method: "GET"; path: string }[] };
export type Policy = { id: number; version: number; operation_id: number; resource_type_id: number; decision: "ALLOW" | "DENY" | "UNKNOWN"; identity_id: number | null; role: string | null; resource_id: number | null };
export type OperationResourceMapping = { id: number; project_id: number; operation_id: number; resource_type_id: number; selected: boolean };
export type BatchPlanTarget = { operation_id: number; operation_path: string; resource_type_id: number; resource_type_name: string; resource_count: number; actor_case_count: number };
export type BatchMatrix = { identity_count: number; concrete_target_count: number; actor_case_count: number; identity_verifications: number; owner_baselines: number; planned_attempts: number; maximum_http_requests: number; request_limit: number; within_request_limit: boolean; targets: BatchPlanTarget[]; cases?: MatrixCase[] };
export type MatrixCase = { case_key: string; actor_alias?: string; actor_role?: string | null; owner_alias?: string; owner_role?: string | null; resource_alias?: string; ownership_category?: string; expected_decision?: string; method?: string; path_template?: string; control_type: string; actor_identity_id: number; resource_id: number; operation_id: number; owner_identity_id: number; resolved_decision: Policy["decision"] | null; policy_id: number | null; policy_version: number | null; policy_status: string; warnings: string[] };
export type ExecutionSummary = { planned_attempts: number; transport_attempts: number; completed_responses: number; scope_blocked: number; transport_errors: number; cancelled_cases: number };
export type Run = { id: number; project_id: number; status: string; snapshot: Record<string, unknown>; execution_summary: ExecutionSummary | null };
export type ResultEvidence = { schema_version: 1 | 2; actor_role?: string | null; owner_role?: string | null; ownership?: string | null; protected_fields?: { alias: string; owner_present: boolean; actor_present: boolean; owner_type: string | null; actor_type: string | null; matches_owner: boolean }[] | null; run_id: number; case_key: string; owner_identity_id: number; actor_identity_id: number; owner_body_truncated?: boolean; owner_json_parse_error?: boolean; owner_principal_matches?: boolean; actor_principal_matches?: boolean; owner_resource_matches?: boolean; owner_restricted_evidence_valid?: boolean; owner_control_valid: boolean; owner_http_status: number | null; owner_execution_status: string; policy_id: number | null; policy_version: number | null; policy_decision: Policy["decision"] | null; policy_resolution: string; actor_resource_matches: boolean; restricted_fields_match_owner: boolean };
export type Result = { case_key: string; execution_status: string; authorization_conclusion: string; reason_codes: string[]; http_status: number | null; response_metadata: { evidence?: ResultEvidence | null } };
export type Finding = { id: number; fingerprint: string; conclusion: string; operation: { method: string; path: string }; policy: { id: number; version: number }; reproduction_count: number; reproductions?: { run_id: number; run_result_id: number; case_key: string | null }[] };
export type ExternalLabJob = { public_id: string; project_id: number; job_kind: string; protocol_version: number; status: string; requested_at: string; dispatched_at: string | null; started_at: string | null; finished_at: string | null; cancel_requested_at: string | null; result_summary: Record<string, unknown>; artifact_manifest_sha256: string | null; failure_code: string | null };

export type TargetInput = Omit<Target, "id" | "project_id">;
export type IdentityInput = { display_name: string; role?: string | null; principal_pointer?: string | null; expected_principal?: string | null; bearer_token?: string };
export type ResourceTypeInput = Omit<ResourceType, "id">;
export type ResourceInput = { external_id: string; owner_identity_id: number; path_parameter: string };
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
  inspectResource: (projectId: number, resourceId: number) => request<ResourceInspection>(`/api/projects/${projectId}/resources/${resourceId}/inspect`, { method: "POST", cache: "no-store" }),
  importAuthorizationOpenApi: (p: number, document: unknown) => request(`/api/projects/${p}/authorization/openapi`, {method: "POST", body: JSON.stringify({document})}),
  authorizationConfig: (p: number) => request<{revision: string | null; configuration: Record<string, unknown>}>(`/api/projects/${p}/authorization/config`),
  saveAuthorizationConfig: (p: number, configuration: unknown) => request(`/api/projects/${p}/authorization/config`, {method: "PUT", body: JSON.stringify(configuration)}),
  authorizationPreview: (p: number, t: number) => request<AuthorizationPreview>(`/api/projects/${p}/authorization/preview?target_id=${t}`),
  queueAuthorization: (p: number, t: number, revision: string, ids: string[]) => request<{id: number}>(`/api/projects/${p}/authorization/runs`, {method: "POST", body: JSON.stringify({target_id:t, policy_revision:revision, case_ids:ids})}),
  authorizationResults: (p: number, r: number) => request<{run_id: number; status: string; policy_revision: string; cases: AuthorizationResult[]}>(`/api/projects/${p}/authorization/runs/${r}/results`),
  async login(password: string) {
    const response = await request<{ csrf_token: string }>("/api/auth/login", { method: "POST", body: JSON.stringify({ password }) });
    csrfToken = response.csrf_token;
  },
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  seedSshDemo: () => request<{project_id: number; created: boolean; synthetic: boolean}>("/api/demo/ssh-seed", {method: "POST"}),
  seedDemo: () => request<{project_id: number; created: boolean; synthetic: boolean}>("/api/demo/seed", {method: "POST"}),
  projects: () => request<Project[]>("/api/projects"),
  createProject: (name: string, description: string) => request<Project>("/api/projects", { method: "POST", body: JSON.stringify({ name, description }) }),
  deleteProject: (projectId: number, confirmationName: string) => request<void>(`/api/projects/${projectId}`, { method: "DELETE", body: JSON.stringify({ confirmation_name: confirmationName }) }),
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
  operationResourceMappings: (projectId: number) => request<OperationResourceMapping[]>(`/api/projects/${projectId}/operation-resource-mappings`),
  createOperationResourceMapping: (projectId: number, value: { operation_id: number; resource_type_id: number; selected: boolean }) => request<OperationResourceMapping>(`/api/projects/${projectId}/operation-resource-mappings`, { method: "POST", body: JSON.stringify(value) }),
  updateOperationResourceMapping: (mappingId: number, selected: boolean) => patch<OperationResourceMapping>(`/api/operation-resource-mappings/${mappingId}`, { selected }),
  createResourceType: (projectId: number, value: ResourceTypeInput) => request<ResourceType>(`/api/projects/${projectId}/resource-types`, { method: "POST", body: JSON.stringify(value) }),
  updateResourceType: (resourceTypeId: number, value: ResourceTypeInput) => patch<ResourceType>(`/api/resource-types/${resourceTypeId}`, value),
  resourceTypes: (projectId: number) => request<ResourceType[]>(`/api/projects/${projectId}/resource-types`),
  resources: (projectId: number) => request<Resource[]>(`/api/projects/${projectId}/resources`),
  createResource: (typeId: number, value: ResourceInput) => request<Resource>(`/api/resource-types/${typeId}/resources`, { method: "POST", body: JSON.stringify(value) }),
  updateResource: (resourceId: number, value: Partial<ResourceInput>) => patch<Resource>(`/api/resources/${resourceId}`, value),
  policies: (projectId: number) => request<Policy[]>(`/api/projects/${projectId}/policies`),
  createPolicy: (projectId: number, value: PolicyInput) => request<Policy>(`/api/projects/${projectId}/policies`, { method: "POST", body: JSON.stringify(value) }),
  updatePolicy: (policyId: number, value: PolicyInput) => patch<Policy>(`/api/policies/${policyId}`, value),
  matrix: (projectId: number, operationId: number, resourceId: number) => request<MatrixCase[]>(`/api/projects/${projectId}/matrix?operation_id=${operationId}&resource_id=${resourceId}`),
  createRun: (projectId: number, value: { target_id: number; resource_id: number; operation_id: number }) => request<Run>(`/api/projects/${projectId}/runs`, { method: "POST", body: JSON.stringify(value) }),
  batchMatrix: (projectId: number, targetId: number) => request<BatchMatrix>(`/api/projects/${projectId}/batch-matrix?target_id=${targetId}`),
  createBatchRun: (projectId: number, targetId: number) => request<Run>(`/api/projects/${projectId}/batch-runs`, { method: "POST", body: JSON.stringify({ target_id: targetId }) }),
  runs: (projectId: number) => request<Run[]>(`/api/projects/${projectId}/runs`),
  comparisonBundles: (projectId: number, offset = 0) => request<BundleInventory[]>(`/api/projects/${projectId}/comparisons?offset=${offset}&limit=100`),
  comparisonBundle: (projectId: number, digest: string) => request<ComparisonBundle>(`/api/projects/${projectId}/comparisons/${encodeURIComponent(digest)}`),
  comparison: (projectId: number, runId: number) => request<Comparison>(`/api/projects/${projectId}/runs/${runId}/comparison`),
  results: (runId: number) => request<Result[]>(`/api/runs/${runId}/results`),
  findings: (projectId: number, runId?: number) => request<Finding[]>(`/api/projects/${projectId}/findings${runId === undefined ? "" : `?run_id=${runId}`}`),
  cancelRun: (runId: number) => request<void>(`/api/runs/${runId}/cancel`, { method: "POST" }),
  externalLabJobs: (projectId: number) => request<ExternalLabJob[]>(`/api/projects/${projectId}/external-lab-jobs`),
  createReadOnlyExternalLabJob: (projectId: number) => request<ExternalLabJob>(`/api/projects/${projectId}/external-lab-jobs/read-only-verification`, { method: "POST" }),
  cancelExternalLabJob: (publicId: string) => request<void>(`/api/external-lab-jobs/${publicId}/cancel`, { method: "POST" }),
};


export type ComparisonMethod = {
  method: "MANUAL" | "T18" | "ZAP";
  execution_status: string;
  observation: Result | null;
  provenance: string;
  artifact: "UNAVAILABLE";
  timing_status: "TIMING_NOT_AVAILABLE";
};
export type Comparison = { run_id: number; cases: { run_id: number; case_key: string | null; methods: ComparisonMethod[] }[] };

export type BundleMethod = "MANUAL" | "T18" | "ZAP";
export type BundleInventory = { content_digest: string; attestation_status: "UNVERIFIED" };
export type BundleCase = { case_id: string; method: string; operation_template: string; actor_role: string; owner_category: string; policy_id: string; policy_version: string; expected_decision: string };
export type BundleProvenance = { artifact_ref: string; artifact_hash: string; producer_kind: string; producer_version: string; operator_alias: string | null };
export type ComparisonBundle = BundleInventory & {
  schema_version: 1 | 2;
  manifest: { content_digest: string; version: string; cases: BundleCase[] };
  selections: { method: BundleMethod; execution_id: string }[];
  observations: { method: BundleMethod; execution_id: string; manifest_digest: string; manifest_version: string; case_revision: BundleCase; execution_status: string; signal: string; provenance: BundleProvenance | null }[];
  legacy: { method: BundleMethod; source_alias: string; linkage_status: "UNLINKED"; conclusion: "UNKNOWN"; provenance: BundleProvenance | null }[];
  // Receipt bytes deliberately have no presentation fields.
  artifacts: { artifact_ref: string; artifact_hash: string; integrity_status: string; attestation_status: string }[];
};

export type AuthorizationCase = {case_id: string; kind: string; operation_id: number; method: string; path_template: string; actor_identity_id: number; actor_role: string | null; resource_id: number | null; owner_identity_id: number | null; relationship: string; expected_decision: string; matched_rule_keys: string[]; policy_revision: string; baseline_identity_id: number | null; execution_eligible: boolean; reasons: string[]};
export type AuthorizationPreview = {policy_revision: string; cases: AuthorizationCase[]; exclusions: {identity_id: number; reason: string}[]; warnings: {operation_id: number; reason: string}[]; identity_count: number; actor_case_count: number; executable_case_count: number; planned_attempts: number; request_limit: number};
export type AuthorizationResult = {operation_id?: number; presentation?: CasePresentation;case_id: string; run_id: number; result_id: number | null; finding_id: string | null; artifact_ref: string | null; policy_revision: string; matched_rule_keys: string[]; kind: string; expected_decision: string; actor_identity_id: number; resource_id: number | null; baseline_identity_id: number | null; execution_status: string; conclusion: string; reason_codes: string[]; http_status: number | null; evidence: Record<string, boolean | number | null> | null};

export type SnapshotIdentityLabel = {id: number | null; display_name: string | null; role: string | null; source: string};
export type CasePresentation = {actor: SnapshotIdentityLabel; owner: SnapshotIdentityLabel; planned_baseline: SnapshotIdentityLabel; actual_baseline: SnapshotIdentityLabel; resource_name: string | null; method: string | null; path: string | null; relationship: string | null; baseline_kind: string | null; baseline_provenance: string};
