# Báo cáo thực hiện Tuần 4 — BFLA disposable, ZAP Access Control và bảng so sánh

**Phạm vi:** VAmPI Docker local read-only tại `http://127.0.0.1:5000`; BFLA disposable tách biệt tại `http://127.0.0.1:5003`  
**Ngày cập nhật:** 23/10/2026  
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
python3 -I week4/run_week4.py --run-id <run-id> --skip-zap
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

Không có query/fragment. Mọi method khác `GET`, mọi port/host/scheme khác, `/createdb`, path không duyệt, request line malformed hoặc history page không đầy đủ đều dừng assessment trước scan hoặc invalidates kết quả sau scan.

**Site Tree không phải evidence containment.** ZAP có thể tự tạo node cha như origin, `/books`, `/books/v1`, `/users`, `/users/v1`. Runner ghi chúng thành diagnostic count; chúng không tự làm scan pass hay fail. Evidence quyết định là paginated ZAP target history: mọi HTTP message thật phải là GET chính xác đến một trong năm URL trên.

### 3.2. Chuẩn bị Context trong ZAP Desktop — làm một lần, review trước export

1. Chạy ZAP Desktop/daemon trong session mới; chỉ expose API loopback.
2. Trong ZAP Desktop tạo Context `vampi-safe-authz`; include regex phải khớp **đúng** năm absolute URL ở bảng trên, không dùng wildcard origin hoặc đường dẫn cha.
3. Cấu hình **ba user riêng biệt** `admin`, `userA`, `userB`, mỗi user có authentication/session state riêng. Không dùng global Replacer rule thay cho per-user authentication vì nó có thể gắn cùng header/token cho mọi user.
4. Thiết lập Authorization Detection Method trong Context và review rằng mỗi user được nhận diện authenticated.
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

### 3.4. Chạy ZAP daemon loopback-only (Fish)

Mount **chỉ** private Context read-only và disposable output directory. Quote `.*` để Fish không coi nó là wildcard.

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

### 3.5. Chạy runner và đọc artifact an toàn

```fish
python3 -I week4/run_week4.py \
  --run-id bf1a2026 \
  --zap-api-key '<local-zap-api-key>' \
  --zap-context zap/private/vampi-safe-authz.context \
  --zap-context-in-container /zap/context/vampi-safe-authz.context \
  --zap-attestation zap/imported-context-attestation.json \
  --zap-html-on-host zap/run-output/access-control.html \
  --zap-html-in-container /zap/output/access-control.html

# Chỉ đọc artifact JSON redacted:
python3 -I -m json.tool results/zap/zap_run_status.json
python3 -I -m json.tool results/zap/zap_access_control_report.json

docker stop zap-week4
rm -rf zap/run-output
```

Runner dùng documented Access Control lifecycle: `scan(contextId,userId)`, poll `getScanProgress(contextId)` + `getScanStatus(contextId)`, rồi yêu cầu ZAP tạo HTML report **tạm thời** trong mounted output. Runner chỉ trích xuất path/user/result whitelisted, xóa HTML trong `finally`, và không copy raw HTML vào `results/`.

Một run được đánh dấu `COMPLETED` chỉ khi: ZAP/add-on sẵn sàng; Context fingerprint/attestation khớp; đúng 3 user enabled/authenticated; Context regex đúng; fresh history trống; đúng 5 seed GET tạo history hợp lệ; scan hoàn tất; transient result có row hợp lệ; và post-scan history vẫn containment. Nếu bất kỳ gate nào fail, artifact mới sẽ là `NOT_RUN` với reason class redacted và scan không được coi là hoàn thành.

### 3.6. Trạng thái evidence hiện tại

Artifact hiện có vẫn là **`NOT_RUN`**, vì nó được tạo bởi runner cũ trước khi verified imported Context workflow tồn tại. Nó không đưa ra finding ZAP. Không được ghi đè thành `COMPLETED` cho tới khi run mới thỏa tất cả gate ở trên và tự tạo artifact redacted mới.

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

`results/week4_comparison_final.json` hiện tổng hợp: script `MEASURED`/2 BOLA; manual `COMPLETED_NO_TIMING`/2 BOLA; BFLA `EXECUTED`/`DENIED_CONTROL`; và ZAP theo trạng thái evidence thật (`NOT_RUN` cho đến run mới).

## 5. Kiểm thử kỹ thuật

```fish
.venv/bin/python -I -m unittest discover -s tests -v
```

Unit tests cover exact manifest scope, Context attestation mode/fingerprint, enabled unique users, paginated history, malformed/foreign/query/fragment/state-changing history rejection, non-blocking Site Tree parent diagnostics, documented API lifecycle, fresh caller paths, redaction, and no-timing manual completion.

## 6. Kết luận Tuần 4

1. BFLA disposable thực thi đúng isolation: `DENIED_CONTROL`, không có BFLA confirmed.
2. Hai BOLA user-to-user được script và Postman độc lập xác nhận; manual timing không được đo nhưng functional evidence hoàn chỉnh.
3. ZAP được thay bằng quy trình verified imported Context, history-based containment, and redacted evidence. Hiện chưa có real scan artifact mới, vì vậy status trung thực vẫn là `NOT_RUN`.
4. Shared lab `vampi-week1` không bị destructive testing trong Tuần 4.
