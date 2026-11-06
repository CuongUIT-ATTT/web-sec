# Công cụ cho lab phân quyền

Đây là một package lab giảng dạy độc lập, chỉ hoạt động cục bộ. Package này **không** được ứng dụng web FastAPI import và ứng dụng web không bao giờ gọi nó qua `subprocess`.

## Ranh giới an toàn

- `vampi-authz-lab` chỉ đọc và chỉ chấp nhận target VAmPI cục bộ cố định `http://127.0.0.1:5000`; công cụ từ chối các method làm thay đổi trạng thái và `/createdb`.
- `vampi-authz-evaluate` sử dụng bằng chứng đã được tạo và chỉ chạy đánh giá ZAP có giới hạn khi đã cung cấp các đầu vào vận hành được rà soát.
- `vampi-bfla-disposable` là workflow destructive riêng biệt, được gọi một cách tường minh. Công cụ này cố định vào target dùng một lần bị ràng buộc bởi manifest tại `127.0.0.1:5003`, dùng [`deploy/labs/vampi-bfla-disposable.compose.yaml`](../../deploy/labs/vampi-bfla-disposable.compose.yaml), và không bao giờ vận hành trên lab dùng chung.
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

`.env` phải đặt `AUTHZ_ADMIN_PASSWORD` và backend phải chạy với `AUTHZ_ALLOWED_TARGET_NETWORKS` cho phép `100.106.64.21/32`, cùng `AUTHZ_ALLOWED_TARGET_PORTS` bao gồm `5003`. Launcher không tạo run. `--health-smoke` là tùy chọn duy nhất gửi request trực tiếp đến lab và chỉ gọi `GET /health`.

## Kiểm thử

```bash
PYTHONPATH=tools/authorization-lab/src python -m pytest tools/authorization-lab/tests -q
```
