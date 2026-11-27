# Phase 1 — Audit OpenAPI, matrix, planner, policy và snapshot

Ngày audit: 2026-11-15 (giờ Việt Nam). Người thực hiện: T18 OpenAPI Matrix.
Phạm vi: R1, R2 và phần R6; đọc mã backend/frontend/tests và báo cáo evidence sẵn có. Không sửa production/tests, không chạy suite, không truy vấn DB, không gọi lab/queue/deploy/ZAP/BFLA. Chỉ tạo báo cáo này. Không đọc bảng credentials, response thô hay file secret. Run #2 và snapshot không bị tác động.

## Baseline và mức chứng minh

Đã chạy `git rev-parse HEAD`, `git status --short`, `git diff --stat` và đọc source. HEAD đúng `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Có sẵn 7 file tracked thay đổi: workflow_routes.py, workflow_schemas.py, evaluator.py, runner.py, App.tsx, api.ts, styles.css; các tests web-demo và audit-final chưa track. Báo cáo phản ánh working tree, không chỉ commit HEAD. Các thay đổi cũ được giữ nguyên.

Nguồn requirement: `audit-final/requirements-traceability.md` gọi R1 multi-role, R2 OpenAPI matrix, R6 reusable tool. Đây là mapping hiện có của repo, không phải tự bổ sung định nghĩa R1–R8. R3–R5/R7–R8 do các audit chuyên trách đánh giá; không kết luận thay họ.

Evidence lịch sử đã đọc: `audit-final/web-demo-e2e-recovered-s01-qa.md`. QA ghi run #2 COMPLETED, planned/transport/responses = 5/5/5, errors=0; hai case có key `operation:1:resource:1:actor:1` và `operation:1:resource:1:actor:2`, một CONFIRMED_VIOLATION theo policy #2 v1 DENY, một POLICY_CONSISTENT_CASE. QA xác minh metadata; Browser do Lead quan sát. Báo cáo này không tái xác minh DB, lab, browser hay hash lịch sử; không coi báo cáo đó là một lần thực thi mới.

## Phân loại yêu cầu

| Yêu cầu/phần | Triển khai | Hiện trên web theo source | Đã demo/bằng chứng | Verdict trong audit này |
|---|---|---|---|---|
| R1 identity và role | Đã triển khai lưu identity/role, principal check, policy identity hoặc role | Có cấu hình identity và role policy | Run #2 chỉ hai identity cùng một role; chưa đạt tối thiểu ba role | PARTIAL; gate đa role NOT VERIFIED |
| R2 import OpenAPI GET | Đã triển khai inventory GET, select operation | Có nhập JSON và chọn operation | Báo cáo trước có browser mapping/matrix; chưa tái kiểm tra browser | PARTIAL cho toàn R2 |
| R2 matrix đơn | Có owner/cross-identity, policy decision/id/version và warning | Có nút sinh và danh sách; chưa in case_key ở preview | Tests có contract mô phỏng; không chạy trong lượt này | Implemented, thiếu trình bày và liên kết batch |
| R2 batch preview | Planner có tích identities × mapped resources × operations; budget I+C+I×C | Chỉ số lượng và nhóm operation/type | Run #2 chứng minh batch nhỏ đã chạy theo báo cáo QA | Partially implemented; thiếu từng case policy-aware |
| R2 completeness/provenance | Có mapping và resource owner bắt buộc | Chưa có bảng bao phủ/skips hoặc hash spec/fixture | Chưa có acceptance cho full matrix | Missing một phần |
| R6 reusable engine | Backend parser/planner/generator/policy/HTTP tách module; CLI có parser/matrix riêng | Chỉ web workflow; CLI không nối trực tiếp | Không xác minh cài đặt/CLI execution trong lượt này | PARTIAL; CLI capabilities có code, không có demo web tương ứng |

## Source và các phát hiện cụ thể

### Matrix/policy đã tồn tại, không nên viết lại từ đầu

- `backend/app/scanner/openapi/parser.py::parse_openapi_json`: nhận JSON tối thiểu, chỉ inventory GET, đọc path params/security/diagnostics; không giải quyết đầy đủ OpenAPI refs. `backend/app/api/workflow_routes.py::import_openapi` chỉ persist operation key/method/path, bỏ metadata parameters/security/diagnostics. Import cùng operation key sẽ giữ record cũ, không reconcile path/spec đã đổi; không có input hash/version để truy ngược nguồn. Non-GET bị bỏ qua im lặng ở inventory web.
- `backend/app/scanner/matrix/generator.py::generate_cases`: sort/dedup identity IDs, OWNER_CONTROL hoặc CROSS_IDENTITY; có warnings unverified/no policy/conflict. Không tự sinh resource ngoài cấu hình. Không có anonymous/invalid-token trong generator web.
- `backend/app/api/workflow_routes.py::get_matrix`: trả operation, owner, actor, decision, policy id/version; resolve policy thực sự. Tuy nhiên chỉ kiểm tra operation/resource cùng project; không bắt buộc operation selected, mapping bật hoặc path parameter tương thích như batch. Vì vậy preview đơn có thể không đại diện batch sẽ queue.
- `backend/app/scanner/classification/policy.py::resolve_policy`: identity+resource > identity > role+resource > role; xung đột quyết định ở cùng specificity trả UNRESOLVED_CONFLICT; rule cùng decision chọn id nhỏ nhất; NO_MATCH không biến thành ALLOW. Không có admin bypass mặc định. UI câu “policy conflict vẫn bị chặn” cần giải thích: planner không reject conflict trước queue; evaluator giữ trạng thái không đủ policy cho kết luận, khác với chặn network.
- `frontend/src/App.tsx::MatrixPanel`: có role policy, resource scope, policy edit/version và sinh matrix. Dòng matrix chỉ hiển thị actor/owner/operation IDs, decision/policy/warnings; thiếu role label, ownership category diễn giải, request preview và case ID hiển thị.

### Case ID chưa thống nhất xuyên workflow

Matrix đơn dùng `resource:{resource_id}:actor:{identity_id}`. Batch runner (`backend/app/workers/runner.py::_cancelled_actor_keys` và luồng batch) dùng `operation:{operation_id}:resource:{resource_id}:actor:{identity_id}`. Với hai operation cùng resource/actor, preview đơn có cùng key mặc dù là hai case khác nhau. Key batch ổn định theo các DB IDs khi cấu hình giữ nguyên, chưa phải ID portable qua import/export hoặc manual/CLI/ZAP. UI batch preview không trả rows/key nên không thể đối chiếu chính xác preview → run → comparison. Cần giữ key legacy và Run #2; không backfill/rewrite lịch sử để sửa vấn đề này.

### Redaction: result summary tốt hơn snapshot/config APIs

- `backend/app/workers/runner.py::_evidence_metadata` lưu booleans/codes, không lưu protected response values. `workflow_schemas.py::ResultEvidenceView/ResultMetadataView` cùng serializer results có allowlist. Frontend `Evidence` hiện owner-valid, policy, resource-match/field-match và reason codes. Chưa hiện tên trường bảo vệ theo alias an toàn, role và ownership category ở evidence.
- `backend/app/services/run_snapshot.py::snapshot_batch_run/snapshot_run` không chứa token/ciphertext/body nhưng có `resource.external_id` và `identity.expected_principal`. `workflow_routes.py::_run_view` trả nguyên `run.snapshot` trong list/queue response; `RunView.snapshot` là dict rộng. Vì vậy không thể gọi đây là snapshot đã redact đầy đủ theo yêu cầu mới “không expose unredacted resource identifiers”. Đây là phát hiện luồng dữ liệu từ source, chưa phải xác minh response deployed hoặc rò rỉ credential.
- `App.tsx::ResourcePanel/MatrixPanel` và resource API còn dùng external_id thẳng cho cấu hình/select. Cần quy định alias an toàn cho các màn hình/demo/output; không sửa dữ liệu internal dùng để thực thi. Principal có thể là thông tin nhạy cảm; không nên xuất snapshot thực thi cho browser chỉ để render run.

### Các invariants đã thấy trong code và giới hạn

| Invariant | Source/chứng cứ code | Giới hạn xác minh |
|---|---|---|
| Selected GET mapping | `services/batch_plan.py::build_batch_plan`, routes `_build_project_batch_plan` | Batch dùng mapping selected + operation selected GET; matrix đơn chưa ràng buộc giống batch |
| Configured identities/resources/owner | Planner nhận project-filtered DB rows, owner phải nằm trong identities, path parameter phải khớp | Không enumeration; chưa có coverage/skipped reasons cho mapping không có resource |
| Caps | `BatchPlan.planned_attempts/within_request_limit`, `create_batch_run` reject vượt cap; runner dùng snapshot plan | Tests có code, chưa chạy lại; legacy `create_run` không có cùng gate budget rõ như batch, cần kiểm tra riêng trước khi quảng bá invariant toàn API |
| Scope | `scanner/execution/scope.py::validate_base_url/build_request_url`: IP ranges/ports, chặn query/userinfo/traversal/reset endpoint | Code review; không probe network |
| No retries/redirects | `scanner/execution/http_client.py::get_json`: một GET, follow_redirects=False, không vòng retry; response bounded | Không tái thực thi |
| Snapshot | Queue tạo JSON metadata riêng từ config; worker đọc snapshot | Không thấy DB/ORM append-only enforcement ở model Run; “immutable” hiện là thiết kế luồng ứng dụng, không khẳng định tamper-proof |
| Queue-time credentials | `create_batch_run/create_run` copy ciphertext/key_version vào `RunIdentitySecret` trong transaction; runner dùng bản của run | Không đọc credential; thiếu live mutation acceptance trong audit này |
| Idempotency | `persistence/models.py` unique run/case claim và finding/run-result; runner claim/persist; tests idempotency/regressions | Không coi code là proof crash/concurrency đã chạy |

### CLI độc lập và candidate classification (R6 một phần)

`tools/authorization-lab/src/authz_lab/read_only/spec_parser.py::extract_endpoints` inventory GET/POST/PUT/PATCH/DELETE; đánh dấu BOLA/write-BOLA/BFLA/API3/mass assignment bằng metadata/heuristics, chặn /createdb. Candidate không phải kết luận lỗ hổng. Web parser GET khác parser CLI, không nên import CLI vào web để lấp UI.

`.../matrix_builder.py::build_test_matrix` dùng fixture path và configured role filtering; tạo owner/cross-user/anonymous/invalid-token cho authenticated object reads; public observation và debug/API3 cases riêng. `_is_admin_role` ưu tiên is_admin config, fallback prefix admin. Không có equivalence trực tiếp với role string web: userA/userB trong CLI được dùng như actor labels, trong Run #2 hai identity cùng role user. Phải mô tả số role thật, không đếm identity thành role.

CLI `_case_id` sanitize operation/resource sang chữ/số và dấu gạch: có khả năng collision khi input khác nhau chỉ ở dấu phân cách; không thấy dedup/error collision trong build_test_matrix. Không sửa CLI trong pha audit. Fixture filtering có code nhưng hash repository không chứng minh fixture runtime của Run #2.

## Ticket triển khai đề xuất

| Ticket / ưu tiên | File/function dự kiến | Dependencies | Acceptance cần chạy ở pha triển khai |
|---|---|---|---|
| MATRIX-01 / P0 — contract case thống nhất | `scanner/matrix/generator.py`, `services/batch_plan.py`, `api/workflow_routes.py`, `workflow_schemas.py`, `workers/runner.py`, `frontend/src/api.ts` | Chốt case schema + version trước comparison | Hai operations cùng resource/actor có key riêng; reorder config không đổi key; preview rows khớp snapshot/executed rows; Run #2/legacy đọc nguyên vẹn; không gọi lab trong unit tests |
| MATRIX-02 / P0 — full batch preview policy-aware | `get_batch_matrix`, BatchMatrixView, `App.tsx::MatrixPanel/RunPanel` | MATRIX-01 | Rows có case id, method/path template, actor role/alias, owner alias/category, decision/policy/version, warnings; row count = I×C; cap gồm verification và baseline; selected/unselected/foreign scope tests; preview không có side effect |
| REDACT-01 / P0 — public run DTO | `_run_view`, `RunView`, resource presentation DTO, `frontend/src/api.ts/App.tsx`; giữ `run_snapshot.py` internal | Trước browser acceptance | Canary token/ciphertext/principal/external id không có trong run/list/queue/results/preview DTO và DOM; worker vẫn chạy đúng bằng internal snapshot; snapshot/Run #2 byte-content không bị rewrite |
| MATRIX-03 / P1 — completeness và provenance | `scanner/openapi/parser.py`, `import_openapi`, planner/DTO; có thể thêm metadata model/migration | MATRIX-01; migration review | Ghi spec digest/version, fixture alias/provenance, coverage selected/mapped/skipped + lý do; duplicate operation key/spec drift/refs được báo rõ; không âm thầm thay lịch sử; collision tests |
| ROLES-01 / P1 — readiness gate | `App.tsx`, preview DTO/routes | MATRIX-02, policy fixtures được chủ lab xác nhận | Đếm unique role riêng identity; hiển thị missing owner/policy và UNKNOWN/conflict; admin cần policy tường minh; deterministic 3-role/5-identity tests không giả làm runtime proof |
| MATRIX-04 / P1 — giải thích và comparison handoff | `App.tsx::Evidence`, schemas metadata aliases, comparison DTO pha sau | MATRIX-01/02, BOLA Evaluator chốt conclusion mapping | Case/run/policy link rõ; protected field alias không lộ values; owner vs cross-user/cross-role; manual/scanner/ZAP chỉ align có provenance; unexecuted = NOT_RUN |
| SAFETY-01 / P1 — legacy và immutability regression | `create_run`, queue/snapshot tests, models nếu thực sự cần enforcement | Chốt đường chạy còn hỗ trợ | Legacy cap/path/mapping được kiểm thử hoặc legacy route bị hạn chế rõ; đổi live config/token sau queue không đổi snapshot/credential dùng; crash/resume không replay; Run #2 giữ nguyên |

Không tự thêm anonymous/invalid-token vào web batch hiện tại: cần ticket scope/budget riêng sau khi chốt configured identities và credential semantics. BFLA tiếp tục workflow disposable riêng; không mở write methods trong planner/HTTP GET này.

## Test inventory và phần chưa xác minh

Đã đọc source tests, chưa chạy test nào trong lượt audit. Các file có sẵn đáng dùng làm nền: `backend/tests/test_openapi_parser.py`, `test_matrix_generator.py`, `test_policy.py`, `test_batch_plan.py`, `test_run_snapshot.py`, `test_workflow_api.py`, `test_batch_runner_idempotency.py`, `test_batch_runner_regressions.py`, `test_web_demo_contracts.py`, `test_web_demo_evidence.py`; `frontend/src/WebDemo.test.tsx`; CLI `tools/authorization-lab/tests/read_only/test_spec_parser.py`, `test_matrix_builder.py`. Test mock/SQLite tạm chỉ chứng minh behavior tương ứng, không chứng minh thực nghiệm đa role hoặc BFLA.

Lượt audit này: source inspection PASS; deployed rendering/API redaction NOT VERIFIED; full R1/R2 acceptance NOT VERIFIED; R6 installability/runtime NOT VERIFIED. R5 vẫn NOT_RUN theo evidence lịch sử, không tạo số liệu mới. Không đánh dấu project fully demo-ready. Đã kiểm tra automation của bot: không có automation liên quan.
