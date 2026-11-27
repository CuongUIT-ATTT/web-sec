# AUDIT-01 — Web demo contracts

Ngày: 2026-11-13. Người thực hiện: T18 OpenAPI Matrix.
Baseline đã kiểm tra: `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`.
Working tree ban đầu chỉ có `?? T18-context-snapshot.zip`, `?? context-snapshot/`; giữ nguyên.
Không thấy AGENTS.md trong repo hoặc các thư mục cha đã kiểm tra. Kế hoạch đã đọc từ `/home/cuong/.openmausbot/attachments/7360d4f9-3db2-460c-8322-b6e100f83310.md`.

## Kết luận

PASS cho inventory tĩnh: API cấu hình, matrix preview, batch queue, runs/results/findings/cancel đã tồn tại. PARTIAL cho hợp đồng demo: policy role/resource scope chưa được UI hỗ trợ; matrix thiếu resolved policy detail; findings chưa nối run/case; evidence owner baseline chưa được lưu đủ cho drill-down. Runtime, browser, tests: NOT_RUN trong audit này; không khởi động ứng dụng/lab, không gọi API, không sửa production source.

GET-only là giới hạn request gửi tới target; browser vẫn dùng POST/PATCH để cấu hình, queue và cancel. Không được bỏ CSRF vì hiểu GET-only là toàn bộ browser API.

## API map theo code

Viết tắt: P=`/api/projects/{project_id}`. GET nghiệp vụ dùng require_admin; POST/PATCH cấu hình/workflow dùng require_csrf (bao gồm require_admin), trừ login. Nguồn guard: `backend/app/core/auth.py:26–36`.

| Luồng | Hợp đồng hiện có | Backend source | Frontend source |
|---|---|---|---|
| Login/logout | POST /api/auth/login `{password}` → `{csrf_token}`; POST /api/auth/logout → 204 | api/routes.py:32–41 | api.ts:24–50; App.tsx:64–66 |
| Project | GET/POST /api/projects; PATCH P `{name,description}` | api/routes.py:44–75 | api.ts:52–54; App.tsx:91–100 |
| Target | GET/POST P/targets; PATCH /api/targets/{id}; POST .../connection-test | api/routes.py:78–136 | api.ts:55–58; App.tsx:103–109 |
| Identity | GET/POST P/identities; PATCH /api/identities/{id}; POST .../verify?target_id= | api/routes.py:139–250 | api.ts:59–62; App.tsx:112–117 |
| OpenAPI | POST P/openapi `{document}` → Operation[]; GET P/operations; PATCH /api/operations/{id} `{selected}` | api/workflow_routes.py:67–96 | api.ts:63–65; App.tsx:120–123 |
| Ownership fixtures | GET/POST P/resource-types; PATCH /api/resource-types/{id}; GET P/resources; POST /api/resource-types/{id}/resources; PATCH /api/resources/{id} | api/workflow_routes.py:99–193 | api.ts:69–74; App.tsx:126–136 |
| Mapping | GET/POST P/operation-resource-mappings; PATCH /api/operation-resource-mappings/{id} `{selected}` | api/workflow_routes.py:206–256 | api.ts:66–68; App.tsx:139–153 |
| Policy | GET/POST P/policies; PATCH /api/policies/{id}; payload operation_id, resource_type_id, decision, identity_id XOR role, optional resource_id | api/workflow_schemas.py:104–119; api/workflow_routes.py:335–392 | api.ts:7,22,75–77; App.tsx:144–153 |
| Matrix | GET P/matrix?operation_id=&resource_id= → case_key,control_type,actor_identity_id,resource_id,policy_status,warnings | api/workflow_routes.py:395–435 | api.ts:11,78; App.tsx:153 |
| Batch preview | GET P/batch-matrix?target_id= → counts, grouped targets, request budget | api/workflow_routes.py:259–313 | api.ts:9–10,80; App.tsx:167–173 |
| Queue | POST P/batch-runs `{target_id}` → Run; single POST P/runs `{target_id,resource_id,operation_id}` also exists | api/workflow_routes.py:316–332,438–476 | api.ts:79,81; App.tsx:173 uses batch |
| Run history/results | GET P/runs newest first; GET /api/runs/{id}/results | api/workflow_routes.py:479–517 | api.ts:12–14,82–83; App.tsx:167–173 |
| Findings | GET P/findings → project aggregate: fingerprint, conclusion, operation, policy id/version, reproduction_count | api/workflow_routes.py:520–534 | api.ts:15,84; App.tsx:171–173 |
| Cancel | POST /api/runs/{id}/cancel → 204; QUEUED→CANCELLED, RUNNING→CANCEL_REQUESTED | api/workflow_routes.py:537–543; workers/queue.py:41–46 | api.ts:85; App.tsx:170–173 |
| Optional external lab | GET P/external-lab-jobs; POST .../read-only-verification; GET /api/external-lab-jobs/{public_id}; POST .../cancel | api/external_lab_routes.py:27–62 | api.ts:16,86–88; App.tsx:156–163 |

Backend source paths trong bảng tính từ `backend/app/`; frontend từ `frontend/src/`.

## Gaps, semantics và rủi ro tích hợp

1. **P0 policy round-trip mất scope:** `App.tsx:149,153` chỉ load identity; submit luôn `role:null, resource_id:null`. Sửa một role policy hoặc resource-specific policy có thể chuyển semantics khi người dùng chọn identity rồi lưu. Backend đã hỗ trợ XOR và kiểm tra cùng project/type (`workflow_routes.py:342–351,375–384`); semantic change tăng version (`385–389`). Cần subject mode identity/role và scope all resources/specific resource, giữ dữ liệu khi edit. Role rỗng hiện chưa bị backend chặn bằng min_length; UI nên trim và chặn rỗng.
2. **P0 matrix chưa đủ expected policy:** DTO `workflow_schemas.py:122–128` chỉ có resolution status; `RESOLVED` không nói ALLOW/DENY/UNKNOWN. Phải dùng cùng resolver backend, không tự suy diễn ở UI. `classification/policy.py:29–84`: identity-specific ưu tiên hơn role; resource-specific ưu tiên trong cùng subject; conflict ở specificity cao nhất chặn; admin không có bypass tự động.
3. **P0 precheck warning không phải kết quả verify:** `workflow_routes.py:423` luôn truyền verified_identity_ids=set(), nên mọi matrix row đều có identity.unverified_precheck kể cả trước đó verify thành công. Hiển thị là preview chưa xác minh cho run, không coi danh tính đã thất bại. Worker xác minh fresh.
4. **P0 case provenance:** preview key `resource:{rid}:actor:{iid}` (`matrix/generator.py:42`), batch result key có prefix `operation:{oid}:...` (`workers/runner.py:255`); single-run key không có operation (`193`). Dùng composite run_id + case_key cho evidence. Khi ghép preview nhiều operation, thêm operation_id vào row/key; không giả định hai key là cùng schema.
5. **P0 findings/evidence thiếu liên kết:** project findings không trả reproduction run/case (`workflow_routes.py:520–534`); `App.tsx:171` nạp findings toàn project khi chọn một run. Không được gắn nhãn toàn bộ findings này là findings của run đang mở. Results có reason_codes và response_metadata nhưng UI chỉ vẽ 4 cột (`App.tsx:173`). Worker metadata chỉ body_length/body_truncated/json_parse_error (`runner.py:193,255`); owner_control_valid, owner HTTP status, comparison summary không được lưu ở đây. Chỉ đọc endpoint mới không thể tái tạo evidence chưa persist; cần quyết định scope lưu dữ liệu redacted trước.
6. **P0 execution state:** `App.tsx:173` ready chỉ kiểm tra plan; không có pending/active guard cho queue, click lặp có thể tạo thêm run. Poll `170` chỉ theo runs[0], interval 1s không có timeout/backoff, nuốt lỗi; latest terminal có thể làm ngừng theo dõi run cũ còn active. Chọn active run và giới hạn polling; cancel 204 chỉ là yêu cầu, không khẳng định mọi request bị dừng ngay. Terminal cancel no-op vẫn có 204 do route bỏ qua bool (`workflow_routes.py:542`).
7. **P1 stale selections/preview:** RunPanel preview effect phụ thuộc projectId/targetId/mappings (`App.tsx:169`), không trực tiếp phụ thuộc resources/identities/policies/operations. Refresh thường thay mappings array nên cần test thay cấu hình thực, không chỉ dựa vào dependency tình cờ. Matrix type/resource selection (`146–148`) và local panel state cần reset khi đổi project/type; async refresh cũ chưa có abort/stale-response guard (`39–62`).
8. **P1 session/config chưa tồn tại:** không thấy GET session/config trong các routers gắn tại `main.py:67–70`; chỉ health public (`63–65`). App khởi đầu authenticated=false; CSRF chỉ nằm trong bộ nhớ JS. Phase 1 giữ login lại khi reload là lựa chọn không cần backend mới; nếu muốn restore session phải định nghĩa endpoint authenticated trả CSRF an toàn. `api.ts:26–39` mất structured validation detail và status, chưa phân biệt 401/403/network.
9. **P1 optional bridge:** disabled queue trả 409 (`external_lab_routes.py:34–35`), list rỗng không đủ biết disabled/unknown. App refreshProject dùng Promise.all gồm external jobs (`39–43`): lỗi optional API có thể chặn cả setup hydration. Cần tách optional failure và capability đọc nếu muốn NOT_CONFIGURED chính xác.
10. **P1 OpenAPI provenance:** parser GET-only (`scanner/openapi/parser.py:8,25–59`), diagnostics/security_mode/path_parameters không được import response persist. Import là additive theo operation_key (`workflow_routes.py:74–79`), không replace/update path cũ; UI cần nói rõ không phải sync spec. Không coi imported operation là policy hoặc vulnerability.
11. **Phạm vi role/cases:** backend web tạo mỗi configured identity một row, dedup/sort IDs (`matrix/generator.py:30–48`); hỗ trợ số danh tính linh hoạt nhưng không bắt buộc 3/5 role. Không sinh anonymous/invalid-token controls tự động. Không gán các controls CLI sang web. Owner fixtures bị ràng buộc cùng project (`workflow_routes.py:161–163`); role admin chỉ ALLOW khi policy tương ứng resolve ALLOW.
12. **Comparison:** không thấy browser comparison/report/evidence export route trong main/3 routers đã đọc. External job summary không tương đương benchmark manual/ZAP/disposable. Để Phase 4, dùng NOT_RUN/BLOCKED đến khi verified artifact contract được duyệt.

## Ticket đề xuất và dependency Phase 1–3

Đây là ownership đề xuất, chưa phải giao lock; Lead phân công trước khi sửa. Không để nhiều bot cùng sửa App.tsx/api.ts.

| Ticket / phase | Owner và file | Dependency | Acceptance |
|---|---|---|---|
| UI-01 / P1 shell | Lead: App.tsx, styles.css, components/pages mới | AUDIT-01 | Giữ các API action hiện có; nav setup/matrix/execution/evidence; loading/empty/error và keyboard; 3 test cũ vẫn PASS |
| API-01 / P1 typed errors | Lead hoặc một frontend owner duy nhất: api.ts | UI-01 interface freeze | Giữ same-origin + CSRF; error có status/code an toàn, 401/403 rõ; không echo bearer; quyết định reload login rõ ràng |
| UI-02 / P2 policies + fixtures | Lead: setup/matrix components sau tách | UI-01, API-01 | Create/edit identity XOR role, resource scope round-trip; UNKNOWN/no-match/conflict tách riêng; owner cùng project; kiểm thử 3 và 5 identities |
| CONTRACT-02 / P2 matrix enrichment | Backend owner do Lead giao: workflow_schemas.py, workflow_routes.py; frontend owner cập nhật api.ts sau backend schema freeze | resolver semantics cố định | Thêm operation_id, resolved decision, policy id/version nullable, owner id; giữ warnings và key compatibility; test no-match/UNKNOWN/conflict/role admin và specificity |
| UI-03 / P2 access matrix | Lead: matrix page | UI-02, CONTRACT-02 | Join identity/role/owner thật; filter/sort/detail; không tự gán policy; reset project/type; case key không collision giữa operations |
| UI-04 / P3 execution | Lead: execution page | UI-03; batch API sẵn có | Preview exact budget; chặn double-submit; queue không coi completed; bounded poll active runs; cancel-requested/terminal/error; chọn run gắn results đúng run |
| CONTRACT-03 / P3 evidence | Backend owner: worker result persistence + workflow result/findings DTO; Evaluator review semantics; frontend owner api.ts sau freeze | Review owner-control Web/CLI; quyết định redacted persisted fields | run_id/case_key → policy version + owner baseline status/validity + comparison facts có nguồn; historical thiếu evidence hiển thị unavailable; không chứa raw body/token. Đây có thể cần thay đổi worker/schema, không chỉ GET endpoint; Lead duyệt scope trước triển khai |
| UI-05 / P3 findings | Lead: evidence page | UI-04, CONTRACT-03 | Run-filter rõ; project aggregates nhãn riêng; reason_codes; không lấy 200 làm BOLA; case links và evidence redacted |
| QA-01 / xuyên P1–3 | QA Evidence: App.test.tsx và tests mới riêng; backend owner viết API tests, QA review độc lập | Từng contract freeze | Policy XOR/edit scope; stale refresh; matrix key/UNKNOWN/conflict; duplicate queue/cancel/poll; redaction; sau đó E2E local được phép mới kết luận demo PASS |

Chuỗi chính: UI-01 → API-01/UI-02 → CONTRACT-02 → UI-03 → UI-04 → UI-05. CONTRACT-03 chạy sau semantics review và phải xong trước evidence acceptance UI-05. Phase 4 capability/comparison không chặn main setup/run, nhưng evidence acceptance không thể tự điền dữ liệu thiếu.

## Verification và handoff

Đã thực hiện: git HEAD/status; đọc plan, App.tsx/api.ts, routers/DTO, resolver, matrix generator, parser, planner, queue và vị trí worker metadata; kiểm kê tên tests/dependency. Không import app vì create_app có DB initialization và lifespan khởi động worker (`main.py:24–38`). Không đọc env/token hoặc snapshot private data.

Test inventory (chưa chạy): frontend App.test.tsx có 3 tests login, external fixed workflow, identity token không prefill; chưa thấy resource/policy/matrix/batch/results/cancel coverage ở file này. Backend có test_workflow_api.py, test_update_api.py, test_policy.py, test_matrix_generator.py, test_batch_plan.py và batch runner suites. frontend/package.json có Vitest/Testing Library; chưa có Playwright dependency, cần chọn/cài riêng nếu E2E được giao. Không tuyên bố bộ test PASS từ việc đọc code.

Handoff Evaluator: gaps 4–5 và CONTRACT-03; giữ policy UNKNOWN khác NO_MATCH, HTTP 200 khác confirmed BOLA. Handoff QA: assertions tại bảng ticket; fixture provenance và 3/5 identities cần runtime evidence riêng. Các con số request phải lấy BatchMatrix API; không tạo sample counters.

Audit không có automation liên quan: kiểm tra danh sách của bot trả không có automation. Chưa xác minh runtime, browser, fixture thực hay API response thực; tất cả NOT_RUN. Chỉ tạo báo cáo này, không commit/push/reset hay sửa các untracked artifacts cũ.
