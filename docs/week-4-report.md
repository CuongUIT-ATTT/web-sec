# Báo cáo thực hiện Tuần 4 — BFLA disposable, ZAP Access Control và bảng so sánh

**Phạm vi:** VAmPI Docker local read-only tại `http://127.0.0.1:5000`; BFLA disposable tách biệt tại `http://127.0.0.1:5003`  
**Ngày cập nhật:** 26/10/2026
**Mục tiêu:** ghi nhận BFLA trên môi trường disposable, hoàn thiện quy trình ZAP Access Control có containment fail-closed, và tổng hợp bằng chứng thủ công/automation.

> Chỉ kiểm thử lab local được ủy quyền. Báo cáo chỉ khẳng định kết quả đã có artifact. `NOT_RUN` của ZAP không phải bằng chứng không có lỗ hổng.

## 1. Nguyên tắc an toàn

- Shared lab `vampi-week1` chỉ nhận request read-only trong Tuần 2–4; không reset và không dùng cho BFLA destructive test.
- Ordinary runner chấp nhận duy nhất `http://127.0.0.1:5000`, chỉ `GET`/`HEAD`/`OPTIONS`; `GET /createdb` bị cấm vĩnh viễn.
- ZAP chỉ được dùng với **năm GET fixture** trong `zap/allowlist-v2.json`; không spider, AJAX Spider, active scan, fuzz, wordlist, discovery hay enumeration.
- Bearer token/JWT, password, `Authorization` header, raw response body, raw ZAP HTML và raw API error body không được ghi vào artifact, ảnh chụp, log hoặc báo cáo.
- `roles_config.json`, Context `.context` và auxiliary authentication material là private file mode `0600`; không commit.

## 2. BFLA disposable — tái hiện và kết quả

### 2.1. Quy trình bắt buộc

BFLA chạy hoàn toàn tách biệt với shared lab. Chọn `<run-id>` lowercase 8–32 ký tự, ví dụ `bf1a2026`.

```fish
# Trong thư mục Project, sau khi cài .venv
.venv/bin/vampi-bfla-disposable create-manifest --run-id <run-id>
.venv/bin/vampi-bfla-disposable preflight --run-id <run-id>

docker compose \
  --project-name vampi-bfla-<run-id> \
  --file bfla-disposable/compose.yaml \
  up --detach --wait --wait-timeout 60

.venv/bin/vampi-bfla-disposable prepare --run-id <run-id>
.venv/bin/vampi-bfla-disposable execute --run-id <run-id>
.venv/bin/vampi-bfla-disposable teardown --run-id <run-id>

# Chuyển receipt đã có thành artifact Tuần 4; không chạy ZAP ở bước này
.venv/bin/python -I week4/run_week4.py --run-id <run-id> --skip-zap
```

Luôn chạy `teardown`, kể cả khi authorization cho kết quả bất thường. Cleanup dùng container/volume destruction của Compose project riêng, không dùng shared `/createdb`.

### 2.2. Guardrail và kết quả đã có

`week4/bfla_executor.py` gọi `assert_disposable_target()` trên mọi destructive username. Nó từ chối `admin`, `userA`, `userB`, `name1`, `name2` và chỉ chấp nhận username disposable theo pattern cho phép.

Run `bf1a2026` có receipt redacted:

| Control | DELETE status | Post-condition | Kết luận |
| --- | ---: | --- | --- |
| Non-admin → disposable victim | 401 | victim còn tồn tại | DENIED |
| Admin → disposable control | 200 | control không còn | POSITIVE_CONTROL |

**Verdict: `DENIED_CONTROL`.** Non-admin bị từ chối; không có BFLA confirmed.

## 3. ZAP Access Control — Context đã review, containment và tái hiện

### 3.1. Scope cố định

`zap/allowlist-v2.json` chỉ cho phép năm URL sau tại origin chính xác `http://127.0.0.1:5000`:

| Path | Mục đích |
| --- | --- |
| `/books/v1/week1-userA-book` | BOLA owner/cross-user fixture |
| `/books/v1/week1-userB-book` | BOLA owner/cross-user fixture |
| `/users/v1/userA` | Public profile control |
| `/users/v1/userB` | Public profile control |
| `/me` | Authenticated self-identity control |

Không có query/fragment. Mọi method khác `GET`, mọi port/host/scheme khác, `/createdb`, path không duyệt, request line malformed, identity History không hợp lệ/không liên tục hoặc history page không đầy đủ đều dừng assessment trước scan hoặc invalidates kết quả sau scan.

**Site Tree không phải evidence containment.** ZAP có thể tự tạo node cha như origin, `/books`, `/books/v1`, `/users`, `/users/v1`. Runner ghi chúng thành diagnostic count; chúng không tự làm scan pass hay fail. Evidence quyết định là paginated ZAP Core target history.

ZAP 2.17 có thể giữ authentication/verification-poll record trong Core history nhưng không hiện record đó sau khi History/Sites Desktop rebuild. Vì vậy, sau khi runner xác thực cả ba user, nó thực thi gate quiescence: đọc target-scoped `core.number_of_messages()` hai lần cách nhau một giây. Nếu count thay đổi, runner thử lại; quá mười giây thì dừng `NOT_RUN` trước baseline, seed và scan. Count này không được export. Chỉ sau khi quiesce, runner chụp hai lần một **baseline identity** ổn định trong bộ nhớ. Baseline này không được export và không phải scanner evidence. Sau đó seed delta phải có đúng một `GET` cho mỗi năm path; mọi message mới do scan tạo ra cũng phải là `GET` chính xác đến một trong năm URL. Bất kỳ non-GET, query/fragment, target ngoài scope, duplicate/missing identity hoặc mất predecessor identity đều fail-closed. Bảng History trống không thay thế Core API proof.

### 3.2. Chuẩn bị Context trong ZAP Desktop — làm một lần, review trước export

1. Chạy ZAP Desktop/daemon trong session mới; chỉ expose API loopback.
2. Trong ZAP Desktop tạo Context `vampi-safe-authz`; include regex phải khớp **đúng** năm absolute URL ở bảng trên, không dùng wildcard origin hoặc đường dẫn cha.
3. Cấu hình **ba user riêng biệt** `admin`, `userA`, `userB`, mỗi user có authentication/session state riêng. Không dùng global Replacer rule thay cho per-user authentication vì nó có thể gắn cùng header/token cho mọi user.
4. Thiết lập Authentication Verification Strategy trong Context và review rằng mỗi user được ZAP poll thành công. Runner chỉ chấp nhận `lastPollResult=true` từ một trong hai response contract đã review (legacy wrapper hoặc current Desktop top-level state); timestamp, history ID hay previous-success metadata không tự chứng minh current authentication.
5. Trong Access Control, tạo/review Rule theo `authorization_expectations` của `zap/allowlist-v2.json`: owner allowed, cross-user book denied, profile/self control allowed, admin book access policy-dependent.
6. Export Context sang private local file, ví dụ `zap/private/vampi-safe-authz.context`; không commit file này hoặc script credential/authentication liên quan.

### 3.3. Fingerprint attestation không chứa secret

Copy template `zap/imported-context-attestation.example.json` thành `zap/imported-context-attestation.json`; file này được `.gitignore`. Thiết lập quyền private và điền hash của chính Context đã review:

```fish
mkdir -p zap/private zap/run-output
chmod 700 zap/private zap/run-output
chmod 600 zap/private/vampi-safe-authz.context
set -l context_hash (sha256sum zap/private/vampi-safe-authz.context | string split ' ')[1]
# Chỉ thay placeholder context_sha256, reviewed_on và reviewer trong attestation.
# Không dán token/password/header/body vào attestation.
chmod 600 zap/imported-context-attestation.json
```

Attestation phải chứa đúng Context name, target, 3 user display name, 5 path và access-rule expectation matrix. Runner so fingerprint file/context attestation trước khi gọi import API.

### 3.4. Chạy bằng ZAP Desktop đã load Context (Fish)

Dùng mode này chỉ khi Context `vampi-safe-authz` đã được operator load và review trong **chính Desktop session đang chạy**. Runner vẫn kiểm tra local exported Context mode `0600` và SHA-256 attestation, nhưng **không gửi/import/copy Context qua ZAP API**. Nó chỉ lookup đúng Context name, kiểm tra regex/user/authentication state rồi áp dụng các gate containment hiện có.

```fish
# Copy the key from the local ZAP GUI; keep it only in this shell session.
set -lx ZAP_KEY '<key-from-zap-gui>'

set -l PROJECT (pwd)
.venv/bin/python -I week4/run_week4.py \
  --run-id bf1a2026 \
  --zap-context-mode preloaded-desktop \
  --zap-api-key "$ZAP_KEY" \
  --zap-context "$PROJECT/zap/private/vampi-safe-authz.context" \
  --zap-attestation "$PROJECT/zap/imported-context-attestation.json" \
  --zap-html-on-host "$PROJECT/zap/run-output/access-control.html" \
  --zap-html-in-container "$PROJECT/zap/run-output/access-control.html"
```

Không truyền `--zap-context-in-container` trong mode Desktop. Nếu Context chưa được load, sai tên, sai regex, thiếu/thừa user, user chưa authenticated, Core-history baseline không ổn định, seed/scan delta ngoài scope, hoặc transient-report path không absolute/đã tồn tại/đụng artifact JSON, runner tạo artifact `NOT_RUN` đã redaction và không seed/scan. Local file hash xác nhận reviewed export nhưng không chứng minh in-memory Desktop Context chưa bị operator thay đổi sau khi load; vì vậy phải review Context session trước mỗi lần chạy.

### 3.5. Bootstrap authentication rồi quiesce traffic (Desktop)

Sau restart, Context configuration vẫn có thể còn nhưng User runtime session/poll state có thể mất. Không nới allowlist năm `GET` để chứa login; thay vào đó chạy bootstrap chỉ-đọc sau. Nó kiểm tra Context, regex và ba user enabled, nhưng **không** login/poll, không seed, không scan, không tạo HTML, không import Context, và không xóa History:

```fish
# Copy the key from the local ZAP GUI; keep it only in this shell session.
set -lx ZAP_KEY '<key-from-zap-gui>'

set -l PROJECT (pwd)
.venv/bin/python -I week4/run_week4.py \
  --run-id bf1a2026 \
  --zap-bootstrap-only \
  --zap-context-mode preloaded-desktop \
  --zap-api-key "$ZAP_KEY" \
  --zap-context "$PROJECT/zap/private/vampi-safe-authz.context" \
  --zap-attestation "$PROJECT/zap/imported-context-attestation.json"
```

Khi artifact `results/zap/zap_bootstrap_readiness.json` báo `BOOTSTRAP_REQUIRES_OPERATOR_AUTH_AND_QUIESCE`, operator làm trong chính ZAP Desktop session:

1. Authenticate/poll từng `admin`, `userA`, `userB` bằng Context đã review; không dùng Global Replacer và không copy token/header ra clipboard.
2. Stop browser proxy traffic, Spider, AJAX Spider và scan activity để không có request mới xen vào assessment.
3. Không chọn File → New Session, không restart ZAP và không dùng API `deleteSiteNode`. Không cần coi History/Sites trống là điều kiện pass: ZAP có thể ẩn authentication history dù Core API còn record.
4. Chạy command Desktop thông thường tại §3.4. Runner chụp baseline Core history riêng tư sau authentication, yêu cầu seed delta đúng năm `GET`, rồi kiểm tra scan delta. Không poll/login/curl sau bootstrap trừ khi phải khôi phục authentication state; nếu phải làm vậy, quiesce traffic lại trước khi chạy runner.

Runner assessment yêu cầu ba user có `lastPollResult=true`, một baseline identity ổn định và containment đầy đủ của mọi post-baseline assessment request. Nếu state hoặc identity/history gate fail thì dừng `NOT_RUN`; không giả state qua API hoặc làm yếu containment. Bootstrap/login traffic không phải scanner evidence và không xuất hiện trong final artifact.

### 3.6. Chạy ZAP daemon loopback-only (Fish)

Đây là mode Docker import. Mount **chỉ** private Context read-only và disposable output directory. Quote `.*` để Fish không coi nó là wildcard.

```fish
docker run --rm -d --name zap-week4 \
  -p 127.0.0.1:8080:8080 \
  -v "$PWD/zap/private:/zap/context:ro" \
  -v "$PWD/zap/run-output:/zap/output" \
  zaproxy/zap-stable \
  zap.sh -daemon -host 0.0.0.0 -port 8080 \
    '-config' 'api.addrs.addr.name=.*' \
    '-config' 'api.addrs.addr.regex=true' \
    '-config' 'api.key=<local-zap-api-key>'

for i in (seq 1 30)
    if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/ | grep -qE '200|401|403|404'
        echo 'ZAP ready'
        break
    end
    sleep 2
end
```

Readiness alone is not evidence that the assessment is configured correctly; all runner gates remain mandatory.

### 3.7. Chạy runner Docker import và đọc artifact an toàn

```fish
# Copy the key from the local ZAP GUI; keep it only in this shell session.
set -lx ZAP_KEY '<key-from-zap-gui>'

.venv/bin/python -I week4/run_week4.py \
  --run-id bf1a2026 \
  --zap-context-mode import \
  --zap-api-key "$ZAP_KEY" \
  --zap-context zap/private/vampi-safe-authz.context \
  --zap-context-in-container /zap/context/vampi-safe-authz.context \
  --zap-attestation zap/imported-context-attestation.json \
  --zap-html-on-host zap/run-output/access-control.html \
  --zap-html-in-container /zap/output/access-control.html

# Chỉ đọc artifact JSON redacted:
.venv/bin/python -I -m json.tool results/zap/zap_run_status.json
.venv/bin/python -I -m json.tool results/zap/zap_access_control_report.json

docker stop zap-week4
rm -rf zap/run-output
```

Runner seed từng URL allowlist bằng `core.accessUrl` một lần. ZAP trả wrapper request/response transient `accessUrl`; runner chỉ xác nhận wrapper tồn tại và non-null, không parse/log/export nested content có thể chứa dữ liệu nhạy cảm. Evidence containment vẫn là private paginated History delta: sau seed phải có đúng một `GET` cho mỗi path approved. Sau đó runner dùng documented Access Control lifecycle: `scan(contextId,userId)`, poll `getScanProgress(contextId)` + `getScanStatus(contextId)`, rồi yêu cầu ZAP tạo HTML report **tạm thời** trong mounted output. Với Access Control 13.0.0, `writeHTMLreport` xác nhận bằng envelope chính xác `{"writeHTMLreport": "OK"}` (khác generic `{"Result": "OK"}` của `scan`); runner kiểm tra envelope trước khi xác nhận file tồn tại và chỉ trích xuất path/user/result whitelisted. HTML bị xóa trong `finally` và không bao giờ được copy vào `results/`.

Một run được đánh dấu `COMPLETED` chỉ khi: ZAP/add-on sẵn sàng; Context fingerprint/attestation khớp; đúng 3 user enabled/authenticated; Context regex đúng; post-auth Core-history baseline đọc ổn định với identity duy nhất; đúng 5 seed GET xuất hiện đúng một lần trong seed delta; scan hoàn tất; transient result có row hợp lệ; và mọi scan delta vẫn containment. Nếu bất kỳ gate nào fail, artifact mới sẽ là `NOT_RUN` với reason class redacted và scan không được coi là hoàn thành. Artifact chỉ chứa count/path-count/violation-code; không chứa history ID, raw request, header, token hay body.

### 3.8. Trạng thái evidence hiện tại

Live run 26/10/2026 hiện là **`COMPLETED`**: `scan_start`, `scan_completion`, exact `writeHTMLreport` acknowledgement, whitelist parser và post-scan History delta đều pass. Artifact ghi 15 result rows (5 path × 3 reviewed user), 15 scan-delta GET đều thuộc allowlist và `violation_counts` rỗng; HTML tạm đã bị cleanup.

ZAP xuất 5 row `ILLEGAL`, nhưng actor mapping làm rõ rằng đây không phải hai BOLA cross-user đã biết: `/books/v1/week1-userA-book` bị gắn cờ cho owner `userA`, còn `/books/v1/week1-userB-book` bị gắn cờ cho owner `userB`. Ba row còn lại là `/me` cho cả ba reviewed user. Vì report redacted chỉ lưu `ILLEGAL` row, không có finding admin-book không chứng minh các tổ hợp còn lại là `VALID`. Các row owner-book và `/me` là rule-alignment discrepancies cần review Context/Access Rules, không phải BOLA mới và không phải xác nhận độc lập hai BOLA user-to-user đã được script/Postman chứng minh bằng sensitive-field baseline. Artifact hiện có không đủ để kết luận nguyên nhân gốc rễ; Access Rule Allow/Deny bị lệch hoặc giới hạn đánh giá self-identity chỉ là giả thuyết cần kiểm chứng thủ công. Bounded diagnostic trước đó cũng xác nhận `writeHTMLreport` tạo report tạm rồi cleanup thành công và trả envelope `writeHTMLreport`; parser dùng exact `GET`, exact approved href, reviewed header user và stable result-cell class, không export raw HTML.

## 4. Manual Postman và bảng so sánh

Bảy case Postman trong `results/week3_manual_worksheet.md` đã hoàn thành:

| Case | Status | Kết luận |
| --- | ---: | --- |
| M-01 | 200 | Owner control pass |
| M-02 | 200 | **BOLA confirmed**: userB đọc book userA và sensitive field owner bị lộ |
| M-03 | 200 | **BOLA confirmed**: userA đọc book userB và sensitive field owner bị lộ |
| M-04 | 401 | Anonymous bị từ chối |
| M-05 | 401 | Invalid token bị từ chối |
| M-06 | 200 | Public profile observation |
| M-07 | 200 | Identity control pass |

Không đo stopwatch. Builder báo `COMPLETED_NO_TIMING`, `elapsed_minutes: null`, 7 completed cases và 2 confirmed finding. Điều này là bằng chứng chức năng độc lập; chỉ thiếu metric hiệu quả thao tác thủ công.

`results/week4_comparison_final.json` hiện tổng hợp: script `MEASURED`/2 BOLA; manual `COMPLETED_NO_TIMING`/2 BOLA; BFLA `EXECUTED`/`DENIED_CONTROL`; và ZAP `COMPLETED`/15 reviewed result rows/5 scanner-labeled rule anomalies. Hai book-path anomaly là owner access, không phải các actor cross-user xác nhận BOLA; do đó ZAP không thay thế hoặc xác nhận độc lập baseline-sensitive-field proof của script/Postman.

## 5. Kiểm thử kỹ thuật

```fish
.venv/bin/python -I -m unittest discover -s tests -v
```

Evidence theo mốc thời gian:

- Tuần 2: **13 tests passed**.
- Tuần 3, trước BFLA/ZAP Tuần 4: **19 tests passed**.
- Regression trung gian sau BFLA disposable: **42 tests passed**.
- Tuần 4, trước quiescence gate hiện tại: **87 tests passed** (`48` regression trước đó và `39` test Tuần 4).
- Sau quiescence gate: **125 tests passed**.
- Hiện tại, sau regression contract `core.accessUrl`, `writeHTMLreport` và parser report table: **128 tests passed**.

Unit tests cover exact manifest scope, Context attestation mode/fingerprint, enabled unique users, paginated history, malformed/foreign/query/fragment/state-changing history rejection, non-blocking Site Tree parent diagnostics, documented API lifecycle, fresh caller paths, redaction, and no-timing manual completion.

## 6. Kết luận Tuần 4

1. BFLA disposable thực thi đúng isolation: `DENIED_CONTROL`, không có BFLA confirmed.
2. Hai BOLA user-to-user được script và Postman độc lập xác nhận; manual timing không được đo nhưng functional evidence hoàn chỉnh.
3. ZAP dùng quy trình verified imported Context, history-based containment và redacted evidence. Live assessment đã tạo artifact `COMPLETED`: 15 reviewed rows/5 scanner-labeled `ILLEGAL` anomalies. Hai book anomaly gắn với owner thay vì cross-user actor; ba `/me` anomaly cần review policy/Context alignment. Không row nào trong số này được diễn giải thành sensitive-field finding hay xác nhận độc lập BOLA.
4. Shared lab `vampi-week1` không bị destructive testing trong Tuần 4.
