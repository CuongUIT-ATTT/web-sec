# QA độc lập — audit workflow nghiên cứu R1–R8

Ngày 2026-11-15, khoảng 14:58–15:02 UTC+07:00. Root mọi đường dẫn tương đối: `/home/cuong/Dự án/Bảo mật web/Project`.

## Phạm vi và execution manifest

Chỉ audit source/test và báo cáo lịch sử; không chạy suite, Browser, DB, worker, lab, queue, deploy, ZAP hay BFLA. Chỉ tạo `audit-final/research-workflow-qa-audit.md`; không sửa production/tests, commit/push/reset hoặc xóa. Run #2 và mọi snapshot được bảo toàn vì không truy cập runtime. Không đọc credentials, raw response hay marker. Đã tra lịch sử QA để tiếp nối audit cũ.

HEAD thực tế `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Git status ban đầu có modifications workflow_routes.py, workflow_schemas.py, evaluator.py, runner.py, App.tsx, api.ts, styles.css; untracked audit-final/, context-snapshot/, archive và test web demo. Chúng là baseline chưa commit, không gán thay đổi đó cho audit này. Không có AGENTS.md trong danh sách file tìm được bằng rg ở workspace.

Toolchain quan sát: Python 3.14.8, Node v26.12.1, npm 12.2.1, Git 2.56.0; frontend dùng Vitest/jsdom, React Testing Library; backend pytest/TestClient. Phiên bản package thực cài chưa kiểm chứng. Không đọc container hiện tại. Lab digest và OpenAPI runtime SHA-256: NOT VERIFIED. Báo cáo QA lịch sử ghi web image sha256:ecabf68c551ec31c29df6cee7f22db9d164753ead1eb1e61d7e83147d3b47f5d; đây không phải lab digest hiện tại.

Fixture repository được hash lại: `tools/authorization-lab/src/authz_lab/fixtures/vampi_spec.json` = `dfff32264cc1eaf1714a18fe063399664d726d70b437866904e4d8f2f075810b`; `ownership.csv` cùng thư mục = `a799ce97a89a89acb03b543b9a33def3f869c4bb3835e6810c197e14ab41c72f`. Không coi fixture repository là input runtime đã chứng minh.

## Ma trận nghiệm thu

Tên R1–R8 theo `audit-final/requirements-traceability.md`; không tự định nghĩa lại requirement từ tên phase. Verdict dưới đây là gate đầy đủ của requirement, không phủ nhận capability từng phần. FAIL chỉ dùng cho thiếu sót nhìn thấy trong source; NOT VERIFIED dùng khi thiếu bằng chứng thực thi.

| Requirement | Phân loại triển khai | Source chính | Bằng chứng thực thi đã có | Gap / việc còn lại | Verdict đầy đủ |
|---|---|---|---|---|---|
| R1 đa role | Một phần | backend/app/api/workflow_routes.py; backend/app/scanner/classification/policy.py; frontend/src/App.tsx | Run #2: hai identity cùng một role; QA metadata lịch sử | Chưa đủ tối thiểu 3 roles; profile 5 roles chưa thực nghiệm; anonymous/invalid và admin-policy cần cohort rõ | NOT VERIFIED |
| R2 OpenAPI × role × owner × policy | Một phần; resolver đã có và UI đơn hiện một phần | backend/app/scanner/openapi/parser.py; backend/app/scanner/matrix/generator.py; backend/app/services/batch_plan.py; workflow_routes.py; App.tsx | Lead ghi browser matrix/mapping; Run #2 không chứng minh matrix đa role | Batch preview chỉ counts/targets; không row-level expected decision/case IDs; key đơn khác batch; thiếu coverage/skips | FAIL |
| R3 đối chiếu response | Backend có, web hiện một phần; đã demo phạm vi hẹp | backend/app/scanner/classification/evaluator.py; backend/app/workers/runner.py; workflow_schemas.py; App.tsx Evidence | Run #2 valid owner control + protected-field equality theo QA persisted metadata | UI thiếu danh mục protected pointers và từng field result, actor/owner role/category; thiếu nghiệm thu controls đầy đủ | NOT VERIFIED |
| R4 BOLA/BFLA | BOLA một phần đã demo; BFLA độc lập chưa hiện web, bị chặn điều kiện thực nghiệm | evaluator.py; runner.py; tools/authorization-lab/src/authz_lab/disposable/; tools/authorization-lab/src/authz_lab/evaluation/bfla_evidence.py | Run #2 một CONFIRMED_VIOLATION, một POLICY_CONSISTENT_CASE; BFLA audit khác ghi historical DENIED_CONTROL | Chưa mapping SUSPECTED; BFLA web NOT_RUN, không có quyền thêm write vào GET runner; cần approvals/lifecycle riêng | NOT VERIFIED |
| R5 manual/T18/ZAP | CLI có nhưng chưa nối web; case alignment thiếu | tools/authorization-lab/src/authz_lab/evaluation/comparison.py; verification/manual_verifier.py; zap/runner.py; App.tsx comparison | Artifact lịch sử được bot comparison báo cáo; QA này không tái chứng thực; không có comparison Run #2 | Bảng web tĩnh NOT_RUN, không case-aligned provenance/worksheet; không biến NOT_RUN thành negative | FAIL |
| R6 reusable tool | Một phần; CLI/web riêng, backend safeguards có source/tests | backend/app/services/run_snapshot.py; batch_plan.py; backend/app/scanner/execution/{scope,http_client}.py; pyproject.toml; tools/authorization-lab/pyproject.toml | Regression lịch sử, không có fresh install/runtime audit này | Cần clean-install/smoke độc lập, no web→CLI import/execution và snapshot history regression | NOT VERIFIED |
| R7 báo cáo/evidence | Một phần; allowlist API và report đã có, traceability UI thiếu | workflow_schemas.py ResultEvidenceView; workflow_routes.py _run_view/results/findings; backend/app/services/findings.py; frontend/src/api.ts | QA Run #2 metadata join finding→reproduction→result→run có sẵn | RunView trả nguyên snapshot; UI resource.external_id chưa redact; chưa fieldwise explanation/reproduction drilldown; không đủ export acceptance | FAIL |
| R8 comparison mở rộng/timing | CLI có, chưa visible web; benchmark đầy đủ thiếu | tools/authorization-lab/src/authz_lab/evaluation/{comparison,timing}.py; App.tsx comparison | Chưa có bộ cohort/case provenance được QA xác minh cho Run #2 | Thiếu ground truth, TP/FP/FN denominator và timings comparable; không lấy counts mặc định làm số liệu | NOT VERIFIED |

Phân loại “đã triển khai và đã demo” chỉ áp dụng phần GET/BOLA hẹp của R3/R4, không toàn R1–R8. “Đã triển khai nhưng chưa visible” áp dụng phần CLI comparison/disposable và chi tiết reproduction backend; không suy backend missing từ UI.

## Bằng chứng Run #2 và giới hạn

Đọc trực tiếp cả hai report, hash lại khớp:

- `audit-final/web-demo-e2e-recovered-s01.md`: SHA-256 `59553be792db0823443b139d03ec6768ba2748bfcbe6cc952cd925553fa7ea29`.
- `audit-final/web-demo-e2e-recovered-s01-qa.md`: SHA-256 `52ea1decbd1892ba0a50b018f9b07e9781589f08e2a9c978d478b7d4aff3a5b8`.

Browser do Lead quan sát 2026-11-13 khoảng 21:46 giờ Việt Nam. QA lịch sử đã xác minh persisted metadata khoảng 21:47–21:49. Run #2 COMPLETED, planned/transport/responses=5/5/5, errors=0; hai case `operation:1:resource:1:actor:1` và `operation:1:resource:1:actor:2`. Case actor 1 có DENY policy #2 v1, owner valid, restricted-field match, CONFIRMED_VIOLATION; actor 2 ALLOW #1 v1, POLICY_CONSISTENT_CASE. Finding #1/reproduction #1 liên kết result #3/run #2. Không suy từ HTTP 200. DB timestamps lịch sử không offset, không tự coi là UTC. Audit này không tái query DB hoặc xác minh freshness/body/network capture. Token/lab còn hoạt động hôm nay không được giả định.

Run #1 NETWORK_ERROR là bằng chứng lỗi lịch sử, giữ nguyên; không overwrite bằng Run #2. R5 cho run này NOT_RUN, R8 chưa chạy; 3/5-role chưa đạt. Historical BFLA/ZAP không được gán sang Run #2.

## Inventory test và missing regression

Đã inventory tên test, đọc trực tiếp WebDemo.test.tsx, vertical_slice_integration.py, contract fixture và source liên quan; không tuyên bố đã đọc mọi dòng của mọi test.

| Loại | File / behavior sẵn có | Giá trị và giới hạn |
|---|---|---|
| Unit | backend/tests/test_{openapi_parser,matrix_generator,policy,evaluator,json_pointer,batch_plan}.py | GET/security override; owner/cross; policy specificity/conflict; 200 denial/403 leakage; baseline guards. Source không phải suite PASS |
| API/persistence | test_web_demo_contracts.py; test_web_demo_evidence.py; test_update_api.py; test_finding_persistence.py; test_persistence_serializers.py | Typed allowlist, malformed metadata, sharing, no admin bypass, project isolation, policy versioning/idempotency. Contract fixture bypass auth và worker, không chứng minh deployed security |
| Runner safety | test_run_worker.py; test_run_snapshot.py; test_batch_runner_idempotency.py; test_batch_runner_regressions.py; test_worker_queue.py; test_run_limit.py; test_http_client.py; test_scope.py | Queued token rotation, exact targets/baselines, cancellation/crash/no replay, caps/accounting, no redirect; cần chạy lại sau thay đổi |
| Deterministic UI | frontend/src/WebDemo.test.tsx; App.test.tsx; frontend/vite.config.ts | vi.mock toàn api + jsdom; policy XOR, matrix fields, run/project stale responses, duplicate queue/cancel. Synthetic identity_count=3 không phải runtime 3 roles |
| Integration HTTP | backend/tests/test_vertical_slice_integration.py | ThreadingHTTPServer localhost + FastAPI TestClient, 2 identity/1 reader role; tên “survives_browser_reload” không có Browser. Có tạo lab/queue nên không chạy trong assignment này |
| Disposable/comparison | tools/authorization-lab/tests/{disposable,evaluation,zap,verification}/ | Inventory contract/lifecycle tests; dùng audit chuyên trách để đề xuất, không coi mock là experimental evidence |

Không thấy Playwright config/suite qua rg --files; frontend package.json chỉ có vitest, không có browser E2E script. Không kết luận browser không khả dụng; chỉ chưa dùng trong scope audit.

Evidence regression lịch sử: `audit-final/web-demo-integration-qa.md` ghi backend 139 passed và frontend 9 passed/1 failed (F01); `audit-final/web-demo-stale-response-recheck-logs/tests-final.log` sau đó ghi 15 passed/2 files. Không giữ FAIL cũ như trạng thái hiện tại, cũng không nâng log sau thành fresh PASS hôm nay. `web-demo-integration-qa-logs/runtime-acceptance.md` là historical gate, cần đọc cùng diễn tiến; không sửa file đó.

Missing coverage ưu tiên: canonical case ID xuyên preview/run/result/finding/compare; đầy đủ 3/5 roles; redaction toàn bộ run DTO/snapshot/resource selectors và rendered DOM; per-field protected evidence chỉ alias/boolean; SUSPECTED mapping không overwrite lịch sử; HTTP 204/200 generic không confirmed; anonymous/invalid là identity mode riêng chứ không bỏ token guard ngầm; matrix response cũ sau switch project; comparison missing/invalid provenance; historical artifact tamper/hash; browser cancellation/duplicate queue/no replay.

## Ticket QA đề xuất và dependencies

| Ticket | File ownership đề xuất | Dependency | Acceptance cụ thể |
|---|---|---|---|
| QA-RW-01 P0 — case contract | backend/tests/test_batch_plan.py; test_web_demo_contracts.py; test_workflow_api.py | Matrix canonical ID + row preview ticket của Lead | Cùng config sinh cùng ID; khác operation không collide; preview/queued snapshot/result/finding cùng case; DENY/ALLOW/UNKNOWN/conflict/version/coverage/skips rõ; disabled GET/non-GET/foreign resource không được mở rộng |
| QA-RW-02 P0 — redaction/history | test_web_demo_contracts.py; test_run_snapshot.py; test_update_api.py; frontend/src/WebDemo.test.tsx | Sanitized DTO và aliases | Synthetic canary token/body/resource identifier không xuất hiện trên tất cả response DTO, DOM, error/export; internal immutable snapshot không bị sửa để redact; sửa policy/credential chỉ ảnh hưởng run mới; Run #2 metadata/hash snapshot không đổi |
| QA-RW-03 P1 — explanation/conclusions | test_evaluator.py; test_web_demo_evidence.py; WebDemo.test.tsx | Analysis DTO/mapping ticket | Positive DENY+principal+valid owner+meaningful protected equality confirmed; sharing ALLOW consistent; invalid owner/principal INVALID_TEST; unknown/conflict/missing evidence không confirmed; 200/204/generic/length/empty/null/type mismatch không confirmed; 403 leak vẫn đánh giá evidence; UI field aliases/checks/reason/provenance không lộ values; SUSPECTED không fabricate historical data |
| QA-RW-04 P1 — cohort roles | backend/tests/test_matrix_generator.py; test_policy.py; test_web_demo_evidence.py | Fixture/policy manifest 3 và 5 roles, owner/cross-user peer identities | Assert actual distinct roles, same-role cross-user và cross-role, admin explicit ALLOW/DENY/no match, sharing, anonymous/invalid fail closed; expected case set/coverage/hash deterministic; tests không gọi lab thật |
| QA-RW-05 P1 — comparison provenance | tools/authorization-lab/tests/evaluation/test_comparison.py; frontend/src/WebDemo.test.tsx; backend/tests/test_web_demo_contracts.py | Case-aligned importer/schema/API | Same case/run/fixture/policy/hash joins; missing manual/ZAP NOT_RUN, failure/error không TN; absent timings/counts null; mismatch/quarantine; TP/FP/FN chỉ evaluated ground truth; import không tự chạy CLI/ZAP/BFLA |
| QA-RW-06 P1 — Browser acceptance | file mới frontend/e2e/research-workflow.spec.ts nếu Lead chọn Playwright; audit evidence path giao riêng | 01–05 + deployed build hash + authenticated approved lab + role fixtures | Configure→Matrix→Execute→Analyze→Compare trên browser thật; selected GET/caps snapshot; stable case links; hai positive/negative controls và invalid case; refresh preserves; duplicate queue/cancel; no replay after terminal; capture redacted screenshots + step log; 3 roles tối thiểu, 5 roles profile riêng |
| QA-RW-07 P0 trước BFLA experiment — isolation | tools/authorization-lab/tests/disposable/test_{preflight,runner,manifest,teardown}.py; tests/evaluation/test_bfla_evidence.py | BFLA correctness/safety tickets + approval riêng | Không write từ web runner; no redirects/retries; explicit approval/preflight/attestation, disposable localhost, unique run/lifecycle, request ledger, postcondition distinguishes denied vs network failure/absence; cleanup receipt; no receipt=NOT_RUN/NOT VERIFIED, không CONFIRMED từ HTTP200 |

Đề xuất không tạo tests mirror implementation. Các assertions trên chặn policy false-positive, identity leakage, cross-run evidence mix và unsafe execution. Lead giao ownership tách biệt trước khi edit để không đụng file bot khác.

## Kế hoạch chạy và gates nghiệm thu

1. Sau implementation, inventory lại HEAD/status/toolchain, exact selected test argv, start/end ISO timezone, exit code, fixture/OpenAPI SHA và deployed/lab digests. Regression isolated: pytest backend trừ test_vertical_slice_integration.py, tắt cache/bytecode nếu cần; Vitest + TypeScript. Chỉ báo PASS sau exit 0 và kiểm logs; không build/runtime mutation trong audit này.
2. Chạy HTTP integration localhost trong pha được giao riêng; báo riêng với mocks. Không gọi nó Browser E2E. Không dùng total suite count từ report cũ cho checkout mới.
3. Browser thật: ghi browser build/runtime fingerprint và observed steps, stable IDs, policy versions, alias-only evidence. Trước queue cần authorized lab/fixtures/current credentials; không tái dùng token expired theo giả định. Kiểm persisted metadata độc lập, không đọc raw body. Giữ run lịch sử; không reset DB. Không hứa 3 roles PASS nếu mới có 2 identities/1 role.
4. Experimental BFLA cần workflow/approval riêng, chưa chạy thì NOT_RUN. ZAP/manual cohort có provenance riêng; không tự chạy khi mở Compare; unexecuted cells luôn NOT_RUN. Chỉ so timing khi cùng cohort và phương pháp đo ghi rõ.
5. Gói acceptance cuối cần R1–R8 source paths + executed artifacts + case/run/fixture/policy/hash + gaps + PASS/FAIL/NOT VERIFIED. Các file runtime-acceptance.md, evidence-gaps.md, execution-manifest.md chỉ tạo/cập nhật khi được giao ownership trong pha test; assignment hiện tại chỉ cho một báo cáo này. Không tuyên bố demo-ready khi còn gate thiếu.

Automation QA đã kiểm tra: không có, không cần pause. Kết luận: audit source hoàn thành; unit/regression/live/Browser mới đều NOT_RUN trong lượt này; toàn demo PARTIAL, nghiệm thu R1–R8 chưa đạt. Không cần thêm input cho Phase 1.
