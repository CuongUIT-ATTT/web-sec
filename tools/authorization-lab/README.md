# Công cụ cho lab phân quyền

Đây là package lab giảng dạy độc lập, chỉ hoạt động cục bộ. Package này **không** được ứng dụng web FastAPI import và FastAPI không bao giờ gọi nó qua `subprocess`. Khi operator bật bridge riêng, bridge (không phải FastAPI) chỉ có thể chạy workflow VAmPI read-only cố định qua Unix socket/HMAC; bridge không có capability BFLA, ZAP runtime hoặc Docker.

## Ranh giới an toàn

- `vampi-authz-lab` chỉ đọc và chỉ chấp nhận target VAmPI cục bộ cố định `http://127.0.0.1:5000`; công cụ từ chối các method làm thay đổi trạng thái và `/createdb`. Hỗ trợ tự động lọc `ownership.csv` theo danh sách role trong `roles_config.json` (ví dụ bộ 5 vai trò `admin`, `admin2`, `userA`, `userB`, `userC` hoặc bộ 3 vai trò `admin`, `userA`, `userB`), phân loại BOLA 4 chiều và kiểm chứng `GET /users/v1/_debug` (API3 Excessive Data Exposure) không lưu giá trị mật khẩu.
- `vampi-authz-evaluate` sử dụng bằng chứng đã được tạo và chỉ chạy đánh giá ZAP có giới hạn khi đã cung cấp các đầu vào vận hành được rà soát.
- `vampi-bfla-disposable` là workflow destructive riêng biệt, được gọi một cách tường minh. Công cụ này cố định vào target dùng một lần bị ràng buộc bởi manifest tại `127.0.0.1:5003`, dùng [`deploy/labs/vampi-bfla-disposable.compose.yaml`](../../deploy/labs/vampi-bfla-disposable.compose.yaml), và không bao giờ vận hành trên lab dùng chung. Lệnh `execute` mặc định giữ nguyên phạm vi `DELETE /users/v1/{username}`; lệnh opt-in `execute-extended` kiểm chứng Write-BOLA (`PUT .../password`), False Positive HTTP 204 (`PUT .../email`) và Mass Assignment (`POST /users/v1/register`).
- `roles_config.json`, các tệp ZAP Context riêng tư, kết quả, `.bfla-runs` và database là dữ liệu cục bộ/được ignore. Không thêm chúng vào Git.

## Cài đặt và xác thực

```bash
python -m pip install -e "./tools/authorization-lab"
```

```bash
vampi-authz-lab --help
```

```bash
vampi-authz-lab check-zap-allowlist
```

```bash
vampi-authz-evaluate --help
```

Các lệnh chỉ đọc giữ nguyên giá trị mặc định đã thiết lập cho thư mục làm việc: `vampi_spec.json`, `roles_config.json`, `ownership.csv` và `results/`. Dùng các giá trị tường minh cho `--roles-config`, `--spec`, `--ownership` và `--output-dir` khi đầu vào của lab có kiểm soát nằm ở nơi khác. Fixture đóng gói chỉ là dữ liệu tham chiếu công khai, không chứa bí mật.

## Bootstrap Controlled BOLA Lab

Khi web local hoặc Docker Compose đang hoạt động ở `http://127.0.0.1:8000`, dùng launcher Bash từ Linux để nạp `.env`, yêu cầu token qua prompt ẩn và cấu hình lab được phê duyệt:

```bash
bash tools/run_controlled_bola_bootstrap.sh
```

Launcher tự xác định thư mục project, cố định target `http://100.106.64.21:5003`, dùng OpenAPI tại `../VAmPI/openapi_specs/bola-lab.openapi.json` nếu `BOLA_OPENAPI_PATH` chưa được đặt, và chuyển tiếp tùy chọn cho helper Python:

```bash
bash tools/run_controlled_bola_bootstrap.sh --health-smoke
```

`.env` phải đặt `AUTHZ_ADMIN_PASSWORD` và backend phải chạy với `AUTHZ_ALLOWED_TARGET_NETWORKS` cho phép `100.106.64.21/32`, cùng `AUTHZ_ALLOWED_TARGET_PORTS` bao gồm `5003`. Launcher không tạo run mặc định. `--health-smoke` là tùy chọn duy nhất gửi request trực tiếp đến lab và chỉ gọi `GET /health`. Dùng `--queue-batch` để opt-in queue một batch GET; thêm `--wait` nếu cần polling tối đa 30 giây. `--cancel-run ID` hoặc `--show-results ID` chỉ thao tác run thuộc project vừa reconcile và output kết quả chỉ là aggregate conclusion.

## Operator-side read-only bridge

`vampi-authz-lab-bridge` là tiến trình riêng duy nhất được phép khởi chạy CLI theo request từ web. FastAPI không import package này và không gọi `subprocess`. Bridge chỉ nhận HMAC request trên Unix socket cho literal job `READ_ONLY_VAMPI_VERIFICATION_V1`, sau đó chạy fixed argv `vampi-authz-lab verify-workflow` trên `http://127.0.0.1:5000`. Không có flag hay API cho arbitrary command, argv, target, BFLA, ZAP, Docker, Docker socket, hoặc artifact path từ browser/web.

Operator phải cung cấp các biến môi trường `AUTHZ_LAB_BRIDGE_SOCKET_PATH`, `AUTHZ_LAB_BRIDGE_SHARED_SECRET`, `AUTHZ_LAB_BRIDGE_CALLBACK_URL`, `AUTHZ_LAB_BRIDGE_EXECUTABLE`, `AUTHZ_LAB_BRIDGE_SPEC`, `AUTHZ_LAB_BRIDGE_ROLES_CONFIG`, `AUTHZ_LAB_BRIDGE_OWNERSHIP`, `AUTHZ_LAB_BRIDGE_ARTIFACT_ROOT`, và `AUTHZ_LAB_BRIDGE_JOURNAL`. Tất cả path phải tuyệt đối; callback phải là `http://127.0.0.1:<port>`; secret dài ít nhất 32 ký tự và dedicated. Start bridge trước web dispatcher, bảo vệ socket/journal/artifact root theo UID/GID của operator, và không mount Docker socket. Callback tạm thời lỗi được lưu outbox journal để retry ở lifecycle kế tiếp; restart không replay child đang dở mà phát event `INTERRUPTED`.

## Kiểm thử

```bash
PYTHONPATH=tools/authorization-lab/src python -m pytest tools/authorization-lab/tests -q
```
