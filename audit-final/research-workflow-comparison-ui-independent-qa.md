# CMP06/UI — QA độc lập

**PASS regression độc lập trong phạm vi synthetic đã chạy; tổng thể PARTIAL.** T18 QA Evidence, 2026-11-15, Asia/Ho_Chi_Minh (UTC+07). HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`; giữ mọi diff. Không sửa production/tests, không browser/login/lab/runtime/Run #2/DB thật.

## Execution manifest và inventory

Fresh run bắt đầu 2026-11-15T23:41:32+07:00. Node v26.12.1, npm 12.2.1, Python 3.14.8, Vitest 5.0.5, Vite 8.3.5. Không có AGENTS.md tại repo/frontend và các thư mục cha đã kiểm tra. Đã đọc bàn giao UI, QA schema2 trước đó, App/api/tests và validator backend. Fixture UI synthetic trong Compare.test.tsx, không phải receipt cryptographic hợp lệ; backend contract validation được QA riêng ở CMP05, không chạy lại ở lượt này.

| Lệnh fresh | Kết quả |
|---|---|
| `npm --prefix frontend test` | exit 0; 4 files, 44 tests PASS |
| `npm --prefix frontend run build` | exit 0; 17 modules, dist ignored |
| `npm --prefix frontend run lint` | exit 0; thực chất TypeScript noEmit, không phải ESLint |
| `git diff --check` | exit 0 |

Toàn bộ stdout, argv, timestamp và SHA-256 trước/sau trong [cmp06-independent-evidence.json](cmp06-independent-evidence.json). **14/14 hashes khớp**, gồm toàn frontend/src, package/lock, OpenAPI fixture và ownership.csv. Bốn file ownership khớp hash bàn giao. OpenAPI SHA-256 `dfff32264cc1eaf1714a18fe063399664d726d70b437866904e4d8f2f075810b`. Disposable Compose inventory hash lấy sau khi bắt đầu verification: `4436663ddd9327dd65bf3b57250bcb0790869c4822d2fec6eb6361ff37f17372`; không coi đây là hash trước–sau hoặc digest container đang chạy. Không truy cập lab để lấy live digest.

## Test matrix và audit

| Phạm vi | Bằng chứng và nhận định | Verdict |
|---|---|---|
| Case/cohort/execution | cell lọc method/case_id/execution/digest/version; selection độc lập run hiện tại. Test schema1/2 historical COMPLETED và current unexecuted. Backend ObservationSet bắt exact revision, cohort và duplicate; UI tin DTO đã validate. | PASS review + regression đã chạy |
| Project isolation | Project-bound state và key; tests project-scoped GET, late inventory và late detail sau đổi project; không render dữ liệu project cũ. Không thay thế API authorization test. | PASS synthetic |
| Stale bundle/detail | Cleanup flag, digest-bound render; test late response từ bundle cũ không hiện sau chọn bundle mới. | PASS synthetic |
| Pagination | Review vòng offset +=100 đến page.length<100; API limit100/order_by id. Test URL offset100/limit100. **Chưa có test chạy tích hợp vòng 100+1, đúng 100 rồi empty, hoặc lỗi trang thứ hai**. Không snapshot transaction; concurrent append chưa kiểm. | PASS review; regression nhiều trang NOT_RUN |
| Coverage | Đếm COMPLETED của selected execution/cohort; 0/N không là finding zero. Unknown khi thiếu selection/cohort; empty cohort test. Count không lọc version riêng nhưng backend bảo đảm toàn bộ observation đúng manifest/version/revision, không trùng case/method/execution. | PASS theo contract backend |
| Timing/legacy | TIMING_NOT_AVAILABLE; legacy UNLINKED/UNKNOWN/UNVERIFIED; provenance thiếu không tạo conclusion xác định. Tests schema1/2, legacy và empty/error. | PASS synthetic |
| Receipt/redaction | JSX chỉ render allowlist source/hash; không stringify raw object. Test receipt_base64_chunks/raw_body canary không lên DOM. Không chứng minh upstream mọi label đều sạch secret. | PASS synthetic |
| Lỗi tải | Alert cố định, không hiện exception/body; inventory failure/detail digest mismatch không tạo kết quả giả. | PASS synthetic |

Không phát hiện regression failure trong 44 tests. EXECUTION_MISMATCH/NO_EXECUTION_SELECTION có review code nhưng chưa có assertion riêng cho mọi nhánh; cross-cohort mutation cũng chưa là test UI độc lập. Không suy rộng PASS thành coverage đầy đủ các tình huống này. Receipt canary test kiểm text DOM; review JSX bổ sung bảo đảm không gắn receipt vào attribute/HTML.

## Evidence gaps và bước tiếp

CMP06 đạt gate regression đã chạy để Lead tiếp CMP07; chưa phải visual/browser acceptance. Browser E2E **BLOCKED**, không login lại. Tests jsdom/mock API, không OS network sandbox, không phải live integration. Không chạy lab, manual/ZAP/BFLA hoặc 3+/5 roles: **NOT_RUN**. DB provenance proof **UNKNOWN**.

CMP07 cần evidence thực nghiệm có case_id/run_id, fixture/policy, cohort/execution và artifact hashes; đối chiếu manual–T18–ZAP trên cùng cohort, tách execution coverage khỏi truth/evidence coverage, timing có dữ liệu thật, BOLA/BFLA và giới hạn so sánh. Chưa có ground truth thì không tính TP/FP/FN. Cần giữ gate lab/disposable và phạm vi được cấp phép trước khi thực nghiệm. Ngoài ra bổ sung regression pagination nhiều trang và browser acceptance khi được giao; QA lượt này không mở rộng ownership để sửa code/tests.

Automation kiểm 2026-11-15T16:41:17.995Z: bot không có automation, không có monitor cần dừng. Chỉ tạo báo cáo/evidence và cập nhật ba docs trạng thái; không commit/push/reset hoặc xóa evidence.
