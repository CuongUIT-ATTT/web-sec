# Trạm kiểm thử phân quyền REST có kiểm soát

Repository này có hai thành phần **tách biệt theo ranh giới an toàn**:

1. **Ứng dụng web** — FastAPI/React phục vụ kiểm thử phân quyền REST chỉ đọc, có SQLite lưu bền.
2. **Công cụ cho lab phân quyền** — công cụ VAmPI/ZAP/BFLA hoạt động cục bộ tại [`tools/authorization-lab/`](tools/authorization-lab/). Web runtime không import hay gọi CLI qua `subprocess`; khi được bật tường minh, web chỉ gửi một job VAmPI read-only cố định tới bridge do operator vận hành qua Unix socket riêng.

Bridge mặc định bị tắt. Bridge không nhận command/argv/target/path từ trình duyệt, không chạy BFLA, ZAP runtime hay Docker, và chỉ trả summary/hash artifact đã rút gọn. BFLA vẫn là workflow disposable được operator chạy tường minh ngoài web runtime.

> Chỉ dùng trên lab đã được ủy quyền. Đây không phải scanner dùng cho production hay mục đích tổng quát.

## Cấu trúc repository

```text
backend/                  FastAPI web API, worker và persistence
frontend/                 React/Vite web client
deploy/                   Web Docker/Compose deployment
tools/authorization-lab/  Package CLI `authz_lab` độc lập và hướng dẫn vận hành lab
```

Không còn package/source runtime theo `week1`–`week4`.

## Web MVP

| Hỗ trợ | Không hỗ trợ ở web runtime |
| --- | --- |
| Bearer token write-only, mã hóa Fernet phía server | Cookie/header auth, login automation |
| OpenAPI **JSON** và operation **GET** | YAML, nhập spec qua URL, external `$ref` |
| Response JSON, JSON Pointer RFC 6901 tuyệt đối | JSONPath, wildcard, filter, script |
| SQLite + single-process FIFO worker | Redis, Celery, multi-node worker |
| IP/CIDR + scheme + port + path scope | Hostname/DNS, redirect, absolute request URL từ client |
| Owner/cross-user evidence controls mới trong run | State-changing BFLA hoặc ZAP runtime integration |

`GET /createdb` luôn bị chặn. Không có identifier enumeration. `HEAD`/`OPTIONS` không đi qua JSON comparator.

- Admin/session secrets là environment variables; session dùng cookie `HttpOnly`/`SameSite=Strict` và write API yêu cầu CSRF token trong memory.
- Bearer token không vào localStorage, log, API response, export hay raw result. SQLite chỉ lưu ciphertext và keyed HMAC fingerprint.
- Kết quả chỉ giữ metadata/evidence allowlisted, không giữ full response body, header, cookie hay password.
- `execution_status`, `authorization_conclusion`, `reason_code` là ba lớp độc lập. HTTP 4xx/5xx có response vẫn là `COMPLETED_RESPONSE` và body đủ điều kiện vẫn có thể được đánh giá disclosure.

Hướng dẫn vận hành, lệnh, fixtures và quy tắc an toàn của lab nằm tại [tools/authorization-lab/README.md](tools/authorization-lab/README.md). Để bootstrap Controlled BOLA Lab từ Linux, chạy `bash tools/run_controlled_bola_bootstrap.sh`; script tự tìm project root, nạp `.env`, hỏi token ẩn khi chưa có và chuyển tiếp tùy chọn như `--health-smoke`.

## Chạy web local

1. Sao chép `.env.example` thành `.env`, thay tất cả placeholder, và allowlist đúng network/port lab.
2. Cài dependencies:

```bash
python -m pip install -e ".[dev]"
```

```bash
cd frontend && npm install
```

3. Chạy loopback services:

```bash
uvicorn backend.app.server:app --host 127.0.0.1 --port 8000
```

```bash
cd frontend && npm run dev -- --host 127.0.0.1
```

Hoặc build container local-only:

```bash
docker compose -f deploy/compose.yaml up --build
```

SQLite container data nằm trong named volume `authz-data`; không xóa volume khi refactor/upgrade nếu cần giữ run history.

## Authorization-lab CLI độc lập

Cài package riêng:

```bash
python -m pip install -e "./tools/authorization-lab"
```

Các entry points:

- `vampi-authz-lab`: read-only VAmPI checks tại `127.0.0.1:5000`.
- `vampi-authz-lab-bridge`: bridge Unix socket do operator vận hành, chỉ khởi chạy `verify-workflow` với đầu vào tuyệt đối đã review và target VAmPI cố định.
- `vampi-authz-evaluate`: nhận evidence có sẵn, điều phối BFLA receipt/ZAP constrained evaluation.
- `vampi-bfla-disposable`: lifecycle destructive riêng, manifest-bound, chỉ cho disposable target `127.0.0.1:5003`.

Xem lệnh, fixtures và quy tắc an toàn tại [tools/authorization-lab/README.md](tools/authorization-lab/README.md). Compose BFLA độc lập là [`deploy/labs/vampi-bfla-disposable.compose.yaml`](deploy/labs/vampi-bfla-disposable.compose.yaml), không bao giờ nằm trong web Compose.

### Bật bridge read-only (operator-side, tùy chọn)

Không bật bridge trong Compose mặc định và không mount Docker socket. Operator chạy bridge trong venv/package lab riêng, rồi mới bật web feature bằng `AUTHZ_EXTERNAL_LAB_BRIDGE_ENABLED=true`, một Unix socket private và shared secret **riêng** ít nhất 32 ký tự. Secret này không được tái dùng admin password, session secret hay Fernet key. Bridge chỉ chấp nhận callback về `http://127.0.0.1:<port>` và các path tuyệt đối đã được review cho executable, OpenAPI, roles config, ownership CSV, artifact root và journal.

Bridge journal giữ callback terminal chưa gửi để retry khi callback tạm thời không sẵn sàng. Sau restart, bridge không chạy lại child process không chắc chắn mà báo `INTERRUPTED`; web cũng chuyển job đang không chứng minh được sang `UNKNOWN`. Chỉ summary allowlisted và SHA-256 manifest vào web database—không có stdout/stderr, token, artifact, response body hay host path. Dọn artifact host-side theo chính sách retention của operator.

CLI bootstrap vẫn là reconcile-only mặc định. `--queue-batch` là opt-in để queue batch GET hiện có; `--wait` chỉ dùng cùng nó; `--cancel-run ID` và `--show-results ID` chỉ chấp nhận run thuộc project vừa reconcile.

## Kiểm thử

Web backend:

```bash
python -m pytest backend/tests -q
```

Frontend:

```bash
cd frontend && npm run lint && npm run test && npm run build
```

Authorization-lab tooling:

```bash
PYTHONPATH=tools/authorization-lab/src python -m pytest tools/authorization-lab/tests -q
```

## Evidence và dữ liệu được bảo toàn

- Credentials, `roles_config.json`, `.env`, private ZAP Context/session files, `.bfla-runs`, `results/`, databases, frontend builds và downloaded VAmPI source vẫn ignored/local-only.
- `deploy/labs/vampi-bfla-disposable.compose.yaml` giữ loopback binding, dedicated volume và guardrails hiện có.
- Web app không chạy ZAP/BFLA hoặc legacy CLI; CLI không import `backend.app`.
