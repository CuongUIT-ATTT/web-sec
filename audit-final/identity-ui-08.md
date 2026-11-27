# IDENTITY-UI-08 — Legacy role follow-up

Date: 2026-11-16. This report records the resumed F1/F2 correction only; it does not independently certify the earlier UI/browser work.

## Changes

- `backend/app/services/demo_presentation.py`, `public_snapshot`: Run case labels retain role from immutable snapshot identities when display metadata or its role is absent.
- `backend/app/api/authorization_routes.py`, `authorization_results`: the same fallback applies to partially populated identity metadata.
- `backend/tests/test_authorization_execution.py`: four metadata variants (complete, legacy absent, one identity missing, role missing); compares Run and Results actor/owner/planned baseline labels, checks immutable roles, observed baseline divergence, redaction and snapshot preservation after current identity rename. An archive adapter permits only the Run lookup and result query, verifying presentation does not require current identity records. This simulates unavailable identities; no persistent deletion was performed.

## Fresh verification

Command: `.venv/bin/python -m pytest backend/tests/test_authorization_execution.py backend/tests/test_research_matrix_contract.py -k 'identity_labels or redaction' -q`

Exit 0: **6 passed, 57 deselected**. Log: `results/identity-ui-08/legacy-role-followup-tests.log`. Temporary SQLite fixtures only; selected tests issue no lab requests. `git diff --check`: exit 0 before final report creation.

No frontend changes in this follow-up, no app/lab launch, no persistent DB/Run #2 access, no snapshot migration, commit or push. Existing dirty work preserved. No related automation exists.

## Limits and provenance

Original PDF baseline #3/#5 discrepancy remains **INCONCLUSIVE**. Independent reviewer reports 12/12 saved synthetic cases with planned=observed; that is not proof of the original run's provenance. See `audit-final/identity-ui-08-baseline-review.md`.

Browser/responsive work and screenshots already present in `results/identity-ui-08/` were not rerun or independently verified in this follow-up. Complete ticket acceptance remains **PARTIAL**, pending independent QA and consolidated validation of the earlier implementation artifacts. This focused correction does not claim completion of all user acceptance criteria.

## Follow-up QA-01 / QA-02 — 2026-11-16, 21:25–21:34 giờ Việt Nam

**QA-01: sửa và regression PASS. QA-02: bản synthetic final source đã phục vụ và kiểm tra hash PASS. Ticket tổng thể vẫn PARTIAL, chờ QA độc lập kiểm tra lại.**

### Thay đổi của lượt này

- `frontend/src/AuthorizationWorkflow.tsx`: mỗi dòng Results dùng native `dl` gồm 5 cặp `dt`/`dd` cho người gọi, tài nguyên/chức năng, policy, HTTP và kết luận. Header thị giác vẫn `aria-hidden` để tránh đọc lặp; nhãn từng giá trị luôn nằm trong cây accessibility. Matrix thêm nhãn từng field khi thu thành danh sách trên màn hình hẹp.
- `frontend/src/styles.css`: nhãn Results dùng visually-hidden ở desktop thay cho `display:none`, hiện bình thường ở tablet/mobile; reset margin của definition list. Nhãn Matrix chỉ hiện ở màn hình hẹp.
- `frontend/src/AuthorizationWorkflow.test.tsx`: regression kiểm tra 5 native term/value pairs của finding được giữ, đúng nội dung, không nằm trong ancestor `aria-hidden`.
- Không sửa backend/policy/evaluator/matrix/runner ở lượt này. Giữ mọi thay đổi dirty có sẵn, không commit/push, không restart cổng 8000, không mở DB hiện hành hay Run #2 thật.

### Lệnh và exit code

Tất cả lệnh ở repo, trừ npm chạy tại `frontend/`. Evidence mới nằm trong `results/identity-ui-08/qa-followup/`.

| Lệnh | Exit | Evidence |
|---|---:|---|
| `npm test -- --reporter=verbose` | 0 | 63 PASS, `frontend-final.log` |
| `npm run build` | 0 | TypeScript/Vite PASS, `build.log` |
| `.venv/bin/python -m pytest backend/tests/test_authorization_execution.py backend/tests/test_research_matrix_contract.py -q` | 0 | 63 PASS, gồm 6 fallback/redaction tests, `backend.log` |
| `.venv/bin/python -m pytest backend/tests -q` | 0 | 242 PASS, `backend-full.log`; có deprecation warning Starlette/httpx |
| `docker build -t t18-identity-ui08-final:qa02 /tmp/t18-identity-ui08-qa02-build` | 0 | `docker-build-final.log`; context riêng chứa backend và dist đã build |
| `.venv/bin/python results/identity-ui-08/qa-followup/e2e.py queue` | 0 | Seed synthetic riêng, preview 12 cases, queue Run #1, `queue.log` |
| `.venv/bin/python results/identity-ui-08/qa-followup/e2e.py verify` | 0 | Worker hoàn tất 12 cases; 6 synthetic confirmed; repeated reads/seed giữ run/results/sentinel, `verify.log` |
| `docker exec t18-identity-ui08-final-qa02 python /app/create_archive_fixtures.py` | 0 | Append-only archive fixtures riêng; `archive-fixtures.json` |
| `.venv/bin/python results/identity-ui-08/qa-followup/e2e.py verify` sau fixtures | 0 | Original Run #1/results còn nguyên, `verify-after-fixtures.log` |
| `git diff --check` | 0 | Không lỗi whitespace tracked diff |

Lần regression đầu có 1 assertion dùng nhầm chuỗi tiếng Anh `Identity` trong khi UI dùng `Danh tính`; sửa assertion rồi chạy lại toàn frontend PASS. Build Docker đầu không COPY được dist vì `.dockerignore`; chuyển context tạm riêng, build lại PASS. Lệnh đọc assets đầu dùng system Python thiếu httpx; chạy lại bằng `.venv/bin/python` PASS. Log thất bại ban đầu được giữ, không coi là PASS.

### Synthetic final source và hướng dẫn QA chỉ đọc

URL **http://127.0.0.1:18989**; container `t18-identity-ui08-final-qa02`, volume mới `t18-identity-ui08-final-qa02-data`; lab GET synthetic chia sẻ network namespace, loopback `127.0.0.1:5099`. Không dùng volume hay DB của cổng 8000/18988. Chỉ fixture synthetic local, không live-lab/external/ZAP. Tài khoản fixture dùng password thử nghiệm giống script `e2e.py`; không có credential thật trong evidence.

`source-manifest.json` chứa image ID cùng SHA-256 host/container của 10 file: presentation backend, authorization routes, execution/model/runner, source UI/CSS và build HTML/JS/CSS. **10/10 khớp**; đặc biệt hai file backend fallback cuối đã được copy vào image mới. `served-assets-baselines.json` xác minh thêm bytes của cả JS/CSS qua HTTP khớp host; 12/12 planned baseline = observed baseline của fresh Run #1. Không chỉ so hash file trên đĩa rồi suy ra serving.

QA có thể đăng nhập URL này, chọn project **T18 Synthetic GET Demo v1** (project 2), vào Results chọn Run #1 COMPLETED; Run #2 legacy, #3 missing_role, #4 partial_metadata, #5 large_cancelled đều **là fixtures mới trong DB tạm**, không liên quan Run #2 thật. Không cần queue/seed lại. Đọc `source-manifest.json`; dùng `docker exec ... sha256sum <container_path>` để so với hash host đã lưu nếu cần. Giữ app này chạy để QA kiểm tra độc lập.

### Browser kiểm tra trên bản final source

Dùng Browser tab chính thức, không shell browser. Fresh queue→worker thực hiện qua API fixture rồi đọc Results thật trong Browser. Responsive dùng document iframe cùng origin ở **1200/768/390 CSS px**, không giả lập mobile engine/touch. `browser-assertions.json` lưu các kết quả quan sát.

- **15/15** tổ hợp 5 bước × 3 width có heading đúng và không tràn ngang document.
- Results: 12 rows, 60 native terms; cả 5 nhãn field mỗi row đều không `display:none`, không `visibility:hidden`, không ancestor `aria-hidden`; evidence mở được ở 3 width. Ảnh `after-results-desktop.png`, `after-results-1200.png`, `after-results-768.png`, `after-results-390.png` đã chụp và xem ảnh đại diện desktop/mobile.
- Matrix mobile: 6 field labels hiển thị `block`, 12 cases giữ nguyên; `after-matrix-390.png` đã xem.
- Fixture legacy Run #2: actor hiện `Danh tính #1 (user) · thiếu nhãn snapshot lịch sử`; Run summary cũng giữ role `user`. Missing_role Run #3: `userA (user) · #1`. Partial_metadata Run #4: fallback role đúng và báo thiếu nhãn. Đây là kiểm tra Browser trên backend final, đóng khoảng trống source mismatch QA-02.
- Fixture large_cancelled Run #5: 123 kết quả; trang đầu 50 rows (1 response preserved + 49 cancelled), trang cuối 23 rows. Đây là archive presentation fixture, **không phải execution/cancellation mới**; cancellation checkpoint/preserved findings thực thi đã chạy trong backend suite. Script chỉ INSERT bản ghi fixture mới, không UPDATE snapshot/result cũ; original Run #1 snapshot và kết quả được xác minh giữ nguyên.

### Ảnh trước/sau và giới hạn còn lại

Ảnh trước kế thừa: `results/identity-ui-08/before-user-results.png`, `before-user-matrix.png`; nguồn là PDF người dùng. Ảnh sau lượt này nằm trong `qa-followup/after-*.png`. So sánh bằng mắt: nhãn field rõ ở mobile, desktop giữ bố cục gọn và có term/value semantics. **Canonical automated pixel-diff: NOT VERIFIED** vì ảnh PDF cũ khác viewport/run/scale; không gán PASS từ ảnh không tương đương. Các ảnh 5 bước × 3 width đầy đủ của lượt trước vẫn giữ nguyên; lượt này chụp lại Results 3 width và Matrix mobile, còn 15 tổ hợp được kiểm tra DOM.

Full screen-reader/keyboard audit: **NOT VERIFIED**; chỉ khẳng định native semantics và computed accessible DOM regression đã kiểm tra. Rename/deleted current identity được mô phỏng trong regression bằng archive adapter; không xóa record thật. Browser large/cancelled dùng fixture, không tuyên bố cancellation runtime Browser PASS. Nguyên nhân baseline #3/#5 cũ vẫn **INCONCLUSIVE**; actual Run #2 hiện hành vẫn **NOT VERIFIED** theo phạm vi cấm mở DB. Không automation liên quan khi kiểm tra cuối lượt.
