## QA-BROWSER-05 — cập nhật từ chối đăng nhập 2026-11-15T22:21:25.360480+07:00

**Tổng thể PARTIAL; authenticated Browser E2E BLOCKED.** Người dùng đã từ chối đăng nhập tại 127.0.0.1. Không còn yêu cầu đăng nhập đang chờ; không yêu cầu lại và không thử cách đăng nhập thay thế. Asset parity PASS là bằng chứng browser ở lượt 22:13, không phải kiểm tra mới trong lượt này.

Tài khoản/alias/role/credential-configured, phân biệt web/lab role, owner, ma trận từng case/policy/version/ALLOW–DENY/coverage, Analyze baseline/reason/provenance và Compare manual/ZAP NOT_RUN/artifact UNAVAILABLE: **NOT_RUN sau đăng nhập**, chưa xác minh giao diện. Synthetic 3 role không đạt gate thực nghiệm 3+/5 roles. Manual/ZAP/BFLA thực nghiệm vẫn NOT_RUN; R1/R4/R5/R8 chưa nghiệm thu.

Khắc phục tối thiểu nếu người vận hành sau này chủ động tiếp tục: đăng nhập trực tiếp tại http://127.0.0.1:18080/ trong Browser tab của Screen panel bằng credential QA đã chỉ định, rồi QA tiếp tục checklist; không gửi secret qua chat. Hiện không đề nghị người dùng thực hiện lại bước đã từ chối.

Lượt này chỉ xác minh HEAD/status và hash evidence đã lưu, cập nhật báo cáo; không đọc credential, không mở browser/đăng nhập, không chạy lại tests, không mutation/queue/lab/ZAP/deploy hoặc tác động runtime/Run #2. Không có automation của bot cần dừng. Evidence bổ sung: [sign-in-declined.json](qa-browser-05/sign-in-declined.json). Các mục bên dưới là lịch sử.

## QA-BROWSER-05 — độc lập 2026-11-15T22:13:26.642926+07:00

**Tổng thể PARTIAL; browser asset parity PASS; authenticated Browser E2E BLOCKED.** Trạng thái này thay thế blocker bundle cũ tại QA localhost:18080; không xác nhận parity runtime cổng 8000.

Đã đọc handoff QA-PARITY-05, localhost-verification.json và QA-WORKFLOW-04; HEAD trực tiếp bdbba9933ca057cb2247c3a1de9b3ee239c452bd, giữ mọi diff. Python 3.14.8, Node v26.12.1; thời gian UTC+07:00. OpenAPI SHA-256 dfff32264cc1eaf1714a18fe063399664d726d70b437866904e4d8f2f075810b; ownership fixture a799ce97a89a89acb03b543b9a33def3f869c4bb3835e6810c197e14ab41c72f. Lab digest NOT VERIFIED vì không truy cập lab. Image QA theo bàn giao ec57dc2d6b0bd70042a7f42727ba7470c87563b492219c20fb1f20df5155ff9b; chưa xác minh lại image độc lập trong lượt này.

| Bước | Kết quả độc lập |
|---|---|
| Mở Browser đúng http://127.0.0.1:18080/ | PASS; title Trạm kiểm thử phân quyền; form Mật khẩu quản trị/Vào trạm kiểm thử |
| GET + SHA-256 JS/CSS bằng browser | PASS; HTTP 200, cả hai hash khớp localhost-verification.json |
| Đăng nhập an toàn | BLOCKED; không có saved login; cơ chế không nhận file credential cục bộ |
| Alias/role/credential configured; web role khác lab role | NOT_RUN sau login |
| Resource owner; từng case policy/version ALLOW/DENY; coverage 3 role | NOT_RUN sau login |
| Analyze baseline/reason/provenance | NOT_RUN sau login |
| Compare manual/ZAP NOT_RUN; artifact UNAVAILABLE | NOT_RUN sau login; trạng thái này mới là kỳ vọng từ bàn giao |

Bằng chứng browser đã rút gọn: qa-browser-05/browser-verification.json. Không có step number được browser trả về; các bước ghi theo thứ tự thực hiện, không tự gán recorded step. Không chụp form có credential. Không đọc file password, không gửi secret vào chat/log/JavaScript hay đăng nhập qua shell để thay bằng chứng Browser. Saved-login thất bại chỉ chứng minh cơ chế đó không có credential, không phải toàn bộ browser hỏng.

Khắc phục tối thiểu: người vận hành đọc cục bộ file đã chỉ định /tmp/t18-qa-parity-05.password và nhập trực tiếp tại Browser tab của Screen panel, rồi xác nhận Done trên yêu cầu đăng nhập. Không gửi mật khẩu qua chat. Sau đó tiếp tục cùng URL và toàn bộ checklist authenticated phía trên.

Không chạy lại full tests; 107 backend/34 frontend là kết quả QA-WORKFLOW-04, 37 frontend là báo cáo implementation, không phải test mới của lượt này. Unit/regression mới NOT_RUN; live lab/E2E thực nghiệm NOT_RUN. Không queue/mutation/login thành công, runtime DB/Run #2/lab/ZAP/deploy hoặc production changes. Synthetic 3 roles không đạt gate thực nghiệm 3+/5 roles; R1/R4/R5/R8 chưa nghiệm thu. Resource edit bị loại khỏi package chỉ đọc; manual/ZAP provenance/importer và disposable BFLA vẫn thiếu.

# QA-WORKFLOW-04 — kiểm chứng độc lập

Ngày 2026-11-15 21:57 UTC+07:00. Gửi T18 Lead. Verdict: **PARTIAL; Browser E2E BLOCKED**.
HEAD bdbba9933ca057cb2247c3a1de9b3ee239c452bd. Giữ toàn bộ diff sẵn có; chỉ ghi báo cáo này và cập nhật ba tài liệu trạng thái được giao. Đã đọc cả bốn báo cáo foundation/UI/Analyze/Compare, git status và review độc lập contract/frontend/Compare; không sửa production.

## Kết quả thực chạy

- Backend tích hợp: **107 passed, 2 warnings, 15.21s; exit 0**. SQLite tmp_path, worker/dispatcher no-op, socket connect/connect_ex blocked. Đây là regression tổng hợp, không phải lab.
- Frontend: `npm --prefix frontend test -- --reporter=dot`: **34 passed, 4 files, 9.90s; exit 0**. React/jsdom/mock API, không phải Browser E2E.
- `npm --prefix frontend run build`: exit 0; Vite 8.3.5, 17 modules, 560ms.
- `npm --prefix frontend run lint`: exit 0; TypeScript tsc -b --noEmit, không phải ESLint.
- `git diff --check`: exit 0.
- Python 3.14.8, Node v26.12.1, npm 12.2.1. Warnings: anyio assertion rewriting, Starlette/httpx deprecation; startup pytest-asyncio loop-scope unset.

Command backend từ root (không skip test lỗi):
```python
from unittest.mock import patch
import pytest
async def noop(*args, **kwargs): pass
names=['test_research_comparison','test_web_demo_evidence','test_web_demo_contracts','test_research_matrix_contract','test_batch_plan','test_matrix_generator','test_run_snapshot','test_update_api','test_evaluator','test_finding_persistence','test_batch_runner_regressions']
args=['backend/tests/'+n+'.py' for n in names]+['backend/tests/test_workflow_api.py::test_workflow_configuration_survives_api_reload','-q','--tb=short']
with patch('backend.app.main.worker_loop',noop), patch('backend.app.main.external_lab_dispatcher_loop',noop), patch('socket.socket.connect',side_effect=AssertionError('QA network blocked')), patch('socket.socket.connect_ex',side_effect=AssertionError('QA network blocked')):
 raise SystemExit(pytest.main(args))
```
Thực thi bằng `.venv/bin/python` qua stdin. Không chạy full backend suite có enqueue/lifecycle ngoài phạm vi.

## Ma trận bằng chứng

| Hạng mục | Regression cô lập | Browser/runtime mới |
|---|---|---|
| Alias/role, resource owner; edit giữ/thay identifier | PASS (frontend mock + API/SQLite reload) | BLOCKED |
| Matrix đơn/batch, policy/version, selected GET, filters, 3/5 identity synthetic | PASS | BLOCKED; 3+ roles thực nghiệm NOT VERIFIED |
| Analyze owner baseline, typed protected fields, finding đúng run/case | PASS | BLOCKED |
| Compare persisted run/case, historical policy, NOT_RUN/UNAVAILABLE | PASS | BLOCKED |
| Redaction, stale responses khi đổi project/run | PASS trong regression | BLOCKED |
| Runtime cancellation/crash/accounting/no replay | Synthetic runner regression PASS | NOT_RUN |
| Manual/ZAP/BFLA mới | NOT_RUN | NOT_RUN |

## P1 — runtime chưa chứa implementation được bàn giao

Không phát hiện P0 mới trong phạm vi review/tests đã chạy. **P1 deployment parity blocker**, không phải kết luận lỗi production code:
- Browser được cấp mở `http://127.0.0.1:8000/`, title Trạm kiểm thử phân quyền; chỉ thấy form đăng nhập. Không có saved login. Chưa kiểm tra authenticated account/project/run.
- Browser đọc script bằng GET và SHA-256: `/assets/index-C0TVFM7Q.js`, HTTP 200, `f7c76b1cc7d69d59c3bc00b8a4e92ffe4da3ea4bd8b87f89a842e07467b475d5`.
- Fresh local build: `/assets/index-BSZgHv66.js`, SHA-256 `9a255b8e4f98340579c3e3b3ed1677c060122c37a4fe899d5e31ecef0b5e3b69`.
- `docker inspect --format '{{.Image}}' deploy-authz-web-1`: exit 0, image ID `sha256:449951653ce9ba0acb37caf6cbc4048dec35de45f0ca6f3009df8ffb72cd5aae`.
- Read-only `docker exec ... sha256sum` exit 0, không mở DB, queue hoặc lab:

| File / vị trí contract mới | Workspace SHA-256 | Container SHA-256 |
|---|---|---|
| backend/app/api/workflow_routes.py:595 (Compare GET) | 25fb2292444e9d93837a45ca096578a93fef64f9bce49c94c0621eab0b88451d | 91d1b350cb5659726a5966a4727e88bf2c5080377ec6af961dc96dc8d658a9c4 |
| backend/app/api/workflow_schemas.py | 9116410696d70caedb4fc5e7faee54f5e32299924d436974f008146cc0291e34 | bde239490d63caac1acc6eabe8e6078a927943ec7477ae8f21b7ee34da12ad4a |
| backend/app/workers/runner.py | 0770cee76b7ec42e12532fcd3019c2a4dc7b257842d08941fa039517f9c49f0b | 070c526c4d5fb75257ebd935bcdc12e2a02a7eb9e4bb7c49598f7e1933bd318e |

UI liên quan: frontend/src/App.tsx:140 resource edit, :144 CaseMatrix, :221 protected-field rendering, :234 ComparePanel. Hash mismatch chứng minh chưa có parity; không suy đoán backend endpoint mới tồn tại trên runtime. Probe `/openapi.json` nhận HTML và JSON parse error, không dùng làm bằng chứng route có/không.

## Inventory fixture / giới hạn

OpenAPI fixture `tools/authorization-lab/src/authz_lab/fixtures/vampi_spec.json` SHA-256 `dfff32264cc1eaf1714a18fe063399664d726d70b437866904e4d8f2f075810b`.
Ownership fixture cùng thư mục `ownership.csv`: `a799ce97a89a89acb03b543b9a33def3f869c4bb3835e6810c197e14ab41c72f`.
Đây là fixture source, không chứng minh lab đang chạy đúng digest. Lab digest chưa kiểm chứng vì không vào lab. Evidence trong báo cáo là command/result/hash và browser snapshot đã giới hạn ở login/static asset; không token/password/response body nhạy cảm. Không tạo raw dump.

## Handoff còn thiếu

- Lead/implementation: phục vụ bundle/backend mới trong môi trường được phép; cung cấp môi trường QA biệt lập và đăng nhập. QA không tự deploy. Sau đó Browser E2E account → owner → matrix → Analyze → Compare, edit identifier chỉ trên fixture biệt lập; không mutation runtime.
- Implementation: importer/manifest mapping manual/ZAP theo persisted run/case và provenance được xác minh; không lấy historical artifact tự ghép. Single-run legacy key giữ nguyên, compatibility regression không đồng nghĩa canonical migration.
- BFLA owner: thực nghiệm disposable theo preflight/attestation riêng; chưa có execution mới. Không ZAP/BFLA trong lượt QA này.
- Writer: cập nhật báo cáo/runbook theo trạng thái regression PASS, Browser BLOCKED, R1/R4/R5/R8 chưa nghiệm thu; không gọi synthetic tests là thực nghiệm.

Không runtime DB, queue, lab traffic, target precheck/verify, mutation, deploy, commit/push/reset hoặc thay Run #2. Browser login là blocker độc lập với parity. Kiểm tra automation: không có automation của bot; không có monitor cần tắt.
