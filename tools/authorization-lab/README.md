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

## Kiểm thử

```bash
PYTHONPATH=tools/authorization-lab/src python -m pytest tools/authorization-lab/tests -q
```
