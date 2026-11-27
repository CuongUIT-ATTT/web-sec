# MAINWEB-DEMO-07 — mẫu tích hợp web chính Docker

Ngày: 2026-11-16. HEAD lúc bắt đầu: `bdbba99`; repo đã dirty trước ticket.
Không có AGENTS.md tại repo, các thư mục cha đã kiểm tra hoặc các thư mục triển khai liên quan.

## Kết quả

**PASS triển khai và kiểm thử local/synthetic, chờ QA độc lập.** Không phải nghiệm thu
nghiên cứu T18 toàn bộ. Chưa triển khai/restart Compose đang dùng, chưa đọc hoặc
mutate persistent DB/Run #2; chưa commit/push. Không sửa task-board, traceability,
final-verdict hoặc các khu vực disposable/ZAP.

Web chính có nút **Nạp dữ liệu mẫu** ở cột Dự án, dùng API có admin session + CSRF.
Nút tạo/chọn `T18 Synthetic GET Demo v1` riêng, gồm 3 identities (`userA`, `userB`,
`admin`), 3 books có owner, 2 GET operations, mapping/evidence/rules. Lưu ý có **2
role khác nhau** (`user` và `admin`): đây là fixture demo đa identity cùng role,
không thay bằng chứng nghiệm thu 3/5 role. Mỗi identity có 4 cases; tổng 12 cases,
19 planned requests khi chọn toàn bộ. Đây là dữ liệu synthetic được ghi nhãn ngay
trong tên, mô tả và thông báo giao diện.

Lần nạp đầu chỉ xác minh 3 identities bằng GET `/me` thực; không tự queue scanner.
Matrix → lựa chọn rõ ràng → Run → Results dùng HTTP thật với API synthetic cố ý
bỏ kiểm tra owner và quyền reports. Không mock response/kết luận, không import
`backend.tests` hoặc CLI vào production web. Manual/ZAP vẫn `NOT_RUN`.

## File/function thay đổi trong ticket

- `backend/app/services/demo_seed.py::seed_demo`: tạo nguyên tử, `BEGIN IMMEDIATE`
  tuần tự hóa nạp đồng thời; nạp lại trả project đã tồn tại mà không chỉnh sửa.
  Token fixture mã hóa qua SecretBox; không trả bearer token ra API.
- `backend/app/api/demo_routes.py::load_demo`: POST `/api/demo/seed`, CSRF/admin,
  dùng đường xác minh identity GET thật. Từ chối collision/scope không hợp lệ;
  không lộ ciphertext/fingerprint trong lỗi uniqueness.
- `backend/app/core/settings.py`: `demo_target_url`, mặc định disabled; đọc
  `AUTHZ_DEMO_TARGET_URL`. `backend/app/main.py`: đăng ký router mới.
- `frontend/src/App.tsx`: nút nạp, busy state, chọn project và refresh dữ liệu,
  nhãn synthetic, lỗi hiển thị kể cả khi chưa có project. `frontend/src/api.ts`:
  `seedDemo`. Giữ nguyên các thay đổi có trước ticket ở hai file này.
- `deploy/compose.yaml`: service synthetic dùng `network_mode: service:authz-web`,
  không publish cổng; loopback `127.0.0.1:5099`; giữ volume `authz-data` hiện có.
  Bổ sung loopback/5099 vào allowlist, giữ các giá trị đã cấu hình.
- `deploy/synthetic_lab.py`, `deploy/Dockerfile.synthetic`: Python stdlib HTTP server,
  chỉ GET; invalid token → 401, phương thức ghi → 501; container read-only,
  non-root, không capabilities. Không lưu dữ liệu.
- `.dockerignore`: allowlist build context, loại secrets/DB/evidence/tests và
  node_modules; tránh gửi nguyên workspace vào daemon.
- `backend/tests/test_demo_seed.py`: 6 tests; `frontend/src/App.test.tsx`: thêm
  2 tests luồng nạp/chọn và lỗi khi chưa có project. README: hướng dẫn web chính.

## Evidence thực chạy

Tất cả đường dẫn dưới đây tương đối từ repo
`/home/cuong/Dự án/Bảo mật web/Project`:

- `results/mainweb-demo-07/backend-tests-final.log`: **238 backend PASS**, exit 0.
- `results/mainweb-demo-07/focused-final.log`: **6 focused PASS**, gồm HTTP GET
  end-to-end, idempotence, immutable results/history, existing sentinel project,
  concurrent seed, giữ operator edits, collision rollback, scope/disabled,
  unreachable target không tạo verification giả, invalid token và từ chối writes.
- `results/mainweb-demo-07/frontend-tests.log`: **60 frontend PASS**.
- `results/mainweb-demo-07/frontend-build.log`, `frontend-lint.log`: exit 0.
- `results/mainweb-demo-07/docker-final-start.log`: config/build/up exit 0 qua
  production Dockerfiles/Compose, override chỉ env test và cổng host.
- `results/mainweb-demo-07/docker-volume.txt`: chỉ volume
  `t18-mainweb-demo07_authz-data`, tách persistent volume hiện hành.
- `results/mainweb-demo-07/docker-source-hashes.txt`: hash code trong image chạy;
  `source-hashes.json` là bản đối chiếu workspace cuối ticket.
- `results/mainweb-demo-07/docker-preview.json`, `docker-manifest.json`,
  `docker-results.json`: case_id, run_id, revision, baseline và conclusion thật.
  Docker API test: **12 cases**, 12 HTTP 200; 6 policy-consistent + 6
  `CONFIRMED_VIOLATION` synthetic (4 BOLA + 2 BFLA). Seed không tạo run; nạp lại
  giữ nguyên run snapshot/results và project sentinel.
- `results/mainweb-demo-07/docker-e2e-queue.log`, `docker-e2e-verify.log`,
  `docker-e2e-final-verify.log`: assertions của HTTP test qua host 18987.
- Browser mounted: mở 18987, login test, bấm Nạp dữ liệu mẫu từ empty state → tự
  chọn project; Matrix chọn target → **3 identities / 12 executable / 0 exclusions**.
  Chọn case `autoauth:v1:project:1:operation:1:BOLA:resource:1:actor:2` và
  `autoauth:v1:project:1:operation:2:BFLA:resource:-:actor:1`, queue bằng UI →
  **Run #2 trong DB Docker tạm**, 7/7 requests completed, cả hai trả
  `CONFIRMED_VIOLATION`, baseline valid/authorized và principal matched = true.
  Đây không phải persistent Run #2. Run #1 tạm là lượt 12 cases qua API test.
- `results/mainweb-demo-07/browser-comparison.txt`: output thao tác Browser thật,
  Comparison giữ Manual/ZAP `NOT_RUN / UNAVAILABLE` cho hai case vừa chạy.
- `results/mainweb-demo-07/docker-stop.log`: dừng hai container tạm; không xóa
  volume/evidence. Không dừng container web đang dùng.

## Chạy bản chính sau bàn giao

Từ thư mục repo, giữ `.env` quản trị hiện có:

```bash
docker compose -f deploy/compose.yaml up --build
```

Mở `http://127.0.0.1:8000`, đăng nhập mật khẩu hiện có → **Nạp dữ liệu mẫu** →
**Matrix** → chọn API → **Tạo lại preview** → chọn case → **Xem lựa chọn trước
khi chạy** → **Queue các case GET đã chọn** → **Results** chọn run.
Không cần chạy browser_fixture hoặc web riêng 18983. Không dùng `down -v`.

## Giới hạn và đề nghị QA

- QA độc lập chưa chạy ticket này; responsive nhiều viewport chưa kiểm lại.
  Phần UI giữ hệ thống giao diện có sẵn, không redesign; không chạy gate thiết kế
  landing page. Browser evidence là thao tác thực trên bản production Docker tạm.
- Synthetic v1 không có sharing/anonymous/invalid-token matrix fixtures và không
  chứng minh coverage nghiệm thu 3/5 role. HTTP service vẫn từ chối anonymous và
  invalid token; có tests trực tiếp.
- Tên/description marker của project mẫu hoặc fixture token bị operator dùng lại
  sẽ khiến seed từ chối thay vì overwrite. Chưa có chức năng reset demo.
- Nếu synthetic chưa sẵn sàng khi nạp, verification thất bại thật và Matrix loại
  identity; sau khi service sẵn sàng bấm Xác minh từng identity trong Setup.
  Không tự retry/replay request và không tự sửa target đã lưu khi nạp lại.
- Production Compose chưa được restart theo giới hạn ticket. Persistent
  DB/Run #2 vẫn **NOT VERIFIED**, manual/ZAP/write-BFLA vẫn **NOT_RUN**.
- QA có thể chạy lại bằng env test/override sinh bởi
  `results/mainweb-demo-07/prepare_compose.py` hoặc tạo project/volume mới;
  không dùng volume production. Docker project test hiện đã dừng và giữ volume.
