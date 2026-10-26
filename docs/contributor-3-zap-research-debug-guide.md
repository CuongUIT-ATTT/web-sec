# Hướng dẫn Thành viên 3 — Điều tra ZAP, nghiên cứu và narrative demo

> **Vai trò:** review Context/Access Rules của OWASP ZAP trong phạm vi local allowlist, nghiên cứu ba tài liệu đã chỉ định, viết phần “Hướng tiếp theo” có trích dẫn và chuẩn bị câu chuyện debug 2–3 phút.
> **Phạm vi được phép:** chỉ VAmPI Docker local tại `http://127.0.0.1:5000`, Context `vampi-safe-authz`, và năm request `GET` trong [zap/allowlist-v2.json](../zap/allowlist-v2.json). Không scan mục tiêu ngoài phạm vi.

## 1. Kết quả cần bàn giao

1. Checklist GUI redacted xác nhận/tìm ra lỗi Access Rules trong Context `vampi-safe-authz`, đặc biệt owner book và `/me` bị gắn sai Allow/Deny hay không.
2. Ba reading memo cho **Barabanov & Dergunov (2022), Le et al. (2022), Zhang et al. (2024)** — đủ citation, câu hỏi/phương pháp, insight áp dụng, hạn chế và reference trang/phần.
3. Ba đoạn ngắn “Hướng tiếp theo” bằng tiếng Việt, chỉ đưa proposal có nguồn, không thay đổi evidence hiện tại.
4. Narrative demo 2–3 phút về debug ZAP: symptom → Site Tree root cause → history-based correction → boundary of interpretation.
5. Handoff redacted nêu trạng thái Context/rules và evidence status thực tế (`COMPLETED`, `NOT_RUN`, hoặc blocker) — không suy diễn kết quả scan chưa có.

Không bàn giao `.context`, ZAP API key, password, token/JWT, header `Authorization`, raw ZAP HTML, raw Core History, raw API error/response body, hoặc attestation private.

---

## 2. Giai đoạn nền tảng bắt buộc — 3–4 ngày

Hoàn thành trước khi vào ZAP GUI hoặc viết phần báo cáo chuyên trách.

### Ngày 1 — Đọc nền tảng và giới hạn evidence

- [ ] Đọc OWASP API Top 10: API1 BOLA và API5 BFLA.
- [ ] Đọc Phần 1 của [final-report-draft.md](final-report-draft.md), [README.md](../README.md), [week-1-report.md](week-1-report.md), [week-2-report.md](week-2-report.md).
- [ ] Giải thích được: `200 OK` chưa đủ BOLA; cần owner baseline + sensitive field equality; admin access là `POLICY_DEPENDENT` nếu policy chưa xác nhận.

### Ngày 2 — Lab local có kiểm soát

Theo [week-1-report.md](week-1-report.md), chỉ thao tác Docker local loopback.

- [ ] Xác nhận target `127.0.0.1:5000`, không LAN/Internet/production.
- [ ] Tạo hai user/fixture theo workflow local được chấp thuận; mỗi user có một book.
- [ ] Dùng credential user 1 đọc known book của user 2 để tận mắt thấy field `secret` trong lab training.
- [ ] Gửi nhóm một screenshot **đã che** mọi token/password/header và giá trị secret; chỉ hiển thị context cần thiết để chứng minh observation.
- [ ] Không `/createdb`, enumeration, fuzz, spider hoặc request state-changing ở shared lab.

### Ngày 3 — Đọc code/báo cáo theo thứ tự

- [ ] Đọc [week2/spec_parser.py](../week2/spec_parser.py), [week2/matrix_builder.py](../week2/matrix_builder.py), [week2/request_runner.py](../week2/request_runner.py), [week2/response_comparator.py](../week2/response_comparator.py).
- [ ] Chạy, chỉ khi environment hợp lệ:

```bash
.venv/bin/python -I week2/main.py
```

- [ ] Đọc [week-1-report.md](week-1-report.md) → [week-2-report.md](week-2-report.md) → [week-3-report.md](week-3-report.md) → [week-4-report.md](week-4-report.md) → [final-report-draft.md](final-report-draft.md).
- [ ] Đọc thêm [week4/zap_context_builder.py](../week4/zap_context_builder.py), [week4/zap_runner.py](../week4/zap_runner.py) và [zap/allowlist-v2.json](../zap/allowlist-v2.json).

### Ngày 4 — Họp sign-off (nếu cần)

Chuẩn bị giải thích miệng 15–20 phút:

- Tại sao Site Tree parent node không tự là out-of-scope HTTP request.
- Vì sao paginated Core HTTP history là containment evidence.
- Vì sao ZAP endpoint/rule evidence không xác nhận đúng hai BOLA cross-user ở precision `$.secret`.

Chỉ tiếp tục phần 4 sau sign-off của người điều phối.

---

## 3. Guardrail, dependency và nguồn chuẩn

### 3.1 Dependency

Bạn có thể đọc nghiên cứu và review thiết kế Context song song. Tuy nhiên trước authentication/run thực tế, cần handoff redacted của Thành viên 1 xác nhận:

- role `admin`, `userA`, `userB` còn valid và khớp ownership;
- fixture/book map đúng [ownership.csv](../ownership.csv);
- local private Context/attestation prerequisite sẵn sàng;
- không còn blocker credential/container.

Nếu thiếu, chỉ ghi nhận trạng thái `NOT_RUN`/blocker; không tạo fake user state, không dùng token cũ, không nới allowlist.

### 3.2 Nguồn chuẩn

| Nguồn | Dùng để làm gì |
| --- | --- |
| [zap/allowlist-v2.json](../zap/allowlist-v2.json) | Năm GET paths, rule expectation matrix, prohibitions và containment policy. |
| [week-4-report.md](week-4-report.md) | Quy trình Desktop/import, quiescence, artifact/redaction và interpretation hiện hành. |
| [final-report-draft.md](final-report-draft.md) | Wording báo cáo cuối §§3.4, 4.1–4.4 và bibliography. |
| [week4/zap_context_builder.py](../week4/zap_context_builder.py) | Context/attestation validation. |
| [week4/zap_runner.py](../week4/zap_runner.py) | Lifecycle, history containment, report parsing/cleanup, fail-closed behavior. |
| [zap/imported-context-attestation.example.json](../zap/imported-context-attestation.example.json) | Template non-secret; bản thật luôn private/ignored. |

### 3.3 Giới hạn tuyệt đối

- Chỉ target `http://127.0.0.1:5000`; ZAP listener phải loopback local.
- Chỉ Access Control add-on, không Spider, AJAX Spider, active scan, fuzzing, discovery, wordlist, enumeration hay import full OpenAPI.
- Không `/createdb`; không query/fragment, host/scheme/port khác, malformed request hoặc method khác `GET`.
- Không Global Replacer/shared header để giả credential cho mọi user.
- Không commit/export Context, credential, raw report/history/body/header/API key.

Nếu không chắc action của GUI có thể gửi request ngoài năm path, hãy **dừng** và hỏi người điều phối.

---

## 4. Tóm tắt đúng lịch sử debug và 9 gate

### 4.1 Bối cảnh lỗi cũ

Lịch sử debug không được diễn giải là “ZAP không tìm thấy gì”. Attempt cũ sai vì containment logic coi các **parent node cấu trúc** trong ZAP Site Tree — origin, `/books`, `/books/v1`, `/users`, `/users/v1` — như HTTP request thật vượt scope.

Điều đó sai vì Site Tree là biểu diễn phân cấp; node cha có thể được ZAP tự tạo dù không hề có một request HTTP parent path tương ứng. Site Tree được giữ làm **diagnostic**, không phải proof pass/fail.

### 4.2 Thiết kế sửa: evidence là actual paginated HTTP history

Quy trình v2 đánh giá mỗi target HTTP message từ paginated Core history. Sau authenticated quiescence/baseline, mọi assessment message phải là:

```text
GET http://127.0.0.1:5000 + một trong năm path được phê duyệt, không query/fragment
```

Sai/missing history page, malformed request line, non-GET, foreign host/scheme/port, unapproved path hoặc `/createdb` đều fail-closed.

### 4.3 Chín nhóm gate cần hiểu trước khi review GUI

1. **Manifest scope:** validate exact v2 allowlist; không broad scope.
2. **Private Context/attestation:** Context regular file mode `0600`, hash và non-secret attestation khớp.
3. **Context identity:** đúng tên `vampi-safe-authz`, exact include regexes.
4. **User model:** đúng ba unique enabled users `admin`, `userA`, `userB`.
5. **Authentication:** mỗi user report authenticated/poll success; không dùng state cũ suy diễn.
6. **Quiescence/baseline:** target-scoped Core history count ổn định hai lần cách nhau một giây trước seed.
7. **Seed containment:** exact năm GET approved, mỗi path một lần trong seed delta.
8. **Scan lifecycle:** chỉ Access Control context/user lifecycle, poll contract được review và result/report transient hợp lệ.
9. **Post-scan containment + redaction:** scan delta vẫn chỉ allowed requests; temporary HTML được parse whitelist rồi cleanup; final artifact không chứa raw history/header/body/token.

`NOT_RUN` tại bất cứ gate nào là một **safe stop**. Nó không phải scanner finding và cũng không chứng minh không có lỗ hổng.

---

## 5. Checklist ZAP GUI — Context và Access Rules

### 5.1 Validate manifest trước

CLI mặc định legacy v1, nên khi validate v2 phải chỉ rõ file:

```bash
.venv/bin/vampi-authz-lab check-zap-allowlist --manifest zap/allowlist-v2.json
```

Output success chỉ cho biết manifest hợp lệ và **không** start scan/send request.

### 5.2 Context `vampi-safe-authz`

Trong session ZAP Desktop mới/private, review thủ công:

- [ ] Context name là `vampi-safe-authz`.
- [ ] Target exact `http://127.0.0.1:5000`.
- [ ] Include regexes narrow, match **chỉ** năm absolute URLs dưới đây — không wildcard origin hay parent path:

```text
http://127.0.0.1:5000/books/v1/week1-userA-book
http://127.0.0.1:5000/books/v1/week1-userB-book
http://127.0.0.1:5000/users/v1/userA
http://127.0.0.1:5000/users/v1/userB
http://127.0.0.1:5000/me
```

- [ ] Có đúng ba enabled users riêng: `admin`, `userA`, `userB`.
- [ ] Mỗi user có auth/session state riêng; không dùng Global Replacer hay một bearer/header chung.
- [ ] Authentication Verification Strategy đã review; successful state/poll phải là hiện tại, không chỉ dựa timestamp/history cũ.
- [ ] Private context export/attestation giữ `0600`, ignored; không upload/commit/copy content.

### 5.3 Access Rules expectation matrix

So Access Rules với `authorization_expectations` trong [allowlist-v2.json](../zap/allowlist-v2.json):

| Path | userA | userB | admin |
| --- | --- | --- | --- |
| `/books/v1/week1-userA-book` | **Allow** (owner) | **Deny** (cross-user) | `policy-dependent` |
| `/books/v1/week1-userB-book` | **Deny** (cross-user) | **Allow** (owner) | `policy-dependent` |
| `/users/v1/userA` | **Allow** | **Allow** | **Allow** |
| `/users/v1/userB` | **Allow** | **Allow** | **Allow** |
| `/me` | **Allow** | **Allow** | **Allow** |

Mục đích review chính là kiểm tra giả thuyết đang có: owner self-book và mỗi user `/me` có thể bị set nhầm **Deny** hoặc mapping actor/rule đảo chiều. Hãy ghi checklist result (match/mismatch, path/rule label), **không** export screenshot/raw Context token.

- Nếu thấy mismatch rõ: ghi redacted finding và báo người điều phối trước khi sửa rule.
- Nếu được ủy quyền sửa: review lại toàn bộ matrix và context fingerprint/attestation sau thay đổi; không “sửa cho scan xanh” mà bỏ owner/cross-user conditions.
- Admin book paths giữ `policy-dependent`: không tự đặt Allow/Deny như một lỗ hổng hay fix trước khi có product policy.

### 5.4 Không được bật

- Spider/AJAX Spider, active scan, fuzzing, forced browsing, wordlists, enumeration.
- Scope wildcard như `http://127.0.0.1:5000/.*`.
- Request method khác GET, import full OpenAPI, global auth replacement.
- Cơ chế bypass/tắt quiescence/history/attestation gate.

---

## 6. Diễn giải evidence ZAP đúng cách

> **Ranh giới bắt buộc:** ZAP Access Control đánh giá quan hệ endpoint/user/rule đã cấu hình. Nó không so response cross-user với fresh owner baseline tại `$.secret`. Vì vậy, kết quả ZAP **không xác nhận chính xác** hai BOLA cross-user M-02/M-03; script owner-baseline và Postman manual mới là evidence trực tiếp cho sensitive disclosure.

### Trạng thái đã ghi trong báo cáo hiện hành

Theo [week-4-report.md](week-4-report.md) và [final-report-draft.md](final-report-draft.md), validated local run là `COMPLETED` khi tất cả gate/report cleanup pass:

- 15 reviewed rows (`5 path × 3 users`), 15 scan-delta GET allowlisted, `violation_counts` rỗng;
- 5 scanner-labeled `ILLEGAL` rule-alignment discrepancies;
- hai book anomalies gắn vào **owner** (`userA` trên book userA, `userB` trên book userB), **không** phải hai actor cross-user đã xác nhận BOLA;
- ba `/me` rows bị gắn `ILLEGAL`.

Vì redacted artifact chỉ lưu `ILLEGAL` rows, absence của admin-book finding **không chứng minh** result `VALID` cho combination không xuất hiện. Các anomaly owner-book/`/me` là tín hiệu review mapping/Context/rule; không phải BOLA mới, không chứng minh root cause, và không thay thế evidence `$.secret`.

Nếu run tương lai không qua gate, nói chính xác `NOT_RUN` + reason class redacted. Không diễn giải thành “ZAP clean”, “không có BOLA”, hoặc reverse confirmation.

---

## 7. Ba bài nghiên cứu: reading memo có traceability

Đọc đầy đủ ba bài người điều phối đã nêu. Bibliography canonical nằm ở [final-report-draft.md](final-report-draft.md).

### A. Barabanov & Dergunov (2022)

A. Barabanov and D. Dergunov, “Automatic Detection of Access Control Vulnerabilities via API Specification Processing,” *Voprosy kiberbezopasnosti*, 2022, doi: `10.21681/2311-3456-2022-1-49-65`.

### B. Le et al. (2022)

H. T. Le, L. K. Shar, D. Bianculli, L. C. Briand, and C. D. Nguyen, “Automated reverse engineering of role-based access control policies of web applications,” *Journal of Systems and Software*, vol. 184, art. 111109, Feb. 2022, doi: `10.1016/j.jss.2021.111109`.

### C. Zhang et al. (2024)

Z. Zhang, F. Zou, J. Hong, L. Chen, and P. Yi, “Detection and Analysis of Broken Access Control Vulnerabilities in App–Cloud Interaction in IoT,” *IEEE Internet of Things Journal*, vol. 11, no. 17, pp. 28267–28280, Sep. 2024, doi: `10.1109/JIOT.2024.3400858`.

DOI resolver link có thể dùng để tìm bài, nhưng không được gán claim cho bài chỉ dựa title/citation metadata.

### Template memo cho mỗi bài

```markdown
## [Citation key]
- Đã đọc: <date>; phiên bản/URL/DOI: <reference>
- Research question: <paraphrase có page/section>
- Method/data: <paraphrase có page/section>
- Kết quả liên quan đến dự án: <claim có page/section>
- Giới hạn/non-transferability: <claim của paper hoặc suy luận được gắn nhãn rõ>
- Liên hệ chính xác với VAmPI/ZAP: <proposal, không biến thành evidence hiện có>
- Claim dùng trong “Hướng tiếp theo”: <sentence + page/section>
```

Không trích claim cụ thể nếu bạn mới xem abstract/title. Nếu không truy cập được full text, báo giới hạn access thay vì phát minh method/finding.

---

## 8. Viết ba đoạn “Hướng tiếp theo”

Viết ba đoạn ngắn bằng tiếng Việt để người điều phối review/chèn vào báo cáo. Mỗi đoạn phải phân biệt **đã quan sát** với **đề xuất**, gắn ít nhất một citation/memo traceable, và không thay đổi count/severity/status hiện có.

### Đoạn 1 — Specification và ownership/policy

Nêu rằng OpenAPI hữu ích để trích operation/inventory, nhưng không thay ownership/provenance/policy. Đề xuất bán tự động hóa trích xuất/mapping dưới review của con người, không enumeration identifier. Kết nối hợp lý với Barabanov & Dergunov sau khi memo có evidence.

### Đoạn 2 — Policy/RBAC-aware authorization

Nêu nhu cầu làm rõ/suy luận policy role-based có review, đặc biệt admin `policy-dependent` và owner/cross-user relation. Đề xuất future policy model/regression matrix; không viết rằng dự án hiện tại đã reverse-engineer RBAC. Kết nối Le et al. sau khi memo có evidence.

### Đoạn 3 — Mở rộng có kiểm soát và ZAP

Nêu rằng đánh giá multi-service/app-cloud hoặc target như crAPI chỉ là future controlled scope sau approval, fixture/ownership map/containment độc lập; ZAP vẫn chỉ endpoint/rule evidence và script/manual baseline tiếp tục cần cho precise data-disclosure confirmation. Kết nối Zhang et al. sau khi memo có evidence.

Không đưa token, response, raw ZAP result hoặc các con số finding mới vào ba đoạn. Không đổi nhận định: hiện có hai BOLA user-to-user confirmed, BFLA `DENIED_CONTROL`, ZAP owner/`/me` anomalies cần review.

---

## 9. Narrative demo 2–3 phút

Dùng outline dưới đây, nói bằng ngôn ngữ tự nhiên và chỉ dùng facts đã redaction:

1. **Mục tiêu (15–20 giây):** “Chúng tôi dùng ZAP Access Control ở local VAmPI, giới hạn đúng năm GET fixture và ba user reviewed; mục tiêu là rule-level signal an toàn, không là scanner Internet.”
2. **Triệu chứng ban đầu (20–25 giây):** “Attempt đầu dừng vì logic containment nhìn Site Tree và thấy các parent `/books`, `/books/v1`, `/users`… ngoài danh sách literal.”
3. **Root cause (25–30 giây):** “Các node này là structural parent do ZAP dựng cho tree, không tự chứng minh HTTP request ngoài scope. Vì vậy kết luận out-of-scope từ tree là không đủ.”
4. **Sửa thiết kế (40–50 giây):** “Chúng tôi chuyển authoritative evidence sang paginated Core HTTP history: post-auth quiescence, private baseline, exactly five seed GET và kiểm tra tất cả scan delta. Thêm Context fingerprint/attestation, three enabled authenticated users, narrow regex và temporary report cleanup.”
5. **Kết quả/boundary (35–45 giây):** “Run hoàn tất có 15 reviewed actor×path rows và 5 `ILLEGAL` rows nhưng actor mapping là owner-book và `/me`, không trùng hai cross-user BOLA. Vì ZAP không so `$.secret` với owner baseline, nó chỉ là rule-alignment evidence.”
6. **Kết (15–20 giây):** “Hai BOLA user-to-user vẫn do script owner-baseline và Postman xác nhận; ZAP giúp điều tra Context/rule chứ không thay thế proof đó.”

Không đọc API key, token, password, raw error/HTML/body hoặc suy đoán root cause như fact. Nếu GUI review chưa xong, thay “run hoàn tất” bằng status thực tế và nhấn mạnh `NOT_RUN` không là negative evidence.

---

## 10. Nghiệm thu và handoff

### Checklist nghiệm thu

- [ ] Hoàn thành Giai đoạn nền tảng và giải thích Site Tree vs HTTP history.
- [ ] Đã nhận hoặc ghi rõ thiếu dependency credential/fixture từ Thành viên 1.
- [ ] Explicit v2 allowlist validation đã dùng; scope gồm chính xác 5 GET paths.
- [ ] Context có 3 user riêng, include regex narrow, authentication/session per-user; không global replacement.
- [ ] Owner book và `/me` Access Rules đã được kiểm tra; cross-user Deny và admin `policy-dependent` giữ nguyên.
- [ ] Không bật Spider/AJAX/active scan/fuzz/discovery, không nới scope/bypass gates.
- [ ] Cả 3 memo có citation + page/section traceability; không invented claims.
- [ ] Ba đoạn future work tách observed/proposed và giữ correct evidence counts/status.
- [ ] Narrative demo nói rõ ZAP endpoint/rule evidence không precise-confirm M-02/M-03.
- [ ] Không có secret/raw ZAP content trong output bàn giao.

### Mẫu handoff redacted

```text
Ngày/giờ:
Người thực hiện:
Dependency identity/fixture từ Thành viên 1: ready | blocked
Manifest v2/context-name/include regex: pass | mismatch | blocked
3 users + per-user auth state: pass | mismatch | blocked
Access Rules owner-book / cross-user / profiles /me / admin-policy: <summary redacted>
ZAP evidence status: COMPLETED | NOT_RUN | blocked
Nếu COMPLETED: actor-level anomalies summary (không raw HTML/body)
Ba memo: complete | pending (nêu citation key)
Ba đoạn future work + demo narrative: ready | pending
Không-secret review: pass | blocker
Action/owner tiếp theo:
```
