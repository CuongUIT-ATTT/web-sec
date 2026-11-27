# AUTOAUTH-QA-06 — independent closure verification

@T18 Lead: **PASS local/synthetic regression; tổng thể PARTIAL.** Kiểm ngày 2026-11-16, giờ Việt Nam (UTC+07). HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`, uncommitted. Không sửa production/tests, không mở persistent DB/Run #2, không write lab/ZAP/commit/push.

| Kiểm chứng độc lập | Kết quả / artifact |
|---|---|
| Full backend | PASS 232 tests, exit 0; check-0.log |
| Frontend | PASS 58 tests / 6 files, exit 0; check-1.log |
| Lint/build/diff | PASS exit 0 từng command; check-2/3/4.log |
| Focused closure/legacy/cancel/cap/evaluator | PASS 66 tests, exit 0; focused.log; nằm trong 232, không cộng thêm |
| Sáu kết luận, thiếu evidence | PASS synthetic regression: partial body/JSON error/timeout/network → INSUFFICIENT_EVIDENCE; pre-dispatch cancel/cap/scope → NOT_RUN; cancellation checkpoints 0/1/4/5/6/24, durable cases/no replay |
| Lịch sử bất biến | PASS DB tạm: test_results_normalize_historical_taxonomy_without_mutation, 8 variants; storage NOT_EVALUATED, snapshot, reason/status không đổi sau DTO projection |
| Mounted browser cancellation | PASS app tạm 18986: select owner case → Queue → Hủy temporary Run #2 → CANCELLED; planned 3, transport 1, responses 1, errors 0, cancelled 1. Case chưa dispatch NOT_RUN / CANCELLED / execution.cancelled |
| Results filters | PASS thao tác cả sáu lựa chọn: NOT_RUN 1 row, năm filter còn lại 0 row trên cancelled run; không suy diễn đã có live sample cho năm kết luận còn lại. filters.json |
| Desktop | PASS hẹp 1280×800, document scrollWidth 1265; browser-observations.json |
| Responsive 390/768/1024/1440 | NOT VERIFIED: mounted browser không có resize/emulation action; resizeTo(390,844) giữ 1280×800. responsive.json |
| Persistent DB / Run #2 | NOT VERIFIED: bị loại khỏi phạm vi; temporary Run #2 không phải persistent Run #2 |
| Manual/ZAP/write-BFLA experiments | NOT_RUN; synthetic regression không thay bằng evidence nghiên cứu |

Manifest closure 6/6 hash khớp trước chạy. Python 3.14.8, Node 26.12.1, npm 12.2.1. Starlette/httpx deprecation warning; không test failure. Lab digest NOT_RUN; synthetic fixture hashes ở inventory.json/fixture-inventory.json. Không load OpenAPI ngoài fixture, không xác minh Docker runtime parity.

Browser trace: case `autoauth:v1:project:1:operation:1:BOLA:resource:1:actor:1` → temporary run 2 → result 1 → `run:2:result:1`, policy revision `c97e3024dcf785687194c5adcb19b0c1a3569c7265dafbc6d901ae8cfd39d3d1`. Evidence thiếu dùng UNAVAILABLE, không có protected body/token trong browser artifact. Fixture DB path ở cancel-environment.json (chỉ DB tạm).

Browser lần đầu login render chưa tải project; mở lại/login rồi thấy fixture. Một eval cú pháp sai và selector Hủy Run #1 không khớp (đó là sentinel completed); Hủy Run #2 thành công, không tạo duplicate run. Những lỗi thao tác không được ghi thành product failure. Browser sáu filter không có case INSUFFICIENT_EVIDENCE thực trong run hủy; positive filter/evidence mapping được chứng minh bằng frontend/backend regression, không gán là browser positive sample.

Commands và exit: execution.json; logs cùng thư mục audit-final/autoauth-qa-06. Không automation đang chạy (list rỗng). App tạm được dừng sau kiểm chứng.

Blocker để Lead chốt: (1) mounted surface cần resize/emulation để nghiệm thu responsive nhiều viewport; (2) owner được giao cần proof bảo toàn persistent DB/Run #2, QA không có scope mở; (3) research owner cần cohort và provenance manual/T18/ZAP thực, write tests cần authorization/preflight riêng. Taxonomy blocker QA-04 đã đóng trong phạm vi local/synthetic. Không đóng toàn bộ R1–R8 bằng regression.
