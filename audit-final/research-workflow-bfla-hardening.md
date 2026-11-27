# BFLA-01 — Harden postconditions

Ngày 2026-11-15; root: /home/cuong/Dự án/Bảo mật web/Project.
HEAD xác minh: bdbba9933ca057cb2247c3a1de9b3ee239c452bd.
Verdict: **PASS regression; thực nghiệm NOT_RUN; tổng thể PARTIAL**.

## Phạm vi

Chỉ sửa tools/authorization-lab/src/authz_lab/disposable/runner.py và
tools/authorization-lab/tests/disposable/test_runner.py; báo cáo tại file này.
Đã đọc README gốc, README authorization-lab và research-workflow-bfla-audit.md.
Không có AGENTS.md trong inventory workspace. Giữ các diff có sẵn ngoài ownership.
Không chạy lifecycle, Compose, HTTP thật, ZAP, deploy, queue; không đọc/ghi runtime DB,
Run #2, results lịch sử hoặc snapshot; không commit/push/reset.

## Thay đổi và bằng chứng

- Profile postcondition tri-state: true khi 200 + JSON đúng username, false chỉ exact 404,
  null cho 401/403/500, malformed JSON hoặc principal sai. Không xuất body.
- DELETE bắt buộc baseline profile hợp lệ trước mỗi target và attestation /me:
  actor fixture đúng run, admin false; bootstrap admin đúng username, admin true.
  Chỉ absence sau baseline hợp lệ mới BFLA_CONFIRMED_DESTRUCTIVE.
  HTTP 200 + victim sống là INCONCLUSIVE. Admin control unknown cũng INCONCLUSIVE.
- Extended xác minh actor/admin như trên; email có baseline victim/self hợp lệ và email
  dạng string. HTTP 204 self update chỉ được gắn FALSE_POSITIVE_HTTP_204_SELF_UPDATE
  khi victim email giữ nguyên và actor email đổi sang probe. Read error giữ null.
- Password có fresh victim profile và chứng minh mật khẩu probe chưa dùng được
  (login 401/403) trước PUT. Sau login thành công, /me phải đúng victim và non-admin;
  mismatch ném BflaExecutionError, không ghi receipt confirmed.
- Mass assignment yêu cầu /me đúng escalated username và admin true; baseline victim
  mới trước DELETE; chỉ exact 404 mới chứng minh deletion. Unknown export null.
- Invalid precondition/principal dừng với exception, không tạo success receipt.
  Durable invalid-attempt receipts còn thuộc lifecycle ticket 03.

Case tests: denied control; deletion positive; 200 + survivor; invalid postcondition;
invalid baseline; actor identity/role mismatch; extended positive; self update;
password principal mismatch; unknown email/deletion; cross-user email positive;
extended denied; admin control unknown; password probe invalid.
Runner tests chặn socket.connect và subprocess.run; mọi HTTP được mock.
Fixtures/artifacts nằm trong TemporaryDirectory riêng và được cleanup bởi unittest.
Không có cleanup lab mới vì không tạo instance; upstream VAmPI không được gọi.
Mock tests chỉ chứng minh không thực thi kết nối trong suite này, không chứng minh
isolation/cleanup upstream của một lần thực nghiệm.

## Fresh commands và kết quả

Working directory: root nêu trên.

1. python -m pytest .../test_runner.py -q: exit 1, system Python thiếu pytest.
2. PYTHONPATH=tools/authorization-lab/src python -m unittest discover -s tools/authorization-lab/tests/disposable -p test_runner.py -v:
   lần đầu exit 1 do fixture control test dùng suffix sai; đã sửa thành delete-control.
3. PYTHONPATH=tools/authorization-lab/src .venv/bin/python -m pytest tools/authorization-lab/tests/disposable -q:
   lần cuối **exit 0; 26 passed, 23 subtests passed in 0.18s**.
   Có PytestDeprecationWarning về asyncio_default_fixture_loop_scope chưa cấu hình.
4. git diff --check: **exit 0**.

Không chạy full repository tests vì ownership chỉ disposable runner và suite disposable đã PASS.
Không sửa các test ngoài test_runner.py.

## Compatibility và dependencies

Receipt schema_version vẫn 1; target_survived và các extended flags có thể null
khi unknown. Consumer phải giữ null, không coercion falsy thành confirmed.
Fixture secrets cũ thiếu username nay bị từ chối; cần fixture do prepare hiện có sinh,
không migrate hoặc sửa artifact lịch sử.
Request count tăng do GET baseline, /me và password rejection control;
request budget/manifest mới phải tính các bước này trước khi thực nghiệm.

- BFLA-02 chưa làm: manifest extended, approval provenance/stage/hash/expiry/one-use,
  runtime budget và scope đầy đủ.
- BFLA-03 chưa làm: redirect rejection, atomic claims/replay/race/crash protection,
  immutable receipts và bounded request enforcement.
- BFLA-04 chưa làm: actual volume/mount/compose attestation, cleanup chain và upstream
  metadata/digest proof.
- BFLA-05 consumer/evidence import ngoài ownership: evaluator có nguy cơ biến unknown
  thành confirmed; cần harden độc lập trước dùng receipt để nghiệm thu.
- BFLA-06 thực nghiệm: **NOT_RUN**; cần phê duyệt riêng execute/execute-extended,
  disposable manifest/preflight/isolation/teardown và evidence chain đầy đủ.
  Không dùng mock PASS làm evidence khai thác hoặc gate 3+ roles.

Đã kiểm tra automation liên quan: bot không có automation.
