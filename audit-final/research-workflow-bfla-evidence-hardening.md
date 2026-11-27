# BFLA-05 — Consumer evidence fail-closed

Ngày 2026-11-15. Root: /home/cuong/Dự án/Bảo mật web/Project.
HEAD đã kiểm tra: bdbba9933ca057cb2247c3a1de9b3ee239c452bd.
Verdict: PASS regression; thực nghiệm NOT_RUN; tổng thể PARTIAL.

## Phạm vi và thay đổi

Đã đọc README gốc/lab, audit BFLA và report BFLA-01; inventory không có AGENTS.md trong project. Giữ diff có sẵn. Chỉ sửa evaluation/bfla_evidence.py, tests/evaluation/test_bfla_evidence.py và báo cáo này. Không sửa runner/comparison/timing hay ba tài liệu QA.

Consumer không còn dùng truthiness: null/missing/string/number/list/dict không là deletion proof. Exact false cũng chưa đủ: phải khớp run/schema/workflow/local target, manifest target/path, fresh baseline 200 đúng username, principal 200 đúng actor/admin với exact boolean role, postcondition exact integer 404 và đúng target/path. DENIED đòi valid exists proof và DELETE 401; admin positive control đòi DELETE 200 và absence proof. Summary mâu thuẫn với case evidence hạ verdict về INCONCLUSIVE; không tin outcome đơn lẻ. HTTP200 + survivor không confirmed. Unknown postcondition ghi unknown, baseline thiếu ghi unverified. Không xuất thêm response/secret.

## Compatibility và dependency

Schema output vẫn 1, giữ case IDs/field names; legacy đọc được nhưng thiếu proof cho verdict INCONCLUSIVE. Không rewrite history. Guardrail/temp-file ingestion test tiếp tục PASS.

**Producer BFLA-01 hiện chưa serialize baseline/principal/postcondition proof**, dù đã kiểm tra trong runtime code. Vì vậy mọi receipt hiện tại thiếu proof đều không confirmed, kể cả exact false hoặc legacy DENIED_CONTROL; không suy ra proof từ việc runner từng chạy. Đây là thay đổi bảo thủ có chủ đích, cần consumer downstream chấp nhận INCONCLUSIVE.

Contract proof được kiểm thử bằng fixture synthetic, chưa là evidence thực nghiệm: mỗi operation có proof.baseline {status:200, username, fresh:true}, proof.principal {status:200, username, admin:bool}, proof.postcondition {status:200|404, username, path}. Producer phải được giao bổ sung riêng và thống nhất version/linkage; ticket này không sửa producer. Positive regression chỉ chứng minh consumer xử lý contract, không chứng minh receipt hiện tại đã có contract. Không có cryptographic authenticity/hash/approval/cleanup validation mới; BFLA-02–04 vẫn là dependency. Extended findings passthrough hiện hữu chưa được harden trong ticket DELETE này; không dùng để nghiệm thu extended. Run-scoped output/importer/UI tiếp tục ngoài scope.

## Fresh commands và exit

Chạy từ root nêu trên:

- `PYTHONPATH=tools/authorization-lab/src .venv/bin/python -m pytest tools/authorization-lab/tests/evaluation/test_bfla_evidence.py -q`: exit 0; 19 passed, 24 subtests passed (trước thay đổi nhỏ cuối về admin DELETE status và mở rộng network guard toàn module).
- `PYTHONPATH=tools/authorization-lab/src .venv/bin/python -m pytest tools/authorization-lab/tests/evaluation -q`: exit 0; 54 passed, 28 subtests passed, 0.20s, sau thay đổi cuối.
- `git diff --check`: exit 0.

Có warning pytest-asyncio về loop scope chưa cấu hình, không sửa ngoài ownership.

Regression: null/missing/false/true/malformed, valid positive proof và denied control, wrong run/workflow/schema, stale baseline, wrong username/admin role, read401/500/200 không là absence, missing/malformed proof, malformed operations, contradictory summary. Toàn module BFLA evidence chặn socket.connect và subprocess.run; ingestion chỉ đọc/ghi TemporaryDirectory được tự cleanup. Không gọi prepare/execute/extended/teardown/Compose/network thật. Suite evaluation rộng hơn chạy kiểm thử deterministic hiện có, không lifecycle runtime.

Không đọc credential, không sửa results/history/DB/runtime/Run #2; không deploy/commit/push/reset/xóa evidence. Không tạo instance nên không có cleanup lab mới; không có bằng chứng upstream từ thực nghiệm mới. Automation đã kiểm tra: không có.
