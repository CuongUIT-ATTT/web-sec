# Phase 1 — Audit R3/R4 BOLA analysis

Ngày 2026-11-15, T18 BOLA Evaluator. Phạm vi: read-only source và báo cáo evidence có sẵn; chỉ tạo báo cáo này. HEAD xác minh `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Working tree có sửa sẵn evaluator, runner, workflow routes/schemas, frontend và tests; audit đọc trạng thái working tree, không quy tất cả tính năng cho HEAD committed. Không sửa code/tests, gọi lab/queue/DB/browser, deploy, commit/push, reset hoặc xóa. Run #2 và snapshot không bị thay đổi.

## Verdict và evidence boundary

R3 cross-request comparison: **PARTIALLY IMPLEMENTED**, phần evaluator và metadata đã có, UI chỉ giải thích một phần. R4 BOLA/BFLA: **PARTIALLY IMPLEMENTED** với BOLA có evidence lịch sử; BFLA thực nghiệm trong audit này **NOT VERIFIED**, không coi GET object comparison là BFLA. Full research acceptance **NOT VERIFIED**.

Nguồn mapping requirement: `audit-final/requirements-traceability.md`. Audit này không nghiệm thu thay các nhánh R1/R2/R5–R8.

Evidence đã đọc: `audit-final/web-demo-e2e-recovered-s01-qa.md` báo cáo QA read-only ngày 2026-11-13: run #2 COMPLETED, 5 responses/0 errors; case `operation:1:resource:1:actor:1` CONFIRMED_VIOLATION, policy #2 v1 DENY, owner valid; case `operation:1:resource:1:actor:2` POLICY_CONSISTENT_CASE, policy #1 v1 ALLOW. Finding #1 → reproduction #1 → result #3 → run #2. Đây là **báo cáo lịch sử đã đọc**, không phải DB/live/browser được tái xác minh bởi evaluator hôm nay. QA chỉ xác minh persisted metadata; Browser do Lead quan sát. Fixture runtime/OpenAPI digest, freshness HTTP và 3-role coverage chưa được xác minh ở lượt này. Không sao chép external resource identifier vào báo cáo này.

Thực thi hôm nay: git HEAD/status, đọc source/test/report, kiểm tra automation liên quan (không có). Không chạy test suite; mọi test bên dưới là coverage được đọc, không tuyên bố PASS thực thi. Không có live artifact mới ngoài báo cáo audit.

## Source và phân loại capability

| Capability | Source chính xác | Phân loại / khoảng trống |
|---|---|---|
| Policy resolution/version | `backend/app/scanner/classification/policy.py:resolve_policy`; `backend/app/workers/runner.py:_evidence_metadata` | Implemented, visible một phần. Identity/role specificity, resource scope, tie conflict và version có; UI hiển thị policy ID/version/decision/resolution. |
| Principal và owner baseline validity | `backend/app/workers/runner.py:_principal_matches`, `_owner_control_valid` | Implemented, visible một phần. Owner phải principal đúng, 2xx, JSON không lỗi/truncated, resource đúng và protected values có nghĩa. UI chỉ hiện owner_valid và owner HTTP/execution; các điều kiện chi tiết bị ẩn. |
| Protected nested JSON equality | `backend/app/scanner/classification/evaluator.py:meaningful_restricted_value`, `restricted_evidence_valid`, `restricted_fields_match` | Implemented. Tất cả configured pointers phải hiện diện/có nghĩa và khớp JSON, key order insensitive; bool khác number; list order vẫn có nghĩa. UI chỉ có aggregate match bool, không tên field an toàn hoặc per-field outcome. |
| Confirmation rule | `backend/app/scanner/classification/evaluator.py:evaluate` | Implemented, demonstrated theo historical QA report trong phạm vi 1 DENY case. Explicit DENY + valid identity/owner + requested resource match + protected owner equality; HTTP 200/length không đủ. 403 có body leak vẫn có thể confirm. |
| Authorized sharing/admin | cùng evaluator/policy | Explicit ALLOW → POLICY_CONSISTENT_CASE khi resource match; không có admin bypass. UNKNOWN/no rule → insufficient; không có enum POLICY_DEPENDENT_ADMIN_ACCESS. Cần giải thích quyết định thực tế thay vì gắn admin access là BOLA. |
| Denial/transport handling | evaluator; runner hai call sites `evaluate` | Implemented nhưng hạn chế: evaluator hỗ trợ denial_convention nhưng runner không truyền cấu hình này. Generic 200 denial và 401/403 JSON không có leak thường insufficient; JSON không quan sát được → NOT_EVALUATED. Không được trình bày những case đó như PASS/negative đã chứng minh. |
| Evidence metadata/API | runner `_evidence_metadata`; `backend/app/api/workflow_schemas.py:ResultEvidenceView`; `backend/app/api/workflow_routes.py:_result_metadata`, `list_results` | Implemented. Versioned allowlist, strict types, run/case binding, invalid legacy evidence unavailable. Không persist raw protected values tại helper này. Có engine, principal/resource validity, policy và owner IDs; thiếu snapshotted role/ownership category, safe field descriptors/per-field checks, explicit violation rationale/artifact identity. |
| Findings persistence | `backend/app/services/findings.py:record_confirmed_reproduction`; `backend/app/scanner/classification/findings.py:FindingKey`; routes `list_findings` | Implemented. Chỉ confirm tạo finding; policy/version/mapping fingerprint; per-result idempotent reproduction, run-scoped/project-scoped joins. Historical QA xác nhận một liên kết. |
| Web analysis | `frontend/src/App.tsx:RunsPanel`, `Evidence`; `frontend/src/api.ts:ResultEvidence`, `Finding` | Partially visible. Case/run, raw enum/reason codes, policy, owner validity, aggregate match có. Không mô tả actor/role/ownership; thiếu diễn giải con người hiểu, field names đã che, reproduction drilldown. API có reproductions nhưng TS Finding bỏ thuộc tính và UI chỉ count. |
| Dynamic field normalization/shape/length | web evaluator và runner; CLI `tools/authorization-lab/src/authz_lab/read_only/response_comparator.py` | Web exact protected pointers, body_length metadata; không có normalized structural comparator hoặc dynamic exclusions. CLI có normalize_json/json_similarity nhưng độc lập, không thể tính là web đã triển khai. Không thêm heuristic similarity thành confirmation. |

## Mapping kết luận cần trình bày

Source enum: `backend/app/domain/contracts.py:AuthorizationConclusion`.

| Hiện tại | Nhãn nghiên cứu đề xuất | Quy tắc |
|---|---|---|
| CONFIRMED_VIOLATION | CONFIRMED | Giữ provenance và lý do explicit DENY + evidence; phân biệt object-owner case với privileged function. |
| INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | Không nâng thành SUSPECTED chỉ vì HTTP 200 hoặc length. |
| INVALID_TEST | INVALID_TEST | Principal mismatch/owner invalid; nêu điều kiện nào thất bại. |
| POLICY_CONSISTENT_CASE | POLICY-CONSISTENT | Không đồng nghĩa toàn API an toàn; ALLOW observed khác DENY được chứng minh. |
| BLOCKED_POLICY_CONFLICT | BLOCKED / policy conflict | Giữ trạng thái riêng; không giả thành negative. |
| NOT_EVALUATED | NOT EVALUATED | Transport/parse/truncation chưa đủ đánh giá; giữ execution tách conclusion. |
| Không có SUSPECTED | Chưa triển khai | Cần tiêu chí evidence rõ được phê duyệt; mặc định thiếu bằng chứng vẫn insufficient. |

Không đổi enum/lưu lại lịch sử chỉ để đổi nhãn UI. Không dựng metadata thiếu cho Run #2 hoặc run cũ.

## Tickets triển khai có thể giao

1. **BOLA-A01 — Safe analysis DTO v2 (P0)**. Files: runner `_evidence_metadata`, workflow_schemas `ResultEvidenceView`, workflow_routes `_result_metadata`; phụ thuộc ticket redacted run DTO và canonical case IDs của Matrix. Snapshot actor/owner role, ownership category (self/same-role-other/cross-role/unknown), safe protected-field aliases và per-field presence/type/equality, evaluator version; không raw values, external IDs hoặc pointers có segments nhạy cảm. Immutable source từ run snapshot, không join cấu hình hiện tại để giải thích lịch sử. Acceptance: sau khi đổi role/policy/mapping hiện tại, evidence cũ không đổi; canary token/secret/external ID không xuất hiện ở API/DOM; malformed/legacy v1 vẫn unavailable hoặc render v1 đúng dữ liệu thực.

2. **BOLA-A02 — Analyze case explanation (P0)**. Files: `frontend/src/App.tsx` (tách component Analysis khi cần), `frontend/src/api.ts`; phụ thuộc A01 và Matrix canonical IDs. Hiển thị actor alias/role → ownership category, expected policy/version → observed resource/protected evidence → violation hay thiếu bằng chứng; chỉ dùng snapshot DTO. Giữ HTTP là transport observation. Acceptance: deterministic UI fixtures cho DENY leak/ALLOW sharing/unknown/conflict/invalid owner/truncated; đúng câu giải thích và không suy từ HTTP/length; missing legacy metadata hiển thị unavailable, không auto-fill từ project hiện tại.

3. **BOLA-A03 — Conclusion vocabulary contract (P0)**. Files: domain/contracts (chỉ nếu cần contract mới), evaluator, workflow_schemas, api.ts, Analysis component. Tạo presentation mapping ở trên, giữ raw enum và provenance; định nghĩa SUSPECTED trước khi phát sinh tự động. Acceptance: table-driven mapping đầy đủ; UNKNOWN/conflict/generic 200/equal length không thành confirmed; authorized cross-user sharing ALLOW không thành finding; không sửa persisted Run #2.

4. **BOLA-A04 — Finding → reproduction → case drilldown (P1)**. Files: workflow_routes `list_findings`, api.ts Finding, App.tsx finding UI. API đã có links nên không tạo lại từ fingerprint. Acceptance: click finding mở đúng run/case, run filter không mang reproduction run khác, project switch không hiển thị evidence cũ; repeat persistence không duplicate; legacy finding thiếu links không chế provenance. Bổ sung artifact reference/digest khi có artifact thực sự, unavailable khi chưa có.

5. **BOLA-A05 — Comparator diagnostics and denial contract (P1)**. Files: evaluator, runner, workflow_schemas; tests evaluator/web_demo_evidence. Đánh giá nhu cầu dynamic exclusions có version từ snapshot; trước mắt mô tả rõ exact protected-pointer comparison. Nếu thêm denial convention, cần cấu hình/version hóa rồi truyền cho cả single/batch; không auto-infer từ 403. Acceptance: nested object key reorder equal; bool vs int và numeric representation semantics được quy định; dynamic unprotected field không đổi confirmation; missing/null/empty protected fields không confirm; supported denial 200 consistent, generic denial insufficient; 403 body leak vẫn confirm. Exclusion không được xóa protected evidence để tạo match giả.

6. **BOLA-A06 — BOLA acceptance evidence pack (P0 sau A01–A04)**. Files: tests nêu dưới, thêm deterministic UI coverage và browser evidence report trong audit-final theo ownership mới. Chạy synthetic regressions trước, rồi browser E2E chỉ trên lab đã được duyệt khi Lead giao. Acceptance: stable case/run/policy/fixture/artifact links; positive DENY owner-match, negative ALLOW sharing, public/generic response, wrong resource, empty protected field, wrong principal, bad baseline, unknown/conflict, timeout/truncation; tối thiểu 3 roles là gate riêng cần lab fixtures thật. Không thay code/test mock bằng evidence thực nghiệm. Không tự chạy ZAP/BFLA.

## Tests đã đọc và missing verification

- `backend/tests/test_evaluator.py`: deny confirmation, 403 leak, supported/generic 200 denial, truncated/parse, conflict/principal mismatch.
- `backend/tests/test_web_demo_evidence.py`: explicit policy; null/empty/nested owner values; nested equality/type/resource guards; synthetic runner owner failures single/batch; canary redaction; authorized sharing. Transport monkeypatched: không phải lab execution.
- `backend/tests/test_web_demo_contracts.py`: policy/version/specificity, run-scoped persisted reproduction joins, strict summary allowlist, malformed/mismatched/legacy metadata.
- `backend/tests/test_finding_persistence.py`: idempotent reproduction; `backend/tests/test_batch_runner_regressions.py`: accounting, cancellation, crash without replay.
- `frontend/src/WebDemo.test.tsx`: policy/matrix rendering, scoped findings/stale response/project switch, duplicate queue/cancel guards; chưa có complete human-readable analysis decision table.
- Tất cả các suite trên **NOT RUN trong audit này**. Browser rendering hôm nay **NOT VERIFIED**; current DB/runtime **NOT VERIFIED**. R3/R4 implementation partial; toàn bộ acceptance không được ghi PASS từ việc chỉ đọc code.

CLI comparator khác web evaluator: có normalization/similarity và verdict vocabulary khác; không import/call CLI từ web. Khi Compare nối dữ liệu ở pha sau phải giữ method/engine/execution provenance, không coi hai CONFIRMED là cùng tiêu chuẩn nếu chưa đối chiếu policy/owner guard. BFLA và write path giữ workflow disposable độc lập, **NOT RUN** tại đây.
