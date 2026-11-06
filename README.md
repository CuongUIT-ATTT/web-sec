# Trạm kiểm thử phân quyền REST có kiểm soát

Repository này có hai thành phần **tách biệt theo ranh giới an toàn**:

1. **Ứng dụng web** — FastAPI/React phục vụ kiểm thử phân quyền REST chỉ đọc, có SQLite lưu bền.
2. **Công cụ cho lab phân quyền** — công cụ VAmPI/ZAP/BFLA chỉ hoạt động cục bộ, độc lập tại [`tools/authorization-lab/`](tools/authorization-lab/), không được web runtime import hay gọi qua `subprocess`.

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

Hướng dẫn vận hành, lệnh, fixtures và quy tắc an toàn của lab nằm tại [tools/authorization-lab/README.md](tools/authorization-lab/README.md).

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
- `vampi-authz-evaluate`: nhận evidence có sẵn, điều phối BFLA receipt/ZAP constrained evaluation.
- `vampi-bfla-disposable`: lifecycle destructive riêng, manifest-bound, chỉ cho disposable target `127.0.0.1:5003`.

Xem lệnh, fixtures và quy tắc an toàn tại [tools/authorization-lab/README.md](tools/authorization-lab/README.md). Compose BFLA độc lập là [`deploy/labs/vampi-bfla-disposable.compose.yaml`](deploy/labs/vampi-bfla-disposable.compose.yaml), không bao giờ nằm trong web Compose.

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
