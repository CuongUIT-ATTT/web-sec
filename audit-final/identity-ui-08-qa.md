# IDENTITY-UI-08 — QA độc lập

**Kết luận: PARTIAL — chưa đủ điều kiện nghiệm thu toàn bộ ticket.**

QA: T18 QA Evidence. Thực hiện ngày 2026-11-16, khoảng 21:15–21:24 giờ Việt Nam (UTC+07). Repo `/home/cuong/Dự án/Bảo mật web/Project`; HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Working tree dirty từ trước; danh sách ghi tại `results/identity-ui-08-qa/git-status.txt`. Không sửa production, không restart web cổng 8000, không mở DB hiện hành/Run #2, không commit/push/xóa evidence. Không chạy API lab thật, external traffic hay ZAP. Backend suite sử dụng SQLite tạm và các HTTP fixture loopback riêng.

## Kiểm thử mới do QA thực hiện

| Lệnh tại repo (trừ khi ghi khác) | Exit | Kết quả / artifact |
|---|---:|---|
| `.venv/bin/python -m pytest backend/tests -q` | 0 | **242 passed**, `results/identity-ui-08-qa/backend.log` |
| `npm test -- --reporter=verbose` tại `frontend/` | 0 | **63 passed**, `frontend.log` |
| `npm run build` tại `frontend/` | 0 | TypeScript và Vite PASS, `build.log` |
| `.venv/bin/python -m pytest backend/tests/test_authorization_execution.py backend/tests/test_research_matrix_contract.py -k 'identity_labels or redaction' -q` | 0 | **6 passed, 57 deselected**, `fallback.log` |
| `.venv/bin/python -m pytest results/identity-ui-08-qa/test_qa_contract.py -q` | 0 | **4 passed**, `independent-contract-final.log` |
| `git diff --check` | 0 | Không lỗi whitespace ở tracked diff; không phải kiểm chứng toàn bộ untracked files |

4 kiểm thử QA bổ sung độc lập chạy với **3/4/5/6 identities**, tương ứng **2/3/4/5 roles**, luôn giữ hai identities cùng role. Kiểm tra số case bằng identities × 9, mọi actor được đại diện, owner/cross-role/cross-identity/sharing/function, method/path, owner và nhãn snapshot, snapshot không bị thay đổi. Chỉ dùng fixture SQLite tạm; không dispatch HTTP.

Backend suite gồm kiểm thử cancellation với findings đã lưu, request cap/accounting, verification failures, scope guards, checkpoint/no replay, crash và persistence, redaction, policy/evaluation negatives. Đây là regression bằng fixture, không phải runtime chứng minh trên DB người dùng. Kiểm thử archive adapter xác minh Results chỉ cần Run/result records, không lookup current identities; deleted/unavailable metadata được mô phỏng, không xóa bản ghi thật. Legacy Run #2 trong test là bản ghi fixture, **không phải Run #2 hiện hành**.

Toolchain: Python 3.14.8, Node 26.12.1, npm 12.2.1. Có cảnh báo pytest-asyncio về loop scope mặc định và Starlette/httpx deprecation; không có test thất bại. Synthetic demo đăng ký operations trực tiếp, không import OpenAPI file, nên OpenAPI SHA-256 **N/A** cho fixture này. Digest source/lab image và thời gian lưu trong `execution-manifest.json`; hash PDF nguồn lưu riêng. Không đọc `.env` hay credential hiện hành.

## Browser và hình ảnh

Dùng Browser tab được cấp, **không shell browser**. Kiểm tra presentation app synthetic đã tồn tại ở `http://127.0.0.1:18988`, project 2 / run 1; không bấm queue, seed hay verify identity. Chỉ đăng nhập tài khoản fixture, đọc preview/lịch sử/kết quả và đổi bộ lọc. Web người dùng cổng 8000 giữ nguyên.

Viewport thực của document trong iframe cùng origin: **1200 / 768 / 390 CSS px**. Đây là responsive browser QA bằng iframe; không giả lập thiết bị cảm ứng hoặc mobile browser engine. Mỗi bước Setup, Matrix, Run, Results, Comparison được mở ở cả ba kích thước, capture screenshot và đo DOM: **15/15 không tràn ngang document**. `browser-assertions.json` lưu heading, width và overflow; `focused-{step}-{width}.png` là ảnh sau khi đưa workflow vào vùng nhìn. `case-matrix-*.png` và `case-results-*.png` chụp nội dung case/evidence. Các ảnh `setup-*`, `matrix-*`, `run-*`, `results-*` chụp vòng đầu có scroll chưa tối ưu, không dùng làm ảnh nghiệm thu chính.

QA đã xem ảnh đại diện desktop Results, tablet Matrix, và mobile cả năm bước cùng case Matrix/Results. Text đọc được, không thấy chồng lấp ở vùng đã xem; bằng chứng này không thay thế kiểm tra toàn bộ chiều dài mỗi trang. Kết quả không có low-level booleans ở cùng cấp với conclusion; details mở được và chứa planned baseline, reason, evidence flags, revision, run/result/case/artifact refs. Native buttons/select/details có tên; `lang=vi`, không positive tabindex. **Full keyboard/screen-reader/contrast audit: NOT VERIFIED**, có finding accessibility bên dưới.

Browser kiểm tra Matrix: 12 cases, 3 identities; userA/userB cùng role vẫn khác tên; owner và baseline có tên. Bộ lọc identity userB còn 4 dòng và đúng actor; identity userA 4, role user 8, operation books 9, resource-1 3, ALLOW 6; bỏ lọc trở lại 12. Chọn 1 case rồi mở Run giữ 1 case/3 planned requests, độc lập với Run #1 đã hoàn tất **12 cases, planned 19, transport 19**. Results có 12 dòng, lọc CONFIRMED_VIOLATION còn 6, mở evidence được. Đây là đọc run synthetic đã tồn tại, **không phải QA queue một run E2E mới**. Pagination 123 results đã chạy trong frontend regression; large-set Browser runtime chưa chạy.

Ảnh trước: `results/identity-ui-08-qa/before-user-results.png`, sao chép nguyên từ evidence implementer và đã xem; PDF nguồn được hash. Ảnh sau tiêu biểu: `focused-results-1200.png`, `case-results-390.png`, `case-matrix-390.png`. So sánh bằng mắt xác nhận trước chỉ có actor/baseline ID và evidence dài; sau có tên/role/owner/method/path và details. **Automated before/after pixel-diff: NOT VERIFIED**: ảnh cũ là PDF capture khác viewport, scale và run; không có canonical same-viewport baseline để khẳng định pixel regression PASS. Không coi hash khác nhau là screenshot comparison PASS.

## Ma trận nghiệm thu

| Yêu cầu | Đánh giá | Căn cứ và giới hạn |
|---|---|---|
| Giữ 5 bước | PASS | Browser 15 screen/width combinations; source và regression |
| Identity-aware Matrix, mọi identities, filters/selection | PASS | Browser 12 cases; frontend tests; 4 QA matrix contracts nhiều identities/roles/owners |
| Nhãn lịch sử sau rename, missing metadata, legacy | PASS ở regression; PARTIAL runtime | 6 focused tests chạy lại, immutable snapshot và archive adapter; chưa Browser legacy trên backend mới |
| Run tách selection khỏi queued/historical | PASS trên synthetic | Browser 1 selected/3 planned và historical 12/19/19, revision/status rõ |
| Compact Results và expandable evidence | PASS về chức năng; PARTIAL accessibility | Browser và frontend regression; finding QA-01 |
| Actor/role/resource/owner/operation/planned và actual baseline | PASS trên synthetic; PARTIAL tổng thể | Browser + immutable snapshot tests, nhãn actual từ persisted observed ID |
| Baseline provenance của evidence synthetic | PASS về consistency | QA tự join 12/12 preview/planned/observed và revision, `baseline-artifact-check.json` |
| Nguyên nhân #3/#5 trong PDF cũ | INCONCLUSIVE | Không có original preview revision/run snapshot/evidence được phép đọc; không suy diễn |
| Legacy/current Run #2 | NOT VERIFIED đối với run thật | Chỉ source và synthetic legacy fixtures; không mở persistent DB |
| Large results | PASS regression; NOT VERIFIED Browser large-set | Frontend pagination 123 rows, 50/50/23 |
| Cancellation, durable findings, request accounting/no replay | PASS regression; NOT VERIFIED Browser runtime mới | Backend tests và frontend cancel-once; không queue/cancel trên app cũ |
| Giữ policy/evaluation/matrix/GET-only/budget/journal | PASS regression; PARTIAL attribution | Toàn backend suite PASS, source reviewed; dirty tree lớn, nhiều untracked files nên không thể gán mọi diff cho ticket này |
| Không sensitive body/token/private marker trong DTO | PASS regression | Allowlisted evidence, sentinel redaction tests; không thu raw body hay secret vào báo cáo |
| Responsive/browser E2E | PARTIAL | 15 screen-width checks, filters/details/synthetic historical consistency; chưa fresh full queue→worker→Results E2E của QA |
| Before/after screenshots | PASS capture/manual comparison; NOT VERIFIED pixel-diff | Có ảnh nguồn và ảnh QA mới, khác run/viewport không phải pixel baseline chuẩn |

## Findings / blockers cụ thể

**QA-01 — medium: Results thiếu nhãn cột accessible trên desktop.** `frontend/src/AuthorizationWorkflow.tsx:97-98`: header `.result-columns` đặt `aria-hidden="true"`, các dòng là div/article không có table/header associations. `frontend/src/styles.css:101` ẩn `.mobile-label` bằng `display:none`; tại 1200 px cả năm cell labels là `none`. Browser xác nhận header hidden, không semantic table, labels hidden (`accessibility.json`). Người dùng trình đọc màn hình không được nhãn rõ cho ALLOW/HTTP/conclusion. Đề nghị giữ tên field dạng visually-hidden accessible ở desktop, hoặc dùng table/list semantics với nhãn từng giá trị; retest accessibility. QA không sửa production.

**QA-02 — verification blocker: Browser backend không cùng source revision với fallback mới.** Image synthetic web `sha256:82521d9ae03edd9a455312d75ffd2ab057649d7240816a00f3ce96add9f651f7`. Source host `demo_presentation.py` SHA-256 `78a9c90fd38b1f96c58c2c23efe688afeeff24bc07669906783478781ef3ef38`, container `ea6af3170703b84a62d099b1014688b985d2da862593273958c2f64c34be92ce`; `authorization_routes.py` host `b093552c519220ada5df5c4c5edb4239494680ed6a073e8190afc56f7dbb1688`, container `5e3fc59eeccb720504c9843fddeb7b1554dbe1b74fff7760aacdff565d9aa790`. Frontend đang phục vụ đúng bundle build QA `index-WPpSUBel.js`. Fallback source tests PASS, nhưng không tuyên bố Browser xác nhận fallback mới. Cần bản synthetic riêng build từ final source và kiểm tra legacy/missing role lại; không restart web người dùng.

**QA-03 — evidence gaps còn mở:** original #3/#5 và current Run #2 không xác minh trong phạm vi; full latest-build E2E mới, Browser large set/cancellation/legacy, screen-reader keyboard audit và canonical screenshot pixel comparison chưa đủ evidence. Đây là giới hạn nghiệm thu, không phải kết luận các chức năng đó bị lỗi. Báo cáo không yêu cầu mở DB hiện hành trái phạm vi.

**Ghi chú UX thấp:** mobile Matrix ẩn thead (`styles.css:120`) nhưng không có field labels cho từng td, và dùng thuật ngữ `CROSS_IDENTITY` thay vì diễn giải cross-user; Results vẫn hiện conclusion/status code kỹ thuật dài. Tên người dùng/owner đã rõ hơn đáng kể, nhưng một người mới vẫn cần giải thích các thuật ngữ. Có thể cải thiện nhãn tiếng Việt ở presentation mà không đổi semantics.

## Provenance / kết thúc

Đã tự đọc source presentation, queue snapshot, preview và runner, không coi báo cáo implementer là execution proof. Snapshot labels lấy ở queue; Results planned từ snapshot, actual từ result evidence, NOT_OBSERVED không được thay bằng planned/current config. Synthetic 12/12 equality không giải thích được ảnh cũ. Build/tests mới chạy là evidence độc lập; saved synthetic receipts và ảnh trước là evidence kế thừa, đã phân loại rõ.

Artifact directory: `/home/cuong/Dự án/Bảo mật web/Project/results/identity-ui-08-qa/`. Có log, 4 test QA, browser assertions, ảnh, execution manifest và SHA-256 inventory. Hash được kiểm tra sau khi tạo. Không có automation liên quan khi kiểm tra ngày 2026-11-16. Skill design-taste-frontend chỉ áp dụng checklist đọc/responsive/accessibility; không chạy shell Chrome/gate vì yêu cầu hiện hành chỉ cho Browser tab và QA không sửa production.

Đề nghị Lead giao sửa QA-01 và dùng synthetic build final source để đóng QA-02; giữ các mục historical provenance/pixel-diff chưa xác minh trong verdict cho đến khi có evidence phù hợp. **Không nâng ticket tổng thể lên PASS ở lượt này.**

## QA độc lập follow-up cuối — 2026-11-16, 21:35–21:41 giờ Việt Nam

**QA-01 CLOSED / PASS. QA-02 CLOSED / PASS. Ticket tổng thể PARTIAL do các giới hạn còn lại bên dưới.** Phần này thay thế trạng thái hai blocker trong báo cáo trước; các quan sát lịch sử được giữ nguyên.

Phạm vi: chỉ đọc synthetic `http://127.0.0.1:18989`, container `t18-identity-ui08-final-qa02`; không seed/queue/cancel, không mở DB hay Run #2 hiện hành, không chạy app thứ hai. Login chỉ tài khoản fixture synthetic. HEAD độc lập vẫn `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`; dirty tree có sẵn được bảo toàn. Inventory, UTC timestamp/timezone và image digest nằm trong `followup/execution-manifest.json` / `independent-hashes.json`. Không có AGENTS.md được tìm thấy trong repo qua rg. Synthetic fixture không nhập file OpenAPI nên OpenAPI file hash N/A.

### Bằng chứng độc lập mới

- `followup/verify.py` tự tính lại host hashes, gọi `docker exec … sha256sum` và GET HTML/JS/CSS: **10/10 host/container/manifest khớp, 3/3 bytes đang phục vụ khớp**, image digest `sha256:dd986e03b86dc71392cd197a14fc6cb23f403552eee39595b749a93661b821b0` khớp. Hai backend fallback cuối đã nằm trong container. Command `.venv/bin/python results/identity-ui-08-qa/followup/verify.py`: exit 0.
- `.venv/bin/python -m pytest backend/tests/test_authorization_execution.py backend/tests/test_research_matrix_contract.py -k 'identity_labels or redaction' -q`: **6 PASS, 57 deselected**, pytest exit 0; log `fallback.log`. Có deprecation warnings như lượt trước.
- Tại frontend: `npm test -- src/AuthorizationWorkflow.test.tsx`: **11 PASS**, exit 0; `frontend.log`. Không chạy lại full suite/build vì không thay source; kết quả full suite trước vẫn là evidence lượt trước, không phải lần chạy mới.
- Browser tab chính thức: same-origin iframe document 1200/768/390 CSS px, không mobile-engine emulation. **15/15 headings đúng, không document overflow** (`browser-assertions.json`). Vòng đầu có timing/rerender làm Results rỗng tại hai width; không dùng chúng chứng minh accessible labels. Kiểm tra focused tiếp theo (`results-labels.json`) xác nhận **12 rows ở mỗi width**, đủ 5 term names, native dt với dd kế tiếp, display block/visibility visible, không ancestor aria-hidden. Desktop labels visually clipped theo CSS nhưng vẫn có semantic text; không coi đây là full screen-reader audit.
- Matrix mobile: **12 rows, 6/6 field labels display:block**, `runtime-readonly.json`.
- Legacy fixture Run #2, missing_role #3, partial_metadata #4: Browser giữ role `user`; legacy/missing identity labels báo thiếu snapshot rõ. Run API legacy summary cũng giữ actor/owner/baseline role từ snapshot. Đây là fixtures synthetic, không phải actual Run #2. `archive-browser.json` và `runtime-readonly.json`.
- Large CANCELLED archive fixture #5: **123 rows, pagination 50/50/23**, response đầu còn HTTP 200 / POLICY_CONSISTENT_CASE. Không gọi nó là preserved violation: fixture sao chép case đầu phù hợp policy. Không chạy cancellation mới; durable violation/cancel execution vẫn chỉ regression trước.
- Đọc lại Run #1 qua GET: COMPLETED, 12 cases; execution summary planned/transport/responses **19/19/19**, 0 errors. Tự đối chiếu **12/12 planned baseline = actual_baseline**, provenance OBSERVED_EVIDENCE, revision đồng nhất (`baselines.json`). Bản `runtime-readonly.json` ban đầu thử tên field observed không tồn tại nên bỏ qua giá trị undefined; file baselines dùng đúng `presentation.actual_baseline`, không suy diễn planned thành actual.
- Đã xem screenshots desktop/tablet/mobile Results trong Browser; `results-768.png`, `results-390.png`, `desktop-final.png`. Screenshot desktop vòng resize đầu bị capture chuyển tiếp, không dùng `results-1200.png` để nghiệm thu. Desktop chụp lại sau khi layout ổn định. Không thấy chồng lấp trong vùng được chụp.

### Evidence kế thừa và giới hạn

Đã đọc `qa-followup/queue.log`, `verify-after-fixtures.log`, `docker-manifest.json`, script queue/verify và archive fixture generator của implementer. Chúng ghi seed/queue→worker 12/12; lượt QA này chỉ GET đối chiếu persisted outcomes, không tự chạy fresh queue→worker. Script verify của implementer có POST seed nên **QA không chạy lại script đó**. Archive fixtures INSERT riêng và không chứng minh cancellation thực tế. Không coi lời báo cáo hay code là execution proof độc lập.

Historical baseline #3/#5: **INCONCLUSIVE**. Actual Run #2: **NOT VERIFIED**. Canonical pixel-diff, full screen-reader/keyboard audit, QA fresh queue/cancellation E2E: **NOT VERIFIED**. Không phát hiện lỗi mới trong phạm vi hai blocker; không nâng các giới hạn này thành PASS. Không có thay đổi production nên không có matrix/policy/evaluation semantics change từ QA. Không restart cổng 8000, không external/live lab/ZAP, không commit/push. Kiểm tra automation cuối lượt: không có automation nào của bot.

Evidence mới: `/home/cuong/Dự án/Bảo mật web/Project/results/identity-ui-08-qa/followup/`; hash inventory riêng `SHA256SUMS` được tạo và tự kiểm tra. Báo cáo và artifacts QA là các file duy nhất được ghi trong lượt này.
