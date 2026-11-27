# CMP06/UI — bàn giao triển khai

PASS regression người triển khai; chờ QA độc lập, tổng thể PARTIAL. HEAD bdbba9933ca057cb2247c3a1de9b3ee239c452bd. Đã đọc README, contract receipt schema2, backend validator/routes/store và QA CMP05-C/D mới nhất; không có AGENTS tại repo/parents/frontend đã kiểm tra. Giữ mọi diff hiện hữu.

## Thay đổi

Chỉ sửa bốn file frontend được giao và tạo báo cáo này. App.tsx thêm BundleComparison trong ComparePanel, giữ phần run cũ; api.ts thêm GET inventory phân trang 100 và GET detail theo project/digest, DTO schema 1/2; styles.css giới hạn wrap/hash và table scroll theo layout có sẵn; Compare.test.tsx thêm regression synthetic. Không sửa backend hoặc docs trạng thái QA.

Bundle chọn riêng với run hiện tại; cohort và execution selection lấy từ persisted bundle, không suy latest. Table case × MANUAL/T18/ZAP; chỉ nối observation đúng case/cohort/selected execution. Missing observation hiển thị NOT_RUN cùng NO_OBSERVATION/EXECUTION_MISMATCH/NO_EXECUTION_SELECTION. Source recorded không thành attestation; conclusion chỉ ACCESS_ALLOWED/ACCESS_DENIED khi COMPLETED có provenance, còn lại UNKNOWN (không kết luận BOLA). Legacy UNLINKED/UNKNOWN/UNVERIFIED, metadata source/hash allowlisted. Không render receipt bytes/base64 hoặc raw object; không thêm nút chạy ZAP/BFLA.

Coverage hiển thị count COMPLETED trong execution được chọn / cohort; đây là observation coverage, không phải evidence/truth coverage. 0/N chỉ là đếm array có selection và cohort, không phải finding zero hoặc proof đã chạy. Không selection/cohort rỗng hiển thị UNKNOWN, không percentage giả. Schema2 không mang timing/reason vận hành nên timing TIMING_NOT_AVAILABLE, reason vắng observation là reason UI dẫn xuất có tên rõ; không bịa duration, TP/FP/FN hay số finding.

Stale async: cleanup flag riêng cho inventory/detail; project-bound state và digest-bound render; đổi project reset chọn bundle, key parent cô lập; đổi bundle ẩn detail ngay. Error chỉ thông báo cố định, không đưa exception/body lên UI. Backend chịu trách nhiệm validation/hash/binding; UI không tự xác minh cryptographic attestation.

## Verification cuối

### `npm --prefix frontend test`

Time 2026-11-15T23:39:59.454306+07:00; exit 0.

```text

 RUN  v5.0.5 /home/cuong/Dự án/Bảo mật web/Project/frontend


 Test Files  4 passed (4)
      Tests  44 passed (44)
   Start at  23:40:00
   Duration  6.13s (tests 46%, environment 41%, transform 5%, setup 4%, import 3%)


```

### `npm --prefix frontend run build`

Time 2026-11-15T23:40:06.597564+07:00; exit 0.

```text
vite v8.3.5 building client environment for production...
transforming...
✓ 17 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.52 kB │ gzip:  0.33 kB
dist/assets/index-DpHb621v.css    7.77 kB │ gzip:  2.48 kB
dist/assets/index-e4GGCM8H.js   272.38 kB │ gzip: 82.18 kB

✓ built in 269ms

```

### `npm --prefix frontend run lint`

Time 2026-11-15T23:40:07.919255+07:00; exit 0.

```text

```

### `git diff --check`

Time 2026-11-15T23:40:08.635904+07:00; exit 0.

```text

```

Tests synthetic gồm historical COMPLETED/current unexecuted; schema1/schema2; legacy; missing provenance/timing; receipt canary không lên DOM; empty cohort/inventory; inventory error/detail mismatch; stale detail khi đổi bundle/project, stale inventory khi đổi project; GET paths. Giữ regression compare run/policy cũ và toàn bộ Analyze/WebDemo tests. Lần đầu test exit 1 (43 tests: 1 failed do exact matcher HASH_MATCHED xen thẻ), sửa regex matcher; lần tiếp 44 PASS. Bản cuối kết quả bên trên. Không browser/lab/network thật/runtime/DB/Run #2/Docker/login/deploy/commit/push/reset/xóa evidence. Test jsdom mock API; không OS network sandbox, không thay thế API integration hoặc E2E. Build tạo dist ignored theo cấu hình có sẵn.

## Hash ownership

Report mới không có hash trước; hashes source trước sửa và sau sửa dưới đây. Hash trước/sau verification cuối bằng nhau cho cả bốn file.

- `frontend/src/App.tsx`: trước sửa `f972ce365e33f206ce984dde3d65a5939ba67a3934a828e21b9704568c5e7d6b`; sau sửa `5c06c308c0a7956986274cb8bcb6f583a5c4a1b0e06ebdc1496cb9b10c0177f5`; verification unchanged=True.
- `frontend/src/api.ts`: trước sửa `0bd48920eb5d02386f58e20106a3f700fb5107862bb488f077b20b77b56e1e79`; sau sửa `9a10fcea01e77f38768b8cceae60e6e337e12d71b081221dc7242b0d99687c38`; verification unchanged=True.
- `frontend/src/styles.css`: trước sửa `e4c75bed000953f918e308e159c871bae638b742b6b6ffacf7273a6c0d3f86fc`; sau sửa `ceab372e36b742e54b00d59303e5f1bcb881ae0d4dc7a538cb2f514ae0383bed`; verification unchanged=True.
- `frontend/src/Compare.test.tsx`: trước sửa `4911200c5431380add0397ffd3f858ca871244bb014ad35476ab0ef0254c89ed`; sau sửa `7e1bd6021a0e1e2759ea63951cc98320f4c08d40e22df4cd9c80407c231b4eb2`; verification unchanged=True.

## Giới hạn và handoff QA

CMP07 thực nghiệm NOT_RUN; 3+ roles NOT_RUN, DB proof UNKNOWN; Browser E2E BLOCKED, không login lại. Visual/browser finish gate trong design-taste-frontend chưa chạy vì assignment cấm browser; không claim visual acceptance. Dùng skill cho tính nhất quán layout hiện có, không mở rộng ownership theo scaffold/gate. QA cần review độc lập mapping/coverage, pagination và synthetic fixtures cùng API đã QA; fixture UI cố ý ngắn và không là receipt/schema cryptographic fixture hợp lệ. Chưa kiểm mạng thật, multiprocess hoặc hiệu năng inventory lớn. API inventory không có total/snapshot; paging không là snapshot transaction.

Automation kiểm 2026-11-15T16:39:05.312Z: bot không có automation; không có monitor cần dừng. Không gửi secret hay raw receipt lên báo cáo/UI. Báo cáo chỉ đánh giá CMP06 regression, không kết luận dự án hoàn tất.
