# AUTOAUTH-QA-04 — QA độc lập, 2026-11-16

Gửi T18 Lead. Tổng thể **PARTIAL**. HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`, dirty/uncommitted. Chỉ thêm audit-final; không sửa production/tests, không mở persistent SQLite/Run #2, không chạy write lab/ZAP, không commit/push. Build tái tạo frontend/dist đã ignored.

## Kết quả thực chạy

| Phạm vi | Kết quả | Evidence |
|---|---|---|
| Backend regression | PASS: 221 tests, exit 0 | autoauth-qa-04/backend.log; execution.json |
| Frontend regression | PASS: 55 tests / 6 files, exit 0 | frontend.log |
| Lint/build/diff | PASS: mỗi command exit 0 | lint.log, build.log, diff.log |
| Focused model/execution, actual loopback | PASS: 51 tests, exit 0; nằm trong 221, không cộng thêm | focused.log; loopback-*.json |
| Deterministic coverage | PASS: shared-role fixture 3 identities/2 roles = 18 BOLA + 9 BFLA; 3-role probe = 27; 5-role probe = 50 BOLA + 15 BFLA = 65; mỗi identity 9 hoặc 13 case, không exclusion | model suite; coverage.json |
| Snapshot/history/credentials/no replay | PASS regression/temp DB; browser legacy sentinel giữ nguyên sau run/revision | backend/focused logs; independent-checks.json |
| Mounted browser five-step | PASS synthetic: Setup/Matrix/Run/Results/Comparison, explicit 3 cases, 8 planned/transport/responses; 2 confirmed + 1 consistent | browser-observations.json |
| Browser stale revision | PASS: preview c97e… đổi thành 8a33… trong temp DB bằng SQLAlchemy để mô phỏng operator khác; queue hiển thị STALE_PREVIEW, clear selection, không tạo run mới; run cũ giữ revision c97e… | browser-observations.json: stale/comparison |
| Browser cancellation | PASS: slow synthetic /me giữ 12 giây; click Hủy khi RUNNING, transport 1/responses 0; sau đó CANCELLED, planned 4/transport 1/responses 1/cancelled case 1; không actor request | cancellation.json; cancel_fixture.py |
| Redaction public DTO | PASS: không bearer value/protected body value trong runs/results/Comparison; metadata boolean được giữ | independent-checks.json; loopback redaction assertions |
| Desktop visual | PASS hẹp: screenshot mounted browser 1265×800, nav/counters/cancel terminal đọc được; document scrollWidth 1265 | screenshot trong hội thoại; comparison browser artifact width |
| Responsive 390/768/1024/1440 | NOT VERIFIED: mounted browser hiện không cung cấp resize viewport; không thay bằng shell browser. CSS inspection không chứng minh mobile runtime | blocker Lead |
| Persistent DB/Run #2 checksum | NOT VERIFIED: bị loại khỏi phạm vi, không mở/checksum DB này | isolation environments |
| Manual/ZAP/write-BFLA research | NOT_RUN: không có execution được phép trong ticket | Comparison hiển thị NOT_RUN/UNAVAILABLE |

## Hash và trust boundary

Đã đọc ba handoff trước kiểm thử. Model manifest **11/13 khớp, exit 1**: authorization_model.py và authorization_routes.py khác hash cũ; đây là hai file execution handoff công khai nhận sửa tiếp. **Không ghi manifest cũ PASS**. Execution manifest **56/56 khớp**, web **24/24 khớp**, mỗi exit 0. Hash nguồn backend/app và frontend/src trước/sau regression giống nhau (execution.json); fixture embedded OpenAPI/model SHA-256 được inventory. Không truy cập lab để lấy digest: lab digest NOT_RUN. Đây là reconciliation nguồn hiện tại, không phải chứng minh manifest model cũ còn nguyên.

Runtime Python 3.14.8, Node 26.12.1, npm 12.2.1; chưa chứng minh parity Python 3.11/Node 22 của image Docker. Một cảnh báo deprecation Starlette/httpx; không có test failure.

## Traceability và tính tái lập

Thư mục evidence tuyệt đối: `/home/cuong/Dự án/Bảo mật web/Project/audit-final/autoauth-qa-04/`.

Browser chính dùng `http://127.0.0.1:18984`, SQLite `/tmp/autoauth-qa-04-qx5ut1dl/isolated.sqlite`; browser cancellation dùng app 18985 và SQLite khác ghi trong cancel-environment.json. **Run #2 ở cả hai fixture đều là run tạm**, tuyệt đối không đồng nhất với persistent Run #2.

Browser execution policy `c97e3024dcf785687194c5adcb19b0c1a3569c7265dafbc6d901ae8cfd39d3d1`:

- `autoauth:v1:project:1:operation:1:BOLA:resource:3:actor:1` → temporary run 2 → result 1 → autoauth-result:1 → run:2:result:1.
- `autoauth:v1:project:1:operation:2:BFLA:resource:-:actor:1` → temporary run 2 → result 2 → autoauth-result:2 → run:2:result:2.
- `autoauth:v1:project:1:operation:2:BFLA:resource:-:actor:3` → temporary run 2 → result 3 → run:2:result:3, không finding vì policy consistent.

Các loopback-*.json ghi riêng từng kind/verification failure, server receipts/case IDs/revision. Fixtures là synthetic cố ý disclosure, không phải ground truth Controlled BOLA Lab hay phát hiện nghiên cứu. Preview POST luôn disabled/NOT_RUN.

Exact command/exits/time UTC trong execution.json. Commands bổ sung:

```sh
AUTOAUTH_EXEC_EVIDENCE_DIR="$PWD/audit-final/autoauth-qa-04" .venv/bin/python -m pytest backend/tests/test_authorization_execution.py backend/tests/test_authorization_model.py -q
# exit 0, 51 passed; loopback artifacts được ghi mới
.venv/bin/python audit-final/autoauth-qa-04/coverage_probe.py
# final exit 0; coverage.json
.venv/bin/python audit-final/autoauth-qa-04/browser_fixture.py
.venv/bin/python audit-final/autoauth-qa-04/cancel_fixture.py
# foreground temporary apps, Ctrl+C sau kiểm; cả hai exit 0
```

Hai lượt đầu coverage probe exit 1 vì QA thêm resource external_id rồi secret fingerprint bị trùng với seed; chỉ sửa prefix trong audit probe, final exit 0. Đây là lỗi fixture QA, không phải product regression; không giấu thành first-run PASS. Browser có failed selectors (CSS :has-text không được hỗ trợ, disabled=false, tên Hủy thiếu Run #2); retry bằng role/ref thành công, không gây request trùng.

## Blocker / follow-up cho Lead

1. Cần mounted surface hỗ trợ đổi viewport để nghiệm thu responsive 390/768/1024/1440; hiện chỉ 1265px được xem.
2. Cần research owner cung cấp experimental cohort, authorized targets và execution provenance manual/T18/ZAP; write-BFLA cần scope/preflight/approval riêng. Không dùng 221 tests hoặc synthetic confirmed để đóng R5/R8.
3. Persistent preservation checksum cần owner được giao DB proof; QA không mở DB theo giới hạn ticket.
4. Cancelled case API trả `conclusion=NOT_EVALUATED`, `execution_status=CANCELLED` (khác sáu conclusion filters của Results). Không có xác nhận vi phạm giả; cần Lead quyết định chuẩn hóa taxonomy/khả năng lọc cancelled trước nghiệm thu toàn bộ UI.

Không có automation của bot (đã kiểm list rỗng). Hai app tạm đã dừng. Không còn suite failure trong phạm vi đã chạy; tổng thể PARTIAL vì các giới hạn trên.
