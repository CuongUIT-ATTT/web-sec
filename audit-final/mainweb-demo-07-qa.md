# MAINWEB-DEMO-07 — QA độc lập

**Verdict: PASS trong phạm vi web chính Docker/local synthetic; tổng thể T18 PARTIAL.**

QA: T18 QA Evidence, 2026-11-16, 19:08–19:12 Vietnam (UTC+07).
HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`, working tree dirty trước test.
Không tìm thấy AGENTS.md trong repo và các thư mục cha đã kiểm tra.
Không sửa production, commit/push, đọc persistent DB/Run #2 hoặc restart Compose hiện hành.

## Inventory và provenance

Python host 3.14.8; Node 26.12.1; npm 12.2.1; Docker client/server 29.9.2.
Production Dockerfiles dùng Python 3.11-slim và Node 22-alpine. QA build từ
`deploy/compose.yaml`, chỉ override env test và host port 18988.
Project Compose `t18-mainweb-demo07-qa`; mount duy nhất của web là volume
`t18-mainweb-demo07-qa_authz-data`, được tạo mới trong lượt này.
Không dùng lại volume triển khai hoặc volume của người triển khai ticket.

Đã đối chiếu handoff: source **13/13**, artifact **26/26** SHA-256 khớp.
Sau kiểm tra, 13/13 source vẫn không đổi. Image đang chạy khớp 5/5 source
(seed, route, settings, app main, synthetic server). Image digest/ID và mount
được lưu trong `results/mainweb-demo-07-qa/docker-attestation.json`.
Fixture: `T18 Synthetic GET Demo v1`, 3 identities / **2 role**, 3 books,
2 GET operations, policy revision
`7cf6570266dd4ad3e0268244acb0fef0ef8e824a1213b9fd2cbc905e53ec6e62`.
Không có OpenAPI import file trong seed; SHA-256 OpenAPI runtime ghi ở
`results/mainweb-demo-07-qa/openapi-sha256.txt`. Fixture và source có hash
trong handoff-hash-check và hash index QA.

## Execution manifest — commands/exits

Artifacts dưới `results/mainweb-demo-07-qa/` từ repo.

| Thực chạy độc lập | Exit | Evidence |
|---|---|---|
| `.venv/bin/python -m pytest backend/tests/test_demo_seed.py -q` | 0, 6 PASS | focused.log |
| `npm --prefix frontend test -- --run src/App.test.tsx` | 0, 5 PASS | frontend-focused.log |
| `docker compose [compose-command.json] config --quiet` | 0 | docker-start.log |
| `docker compose [compose-command.json] up -d --build` | 0 | docker-start.log |
| `.venv/bin/python results/mainweb-demo-07-qa/docker_check.py queue` | 0 | docker-queue.log, manifest.json, preview.json |
| `.venv/bin/python results/mainweb-demo-07-qa/docker_check.py verify` | 0 | docker-verify.log, results.json, history.json |
| Image source/mount assertions | 0 | docker-attestation.json |
| Browser UI run result assertions | 0 | browser-run-results.json |
| `git diff --check` | 0 | diff-check.log |
| `docker compose [compose-command.json] stop` và assert 2 containers exited | 0 | docker-stop.log, docker-stopped-state.jsonl |

`compose-command.json` lưu đầy đủ argv, dùng env test riêng, không chứa secret.
Không lặp full suites: **238 backend + 60 frontend**, lint/build là kết quả
người triển khai được review/hash-check, không được gọi là QA rerun. QA đã
build lại production image thành công. Focused tests có localhost fixture;
kiểm tra phương thức ghi trong suite chỉ xác nhận synthetic từ chối 501,
không thực hiện write-BFLA hay mutation tài nguyên lab.

## Runtime acceptance

- Browser tại `http://127.0.0.1:18988`: login test → empty state → bấm
  **Nạp dữ liệu mẫu** → tự chọn đúng project, Setup hiện target, identities,
  resources và policy. UI nói rõ synthetic và chưa đạt gate 3/5 role.
- Seed lần đầu có 3 verification GET thật; trước queue, API chứng minh runs
  trống. Nạp lại hai lần không tự queue hoặc nhân bản project.
- Tạo project sentinel trên DB tạm; sửa target request limit từ 100 thành 77;
  nạp lại giữ nguyên edit/sentinel. Focused backend còn kiểm concurrent seed,
  giữ operator policy edits, rollback collision và snapshot sentinel lịch sử.
- Docker API: explicit queue **Run #1** của DB QA, đủ **12 cases / 19 requests**;
  19 responses, 0 errors; 12 actor HTTP 200, 6 policy-consistent và 6
  `CONFIRMED_VIOLATION` synthetic. Kết luận có policy/baseline, không dựa riêng
  HTTP 200. Nạp lại sau hoàn tất giữ exact run DTO/snapshot/results và sentinel.
- Browser: Matrix chọn target, tạo preview **3 identities / 12 executable /
  0 exclusions**; chọn BOLA resource 1 actor 2 và BFLA reports actor 1 →
  review budget 7/77 → explicit queue **Run #2 trong DB QA mới** → Results
  COMPLETED, hai `CONFIRMED_VIOLATION`, baseline authorized/valid và principal
  matched true. Không liên quan persistent Run #2.
- Auth: anonymous seed 401; authenticated thiếu hoặc sai CSRF 403.
  Focused test disabled/scope/collision 409; unreachable target không tạo
  verification giả và 0 executable cases.
- Browser UI-only fault injection: giữ request seed pending rồi reject lỗi mạng;
  nút disabled với nhãn `Đang nạp mẫu…`, sau lỗi enabled trở lại, thông báo lỗi
  hiển thị. Đây là kiểm tra trạng thái UI có fault injection, không phải mock
  kết quả scanner. Frontend focused test xác minh lỗi khi empty state.
- Synthetic reachable qua loopback trong cùng network namespace theo Compose;
  HTTP thật, không import tests/CLI vào web. Service không publish lab port,
  non-root/read-only/cap_drop; chỉ GET. Review đường wiring phù hợp handoff.
- Hai containers QA đã dừng, trạng thái `exited`; không xóa volume/evidence.
  Kiểm tra automations: bot không có automation liên quan cần dừng.

Evidence UI và kích thước: `browser-observations.json`. Case/run/policy/artifact
liên kết trong manifest, preview, results và browser-run-results.

## R1–R8 và evidence gaps

| Requirement | Đóng góp ticket này | Giới hạn |
|---|---|---|
| R1 roles | PASS demo đa identity, 3 identities / 2 role | Chưa chứng minh gate 3/5 role nghiên cứu |
| R2 OpenAPI × role × owner | PASS fixture 12 BOLA/BFLA GET cases | Seed operations cố định, không thay thực nghiệm OpenAPI tổng quát |
| R3 baseline/policy | PASS actual baseline/owner/admin synthetic | Không phải nghiên cứu live lab |
| R4 BOLA/BFLA | PASS GET synthetic phân biệt hai kind | Write-BFLA NOT_RUN |
| R5 manual/T18/ZAP | Không có evidence mới | Manual/ZAP NOT_RUN |
| R6 reusable tool/web | PASS main Docker seed→matrix→run→results | Chưa restart production theo scope |
| R7 audit/history | PASS sentinel/operator edits/history trên DB tạm, hashes | Persistent DB/Run #2 NOT VERIFIED |
| R8 comparison | Không có benchmark mới | Không nâng synthetic thành research comparison |

Responsive: Browser **1280×800**, Setup/Results không tràn document ngang.
`resizeTo(390,844)` vẫn trả 1280×800; mounted surface không có resize action.
**Nhiều viewport NOT VERIFIED**, không tuyên bố mobile PASS.

Race service startup: seed trước synthetic ready sẽ lưu verification thất bại
thật; reseed không tự verify lại. Sau khi service ready, dùng Xác minh trong Setup
như handoff. Đây là giới hạn được ghi nhận, không có retry/replay ngầm.

Persistent preservation chỉ là untouched-by-scope, không có checksum DB production.
Không chạy external API, manual, ZAP active, write-BFLA; không reset/xóa DB.
Bản sửa sẵn sàng dùng bằng `docker compose -f deploy/compose.yaml up --build`
trên web chính cổng 8000; QA không chạy lệnh đó với volume hiện hành của người dùng.
