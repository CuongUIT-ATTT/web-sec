## RESOURCE-ID-01 — 2026-11-25

Implemented controlled resource-ID inspection and saved GET path preview; deployed to localhost:8000 preserving volume. **17 backend + 68 frontend tests PASS**, lint/build/diff-check PASS; isolated authenticated browser save/reload/project-switch/reveal PASS. Live read-only SQL confirms four SSH book IDs/owners/`book_id`; health/route/401 and source/bundle parity PASS. Live authenticated browser NOT_RUN; independent QA pending. No SSH lab requests or new authorization conclusions. **Overall PARTIAL**; R5/real experiments unchanged. Evidence and limitations: [resource ID verification](resource-id-verification-20261125.md).

---

## QA CMP07-ADAPTER-01 — 2026-11-16T00:14:44.073286+07:00

**PASS regression độc lập offline**: 147 tests + 392 subtests; thêm 4 QA probes PASS, wrapper exit 0; 22/22 evaluation hashes trước–sau, 5/5 hashes bàn giao và 12/12 nguồn plan khớp. Caps/baseline/redaction/schema2 đạt phạm vi fake transport. External task cancellation đóng response nhưng không trả receipt. Giao tiếp CMP07-TRANSPORT-01, CMP07-CANCEL-RECEIPT-01 và CMP07-WHOLEBODY-01 với tiêu chí cụ thể trong [QA adapter](cmp07-adapter-independent-qa.md).

**Tổng thể PARTIAL**. HTTP thật/thực nghiệm 3+/5 roles/manual–T18–ZAP/BFLA NOT_RUN; DB proof UNKNOWN; Browser E2E BLOCKED theo trạng thái trước. Không tác động production/tests/lab/runtime/Run #2. Các mục dưới là lịch sử.

## QA CMP06 pagination — 2026-11-15 23:59 UTC+07

**CMP06 pagination CLOSED / PASS regression độc lập**: bổ sung 5 cases trong `frontend/src/Compare.test.tsx` (100+1, 100+empty, lỗi trang sau, stale resolve/reject khi đổi project). **49 tests / 4 files PASS**, test/lint/diff-check exit 0; **18/18 hashes** trước–sau verification khớp. Chỉ test/docs thay đổi, production giữ nguyên. Đây thay giới hạn pagination NOT_RUN trong mục QA CMP06 cũ; Browser/visual chưa nghiệm thu.

**Tổng thể PARTIAL**. Bàn giao ticket cụ thể CMP07-PLAN-01 → CMP07-RUN-01 → CMP07-COMPARE-01; nhánh CMP07-BFLA-01; DB-PROOF-01 → DB-PROOF-02; CMP07-ACCEPT-01. Owner, deliverable, dependency và ranh giới quyền nằm trong [báo cáo pagination và gaps](research-workflow-cmp06-pagination-qa.md). Lead có thể giao chuẩn bị manifest/truth và DB proof contract offline ngay; lab recovery/setup/queue/active ZAP/disposable mutation và thu DB thật cần scope/approval vận hành tương ứng. QA không chạy các bước này, không login/chạm runtime/Run #2. CMP07/3+/5 roles **NOT_RUN**, DB proof **UNKNOWN**, E2E **BLOCKED**. Không automation cần dừng. Các mục dưới là lịch sử.

## QA-CMP05CD — cập nhật mới nhất 2026-11-15T23:36:21.876490+07:00

## Cập nhật QA CMP06/UI — 2026-11-15 23:42 UTC+07

**CMP06 PASS regression độc lập trong phạm vi synthetic đã chạy**: 44 tests/4 files, build/lint/diff-check exit 0; 14/14 hashes trước–sau khớp. Mapping case/cohort/execution, project/stale response, coverage/timing/legacy và receipt canary đã review/kiểm theo [báo cáo QA UI](research-workflow-comparison-ui-independent-qa.md); [execution evidence](cmp06-independent-evidence.json). Pagination PASS review và URL test; vòng nhiều trang/second-page error **NOT_RUN**, chưa coi là regression coverage đầy đủ. Không phát hiện failure trong suite đã chạy.

**Tổng thể PARTIAL**. CMP07 cần thực nghiệm manual–T18–ZAP/BFLA trên cohort có fixture/policy/case_id/run_id/artifact và timing thật; 3+/5 roles **NOT_RUN**, DB proof **UNKNOWN**, Browser E2E **BLOCKED**. CMP06 visual/browser chưa nghiệm thu. Không sửa production/tests hoặc tác động runtime/lab/Run #2/login. Không có automation cần dừng. Mục này thay trạng thái CMP06 chưa QA ở các mục lịch sử dưới đây.

**CMP05-C/D PASS regression độc lập; tổng thể PARTIAL.** Fresh importer/contracts **74 tests + 368 subtests**, backend API/store + comparison/matrix contracts **19 tests**; cả hai pytest exit **0**, wrapper exit **0**. Tổng **93 tests + 368 subtests PASS**. Socket/DNS/process guards, worker no-op, SQLite/temp riêng; **32 hashes trước–sau khớp**. Schema2 receipt binding, original-byte hash, recomputed-digest tampering, schema1 fail-closed, legacy UNLINKED/UNKNOWN, UNVERIFIED, session/CSRF/project isolation/idempotency/reload/corruption regression PASS. Web không import CLI qua review; không sửa production/tests.

Evidence: [QA schema2](research-workflow-comparison-schema2-independent-qa.md), [fresh log](cmp05-independent-run.log), [commands/exits/hashes](cmp05-independent-evidence.json). Không có regression failure. Immutability được kiểm ở application layer, chưa kiểm power-loss/multiprocess thực.

CMP05 API/store **đã nối schema2 và qua QA regression**, thay trạng thái chưa nối ở các mục lịch sử dưới đây. CMP06/UI và CMP07 **chưa nghiệm thu**; provenance DB còn dependency, proof **UNKNOWN**. Thực nghiệm manual/ZAP/BFLA và 3+/5 roles **NOT_RUN**; Browser E2E **BLOCKED**, không login lại. Không tác động lab/runtime/Run #2/DB thật. Automation kiểm: không có automation cần dừng.

## QA-BFLA04 — cập nhật mới nhất 2026-11-15T23:09:57.311027+07:00

**BFLA-04 PASS independent focused synthetic regression; tổng thể PARTIAL.** Fresh disposable **59 tests + 78 subtests**, BFLA05 consumer **19 tests + 24 subtests**, từng exit **0**; tổng **78 tests + 102 subtests PASS**. Socket/DNS/process guards, temp riêng; **23 hashes trước–sau khớp**. Compatibility BFLA02/03/05 PASS trong phạm vi synthetic.

Review exact mount/project/image/Compose digest gate trước mutation, cleanup fixed project/path, failure giữ canary/private directory/receipt, upstream DB **UNKNOWN**. Tests chưa bao phủ từng missing field qua từng public stage hoặc fault-inject mọi điểm cleanup; không claim power-loss/multiprocess/attestation thực. DB provenance/digest còn dependency; cleanup COMPLETE không phải full DB proof.

CMP05-A importer đã QA regression; **CMP05 API/store, CMP06/UI, CMP07 chưa nối/nghiệm thu**. Thực nghiệm manual/ZAP/BFLA và 3+/5 roles **NOT_RUN**; Browser E2E **BLOCKED**, không login lại. Không sửa production/tests hoặc tác động lab/runtime/Run #2/DB. Bot không có automation cần dừng.

Fresh commands/exits, review và SHA-256: [research-workflow-bfla-attestation-independent-qa.md](research-workflow-bfla-attestation-independent-qa.md). Các mục dưới là lịch sử, được thay thế về trạng thái BFLA04 bằng cập nhật này.

---

## QA-CMP05A — cập nhật mới nhất 2026-11-15T23:03:52.336691+07:00

**CMP05-A PASS independent focused regression; tổng thể PARTIAL.** Fresh importer **8 tests + 67 subtests**, case_manifest **10 + 89**, observations **11 + 87**, metrics **6 + 35**, exports **4 + 48**; từng exit **0**, tổng **39 tests + 326 subtests PASS**. Network/DNS/process guards và temp riêng; 13 hashes source/tests/fixtures trước–sau khớp. Không sửa production/tests hoặc chạy disposable.

Đã review exact cohort/revision/execution, hash exact bytes, malformed/limits/canaries, legacy UNLINKED và downstream exclusion khi chưa review truth. HASH_MATCHED không phải attestation; chưa có ground truth thực đã review. Legacy receipt có provenance chưa có positive test riêng; structural labels vẫn cần upstream redaction.

CMP05 **pure importer đạt regression**, còn API/store/persistence chưa nối; CMP06/UI và CMP07 chưa nghiệm thu. BFLA04 đang owner triển khai, ngoài phạm vi QA này. Thực nghiệm manual/ZAP/BFLA và 3+/5 roles **NOT_RUN**; Browser E2E **BLOCKED**, không login lại. Giữ nguyên lab/runtime/Run #2/DB. Bot không có automation cần dừng.

Fresh commands/exits và hashes: [research-workflow-importer-independent-qa.md](research-workflow-importer-independent-qa.md). Các mục dưới giữ nguyên như lịch sử.

---

## QA-BFLA03 — cập nhật mới nhất 2026-11-15T22:59:06.675757+07:00

**BFLA-03 PASS independent focused regression/mock integration; tổng thể PARTIAL.** Fresh disposable **54 tests + 69 subtests**, consumer BFLA05 **19 tests + 24 subtests**, từng exit **0**; tổng **73 tests + 93 subtests PASS**. Chặn socket/DNS/process, temp riêng; 22 hashes source/tests/fixtures trước–sau khớp. Compatibility BFLA02/05 vẫn PASS trong phạm vi synthetic.

Đã review replay/crash/race gates, receipt no-overwrite, 30x single attempt/no retry, extended cap22 và overflow trước transport, sanitized failure marker. Race dùng thread/decorator synthetic; không phải public CLI multiprocess. Cap22 là counter với GET /me, không phải đủ chuỗi extended. Không tuyên bố power-loss durability hoặc automatic crash recovery; operator/filesystem vẫn trust boundary.

BFLA-04 mount/compose/image attestation và cleanup/upstream proof còn thiếu. CMP-05 importer đang triển khai riêng; CMP-05–07/API/UI chưa nghiệm thu. Thực nghiệm manual/ZAP/BFLA và 3+/5 roles **NOT_RUN**; Browser E2E **BLOCKED**, không login lại. Không sửa production/tests hoặc tác động lab/runtime/Run #2/DB. Không có automation cần dừng.

Fresh commands/exits và SHA-256: [research-workflow-bfla-lifecycle-independent-qa.md](research-workflow-bfla-lifecycle-independent-qa.md). Các mục phía dưới giữ nguyên như lịch sử.

---

## QA-CMP04 — cập nhật mới nhất 2026-11-15T22:52:21+0700

**CMP-04 PASS independent focused regression; tổng thể PARTIAL.** Chạy mới `.venv` với network/DNS/process guards và temp riêng: metrics **6 tests + 35 subtests**, exports **4 + 48**, observations **11 + 87**, case_manifest **10 + 89**; từng exit **0**, tổng **31 tests + 259 subtests PASS**. 11 hashes source/tests/fixtures trước–sau khớp; không sửa production/tests, không chạy disposable.

Eligibility/review/validation metadata là assertions upstream, không tự attestation hay xác thực hash artifact thực. Đã kiểm 4 confusion cells, exclusions, zero denominators, exact execution binding và export escaping bằng synthetic fixtures. Chưa có ground truth thực đã review; không dùng kết quả mock làm metrics thực nghiệm.

CMP-05–07/importer/API/UI/orchestration comparison còn thiếu/chưa nghiệm thu. BFLA-03 đang triển khai, ngoài phạm vi QA này; BFLA-04 chưa nghiệm thu. Thực nghiệm manual/ZAP/BFLA và 3+/5 roles **NOT_RUN**; Browser E2E **BLOCKED**, không yêu cầu đăng nhập lại. Giữ nguyên runtime/Run #2/DB/lab. Không có automation cần dừng.

Fresh commands/exits, review và hashes: [research-workflow-metrics-independent-qa.md](research-workflow-metrics-independent-qa.md). Các trạng thái bên dưới là lịch sử.

---

## QA-OBSERVATIONS-APPROVAL — cập nhật mới nhất 2026-11-15T22:46:36.430035+07:00

**Tổng thể PARTIAL. CMP-03, BFLA-02 và producer–consumer BFLA-05 PASS independent focused regression/mock integration.** Chạy mới `.venv` dưới network/DNS/process guards, temp riêng: observations **11 tests + 87 subtests**, case_manifest **10 + 89**, bfla_evidence **19 + 24**, disposable **42 + 57**; từng exit **0**. Tổng **82 tests + 257 subtests PASS**. Hash nguồn/tests/fixtures trước–sau khớp; không sửa production/tests. Kết quả này thay trạng thái pending independent QA trước đó trong đúng phạm vi regression, không phải nghiệm thu thực nghiệm.

`human_observation_verified` chỉ kiểm cấu trúc metadata, không attestation người/artifact/ground truth. Approval là local operator acknowledgement có digest pin, không chữ ký xác thực; one-use theo run/stage, scope/budget và rejected-before-side-effect được kiểm bằng mocks/temp. Producer–consumer proof unknown/mismatch fail-closed; functional tests bypass decorator được phân biệt với test public approval gate.

CMP-04 đang triển khai module riêng, **ngoài phạm vi QA**; CMP-04–07, importer/API/UI comparison và artifact provenance thực còn chưa nghiệm thu. BFLA-03–04 lifecycle/race/crash/attestation/cleanup còn thiếu. R1/R4/R5/R8 vẫn **PARTIAL / chưa nghiệm thu đầy đủ**. Manual/ZAP/BFLA thực nghiệm mới và 3+/5 roles **NOT_RUN**; Browser E2E **BLOCKED** sau khi người dùng từ chối đăng nhập, không yêu cầu lại. Không tác động lab/runtime/Run #2/DB hoặc dữ liệu lịch sử; không có automation cần dừng.

Fresh commands/exits, review và SHA-256: [research-workflow-observations-approval-independent-qa.md](research-workflow-observations-approval-independent-qa.md). Các trạng thái phía dưới giữ nguyên như lịch sử.

---

## QA-MANIFEST-CONSUMER — cập nhật mới nhất 2026-11-15T22:43:49.931646+07:00

**Tổng thể PARTIAL. CMP-02 và BFLA-05 consumer PASS independent focused regression.** CMP-02: **10 tests + 89 subtests**, exit 0; consumer BFLA-05: **19 tests + 24 subtests**, exit 0. Chạy riêng bằng `.venv`, chặn network/DNS/process thật, artifacts tạm, hash nguồn/tests/fixture trước–sau khớp. Đây là regression synthetic, không phải bằng chứng thực nghiệm.

BFLA-05 **producer integration/runner final review vẫn PENDING independent QA**; không chạy disposable suite trong lượt này. BFLA-02 **IN PROGRESS về nghiệm thu**: owner đã báo triển khai/regression, chưa QA độc lập approval/scope/budget. BFLA-03–04 lifecycle/replay/crash/attestation/cleanup còn thiếu. CMP-03 **IN PROGRESS về nghiệm thu**, đã có owner handoff nhưng chưa review độc lập; importer/cohort orchestration và CMP-04–07 chưa nghiệm thu. Không dùng trạng thái missing producer trong cập nhật QA-HARDEN-06 cũ như kết luận nguồn hiện tại.

Thực nghiệm manual/ZAP/BFLA mới và gate 3+/5 roles **NOT_RUN**; R1/R4/R5/R8 chưa nghiệm thu đầy đủ. Browser E2E **BLOCKED** sau khi người dùng từ chối đăng nhập; không yêu cầu lại. Không tác động runtime/Run #2/DB/lab hay dữ liệu lịch sử. Các kết quả cũ phía dưới giữ nguyên như lịch sử.

Fresh command/exit, contract review và hashes: [research-workflow-manifest-consumer-independent-qa.md](research-workflow-manifest-consumer-independent-qa.md).

---

## QA-HARDEN-06 — 2026-11-15T22:27:17.906942+07:00

**Tổng thể PARTIAL; CMP-01/BFLA-01 PASS independent regression.** QA chạy mới bằng `.venv`, chặn socket/DNS/process, artifact tạm: evaluation **35 tests + 4 subtests PASS, exit 0** (chủ động loại consumer BFLA-05); disposable **26 tests + 23 subtests PASS, exit 0**. Hash nguồn/fixture trước–sau khớp. Đây là regression synthetic, không phải thực nghiệm.

**BFLA-05 pending consumer review**, dù owner đã bàn giao; runner chưa xuất đầy đủ baseline/principal/postcondition proof. Importer/cohort comparison và BFLA-02–04 còn thiếu. R1 gate 3+/5 roles, R4 thực nghiệm BFLA, R5 manual/ZAP và R8 benchmark/case alignment chưa nghiệm thu; thực nghiệm mới NOT_RUN. Browser E2E vẫn BLOCKED sau khi người dùng từ chối đăng nhập; không yêu cầu lại. Không tác động runtime/Run #2, DB/lab/network hoặc production source.

Fresh commands, exits, findings, inventory và hashes: [research-workflow-hardening-independent-qa.md](research-workflow-hardening-independent-qa.md). Các mục phía dưới là lịch sử.

## QA-BROWSER-05 — cập nhật từ chối đăng nhập 2026-11-15T22:21:25.360480+07:00

**Tổng thể PARTIAL; authenticated Browser E2E BLOCKED.** Người dùng đã từ chối đăng nhập tại 127.0.0.1. Không còn yêu cầu đăng nhập đang chờ; không yêu cầu lại và không thử cách đăng nhập thay thế. Asset parity PASS là bằng chứng browser ở lượt 22:13, không phải kiểm tra mới trong lượt này.

Tài khoản/alias/role/credential-configured, phân biệt web/lab role, owner, ma trận từng case/policy/version/ALLOW–DENY/coverage, Analyze baseline/reason/provenance và Compare manual/ZAP NOT_RUN/artifact UNAVAILABLE: **NOT_RUN sau đăng nhập**, chưa xác minh giao diện. Synthetic 3 role không đạt gate thực nghiệm 3+/5 roles. Manual/ZAP/BFLA thực nghiệm vẫn NOT_RUN; R1/R4/R5/R8 chưa nghiệm thu.

Khắc phục tối thiểu nếu người vận hành sau này chủ động tiếp tục: đăng nhập trực tiếp tại http://127.0.0.1:18080/ trong Browser tab của Screen panel bằng credential QA đã chỉ định, rồi QA tiếp tục checklist; không gửi secret qua chat. Hiện không đề nghị người dùng thực hiện lại bước đã từ chối.

Lượt này chỉ xác minh HEAD/status và hash evidence đã lưu, cập nhật báo cáo; không đọc credential, không mở browser/đăng nhập, không chạy lại tests, không mutation/queue/lab/ZAP/deploy hoặc tác động runtime/Run #2. Không có automation của bot cần dừng. Evidence bổ sung: [sign-in-declined.json](qa-browser-05/sign-in-declined.json). Các mục bên dưới là lịch sử.

## QA-BROWSER-05 — 2026-11-15T22:13:26.642926+07:00

**PARTIAL.** Browser độc lập mở đúng QA localhost:18080 và xác minh JS/CSS HTTP 200, SHA-256 khớp handoff mới: parity asset **PASS**. Blocker bundle cũ đã gỡ riêng tại QA. Đăng nhập **BLOCKED**: không có saved login, không có đầu vào file credential an toàn; đã chuẩn bị yêu cầu người vận hành đăng nhập trong Browser tab của Screen panel bằng file QA cục bộ, không gửi secret qua chat. Toàn luồng tài khoản → owner → ma trận → Analyze → Compare sau login **NOT_RUN**. Không coi HTTP handoff hay synthetic fixture là Browser E2E/3+ roles thực nghiệm. R1/R4/R5/R8 vẫn chưa nghiệm thu; manual/ZAP/BFLA NOT_RUN, resource edit ngoài package chỉ đọc. Không chạy lại tests hoặc chạm runtime/Run #2. Evidence: [research-workflow-independent-qa.md](research-workflow-independent-qa.md), [browser-verification.json](qa-browser-05/browser-verification.json). Các trạng thái bên dưới là lịch sử.

## QA-WORKFLOW-04 — cập nhật độc lập 2026-11-15 21:57 UTC+07:00

**Tổng thể PARTIAL; regression tích hợp PASS; Browser E2E BLOCKED.** QA chạy mới 107 backend tests (SQLite tạm, worker/dispatcher no-op, network blocked), 34 frontend tests; build/lint/diff-check exit 0. UI Matrix/resource edit, Analyze và Compare đã có implementation và regression; các mô tả chúng còn thiếu source phía dưới là lịch sử.

P1: Browser đang phục vụ asset cũ và container backend có hash khác workspace mới. Browser tới login, không có saved login. Chưa nghiệm thu account/role/owner/matrix/Analyze/Compare thực tế; không tự deploy hay mutation runtime. R1 3+ roles, R4 BFLA, R5 manual/ZAP case alignment và R8 metrics vẫn NOT VERIFIED/NOT_RUN. Cần implementation phục vụ môi trường QA biệt lập; BFLA owner làm thí nghiệm riêng; Writer cập nhật báo cáo theo evidence. Run #2 giữ nguyên.

Bằng chứng, command/exit, hash và checklist: [research-workflow-independent-qa.md](research-workflow-independent-qa.md). Trạng thái này thay thế mô tả source cũ nhưng không thay bằng chứng lịch sử.

## Lead verification — 2026-11-15 FOUNDATION-REG-02

Foundation/resource contract gate: **PASS**. Lead independently reran the exact 85-test suite from research-workflow-foundation-implementation.md with worker/dispatcher no-op and socket connect blocked: **85 passed, 2 warnings in 6.12s; exit 0**. `git diff --check` also exit 0. Reviewed reload test: public identifier is redacted; temporary SQLite retains original identifier, owner, resource type and path parameter after app reload.

R2 backend preview now exposes policy-aware cases with canonical operation/resource/actor keys. This supersedes the earlier “batch only counts” description for source code, not deployed UI. R1–R8 overall remain **PARTIAL**. Frontend resource editing must omit unchanged redacted identifiers; Matrix UI, historical Analyze DTO/field explanation, single-run legacy-key compatibility and case-aligned Compare remain pending. Browser E2E, 3/5 roles and new manual/ZAP/BFLA experiments are **NOT VERIFIED / NOT_RUN** as applicable. No runtime DB, lab or historical Run #2 touched during this verification. No active automation.

## Cập nhật điều phối 2026-11-15 — Phase 1 hoàn tất, Phase 2 đang triển khai

HEAD bdbba9933ca057cb2247c3a1de9b3ee239c452bd; working tree có thay đổi cũ được bảo toàn. Lead đã đọc 5 audit và đối chiếu source planner, matrix generator, DTO/routes, README và nhánh xác nhận disposable DELETE. Audit không phải thực thi test/lab mới. Run #2 giữ nguyên; QA metadata lịch sử PASS, không còn pending. Tổng thể PARTIAL.

| Yêu cầu | Phân loại triển khai | Evidence hiện có / thiếu | Verdict nghiệm thu đầy đủ |
|---|---|---|---|
| R1 đa role | Partially implemented | Run #2: 2 identity, 1 role; thiếu 3+ roles | NOT VERIFIED |
| R2 OpenAPI/matrix | Partially implemented; policy có backend và hiện một phần | Preview đơn có policy; batch chỉ counts; thiếu case contract xuyên luồng | NOT VERIFIED |
| R3 cross-response | Implemented but not fully visible on web | Owner baseline/protected comparison có; thiếu giải thích từng field | NOT VERIFIED |
| R4 BOLA/BFLA | Partially implemented; BFLA blocked by experimental requirements | Run #2 BOLA lịch sử; disposable DENIED_CONTROL không phải exploit; web BFLA NOT_RUN | NOT VERIFIED |
| R5 manual/T18/ZAP | Partially implemented; case alignment missing | Có ZAP artifact lịch sử, chưa nối Run #2; manual worksheet chưa kiểm chứng | NOT VERIFIED |
| R6 reusable tool | Partially implemented | CLI độc lập có code; chưa tái nghiệm thu install/runtime | NOT VERIFIED |
| R7 report/evidence | Partially implemented | Run #2 và QA reports; thiếu traceability hoàn chỉnh và browser mới | NOT VERIFIED |
| R8 bonus comparison | Missing case-aligned web integration | Không đủ provenance để tính TP/FP/FN hoặc timing so sánh | NOT VERIFIED |

Nguồn chính xác và ticket chi tiết: research-workflow-matrix-audit.md, research-workflow-bola-audit.md, research-workflow-bfla-audit.md, research-workflow-comparison-audit.md, research-workflow-qa-audit.md trong cùng thư mục. Các cập nhật cũ phía dưới là lịch sử, không phải trạng thái mới nhất.

Thứ tự ticket: REDACT-01 + MATRIX-01/02 (API foundation) → analysis contract/field evidence → UI Configure/Matrix/Execute/Analyze/Compare → case-aligned comparison → independent QA + browser acceptance. BFLA chỉ thiết kế riêng ở pha này, không execute hoặc mở write trong GET runner. Không tự động ZAP. Không deploy/lab mutation, commit/push, sửa lịch sử hoặc xóa dữ liệu.

Gate sau triển khai: tests unit/integration phù hợp, deterministic UI, redaction canaries, legacy snapshot compatibility, selected GET/mapping/cap/scope/credentials/idempotency/no retry/no redirect regression; browser và thực nghiệm ghi riêng PASS/FAIL/NOT VERIFIED. SUSPECTED chỉ dùng khi có evidence heuristic tường minh, không đổi nhãn lịch sử hoặc nâng HTTP 200 thành confirmed.

# T18 task board

Latest 2026-11-13 21:46 Vietnam: LAB-RECOVER-01 authorized and executed preserving old state. S01 live Browser run #2 completed, 5/5 HTTP responses, zero transport errors. One CONFIRMED_VIOLATION (policy #2 v1 DENY, fresh owner control and restricted-field match), one POLICY_CONSISTENT_CASE. Lead observed GET E2E PASS; overall PARTIAL, independent QA pending, 3/5-role gate unmet, R5/R8 NOT_RUN. See web-demo-e2e-recovered-s01.md. Lab mutation lock released after terminal run; no other mutating runner authorized.

Latest 2026-11-13 21:32 authenticated continuation: revised UI matrix and persisted GET mapping/batch preview verified in Browser. Sign-in and missing mapping blockers resolved for this session. Full E2E BLOCKED by configured nonlocal Tailscale target under local-only scope; no scan queued. Only two identities with role user. R5 NOT_RUN. See web-demo-e2e-new-ui.md.


Latest 2026-11-13 21:32: revised UI/backend deployment PASS with verified asset/source hashes; full E2E BLOCKED by client session restoration and missing batch fixtures. Server session remains valid (browser API 200). See web-demo-e2e-new-ui.md. Earlier runtime-mismatch/login statements below are historical. R5 NOT_RUN.

2026-11-13 21:20 sign-in recheck: authenticated view confirmed; revised-flow E2E BLOCKED by verified served/local asset mismatch. Reload shows login UI; server session expiry is not established. No deployment or lab run. See web-demo-e2e-retry.md. R5 NOT_RUN.


Latest continuation 2026-11-13 21:20 Vietnam: BLOCKED after saved-login rejection on fresh navigation. Initial authenticated page showed old UI and batch-matrix HTTP 422; runtime/source parity unverified. No E2E acceptance; R5 NOT_RUN. See web-demo-e2e-retry.md.
E2E retry 2026-11-13: Lead; BLOCKED at administrator sign-in. Browser works; authenticated flow NOT_RUN. See web-demo-e2e-retry.md. QA-WEB-04-F01 independently passed 15 mock regression tests; F01 closed within that scope. Runtime state-change lock remains unassigned pending authenticated preflight.

Base HEAD bdbba99, 2026-11-13; working tree changes uncommitted.

| Ticket | Owner | Status | Evidence |
|---|---|---|---|
| CONTRACT-02 | OpenAPI Matrix | Implemented | web-demo-contract-implementation.md |
| EVAL-01 | BOLA Evaluator | Implemented | web-demo-evidence-implementation.md |
| API-EVIDENCE-03 | OpenAPI Matrix | Implemented | web-demo-api-evidence-implementation.md |
| UI-WEB-01 | Lead | PARTIAL; independent QA pending | web-demo-ui-implementation.md |
| QA-WEB-04 | QA Evidence | Pending assignment | policy/evidence/run regression tests |

Frontend ownership returned to Lead. QA owns only regression test file and its reports/logs; no production changes without a specific follow-up ticket. Runtime state-change lock: nobody assigned. Preserve snapshot and historical evidence.

Latest 2026-11-13 21:34: user confirmed lab scope; Browser queued run #1. COMPLETED with 5 transport attempts, 0 HTTP responses, 5 errors. Two persisted/UI cases NETWORK_ERROR / NOT_EVALUATED. Host and container TCP checks both connection refused at approved port 5003. E2E PARTIAL/error path PASS; successful live authorization BLOCKED. R5 NOT_RUN; 3/5-role gate unmet. See web-demo-e2e-authorized-lab.md.

Latest SSH diagnosis 2026-11-13: SSH PASS; target address confirmed on host. Port 5003 has no listener; existing S01 credentials expired and server lock is stale. E2E BLOCKED; R5 NOT_RUN. Proposed LAB-RECOVER-01 preserves old state and prepares separate S01 state, restricted listener and replacement web credentials, pending explicit lab state-change approval. See web-demo-ssh-lab-diagnosis.md.


## Independent QA addendum — CMP07 closure 2026-11-16 (T18 QA Evidence)

Giữ nguyên các kết luận và source evidence trước mục này. HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`, dirty/uncommitted. Đã audit → tái lập baseline 161 tests + 392 subtests → sửa 8 findings → retest/full tests → review source cuối. Không còn Critical/High in-scope có thể sửa được xác định mà còn mở.

| Requirement | Implementation / regression | Executed evidence | Independent verdict / giới hạn |
|---|---|---|---|
| CMP07-TRANSPORT-01: bounded GET/caps/redirect/proxy/retry/timeout/cleanup | bounded_http.py; test_bounded_http.py và test_cmp07_closure.py::test_independent_reconciliation | results/cmp07-independent-20261116/lab-closure.json; reconcile-*.json | PASS local loopback; không live target |
| CMP07-CANCEL-RECEIPT-01: cancellation/journal/no-replay | bounded_adapter.py, adapter_journal.py; checkpoint cancel, process kill pending HTTP, recovery lock/ID/fsync tests | evaluation-closure.json; crash-boundaries.json | PASS standalone; counts không phải server receipt, không durable per-response store, cross-layer recovery NOT VERIFIED |
| CMP07-WHOLEBODY-01: size/completeness/UTF8/JSON/403/baseline/policy/redaction | bounded_adapter.py; test_cmp07_closure.py và legacy adapter tests | evaluation-closure.json; failed repro logs trước sửa | PASS local policy-aware comparator/metadata; metadata chưa có consumer/schema2 receipt mới/live truth |
| Regression backend/SQLite và frontend | backend full / tmp SQLite concurrency; frontend unit/lint/build | backend-final.json, persistence-concurrency.json, frontend-{test,lint,build}.json | 170 backend + 49 frontend tests PASS; backend proof không được gán cho CLI journal |
| Browser/live research/DB preservation | mounted browser chỉ login heading; executable mock browser spec chưa chạy | browser.json; cmp07-closure-browser.spec.mjs | Browser NOT VERIFIED, live NOT_RUN, persistent DB proof UNKNOWN; tổng thể PARTIAL |

Evaluation cuối **201 tests + 392 subtests PASS**; toàn lab **367 tests + 531 subtests PASS**. Python compile 168 files, frontend lint/build và diff-check PASS. Không cộng tests focused trùng suite full.

Chi tiết requirement/test/evidence matrix, 8 fixes, reconciliation, trust model, giới hạn và file ownership: [cmp07-closure-independent-qa.md](cmp07-closure-independent-qa.md). Hash index: [cmp07-closure-sha256.txt](cmp07-closure-sha256.txt). Không tác động lab/Run #2/persistent DB/ZAP/BFLA; không commit/push/reset. Lead final independent review chưa được thực hiện trong lượt QA này.


## AUTOAUTH-01 — Authorized redesign, 2026-11-16

Lead verified HEAD bdbba9933ca057cb2247c3a1de9b3ee239c452bd and existing dirty tree. Current user explicitly authorizes local implementation and regression testing. Existing CMP07 local acceptance remains scoped; no new execution evidence is claimed.

First implementation owner: T18 OpenAPI Matrix. Ticket AUTOAUTH-MODEL-MATRIX-01 owns backend project authorization model, additive compatibility migration, reusable policy resolver, matrix/planner and configuration/preview APIs plus corresponding backend tests. Preserve legacy policy resolution and historical snapshots. Implement explicit deny precedence, owner/shared/role rules, unknown policy, explicit operation kind/approval, BOLA actor-resource and BFLA actor-operation rows, stable IDs and policy revisions, complete identity accounting, authorized baseline selection and request budgets. Preview non-GET cases as NOT_RUN; do not enable writes in runner. No frontend, evaluator or CMP07 CLI edits under this ticket.

Required handoff: API/schema contract, exact files changed, independent deterministic counts (at least 3 identities / 2 roles / multiple resources per owner), focused and full backend results, compatibility evidence using temporary SQLite, outstanding blockers. Dependencies: evaluator and UI consume this contract after handoff; independent QA follows implementation. Persistent DB/Run #2/lab untouched; no commit/push/ZAP or destructive execution. Overall PARTIAL.

## AUTOAUTH-WEB-03 — frontend handoff 2026-11-16

T18 OpenAPI Matrix: five-screen default workflow đã nối config/preview/explicit selected GET queue/new authorization results; coverage/exclusions/filter/budget/stale/cancel/progress/traceability và manual/ZAP NOT_RUN. **55 frontend tests PASS**, lint/build/diff-check exit 0. Mounted Browser synthetic fixture: 27 preview cases, explicit 3 selected BOLA/BFLA GET, 8/8 completed requests; hai confirmed + một consistent trong SQLite tạm riêng. Không coi fixture là research evidence. Persistent Run #2 untouched-by-scope; checksum proof NOT VERIFIED. Responsive và real-browser cancellation/stale race NOT VERIFIED; write/ZAP/manual NOT_RUN. **READY FOR INDEPENDENT QA / overall PARTIAL.** Contract/files/commands/hashes/limits: [autoauth-web-03.md](autoauth-web-03.md). Không sửa backend hoặc commit/push.


## AUTOAUTH-QA-04 — independent verification, 2026-11-16

**PASS local regression/synthetic browser; overall PARTIAL.** QA rerun: 221 backend + 55 frontend tests, lint/build/diff exit 0; focused 51 nằm trong backend suite. Deterministic 3 identities/2 roles: 27 cases; probes 3 roles: 27, 5 roles: 65, mọi identity represented. Mounted browser temp app: explicit 3 selected cases, 8/8 responses, results/comparison stable case→run→artifact; stale revision blocks new queue; cancellation during pending request ends CANCELLED with 1/4 requests. Temp sentinel/snapshot/redaction PASS. Hashes exec 56/56, web 24/24; model old manifest 11/13 (2 files superseded by execution ticket), không claim model manifest PASS.

Responsive multi-viewport và persistent DB/Run #2 preservation proof **NOT VERIFIED**; manual/ZAP/write-BFLA **NOT_RUN**. Cancellation DTO uses NOT_EVALUATED outside six filters: taxonomy follow-up. No production edits, persistent access, writes/ZAP or commit/push. Exact evidence/commands/limits: [autoauth-qa-04.md](autoauth-qa-04.md), [execution](autoauth-qa-04/execution.json), [browser](autoauth-qa-04/browser-observations.json), [cancellation](autoauth-qa-04/cancellation.json). This addendum supersedes older browser NOT VERIFIED only for the synthetic workflow exercised here.

## AUTOAUTH-CLOSURE-05 — READY FOR QA, 2026-11-16

T18 BOLA Evaluator sửa taxonomy riêng authorization API/new run: pre-dispatch NOT_RUN, incomplete observed evidence INSUFFICIENT_EVIDENCE; giữ execution_status/reasons, legacy và historical rows/snapshots. Focused **66**, full backend **232**, frontend **58 PASS**; lint/build/diff exit 0. Regression cancellation/cap/partial evidence + UI filters. Handoff: [autoauth-closure-05.md](autoauth-closure-05.md); evidence: ../results/autoauth-closure-05/execution.json. QA độc lập pending; overall PARTIAL. Persistent DB/Run #2 untouched-by-scope, browser not rerun; write/ZAP/manual NOT_RUN; no commit/push.


## AUTOAUTH-QA-06 — 2026-11-16, T18 QA Evidence

**PASS local/synthetic; tổng thể PARTIAL.** QA độc lập: 232 backend + 58 frontend tests PASS, focused 66 nằm trong full; lint/build/diff exit 0. DB tạm kiểm projection lịch sử bất biến, cancelled/cap/scope → NOT_RUN và observation thiếu evidence → INSUFFICIENT_EVIDENCE. Mounted browser temporary run 2 CANCELLED: 1/3 requests, result NOT_RUN/CANCELLED, sáu Results filters hoạt động (NOT_RUN 1 row, còn lại 0). Taxonomy blocker QA-04 đã đóng local. Responsive nhiều viewport **NOT VERIFIED**: actual 1280×800, resizeTo không đổi; không có mounted resize action. Persistent DB/Run #2 **NOT VERIFIED**, manual/ZAP/write-BFLA **NOT_RUN**. Không claim research acceptance toàn bộ R1–R8. Commands/exits/artifacts và blocker: [autoauth-qa-06.md](autoauth-qa-06.md), [execution](autoauth-qa-06/execution.json), [browser](autoauth-qa-06/browser-observations.json), [filters](autoauth-qa-06/filters.json), [responsive](autoauth-qa-06/responsive.json). Không production edits/persistent access/lab writes/ZAP/commit/push.


## MAINWEB-DEMO-07 — QA độc lập, 2026-11-16

**PASS web chính Docker/local synthetic; tổng thể PARTIAL.** QA chạy lại 6 backend +
5 frontend focused tests, production Compose build/up trên project/volume mới
`t18-mainweb-demo07-qa`, độc lập với production. Browser empty state → Nạp dữ liệu
mẫu → tự chọn project PASS; explicit API 12 cases GET và Browser 2 cases
BOLA/BFLA → Results PASS. Nạp lại giữ operator target edit, sentinel và exact run
snapshot/results; không autoqueue. Auth/CSRF, disabled/network-error recovery PASS.
Source 13/13, handoff artifacts 26/26 và image source 5/5 hashes khớp. Hai containers
QA đã dừng và xác nhận exited; volume/evidence giữ nguyên.

Fixture 3 identities/**2 role** không chứng minh gate 3/5 role; responsive nhiều
viewport và persistent DB/Run #2 **NOT VERIFIED**; manual/ZAP/write-BFLA **NOT_RUN**.
R1–R8 không được nâng thành full research acceptance. 238 backend + 60 frontend là
full-suite evidence của người triển khai đã đối chiếu, không phải full rerun QA.
Không production edits/persistent access/restart runtime hiện hành/commit/push.
Chi tiết commands/exits và R1–R8: [mainweb-demo-07-qa.md](mainweb-demo-07-qa.md);
artifacts: `results/mainweb-demo-07-qa/`, execution.json và artifact-hashes.json.


Cập nhật 24/11/2026 — SSH-SEED-BUTTON-01: nút nạp cấu hình SSH đã áp dụng web 8000; 10 backend + 6 UI tests và build đạt. Xem ssh-seed-button-20261124.md. Chưa QA độc lập/chưa xác minh runtime lab; không thay verdict R5 hay nghiệm thu tổng thể.
