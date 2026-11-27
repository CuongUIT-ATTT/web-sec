# QA-PARITY-05 — chuẩn bị package QA biệt lập

Gửi T18 Lead. 2026-11-15. **LOCALHOST/PARITY PASS (22:11); Browser E2E NOT_RUN.** Lịch sử chuẩn bị và blocker cũ bên dưới được giữ nguyên; kết quả mới nhất ở cuối báo cáo.
HEAD đọc trực tiếp: `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Giữ nguyên mọi diff sẵn có.
Ownership mới: `audit-final/qa-parity-05/{Dockerfile,compose.yaml,qa_app.py,test_isolation.py}` và báo cáo này. Không sửa production, runtime hoặc Run #2.

## Package và dữ liệu

Dockerfile build frontend workspace mới, copy backend workspace mới và entrypoint QA riêng. Không dùng image runtime cũ. Compose project riêng `t18-qa-parity-05`; chỉ publish `127.0.0.1:18080`; không dùng cổng 8000 host.
SQLite duy nhất `/qa-state/synthetic.sqlite3` trong tmpfs UID 65534, mất khi container bị thay. Không volumes/bind mounts; không mount DB/evidence/queue/socket Docker/bridge runtime. Root filesystem read-only, drop ALL capabilities, no-new-privileges, internal network riêng. Không CLI/lab được copy vào image.

`qa_app.build_app` thay **toàn bộ** lifespan gốc bằng lifespan chỉ cấp settings/session factory. Không dùng biến môi trường worker-disable không tồn tại. Bridge false; không tạo worker/dispatcher task. HTTP middleware chặn mọi mutation trừ login/logout, kể cả enqueue/verify/external-lab. Entry factory chặn socket connect/connect_ex/create_connection và DNS; internal network bổ sung chặn egress. Không có target fixture hoặc token lab. Chưa kiểm chứng firewall/kernel container do chưa chạy container.

Fixture tên project, alias, resource type đều có `SYNTHETIC`; snapshot ghi provenance `QA-PARITY-05 synthetic fixture v1; no transport executed`; từng result có reason `SYNTHETIC_QA_FIXTURE_NO_TRANSPORT`.
Ba role **admin/userA/userB**, hai resource thuộc userA/userB, explicit policy version 1, 6 case canonical `operation:1:resource:{1|2}:actor:{1|2|3}`. Admin và owner ALLOW; non-owner DENY. Run synthetic id=1 nằm trong DB riêng, không liên quan Run #2. Sáu result persisted có evidence v2 cho Analyze; Compare provenance `run:1:result:<id>` gắn đúng case. Đây là dữ liệu dựng để QA trình bày, **không phải thực nghiệm hay bằng chứng lỗ hổng**. Không tạo finding giả.

## Kiểm chứng thực chạy

Từ root repo:

```bash
.venv/bin/python -m pytest audit-final/qa-parity-05/test_isolation.py -q --tb=short
QA_ADMIN_PASSWORD=validation-placeholder docker compose -f audit-final/qa-parity-05/compose.yaml config --quiet
git diff --check
```

Fresh results: pytest **1 passed, 1 warning, 2.21s; exit 0** (một test tích hợp nhiều assertions); Compose config exit 0; diff-check exit 0. Warning Starlette/httpx và startup pytest-asyncio loop-scope. Test dùng tmp_path SQLite, TestClient in-process, không mở listening server. Sentinel worker/dispatcher sẽ fail nếu được gọi trong lifespan; network connect/connect_ex/DNS bị patch deny. Xác nhận login vẫn bắt buộc, 3 role, mỗi resource có 3 matrix rows ALLOW/DENY, 6 persisted results với evidence hợp lệ, 6 Compare cases/provenance, manual/ZAP NOT_RUN, enqueue bị 403, localhost outbound/DNS bị từ chối. Không chạy full regression lặp lại vì production không đổi.

Hash workspace đã đối chiếu với QA trước:
- frontend/dist/assets/index-BSZgHv66.js: `9a255b8e4f98340579c3e3b3ed1677c060122c37a4fe899d5e31ecef0b5e3b69`
- backend/app/api/workflow_routes.py: `25fb2292444e9d93837a45ca096578a93fef64f9bce49c94c0621eab0b88451d`
- qa_app.py: `1aaa71cf987b9f568ed0a6ed22d37a858193f6e7a0f422f237f110cc79dbfcd3`

Build chưa chạy; Dockerfile sẽ build bundle mới tại thời điểm được duyệt. QA cần ghi lại image ID, source/bundle hashes sau build và so với Browser asset; hash workspace không chứng minh image đã tồn tại.

## Lệnh bàn giao — CHƯA CHẠY, cần Lead phê duyệt rõ

Từ `/home/cuong/Dự án/Bảo mật web/Project`, người vận hành cấp password QA riêng qua môi trường an toàn (không paste chat):

```bash
: "${QA_ADMIN_PASSWORD:?Dedicated QA password required}"
docker compose -f audit-final/qa-parity-05/compose.yaml build web
docker compose -f audit-final/qa-parity-05/compose.yaml up -d --no-deps web
docker compose -f audit-final/qa-parity-05/compose.yaml ps
```

Phê duyệt cần nêu rõ: (1) build image QA, gồm tải base image/npm/pip qua network ở build-time; (2) tạo network internal và start **container QA mới** ở localhost:18080 với tmpfs; (3) Browser QA đăng nhập vào môi trường mới. Không rebuild/recreate/deploy stack runtime `deploy/compose.yaml`. Nếu cổng 18080 bận, dừng để Lead chọn cổng, không dừng dịch vụ đang chiếm cổng.

Browser QA URL sau khi được start: `http://127.0.0.1:18080/`. Cần đăng nhập bằng password QA riêng; không dùng lại tài khoản/token runtime. Người dùng thực hiện đăng nhập trong Browser tab của Screen panel khi môi trường đã sẵn sàng. Không yêu cầu bí mật trong chat.

## Giới hạn và phần chưa xong

- Package chỉ đọc để kiểm tra Tài khoản → owner → Matrix → Analyze → Compare. Resource edit bị 403 theo thiết kế QA; nếu muốn nghiệm thu edit, cần giao phạm vi mutation fixture và kiểm chứng isolation bổ sung.
- Chưa build/start container, chưa kiểm tra asset thực phục vụ, Browser E2E **NOT_RUN**, login **PENDING**. Không tuyên bố parity runtime đạt.
- Manual/ZAP importer/manifest mapping và provenance thực theo case **vẫn thiếu**; Compare giữ NOT_RUN/UNAVAILABLE, không ghép historical artifact.
- Disposable BFLA/write-BOLA vẫn thiếu execution/preflight/attestation riêng; **NOT_RUN**. Không lab/ZAP/network ngoài localhost trong lượt này.
- Gate 3+ role **synthetic fixture PASS**, gate 3+ role thực nghiệm **NOT VERIFIED**. Tổng thể **PARTIAL**.


## QA-PARITY-05 fresh execution — 2026-11-15 22:04 Vietnam

**BUILD/START PASS; localhost handoff BLOCKED; Browser E2E NOT_RUN.** User authorization delegated by Lead covers build/start; no additional approval requested. Port preflight `ss -ltn '( sport = :18080 )'` empty; Python bind preflight immediately before start also passed. Docker server 29.9.2.

Dedicated password generated with Python secrets.token_urlsafe(32), exclusively created at `/tmp/t18-qa-parity-05.password`, mode 0600, owner cuong. Value never printed or placed in artifact. Operators on this host may read this file locally to enter password in QA login; never paste into chat. Docker environment necessarily contains this dedicated credential and is accessible to Docker administrators. No runtime credential reused.

Fresh commands (password loaded from file into subprocess environment, never command arguments):

```python
import os, pathlib, subprocess
env = os.environ.copy()
env['QA_ADMIN_PASSWORD'] = pathlib.Path('/tmp/t18-qa-parity-05.password').read_text()
subprocess.run(['docker','compose','-f','audit-final/qa-parity-05/compose.yaml','build','web'], env=env, check=True)
subprocess.run(['docker','compose','-f','audit-final/qa-parity-05/compose.yaml','up','-d','--no-deps','--no-build','web'], env=env, check=True)
```

Both fresh exit 0. Build log `/tmp/t18-qa-parity-05-build.log` (no credential passed to build stage). Image `sha256:8bcd2719dfc8f353c387fb9b05eb7ee25a23e431ed908aade6b89b64594fe9a0`; container `t18-qa-parity-05-web-1`, running, Uvicorn startup complete. No Docker HEALTHCHECK configured: health assertion is HTTP `/api/health` => 200/status ok.

**Concrete failure:** `http://127.0.0.1:18080/api/health` connection refused on two fresh attempts. `docker port t18-qa-parity-05-web-1` empty; `ss` no listener; HostConfig has intended localhost port but NetworkSettings.Ports reports `8000/tcp: null` on this internal network. Do not claim localhost URL ready. Did not weaken internal network or alter daemon/firewall/runtime to work around this.

Host-direct isolated bridge URL `http://172.19.0.2:8000/` responds (diagnostic URL only, not stable localhost handoff). Fresh command `python3 audit-final/qa-parity-05/verify_live.py` exit 0; sanitized evidence `audit-final/qa-parity-05/live-verification.json`. HTTP health OK, dedicated login 200, 3 identities, 6 persisted results, 6 Compare cases, mutation 403. Served JS/CSS == image == workspace hashes; all 47 backend Python/QA source files match image. Script does not print login response/session/credential.

Isolation inspection: no bind/volume mounts; SQLite state only tmpfs; read-only root; cap_drop ALL; no-new-privileges; single internal QA network. Existing sentinel integration test rerun: 1 PASS, 1 warning, 2.01s, exit 0; diff-check exit 0. This supports worker/dispatcher no-op and socket-deny implementation; not a separate packet-level network audit. Runtime container ID, StartedAt and image before/after identical. No lab, Run #2 or ZAP actions performed.

QA handoff: password-only login using dedicated local protected file above; requested URL `http://127.0.0.1:18080/` remains BLOCKED pending isolated publishing fix. Diagnostic bridge URL has not been verified in the mounted Browser. Browser E2E NOT_RUN; synthetic fixture does not count as experimental acceptance. Container left running for diagnosis. No related automations exist (checked this turn).


## QA-PARITY-05 localhost remediation — 2026-11-15 22:11 Vietnam

**localhost handoff PASS; latest source/bundle parity PASS; isolation checks PASS. Browser E2E NOT_RUN. Tổng thể PARTIAL.**

Không đổi production/frontend/backend. Recreate duy nhất `t18-qa-parity-05-web-1` với SQLite synthetic tmpfs mới. Không runtime/Run #2/lab/ZAP/queue. Giữ network `internal: true`, chặn socket/DNS, read-only root, drop ALL, no-new-privileges, không bind mount. Không có default route trong `/proc/net/route`.

Docker trên host vẫn không publish port cho internal network. Giải pháp: relay TCP host bằng `localhost_relay.py`, chỉ bind **127.0.0.1:18080**, upstream cố định là IP internal của container QA, cổng 8000. Không proxy đích tùy ý, không thêm mạng hay gateway cho container. Relay không log request, cookie hoặc credential. Chạy dưới user cuong bằng transient user service `t18-qa-parity-05-relay.service`, NoNewPrivileges, Restart=on-failure. Service sống độc lập shell; không cấu hình tự chạy sau reboot. Nếu recreate QA làm đổi IP, cần restart relay với IP mới; không tự trỏ sang runtime. Rollback chỉ relay: `systemctl --user stop t18-qa-parity-05-relay.service`.

Fresh commands và exit:

- Build đầu `docker compose -f audit-final/qa-parity-05/compose.yaml build web`: **0**; log `qa-parity-05/rebuild.log`.
- Bổ sung manifest SHA256 nguồn frontend ngay trong build stage; build lại cùng lệnh: **0**; log `qa-parity-05/rebuild-with-manifest.log`. Docker cảnh báo thiếu buildx, dùng classic builder; build thành công.
- `.venv/bin/python -m pytest audit-final/qa-parity-05/test_isolation.py -q --tb=short`: **0; 1 PASS, 1 warning, 2.22s**. Sentinel fail nếu worker/dispatcher được gọi; không chạy production worker.
- `docker compose -f audit-final/qa-parity-05/compose.yaml up -d --no-deps --no-build --force-recreate web`: **0**. Password đọc vào subprocess environment từ file 0600, không argv/log.
- `systemd-run --user --unit=t18-qa-parity-05-relay --property=NoNewPrivileges=yes --property=Restart=on-failure /usr/bin/python3 '<absolute root>/audit-final/qa-parity-05/localhost_relay.py' 172.19.0.2`: **0**. `systemctl --user is-active t18-qa-parity-05-relay`: **0, active**. `ss -ltnp '( sport = :18080 )'`: **0**, listener duy nhất 127.0.0.1:18080.
- `python3 audit-final/qa-parity-05/verify_live.py > audit-final/qa-parity-05/localhost-verification.json`: **0**. Health 200/status ok, dedicated login **200**, 3 identities, 6 persisted results, 6 Compare cases, POST run **403**. Đây là HTTP verification, không phải Browser E2E.
- In-image guard check bằng docker exec import `qa_app`, thay build_app bằng no-op rồi gọi application để kiểm tra socket/DNS mà không seed/ghi DB: **0**, connect và DNS đều **DENIED** trước network I/O. Route table không default route. Evidence `qa-parity-05/isolation-live.json`. Đây không phải packet-level audit.
- `git diff --check`: **0**.

Image mới: `sha256:ec57dc2d6b0bd70042a7f42727ba7470c87563b492219c20fb1f20df5155ff9b`.
47 backend/QA source files và 10 frontend source files khớp workspace. Manifest frontend được tạo từ source trong build stage, không dùng bundle cũ ở frontend/dist của host. Served JS `/assets/index-DUcU0a2p.js` SHA256 `5b86d026aa71e91f79d95b21c35c351a18142ca7efd00082bbf084f064887265`; CSS `/assets/index-CwTufpIY.css` SHA256 `8e65978fa0644f64fb1c056c39058852c0a85100d12fb03b44496a35ec849591`; cả hai khớp image. Kết quả source và asset chi tiết trong `localhost-verification.json`.

Runtime container Id/Image/State trước và sau giống nhau (assert trong verify_live); baseline sanitized ở `qa-parity-05/runtime-before.json`. Không đọc hoặc ghi runtime DB. Không lặp full frontend tests vì không sửa production; số 37 tests là bàn giao trước, không nhận là fresh test của lượt này.

QA browser handoff: **http://127.0.0.1:18080/**. Dedicated QA password vẫn ở `/tmp/t18-qa-parity-05.password`, mode 0600; chỉ đọc cục bộ khi đăng nhập, không gửi chat. Browser E2E dành cho QA độc lập, chưa chạy trong lượt này. Resource edit vẫn 403 do package chỉ đọc; manual/ZAP NOT_RUN, BFLA chưa nghiệm thu, synthetic 3 roles không là thực nghiệm. Không có automation liên quan (đã kiểm tra).
