# Hướng dẫn Thành viên 1 — An toàn, đồng bộ VAmPI và tái lập pipeline

> **Vai trò:** tiếp quản an toàn credential, trạng thái user/fixture của VAmPI local, khả năng tái lập của CLI và vệ sinh secret trong repository.
> **Phạm vi được phép:** chỉ lab VAmPI Docker được ủy quyền tại `http://127.0.0.1:5000`. Không dùng hướng dẫn này với production, Internet, LAN hoặc mục tiêu khác.

## 1. Kết quả cần bàn giao

Hoàn thành các đầu việc sau và gửi **bản bàn giao đã redaction** cho người điều phối:

1. ZAP API key mới đã được sinh trong GUI và chỉ tồn tại trong shell session dùng để thao tác local.
2. Ba role `admin`, `userA`, `userB` đã được tạo lại hoặc đổi mật khẩu theo quy trình local; `roles_config.json`, `ownership.csv` và ba ZAP Context users khớp nhau.
3. Toàn bộ unit test đã chạy; ghi **số test pass thực tế** và mọi failure/blocker, không tự ghi sẵn con số kỳ vọng.
4. Bốn CLI `check-inputs`, `run`, `verify`, `week3` đã được đối chiếu với entry point compatibility tương ứng, theo verdict/artifact và giới hạn an toàn.
5. Đã audit đường dẫn secret và `.gitignore`; báo cáo chỉ chứa path, loại dữ liệu và trạng thái khắc phục, không chứa giá trị secret.

**Không bàn giao:** password, bearer/JWT, header `Authorization`, ZAP API key, raw response body, raw ZAP HTML, file `.context`, `roles_config.json`, hay ảnh chụp hiển thị credential.

---

## 2. Giai đoạn nền tảng bắt buộc — 3–4 ngày

Hoàn thành toàn bộ phần này **trước** phần việc chuyên trách. Mục tiêu là hiểu giới hạn bằng chứng, không chỉ biết chạy lệnh.

### Ngày 1 — Khái niệm và evidence model

- [ ] Đọc OWASP API Security Top 10: **API1: Broken Object Level Authorization (BOLA)** và **API5: Broken Function Level Authorization (BFLA)**.
- [ ] Đọc Phần 1 của [final-report-draft.md](final-report-draft.md): đặc biệt nguyên tắc rằng HTTP `200` **không tự đủ** để kết luận BOLA.
- [ ] Đọc [README.md](../README.md), [week-1-report.md](week-1-report.md) và [week-2-report.md](week-2-report.md).
- [ ] Giải thích được bằng lời: hai BOLA user-to-user chỉ được xác nhận khi response cross-user thành công **và** `$.secret` khớp fresh owner baseline; admin cross-user là `POLICY_DEPENDENT`.

### Ngày 2 — Tái lập lab và quan sát có kiểm soát

Làm theo [week-1-report.md](week-1-report.md). Chỉ thao tác trên Docker local loopback.

- [ ] Xác nhận container/port là local `127.0.0.1:5000`, không phải `0.0.0.0` hoặc host ngoài phạm vi.
- [ ] Tạo hai user thường mới theo quy trình VAmPI local; mỗi user tạo một book fixture thuộc chính họ.
- [ ] Dùng token của user 1 gọi đúng book fixture đã biết của user 2 để quan sát việc response trả field `secret` trong lab đào tạo.
- [ ] Chụp **một ảnh bằng chứng đã che** token, password, header `Authorization` và **giá trị** secret. Ảnh chỉ cần cho thấy phương thức/path, actor khác owner, status và sự hiện diện của field `secret`. Gửi ảnh đã che vào nhóm theo quy ước của nhóm.
- [ ] Không gửi raw response, secret value, token, hoặc ảnh browser/Postman có credential chưa che.

> Không gọi `GET /createdb` trong shared lab ở bước này. Endpoint đó reset database và làm hỏng fixture của cả nhóm.

### Ngày 3 — Hiểu pipeline và báo cáo

- [ ] Đọc theo thứ tự: [week-1-report.md](week-1-report.md) → [week-2-report.md](week-2-report.md) → [week-3-report.md](week-3-report.md) → [week-4-report.md](week-4-report.md) → [final-report-draft.md](final-report-draft.md).
- [ ] Đọc bốn module [week2/spec_parser.py](../week2/spec_parser.py), [week2/matrix_builder.py](../week2/matrix_builder.py), [week2/request_runner.py](../week2/request_runner.py), [week2/response_comparator.py](../week2/response_comparator.py).
- [ ] Chạy compatibility entry point sau khi có môi trường hợp lệ:

```bash
.venv/bin/python -I week2/main.py
```

- [ ] Giải thích được: OpenAPI chỉ tạo inventory; `ownership.csv` là input fixture chuẩn; pipeline chỉ sinh identifier có provenance và không enumeration.

### Ngày 4 — Họp kiểm tra (hoặc làm khi cần thêm thời gian)

Chuẩn bị trao đổi miệng 15–20 phút, không đọc slide:

- BOLA khác BFLA như thế nào.
- Vì sao owner baseline và sensitive-field equality cần thiết.
- Vì sao `GET /users/v1/{username}` hiện là `OBSERVATION`, không tự là BOLA.
- Vì sao ZAP cung cấp evidence endpoint/rule alignment chứ không xác nhận chính xác hai case BOLA cross-user.

**Gate chuyển việc:** chỉ bắt đầu phần 3 khi người điều phối xác nhận phần trình bày và checklist trên đủ.

---

## 3. Guardrail chung và điều kiện dừng

### Chỉ được làm

- Chỉ dùng `http://127.0.0.1:5000` và fixture trong [ownership.csv](../ownership.csv).
- Với shared lab, chỉ dùng request read-only đã đóng gói; workflow bình thường chấp nhận `GET`, `HEAD`, `OPTIONS` và các case chuyên trách bên dưới chỉ dùng `GET`.
- Xử lý credential tại local private files/session environment.

### Tuyệt đối không làm

- Không dùng `localhost`, HTTPS, port/IP khác, URL có query/fragment/userinfo, Internet, LAN hoặc production.
- Không enumerate/tăng giảm identifier, wordlist, fuzzing, discovery, listing endpoint để lấy ID mới.
- Không gọi `/createdb`; không dùng `POST`, `PUT`, `PATCH`, `DELETE` trên shared fixture trong phần tái lập này.
- Không paste token/password/key/header/response body vào chat, issue, screenshot, commit hoặc report.
- Không tự sửa/reset Context ZAP để “làm scan pass”; mọi rule change phải review theo guide Thành viên 3.

**Dừng và báo blocker** nếu base URL sai, lab bị reset, token/user không khớp, owner không đọc được fixture, fixture biến mất, hoặc bạn không chắc thao tác có state-changing hay không.

---

## 4. Điều kiện đầu vào và nguồn chuẩn

| Nguồn | Vai trò | Quy tắc xử lý |
| --- | --- | --- |
| [vampi_spec.json](../vampi_spec.json) | OpenAPI inventory | Không tự suy luận policy từ spec. |
| [ownership.csv](../ownership.csv) | Map ownership chuẩn, có provenance | Giữ đúng header; chỉ dùng fixture trong file. |
| `roles_config.json` | Username + bearer token local | Private, ignored, regular file mode `0600`; không commit/copy. |
| [zap/allowlist-v2.json](../zap/allowlist-v2.json) | Scope ZAP hiện hành | Có 5 GET paths; chỉ dùng guide Thành viên 3 để review scan. |
| [vampi_authz_lab/cli.py](../vampi_authz_lab/cli.py) | CLI đóng gói | Là nguồn chuẩn cho 4 subcommand. |

Mối quan hệ cần khớp sau rotation:

| Role | Username kỳ vọng | Fixture/ý nghĩa |
| --- | --- | --- |
| `admin` | `admin` | Access book là `POLICY_DEPENDENT`, không tự là BOLA. |
| `userA` | `userA` | Owner `week1-userA-book`. |
| `userB` | `userB` | Owner `week1-userB-book`. |

`ownership.csv` là input chuẩn. `results/ownership_map.json` chỉ là export redacted, không được dùng thay CSV đầu vào.

---

## 5. Rotate ZAP API key an toàn

1. Mở ZAP Desktop local, vào **Tools → Options → API → Generate**.
2. Sinh key mới. Không copy key vào file project, Postman environment, screenshot, chat hoặc ticket.
3. Khi thật sự cần dùng runner desktop, chỉ export trong shell hiện tại:

```fish
set -lx ZAP_KEY '<key-copied-locally-from-ZAP-GUI>'
```

4. Dùng xong, đóng shell hoặc xóa session variable theo shell của bạn. Không ghi giá trị key vào command history, script hoặc `.env`.
5. Trong handoff chỉ ghi: `ZAP API key rotated: yes`, thời điểm, và ai đã thực hiện — **không** ghi key.

> Sinh key mới không đồng nghĩa key cũ đã được audit khỏi mọi nơi. Nếu nghi key cũ bị lộ, thông báo người điều phối để rotate và kiểm tra nơi lộ, nhưng không paste key vào mô tả sự cố.

---

## 6. Đổi mật khẩu/tạo lại user và đồng bộ fixture

### 6.1 Chuẩn bị an toàn

- Xác nhận đây là VAmPI local container đúng tên/port theo [week-1-report.md](week-1-report.md).
- Phối hợp với nhóm để tránh hai người đồng thời đổi user/fixture.
- Không reset shared database để giải quyết mismatch.
- Password mới chỉ tồn tại trong local password manager hoặc quy trình private của nhóm; không đặt trong tài liệu này.

### 6.2 Cập nhật credential local

1. Đổi password hoặc tạo lại `admin`, `userA`, `userB` bằng workflow local được nhóm phê duyệt.
2. Đăng nhập local để lấy token hiện hành cho từng role.
3. Cập nhật `roles_config.json` **atomically** theo schema cũ, với `username` đúng role và `token` có prefix `Bearer `.
4. Đặt/kiểm tra quyền file:

```bash
chmod 600 roles_config.json
```

5. Không in file này ra terminal và không thêm vào Git.

### 6.3 Kiểm tra identity và ownership

Chạy input-only validation trước:

```bash
.venv/bin/vampi-authz-lab check-inputs
```

Sau đó chạy `GET /me` thông qua preflight/CLI đã đóng gói để xác nhận response identity khớp `admin`, `userA`, `userB`. Chỉ ghi kết quả `pass/fail`, không lưu body.

Tiếp tục xác nhận owner control cho hai fixture chuẩn:

- `userA` đọc `/books/v1/week1-userA-book`;
- `userB` đọc `/books/v1/week1-userB-book`.

Cập nhật [ownership.csv](../ownership.csv) **chỉ khi** fixture thật sự được tạo lại và bạn đã xác minh quan hệ owner. Giữ nguyên năm header:

```text
resource_type,resource_id,owner_role,owner_username,path_template
```

Nếu fixture mới buộc phải đổi ID, hãy đồng bộ carefully với review của người điều phối và yêu cầu Thành viên 2/3 cập nhật trạng thái phụ thuộc trước khi họ chạy Postman/ZAP. Không đoán ID, không dò danh sách book.

### 6.4 Đồng bộ ZAP Context

Trong Context private `vampi-safe-authz`, review thủ công rằng có đúng ba enabled users `admin`, `userA`, `userB`, mỗi user có authentication/session state riêng.

- Tên/display identity phải khớp map trên.
- Không dùng Global Replacer/shared header làm thay per-user authentication.
- Context export, authentication material và attestation là private; phải mode `0600`, ignored và không commit.
- Chỉ review metadata/rule mapping ở đây; chi tiết Access Rules và containment theo [contributor-3-zap-research-debug-guide.md](contributor-3-zap-research-debug-guide.md).

### 6.5 Điều kiện dừng

Không chạy matrix/scan nếu bất kỳ điểm nào sai: `GET /me` trả sai user, owner control fail, fixture không còn tồn tại, Context thừa/thiếu user, token expired, hoặc Container không còn là local target. Báo lại bằng status redacted và chờ đồng bộ thay vì bypass preflight.

---

## 7. Tái lập test suite và CLI

### 7.1 Chuẩn bị môi trường

Nếu `.venv` chưa có package hiện hành:

```bash
.venv/bin/python -m pip install .
```

`-I` loại source checkout khỏi `sys.path`; vì vậy dùng interpreter trong `.venv`, không thay bằng system `python3 -I` chưa cài package.

### 7.2 Chạy unit test

```bash
.venv/bin/python -I -m unittest discover -s tests -v
```

Kỳ vọng lịch sử trong [week-4-report.md](week-4-report.md) là 128 tests pass, nhưng acceptance của bạn là **ghi kết quả chạy thực tế**. Nếu khác 128 hoặc có error/failure, không làm tiếp đối chiếu live; lưu output redacted, nêu tên test và báo người điều phối.

### 7.3 Chạy bốn CLI đóng gói

Chỉ sau khi input/credential hợp lệ và lab local sẵn sàng:

```bash
.venv/bin/vampi-authz-lab check-inputs
```

```bash
.venv/bin/vampi-authz-lab run
```

```bash
.venv/bin/vampi-authz-lab verify
```

```bash
.venv/bin/vampi-authz-lab week3
```

Ý nghĩa cần đối chiếu:

| CLI | Bằng chứng cần kiểm tra | Không được suy diễn |
| --- | --- | --- |
| `check-inputs` | spec, 3 role, 4 fixture có cấu trúc hợp lệ; không network | Không chứng minh token còn sống. |
| `run` | 12 case read-only, verdict/artifact redacted, baseline-based classification | Không tính admin policy-dependent thành BOLA user-to-user. |
| `verify` | xác minh độc lập known books bằng fresh owner baseline | Không dùng result cũ thay cho run mới. |
| `week3` | timed pipeline + independent verification | Script timing không phải timing Postman/manual. |

Khi command dừng an toàn, CLI trả code `2` và in `Command stopped safely: ...`; coi đó là guardrail hoạt động, không cố đổi target hay tắt validation.

### 7.4 Đối chiếu compatibility entry points

Các entry point cần so sánh:

```bash
.venv/bin/python -I week2/main.py
```

```bash
.venv/bin/python -I week3/run_week3.py
```

So sánh theo semantic result sau đây, không so raw timing/token/body:

- Cùng local base URL strict `http://127.0.0.1:5000`.
- Cùng số case và nhóm artifact tương ứng.
- `run` có 12 case; historical raw verdict có `CONFIRMED=4`, `CONTROL_PASS=2`, `DENIED=4`, `OBSERVATION=2`.
- Báo cáo tổng hợp chỉ ghi **2 BOLA user-to-user**; hai admin results vẫn `POLICY_DEPENDENT`.
- `verify` phải phân loại independent results, không reuse Week 2 evidence.
- Cả console entry point và compatibility script phải từ chối base URL không hợp lệ, không tự broad scope.

Không so sánh bằng cách đọc/copy secret từ `raw_results.json`; artifacts trong `results/` là generated, ignored và vẫn có thể chứa bounded lab response data.

---

## 8. Audit token/password và `.gitignore`

### 8.1 Kiểm tra quy tắc ignore

Review [.gitignore](../.gitignore) để xác nhận ít nhất các nhóm sau đang bị loại trừ:

- `roles_config.json`, `.env`, `*.key`;
- `zap/*.context`, `zap/private/`, `zap/imported-context-attestation.json`, `zap/run-output/`;
- `.bfla-runs/` và `results/`;
- cache/build Python và local VAmPI source checkout.

### 8.2 Quy trình audit redacted

1. Kiểm tra tracked documentation/source và staged changes theo quy trình Git của nhóm.
2. Tìm **dấu hiệu** credential trong nội dung tracked, không đưa match/value vào report.
3. Kiểm tra rằng private files không xuất hiện trong `git status --ignored` theo cách bị staged/tracked ngoài ý muốn.
4. Review screenshot, worksheet và report draft để không có raw header/body/key.
5. Ghi một checklist redacted theo mẫu dưới đây.

| Hạng mục | Kết quả | Hành động/bằng chứng redacted |
| --- | --- | --- |
| `roles_config.json` | private/ignored | Mode `0600` đã xác nhận; không commit. |
| Context ZAP/attestation | private/ignored | Path được ignore; không review raw content trong report. |
| `results/` | generated/ignored | Chỉ chia sẻ summary redacted. |
| Tracked source/docs | sạch / cần xử lý | Chỉ nêu path + loại secret nếu phát hiện. |
| Screenshot/Postman export | sạch / cần xử lý | Không token, password, raw secret/body. |

Nếu tìm thấy secret thật trong working tree, staged files hoặc Git history: **dừng**, không paste nó vào issue/chat; rotate/revoke local nếu có thể, thông báo người điều phối với path/category/time, rồi xử lý theo quy trình repository. Đừng tự force-push/rewrite history nếu chưa có quyết định của người sở hữu repo.

---

## 9. Checklist nghiệm thu và handoff

### Checklist nghiệm thu

- [ ] Hoàn thành Giai đoạn nền tảng và phần trình bày miệng.
- [ ] ZAP API key mới chỉ tồn tại session-local; không có key trong repo/chat/screenshot.
- [ ] `admin`, `userA`, `userB` xác minh identity đúng; `roles_config.json` private mode `0600`.
- [ ] Hai owner fixture và [ownership.csv](../ownership.csv) khớp thực tế; mọi mismatch đã báo blocker.
- [ ] ZAP Context có đúng 3 user đã review; credential/context vẫn private.
- [ ] Test suite đã chạy; ghi số pass/failure thực tế.
- [ ] `check-inputs`, `run`, `verify`, `week3` và hai compatibility entry point đã được đối chiếu theo semantic output.
- [ ] Audit `.gitignore`/secret đã hoàn thành, không ghi secret vào evidence.

### Mẫu bàn giao redacted

```text
Ngày/giờ:
Người thực hiện:
Lab target: 127.0.0.1:5000 (đã xác nhận loopback)
Credential/identity: admin/userA/userB = pass | blocker
Fixture ownership: pass | blocker (mô tả redacted)
ZAP Context users: pass | blocker
Tests: <số pass thực tế>, failures: <0 hoặc mô tả redacted>
CLI parity: check-inputs/run/verify/week3 = pass | blocker
Secret audit: clean | escalation opened
Cho Thành viên 2: có thể bắt đầu 7 case? yes | no
Cho Thành viên 3: Context/identity prerequisite available? yes | no
Blocker/owner tiếp theo:
```
