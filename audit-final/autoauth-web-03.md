# AUTOAUTH-WEB-03 — bàn giao frontend

2026-11-16 · T18 OpenAPI Matrix → T18 Lead / QA Evidence.
HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`; working tree đã dirty trước ticket, giữ nguyên. Không commit/push. **PASS local frontend regression và mounted-browser synthetic execution; tổng thể PARTIAL.**

## Triển khai

Luồng mặc định có năm màn Setup → Matrix → Run → Results → Comparison. Tái sử dụng form lab/identity/resource hiện có; không sửa backend. OpenAPI dùng inventory authorization mới, có nonGET để preview nhưng không dispatch. Setup có form phê duyệt operation/kind/resource mapping, rule dùng lại theo quan hệ/role/identity/operation và chia sẻ resource; JSON nâng cao cho selectors/evidence phức tạp. Không tạo policy theo từng test case. Rule precedence hiển thị DENY > UNKNOWN > ALLOW; không đoán quyền từ tên path.

Matrix dùng `/authorization/preview`, hiển thị toàn bộ cases, coverage theo identity, mọi exclusions/warnings và reason NOT_RUN; lọc identity/role/operation/resource/expected decision. Không tự chọn case. NonGET và nonexecutable bị disable. Budget selection deduplicate baseline và identity như backend; không lấy riêng actor count làm request budget. Thay target/setup hoặc edit rule làm mất preview/selection; trước queue đọc lại preview, nếu thay đổi thì chặn và yêu cầu chọn lại. Backend vẫn là authority về validation/revision/cap.

Run hiển thị stable IDs được chọn, revision, budget, nút queue gọi `/authorization/runs` với explicit case_ids. Khóa chống double click, poll counters/status, nút cancel qua API hiện có. Snapshot lưu bởi backend; frontend không chỉnh snapshot. Results chỉ dùng `/authorization/runs/{R}/results`, lọc sáu kết luận, giải thích policy/observation/baseline, metadata evidence đã rút gọn và case→run→result→finding/artifact. Không dùng Finding aggregation legacy cho case mới.

Comparison nối cùng stable IDs với T18 durable results; Manual/ZAP chưa có evidence vẫn NOT_RUN / UNAVAILABLE, không tính metrics giả. Bundle/cohort lịch sử vẫn có trong disclosure. Không gọi CLI, bridge, ZAP hoặc write target từ workflow mặc định. Các panel legacy được giữ trong nhánh React `legacy` chỉ để regression compatibility; entry point không truyền prop này và không có control mở nó trong UI thông thường.

## Ownership

Chỉnh tiếp các file frontend đã có diff trước ticket: `frontend/src/App.tsx`, `api.ts`, `styles.css`; cập nhật `App.test.tsx` và `WebDemo.test.tsx` để regression legacy được mount rõ ràng. File mới: `AuthorizationWorkflow.tsx`, `AuthorizationConfigEditor.tsx` và hai test tương ứng. Không nhận diff có sẵn của các ticket trước là thay đổi ticket này. Backend/lab/SQLite persistent không mở hoặc sửa.

## Kiểm thử và evidence

Recorder `results/autoauth-web-03/verify.py` ghi HEAD, UTC, exact commands/exits và source hashes trước/sau. Lượt chốt **55 tests / 6 files PASS** (49 regressions hiện hữu + 6 tests mới), lint/build/diff-check exit 0; source hash trước/sau không đổi. Tests mới kiểm budget dedup, explicit selection/nonGET/exclusion, stale preview không queue, durable traceability + manual/ZAP NOT_RUN, cancellation double-click/progress và form reusable mapping/rule/sharing.

```sh
.venv/bin/python results/autoauth-web-03/verify.py
# Recorder chạy:
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
git diff --check
```

Các lượt đầu có lỗi regression vì tests cũ mặc định đòi panel đã được chuyển khỏi workflow; đã tách mount legacy rõ ràng và giữ nguyên assertions về hành vi cũ. Lượt fixture browser đầu lỗi cách khởi tạo SecretBox, sửa dùng from_key/encrypt_bearer trước khi khởi động app; không có request target từ lần khởi tạo lỗi.

## Mounted Browser thực chạy

`results/autoauth-web-03/browser_fixture.py` tạo thư mục temp `autoauth-web-03-*`, SQLite riêng, app port 18983 và HTTP fixture numeric loopback port động. Không đọc `.env`, credential thật, persistent DB hoặc lab hiện hữu. Khởi chạy bằng `.venv/bin/python results/autoauth-web-03/browser_fixture.py`; restart tạo DB mới, không tái sử dụng lịch sử tạm. Fixture synthetic 3 identities (user,user,admin), 6 resources, 4 operations được seed từ test fixture backend hiện hữu. Backend source chỉ import để chuẩn bị app fixture; không sửa.

Mounted browser mở đúng app, đăng nhập bằng credential synthetic của fixture, thấy đủ năm bước, reusable config và 27 cases / 18 executable / 0 exclusions. Chọn rõ ba case: BOLA resource 3 actor 1 DENY; BFLA GET actor 1 DENY; BFLA GET actor 3 ALLOW. UI tính budget **8**. Queue và xem Results/Comparison thực tế: **8 planned / 8 transport / 8 completed responses**, 0 errors/scope blocks/cancelled; hai CONFIRMED_VIOLATION và một POLICY_CONSISTENT_CASE. Đây là kết quả synthetic của fixture cố ý trả dữ liệu bảo vệ, không phải scanner finding nghiên cứu trên Controlled Lab hay ZAP.

**Run #2 trong evidence này thuộc SQLite TẠM**, không phải persistent Run #2. Fixture có một legacy sentinel Run #1. Không mở persistent DB để lấy checksum nên preservation proof persistent vẫn NOT VERIFIED; chỉ có isolation-by-construction.

Artifacts: `browser-environment.json`, `browser-observations.json` (mounted accessibility snapshots/actions), `browser-results.json` (read-only fetch qua browser, redacted DTO/counters), `browser-final-asset.json`, execution.json và logs. Screenshot Comparison đã được xem trực tiếp ở viewport 1265 CSS px: navigation, table và disclosure hiển thị; responsive nhiều viewport chưa kiểm. Lượt browser execution trước các bổ sung copy/coverage nhỏ cuối; asset cuối được reload/recheck riêng, không queue thêm để thổi số liệu.

## Giới hạn và bàn giao QA độc lập

| Phạm vi | Trạng thái |
|---|---|
| Five-step default UI / API wiring / frontend regression | PASS local |
| Mounted browser synthetic BOLA + GET BFLA queue/results/comparison | PASS local |
| Browser cancellation khi HTTP đang chờ / stale revision thực hai operator | NOT VERIFIED; UI regressions mock PASS |
| Responsive 390/768/1024/1440, keyboard/screenreader đầy đủ | NOT VERIFIED |
| Skill checker/gate/performance | NOT_RUN; dùng mounted browser theo ràng buộc môi trường, không chạy browser riêng của skill |
| Manual/T18/ZAP research comparison + metrics có truth | NOT_RUN; chỉ có capability/bundle UI và provenance thật |
| Disposable nonGET/BFLA write | NOT_RUN; không mở quyền |
| Persistent DB/Run #2 checksum proof | NOT VERIFIED; không truy cập DB này |
| Backend regression mới | Không rerun trong ticket frontend; dùng contract được bàn giao, chờ QA độc lập |

Áp dụng `design-taste-frontend` cho bố cục, control có label, trạng thái và responsive CSS; giữ hệ màu/typography sẵn có của control room. Không dựng landing-page hero/photography hay tự chạy Chromium của skill. Không tuyên bố GATE PASS.

QA cần chạy lại recorder và fixture trên port riêng nếu port bận, kiểm browser selected queue/cap/stale/cancel, cross-project/run late-response, redaction, coverage không bỏ identity và history/bundle. Cần kiểm responsive và acceptance R1–R8 tổng hợp riêng. Không có automation của bot (đã kiểm list rỗng). Không commit/push/deploy hoặc thay đổi persistent app.
