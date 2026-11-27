# CMP-01 — comparison/timing hardening

Ngày 2026-11-15, T18 ZAP Comparison. Root `/home/cuong/Dự án/Bảo mật web/Project`; HEAD xác minh `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Đọc README root/lab, comparison audit và compare implementation report; không tìm thấy AGENTS.md trong repo và các thư mục cha đã kiểm tra. Bốn file được giao không có diff trước sửa; giữ mọi diff backend/frontend và evidence cũ.

## Kết quả

**PASS regression CMP-01; tổng thể thực nghiệm vẫn PARTIAL/NOT VERIFIED.**

Chỉ sửa `tools/authorization-lab/src/authz_lab/evaluation/{comparison,timing}.py` và `tools/authorization-lab/tests/evaluation/{test_comparison,test_timing}.py`; tạo báo cáo này.

- Bỏ mặc định 12 case/2 BOLA và khẳng định hidden-200 exposure. Thiếu/invalid artifact giữ null, functional_status UNAVAILABLE. Số 7 manual là kích thước mẫu thiết kế, không phải số quan sát hoàn thành.
- Thêm keyword `verification_path` để đọc observations độc lập timing. Counts AVAILABLE có source; không tuyên bố fresh baseline hay ground truth. Adjacent legacy discovery chỉ trong cùng thư mục timing, không tìm parent có nguy cơ trộn run. Malformed/empty/unknown outcome records giữ unknown; số 0 chỉ xuất hiện khi danh sách observations hợp lệ thực sự không chứa outcome đó.
- Legacy script_timing_path đi qua strict loader; TimingEvidence AVAILABLE truyền trực tiếp cũng được revalidate. Thiếu timing không làm mất counts chức năng; thiếu counts không được bù từ timing.
- Manual đủ 7 observations hợp lệ vẫn COMPLETED_NO_TIMING nếu stopwatch thiếu hoặc invalid; không suy elapsed=0. Observed HTTP phải 100–599, duplicate/incomplete rows pending. NaN/inf/âm bị loại; tổng thời gian không hữu hạn không được COMPLETED có timing.
- ZAP yêu cầu explicit COMPLETED + integer scan_result_count không âm + danh sách findings hợp lệ và không vượt count. Payload thiếu/status lạ không tự COMPLETED, trả INVALID/null. NOT_RUN giữ nguyên; bootstrap giữ NOT_RUN. scan rows vẫn không phải TP hoặc số lỗ hổng được chứng minh.
- BFLA chỉ EXECUTED khi overall_verdict thuộc allowlist và cases có ID/verdict hợp lệ, không trùng, không mâu thuẫn verdict tổng. NOT_RUN/failed payload không được biến thành EXECUTED. INCONCLUSIVE được giữ nguyên khi observations hợp lệ, không suy thành confirmed. Legacy BFLA producer không có status vẫn được nhận qua cấu trúc findings hợp lệ; đây là validation summary, không chứng thực receipt/attestation.
- Loader timing xử lý read error và giá trị int cực lớn; reject boolean, NaN, ±inf, âm; không fallback legacy khi current artifact đã tồn tại nhưng invalid.

## Fresh commands và evidence kiểm thử

Từ root:

```sh
PYTHONPATH=tools/authorization-lab/src .venv/bin/python - <<'PY'
from unittest.mock import patch
import pytest
with patch('socket.socket.connect', side_effect=AssertionError('network blocked')):
    raise SystemExit(pytest.main(['tools/authorization-lab/tests/evaluation', '-q', '--tb=short']))
PY
```

Lượt cuối **51 passed, 4 subtests passed in 0.25s; exit 0**. Socket connect bị chặn trong toàn bộ process; artifact test nằm trong TemporaryDirectory riêng. Không orchestration CLI thực hay lab request. Regression gồm absence/null, malformed functional records, counts không timing, direct/legacy timing bypass, bootstrap/invalid completed ZAP, invalid/contradictory/duplicate BFLA, cross-run parent discovery và invalid-current không fallback legacy. Tests evaluation hiện hữu cùng chạy PASS.

`git diff --check`: **exit 0** sau lượt sửa cuối. Warning pytest-asyncio fixture loop scope hiện có, không ảnh hưởng kết quả. Lượt đầu collection exit 2 do typo import khi sửa; đã sửa trước các lượt PASS (26 tests, rồi 49, cuối 51); không skip/xfail để che failure.

## Compatibility và phần chưa xác minh

Giữ signature cũ và alias build_week4_comparison; thêm keyword tùy chọn verification_path. Output giữ các key cũ nhưng unknown nay null; consumer phải chấp nhận INVALID, functional_status và nullable counts. Artifact timing legacy thiếu status MEASURED nay bị reject có chủ ý. Không rewrite results lịch sử. Chưa nối keyword mới vào orchestration CLI vì ngoài ownership; caller có thể truyền explicit functional artifact khi được owner cập nhật.

Importer/cohort vẫn thiếu: chưa có canonical case/run mapping, policy/fixture versions và digest/provenance review giữa manual/custom/ZAP; adjacent files không chứng minh cùng cohort. Không tính TP/FP/FN, không đưa historical CLI artifacts vào web, không gán cho Run #2. Validated summary không thay thế reviewed ZAP context, attestation, auth verification hoặc execution receipt. Manual/ZAP/BFLA thực nghiệm, timing benchmark cùng cohort và gate 3/5 roles chưa nghiệm thu; Browser E2E thuộc QA riêng.

Không sửa web/frontend/schema, CLI orchestration, runner/evaluator BFLA; không đọc secret, mở runtime DB, queue/network/lab/ZAP/deploy, commit/push/reset/xóa evidence hoặc sửa results lịch sử. Kiểm tra automation cuối: bot không có automation. Bàn giao Lead review và independent QA; không tự nhận hoàn tất toàn bộ.
