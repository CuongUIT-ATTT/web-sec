# Compare — triển khai đọc kết quả theo run/case

Ngày 2026-11-15, T18 ZAP Comparison. HEAD xác minh trước sửa: `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Working tree có sẵn Matrix/Analyze/foundation/backend changes và audit files; giữ nguyên. Đã đọc báo cáo comparison audit, foundation, UI Matrix và Analyze; kiểm tra source hiện có trước sửa. Xác nhận các file `results/week4_comparison_final.json`, `results/zap/zap_access_control_report.json`, `results/zap/zap_run_status.json` tồn tại; chỉ đọc metadata whitelist. Hai ZAP JSON tự khai schema 3 / COMPLETED, report 15 scan rows. Đây không phải fresh execution, không chứng minh join với run web. Không import hoặc xuất bodies/context/credentials.

## Phạm vi thay đổi

- `backend/app/api/workflow_schemas.py`: thêm ComparisonView/Case/Method DTO. Không sửa các schema Matrix/Analyze cũ.
- `backend/app/api/workflow_routes.py`: thêm authenticated GET `/api/projects/{project_id}/runs/{run_id}/comparison`. Kiểm tra project/run, đọc đúng RunResult theo run_id, giữ nguyên persisted case_key (kể cả legacy/null), dùng `_result_metadata` sẵn có để validate evidence run/case và allowlist. Không lấy preview hay policy hiện tại, không import CLI hoặc mở artifacts tùy ý.
- `frontend/src/api.ts`: thêm contract Comparison và hàm đọc endpoint.
- `frontend/src/App.tsx`: thay bảng tĩnh bằng ComparePanel; chọn run trong project, hiển thị case × MANUAL/T18/OWASP ZAP, policy/version/resolution lịch sử khi evidence khớp, execution observation/HTTP/conclusion, provenance/artifact và timing. Chặn late response sau đổi run/project; lỗi đọc không bị diễn giải thành NOT_RUN. Không sửa phần Matrix/Analyze, không đổi styles.
- `backend/tests/test_research_comparison.py`: 4 tests SQLite tạm + route TestClient, dùng fixture contract hiện có, không app lifespan/worker. Kiểm tra project/run isolation, exact key legacy/canonical không tự nối, policy v7 không bị snapshot v999 thay thế, null case, empty run, missing/mismatched evidence, redaction canary, không mutate snapshot synthetic.
- `frontend/src/Compare.test.tsx`: 6 tests, chọn đúng run, late response, mismatch run, empty result, missing methods/provenance và policy run binding + redaction canary.

Provenance T18 là reference thật `run:{persisted_run_id}:result:{persisted_result_id}` từ bản ghi SQLite, không phải artifact/digest tự tạo. Artifact luôn UNAVAILABLE vì chưa có artifact reference được xác minh trên nguồn này. Manual/ZAP không có observation đã được ánh xạ và kiểm chứng cho run/case web nên NOT_RUN, provenance UNAVAILABLE. Không đưa fixture vào runtime; mocks chỉ trong test files. Thiếu evidence không xóa observation đã lưu; policy lịch sử ghi UNAVAILABLE. Null key không được gán key suy đoán. Không có confusion metrics, ground truth hay elapsed time được bịa; timing TIMING_NOT_AVAILABLE. BFLA được giải thích là thực nghiệm riêng, không trộn vào GET cohort.

## Fresh verification

Backend command từ root:

```sh
.venv/bin/python - <<'PY'
from unittest.mock import patch
import pytest
async def noop(*args, **kwargs): pass
with patch('backend.app.main.worker_loop', noop), patch('backend.app.main.external_lab_dispatcher_loop', noop), patch('socket.socket.connect', side_effect=AssertionError('network blocked')):
    raise SystemExit(pytest.main(['backend/tests/test_research_comparison.py', 'backend/tests/test_web_demo_evidence.py', 'backend/tests/test_web_demo_contracts.py', 'backend/tests/test_research_matrix_contract.py', '-q', '--tb=short']))
PY
```

**85 passed, 2 warnings, 7.38s, exit 0.** DB fixtures dùng tmp_path SQLite. Worker/dispatcher no-op và socket connect blocked trong process test. Warnings: anyio assertion rewriting, Starlette/httpx deprecation; thêm pytest-asyncio loop-scope startup warning. Không chạy lab/queue hoặc DB runtime.

Frontend từ root:

```sh
npm --prefix frontend test -- --reporter=dot
npm --prefix frontend run build
npm --prefix frontend run lint
git diff --check
```

Lượt cuối: **34 passed / 4 files, 7.68s, exit 0**. Build exit 0 (Vite 8.3.5, 17 modules), lint exit 0. Diff-check exit 0. Test logs tạm `/tmp/t18-compare-frontend-final.log`. Lượt đầu có 12 frontend failures: test Compare dùng exact-text matcher trên cell nhiều text nodes và key sibling Compare trùng station-grid gây React reconciliation/DOM duplication. Đã đổi key Compare có prefix riêng và sửa matcher của test Compare; không sửa tests Matrix/Analyze cũ. Lượt giữa 32 pass; thêm 2 policy-binding/redaction tests thành 34 pass. Không che failure bằng skip.

## Giới hạn và bàn giao

- **Triển khai Compare đọc dữ liệu web: PASS regression; R5 thực nghiệm / tổng thể demo: PARTIAL.** Chưa có importer/manifest đã xác minh cho manual/ZAP; vì vậy hai phương pháp chưa thể hiển thị historical completed observations trong web. Cần cohort/case mapping có version, provenance nguồn thật và review QA trước khi nối, không đoán từ path hoặc raw resource ID. Historical CLI artifacts vẫn nằm ngoài comparison web; code không gọi CLI.
- Không có ground truth độc lập để tính TP/FP/FN, không timing cùng cohort, không manual worksheet được liên kết. NOT_RUN chỉ nói về observation được liên kết ở web, không phủ nhận artifact ngoài web.
- Run chưa có persisted result trả cases=[] và thông báo chưa có observation, không dựng dòng từ current preview/snapshot hoặc giả coverage. Null key hiện UNAVAILABLE; không tự kết luận coverage hoặc completeness.
- QA cần kiểm chứng Browser E2E trên bundle/backend được Lead phục vụ, chọn run/case thật và rà redaction; test DOM/TestClient không phải bằng chứng lab. Chưa deploy hoặc xác minh trình duyệt đang phục vụ user.
- BFLA/disposable lab là dependency nghiệm thu riêng của owner; không có execution mới hoặc kết quả BFLA được thêm vào Compare. Gate 3+ roles và R5 acceptance còn phụ thuộc QA/manual/ZAP có phê duyệt riêng.
- Không sửa evaluator/runner, model/migration, snapshots lịch sử; không mở DB runtime, tác động Run #2, queue/lab/network/ZAP active/BFLA/deploy/commit/push/reset/xóa. Build chỉ tạo bundle cục bộ. Không có automation của bot khi kiểm tra cuối.

Bàn giao ownership Compare frontend/API/schema/test cho T18 Lead và QA; các owner có thể tiếp tục review, chưa tuyên bố nghiệm thu thực nghiệm hoặc Browser E2E.
