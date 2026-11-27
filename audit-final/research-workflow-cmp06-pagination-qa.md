# CMP06 pagination — QA bổ sung và bàn giao CMP07/DB

2026-11-15, giờ Việt Nam UTC+07. HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Kiểm hiện trạng và lịch sử trước khi sửa: test cũ chỉ có URL offset, chưa có vòng nhiều trang. Không có AGENTS.md tại ancestor đã kiểm; báo cáo QA trước xác nhận repo không có. Giữ mọi diff của các owner.

**CMP06 pagination PASS regression độc lập; tổng thể PARTIAL.** Chỉ sửa `frontend/src/Compare.test.tsx` và evidence/docs audit-final. Không sửa production. Không runtime/lab/DB thật/login/Run #2; không commit/push/reset/deploy.

## Execution manifest

Node v26.12.1; npm 12.2.1. Bắt đầu tests 2026-11-15 23:58:55 UTC+07, duration 8.63s. Synthetic jsdom/mock API; không phải live runtime/E2E hoặc OS network sandbox. Lab image digest/attestation NOT_VERIFIED. OpenAPI và fixture đóng gói được hash bên dưới, không phải fixture runtime.

- `npm --prefix frontend test -- --reporter=verbose`: exit **0**, **49 tests / 4 files PASS**; log [cmp06-pagination-tests.log](cmp06-pagination-tests.log). Tăng từ 44 lên 49 tests.
- `npm --prefix frontend run lint`: exit **0**; log [cmp06-pagination-lint.log](cmp06-pagination-lint.log).
- `git diff --check`: exit **0**.
- Không chạy lại build: chỉ thay test; build production đã qua gate CMP06 trước. Không nâng kết quả này thành build mới.

## Test matrix

| Case | Kiểm chứng | Kết quả |
|---|---|---|
| CMP06-P01 | 100+1 rows, offsets 0/100, đủ 101 bundle, chọn detail trang sau đúng project/digest, không request dư | PASS |
| CMP06-P02 | Đúng 100 rows rồi empty, offsets 0/100, chọn row cuối, dừng | PASS |
| CMP06-P03 | Trang sau reject: alert UNKNOWN, không công bố inventory nửa chừng, không gọi detail, không lộ lỗi/case giả | PASS |
| CMP06-P04 | Đổi project khi offset100 pending; response cũ full100 không kéo offset200, không trộn inventory hay mất detail mới | PASS |
| CMP06-P05 | Cùng tình huống nhưng trang cũ reject; không alert lỗi cũ lên project mới | PASS |

## Evidence gaps — ticket đề nghị Lead giao ngay

Các ticket dưới đây là danh sách bàn giao, chưa được giao hoặc thực thi bởi QA. Quyền của lượt QA này chỉ bao gồm test/docs; không diễn giải lời yêu cầu hoàn tất thành quyền vận hành lab.

| Ticket | Owner đề nghị / deliverable cụ thể | Phạm vi có thể làm offline | Bước cần quyền tác động lab |
|---|---|---|---|
| CMP07-PLAN-01 | ZAP Comparison + BOLA Evaluator: pin cohort/case revision, fixture/OpenAPI hash, policy version, 3+ roles (ma trận 5 roles riêng), owner/cross/admin/sharing/anonymous/invalid; reviewed truth + artifact refs/hashes, method/execution selections, exclusions và timing plan | Chuẩn bị manifest, worksheet, policy và review từ evidence đã có; không coi planned là executed | Chưa cần lab cho chuẩn bị. Fresh observations phải đợi scope/target/operation/budget/roles được xác nhận |
| CMP07-RUN-01 | Lead + operator: kiểm điều kiện listener/reachability và fixture/role setup hiện tại; tạo execution mới riêng | Đọc approval/recovery reports hiện có; không dùng trạng thái kết nối ngày 13 làm hiện trạng hôm nay | Start/recover/reconfigure listener, thay credentials, seed roles/fixtures, deploy hoặc queue run là tác động lab/runtime; cần ủy quyền cụ thể, giữ Run #2. Quyền E2E target cũ không mặc nhiên cấp destructive writes |
| CMP07-COMPARE-01 | ZAP Comparison: manual–T18–ZAP cùng cohort, bounded receipts/timing, importer schema2 → API/store; QA độc lập bindings/exclusions/metrics | Chuẩn bị commands, allowlist và worksheet; import chỉ khi được giao đúng output/API scope | Chạy request thực phải trong lab được phép. ZAP active chưa được phép; không tự bật. Không suy manual verified từ metadata hoặc tính TP/FP/FN khi truth chưa review |
| CMP07-BFLA-01 | Disposable BFLA: run prepare/execute/extended/teardown mới riêng, BOLA/BFLA và negative controls, evidence request accounting/no replay/cleanup | Review manifest/Compose/image pins, scope và acceptance matrix | Mỗi stage cần operator approval artifact pin digest/run/stage/scope/expiry; execute cap9 và extended cap22 theo contract. Attest loopback/image/mount/Compose trước mutation. Không tự approve; không chạy against shared lab |
| DB-PROOF-01 | Lead giao backend/disposable owner contract sanitized DB provenance: source alias, snapshot scope/schema/version, before/after digest + timestamp, run/stage/project/image/Compose binding, trust limits và unknown/mismatch rejection; QA tests tamper/missing/wrong binding | Thiết kế contract và synthetic tests sau khi Lead giao ownership; chưa sửa production trong lượt này | Thiết kế thuần không cần lab. Không hash/export raw secret DB hoặc suy DB unchanged từ container labels |
| DB-PROOF-02 | Operator + QA độc lập: thu before/after DB evidence theo contract đã review, xác minh isolation/cleanup và artifact hashes | Chuẩn bị checklist/proof verifier sau DB-PROOF-01 | Đọc snapshot DB thật cũng ngoài scope hiện tại; cần quyền đọc target cụ thể, cách sanitized/quiescence. Writes/cleanup chỉ disposable được duyệt. Giữ upstream/Run #2; thiếu proof tiếp tục UNKNOWN |
| CMP07-ACCEPT-01 | QA + Writer: kiểm receipts, reviewed truth/prediction, coverage denominators và timing; cập nhật R1/R4/R5/R8 | Có thể review evidence mới được bàn giao, không cần chạy lại lab | Browser E2E BLOCKED sau từ chối login; không tự xin login lại. Không coi jsdom/mock/API source là Browser E2E |

Dependencies: PLAN → lab gate → fresh read-only comparison; BFLA stage approvals là nhánh riêng; DB contract → authorized collection → verification. Acceptance chỉ sau evidence đã review, không sau source/test PASS.

## Cơ sở bàn giao

Đã đọc contracts/reports: [case manifest](research-workflow-case-manifest.md), [metrics](research-workflow-metrics-exports.md), [receipt schema2](research-workflow-comparison-receipt-contract.md), [UI QA](research-workflow-comparison-ui-independent-qa.md), [approval QA](research-workflow-observations-approval-independent-qa.md), [attestation QA](research-workflow-bfla-attestation-independent-qa.md), [cleanup limitation](research-workflow-bfla-attestation-cleanup.md), [lab authorization lịch sử](web-demo-e2e-authorized-lab.md), và ba docs trạng thái.

Receipt hash/binding không phải attestation nguồn. `TEARDOWN_COMPLETE` chỉ scoped cleanup; `upstream_database_proof: UNKNOWN` vẫn đúng vì chưa có DB metadata contract và evidence. CMP07 manual/ZAP/BFLA, 3+/5 roles NOT_RUN; live runtime không chạy trong lượt này; Browser E2E BLOCKED. Không automation của bot tại kiểm tra 2026-11-15T16:59:09Z.

## SHA-256 trước = sau verification

18/18 artifacts ổn định (snapshot lấy sau edit test, trước chạy suites). JSON đầy đủ: [cmp06-pagination-evidence.json](cmp06-pagination-evidence.json).

| Artifact | SHA-256 |
|---|---|
| `frontend/src/styles.css` | `ceab372e36b742e54b00d59303e5f1bcb881ae0d4dc7a538cb2f514ae0383bed` |
| `frontend/src/main.tsx` | `5f399294fe164659d4b1edd5a28be0af796a2d30231ea67f50f7852272514d93` |
| `frontend/src/App.test.tsx` | `60527da7746bf28bc32a3058aa5ba678204f2303ced7fc378f6362335c8efb98` |
| `frontend/src/Analyze.test.tsx` | `3934c8d31c76bdf7409bb5e9d5573ba96d64fa12dac00fd64c6470085ca0ef07` |
| `frontend/src/test-setup.ts` | `9b328c4843431fa76d8de00008fc159e95f99a840211085ff3b8f25e53d14409` |
| `frontend/src/App.tsx` | `5c06c308c0a7956986274cb8bcb6f583a5c4a1b0e06ebdc1496cb9b10c0177f5` |
| `frontend/src/api.ts` | `9a10fcea01e77f38768b8cceae60e6e337e12d71b081221dc7242b0d99687c38` |
| `frontend/src/vite-env.d.ts` | `65996936fbb042915f7b74a200fcdde7e410f32a669b1ab9597cfaa4b0faddb5` |
| `frontend/src/WebDemo.test.tsx` | `3bae24b565f456dd197bfe1bb95ad60d3494d2800d79fe0020e5c93796eb01f8` |
| `frontend/src/Compare.test.tsx` | `c24881564c0d377262eb6179efaa46af824cd20535339466c107be5e82719035` |
| `tools/authorization-lab/src/authz_lab/fixtures/ownership.csv` | `a799ce97a89a89acb03b543b9a33def3f869c4bb3835e6810c197e14ab41c72f` |
| `tools/authorization-lab/src/authz_lab/fixtures/vampi_spec.json` | `dfff32264cc1eaf1714a18fe063399664d726d70b437866904e4d8f2f075810b` |
| `tools/authorization-lab/src/authz_lab/fixtures/manual_sample_cases.json` | `0ece045d34599487bfbac175e49efc3afce8f2beda4f34f67c41d39817af6eca` |
| `tools/authorization-lab/src/authz_lab/fixtures/zap/imported-context-attestation.example.json` | `7654ef2fe45b931c0f8ccf5181594dfc8363cb2e40caa8c14f564068ac23eddd` |
| `tools/authorization-lab/src/authz_lab/fixtures/zap/allowlist-v2.json` | `6d175ba50ed4f8d80f9cc3ee0ebb06e15d432c75e567671ab49b25b830a9a33a` |
| `tools/authorization-lab/src/authz_lab/fixtures/zap/allowlist-v1.json` | `a73143f1532569bf767d7f851ea18cc343b34ff0e87d0a5c5dc31f993684176f` |
| `frontend/package-lock.json` | `b575f479bbc8beab9b1d9223e49647ac1993da47d117e7be2fd0f2d3884a2d64` |
| `deploy/labs/vampi-bfla-disposable.compose.yaml` | `4436663ddd9327dd65bf3b57250bcb0790869c4822d2fec6eb6361ff37f17372` |
