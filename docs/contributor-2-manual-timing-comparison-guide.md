# Hướng dẫn Thành viên 2 — Đo thủ công, worksheet và bảng so sánh

> **Vai trò:** thực hiện lại bảy case thủ công trong VAmPI local bằng Postman hoặc `curl`, đo thời gian theo cùng một quy ước, hoàn thiện worksheet/comparison artifact và viết đoạn so sánh phương pháp.
> **Phạm vi được phép:** duy nhất lab Docker được ủy quyền tại `http://127.0.0.1:5000`, chỉ bảy request `GET` đã định nghĩa trong [week3/manual_sample_cases.json](../week3/manual_sample_cases.json).

## 1. Đầu ra cần bàn giao

1. [results/week3_manual_worksheet.md](../results/week3_manual_worksheet.md) local, đủ đúng 7 case M-01 đến M-07, status/quan sát/time hợp lệ và không lộ secret.
2. [results/week4_comparison_final.json](../results/week4_comparison_final.json) được kiểm tra để manual section có `COMPLETED`, 7 rows và `elapsed_minutes` khác `null`.
3. Một đoạn tiếng Việt khoảng 250 từ so sánh thời gian/giới hạn giữa script, manual, ZAP và BFLA disposable để người điều phối chèn vào báo cáo.
4. Một handoff redacted: trạng thái 7 case, số timing hợp lệ, xác nhận M-02/M-03 nếu đã quan sát disclosure, và mọi blocker.

`results/` bị ignore có chủ đích. Nó có thể không có trong checkout mới; bạn phải tạo output local theo workflow, **không commit** artifact/screenshot/raw response.

---

## 2. Giai đoạn nền tảng bắt buộc — 3–4 ngày

Hoàn thành trước khi mở Postman hay gửi request chuyên trách.

### Ngày 1 — Lý thuyết và tiêu chuẩn evidence

- [ ] Đọc OWASP API Top 10, API1 BOLA và API5 BFLA.
- [ ] Đọc Phần 1 của [final-report-draft.md](final-report-draft.md), [README.md](../README.md), [week-1-report.md](week-1-report.md), [week-2-report.md](week-2-report.md).
- [ ] Trình bày được vì sao `200 OK` chưa đủ: BOLA user-to-user cần cross-user success và `$.secret` khớp fresh owner baseline.

### Ngày 2 — Lab local và quan sát controlled

Làm theo [week-1-report.md](week-1-report.md), chỉ tại `127.0.0.1:5000`.

- [ ] Xác nhận local loopback target, không phải Internet/LAN/production.
- [ ] Tạo hai user và mỗi user một book fixture theo procedure được nhóm phê duyệt.
- [ ] Dùng credential user 1 đọc known book của user 2 để quan sát field `secret` trong VAmPI training lab.
- [ ] Chụp bằng chứng đã che hoàn toàn token/password/header và **giá trị** secret; chỉ chia sẻ ảnh đã che theo quy ước nhóm.
- [ ] Không gọi `/createdb`; không dò identifier hoặc gửi request state-changing trong shared lab.

### Ngày 3 — Hiểu script và tài liệu theo trình tự

- [ ] Đọc [week2/spec_parser.py](../week2/spec_parser.py), [week2/matrix_builder.py](../week2/matrix_builder.py), [week2/request_runner.py](../week2/request_runner.py), [week2/response_comparator.py](../week2/response_comparator.py).
- [ ] Chạy khi môi trường hợp lệ:

```bash
.venv/bin/python -I week2/main.py
```

- [ ] Đọc [week-1-report.md](week-1-report.md) → [week-2-report.md](week-2-report.md) → [week-3-report.md](week-3-report.md) → [week-4-report.md](week-4-report.md) → [final-report-draft.md](final-report-draft.md).
- [ ] Giải thích được: public profile là `OBSERVATION`; admin book access là `POLICY_DEPENDENT`; BFLA disposable là `DENIED_CONTROL`; ZAP không chứng minh precise sensitive-field disclosure của M-02/M-03.

### Ngày 4 — Họp miệng/sign-off (nếu cần)

Chuẩn bị trình bày 15–20 phút không dùng slide về scope, evidence model, seven-case matrix và cách tránh làm lộ credential. Chỉ bắt đầu phần 4 sau sign-off của người điều phối.

---

## 3. Điều kiện bắt đầu và giới hạn an toàn

### Dependency bắt buộc từ Thành viên 1

Chỉ gửi request live khi có handoff redacted xác nhận:

- `admin`, `userA`, `userB` identity/token local còn hợp lệ;
- shared lab chưa bị reset và dùng đúng `127.0.0.1:5000`;
- map [ownership.csv](../ownership.csv) và hai book fixture vẫn khớp;
- không có blocker liên quan credentials/fixture ownership.

Nếu thiếu bất kỳ điều kiện nào, ghi `PENDING`/blocker; **không** bịa timing, không tái sử dụng secret/token cũ và không tự reset database.

### Chỉ được làm

- Chỉ bảy case trong [week3/manual_sample_cases.json](../week3/manual_sample_cases.json).
- Chỉ `GET`, exact known paths, `http://127.0.0.1:5000`.
- Chỉ observation/status đã redaction trong worksheet.

### Không được làm

- Không thêm request, endpoint, ID, query/fragment, host/port khác.
- Không `/createdb`, enumeration, fuzzing, wordlist, discovery, Spider/AJAX Spider/active scan.
- Không gửi `POST`, `PUT`, `PATCH`, `DELETE` trong shared lab cho nhiệm vụ này.
- Không copy token/password/JWT/header/raw body/giá trị `secret` vào worksheet, artifact, screenshot, report hoặc chat.
- Không export Postman environment/collection trong khi Current Value vẫn chứa token.

Dừng attempt và báo blocker nếu network/lab/tooling lỗi, response không rõ do target, credential hết hạn, hoặc request có nguy cơ vượt scope.

---

## 4. Chuẩn bị Postman hoặc curl an toàn

### 4.1 Postman (khuyến nghị cho nhiệm vụ đo thủ công)

1. Tạo environment cục bộ **VAmPI Local**:
   - `baseUrl` = `http://127.0.0.1:5000`
   - các token user chỉ lưu ở cột **Current Value**.
2. Không lưu token vào Initial/Shared Value.
3. Lấy credential theo workflow local được Thành viên 1 bàn giao; không dán token/password vào file Markdown.
4. Trước mỗi case, kiểm tra environment đang chọn, URL chính xác, method `GET` và authentication state đúng case.
5. Khi hoàn thành, xóa toàn bộ Current Value token trước khi đóng/export workspace.

> Có thể dùng `curl` cho kiểm tra có kiểm soát, nhưng chỉ Postman phù hợp trực tiếp với protocol “từ Send đến đọc xong response”. Dù dùng công cụ nào, không lưu command chứa bearer token vào shell history hoặc tài liệu.

### 4.2 Bảy case chuẩn — không thêm/bớt

| ID | Request | Auth | Kết quả/diễn giải cần kiểm tra |
| --- | --- | --- | --- |
| M-01 | `GET /books/v1/week1-userA-book` | userA | Owner control; expected `200`, owner fixture hợp lệ. |
| M-02 | `GET /books/v1/week1-userA-book` | userB | Cross-user candidate; API đúng policy phải deny/hide. Chỉ ghi BOLA khi quan sát disclosure thực tế. |
| M-03 | `GET /books/v1/week1-userB-book` | userA | Cross-user candidate; cùng quy tắc M-02. |
| M-04 | `GET /books/v1/week1-userA-book` | none | Negative control, expected `401`. |
| M-05 | `GET /books/v1/week1-userA-book` | intentionally invalid bearer | Negative control, expected `401`. |
| M-06 | `GET /users/v1/userA` | none | Public profile observation; không tự gọi BOLA. |
| M-07 | `GET /me` | userA | Identity control; expected `200` với userA. |

Đây là subset 7 case khác với 12 case script. Không dùng kết quả BOLA, count hoặc timing của script để điền hộ worksheet manual.

---

## 5. Protocol đo thời gian nhất quán

### 5.1 Định nghĩa metric

Metric là **manual request/response interaction time theo từng case**, đơn vị giây: từ ngay trước khi nhấn **Send** đến khi Postman đã render completed response và người thực hiện đọc đủ status để ghi vào bảng.

Metric **không** bao gồm: tạo environment, login, copy token, dựng request, đổi case, suy luận bảo mật, chụp ảnh, hay viết report. Do đó nó không phải tổng giờ công analyst.

### 5.2 Quy trình cho mỗi case

1. Chuẩn bị request hoàn chỉnh **trước khi** bấm giờ: environment, method, exact known path và authentication state đã đúng.
2. Xác nhận request là một trong bảng ở phần 4.2.
3. Khởi động stopwatch ngay trước khi chọn **Send**.
4. Nhấn Send một lần.
5. Dừng stopwatch khi response đã render và bạn có thể đọc status để ghi quan sát.
6. Ghi số giây (cho phép thập phân) cùng status và finding redacted.
7. Nếu có lỗi UI/network/expired token, đánh dấu attempt đó invalid trong ghi chú nội bộ không chứa secret, sửa local setup, rồi đo lại **cùng case được duyệt**. Không thay case hay thêm request chẩn đoán ngoài scope.

Nên giữ cùng stopwatch/tool cho cả bảy case. Ghi mỗi case một lần đo hợp lệ theo assignment; nếu tự thực hiện nhiều lượt để ổn định, báo rõ phương pháp aggregate với người điều phối thay vì lặng lẽ chọn số đẹp nhất.

---

## 6. Điền worksheet đúng parser contract

### 6.1 Đường dẫn và cấu trúc bắt buộc

Tạo/cập nhật local file:

```text
results/week3_manual_worksheet.md
```

[week4/comparison_builder.py](../week4/comparison_builder.py) chỉ nhận row có **đúng 7 cột**, một mỗi ID M-01–M-07, `Status` và `Findings` không rỗng. Dùng chính xác header sau:

```markdown
| Mẫu | Endpoint | Auth | Expected | Status | Findings | Time (s) |
| --- | --- | --- | --- | --- | --- | --- |
```

Template bắt đầu an toàn (thay placeholder bằng quan sát thực tế):

```markdown
| Mẫu | Endpoint | Auth | Expected | Status | Findings | Time (s) |
| --- | --- | --- | --- | --- | --- | --- |
| M-01 | `GET /books/v1/week1-userA-book` | userA | Owner control | `<HTTP status>` | `<owner-control result, no secret>` | `<seconds>` |
| M-02 | `GET /books/v1/week1-userA-book` | userB | Deny/hide expected | `<HTTP status>` | `<actual redacted observation>` | `<seconds>` |
| M-03 | `GET /books/v1/week1-userB-book` | userA | Deny/hide expected | `<HTTP status>` | `<actual redacted observation>` | `<seconds>` |
| M-04 | `GET /books/v1/week1-userA-book` | none | `401` | `<HTTP status>` | `<redacted observation>` | `<seconds>` |
| M-05 | `GET /books/v1/week1-userA-book` | invalid token | `401` | `<HTTP status>` | `<redacted observation>` | `<seconds>` |
| M-06 | `GET /users/v1/userA` | none | Public observation | `<HTTP status>` | `<observation; not BOLA>` | `<seconds>` |
| M-07 | `GET /me` | userA | Identity control | `<HTTP status>` | `<identity control result>` | `<seconds>` |
```

### 6.2 Quy tắc nội dung

- ID phải đúng, không duplicate, không thiếu; mỗi row có Status và Findings khác rỗng.
- Nhập time là số giây (`1`, `1.4`, `12.08`); assignment này yêu cầu đo đủ 7 case.
- Parser chấp nhận `—` hoặc `-` và sẽ tạo `COMPLETED_NO_TIMING`, nhưng đây **không** đáp ứng đầu việc đo thời gian trừ khi có blocker được người điều phối chấp nhận.
- Chỉ dùng exact substring `BOLA confirmed` trong finding M-02/M-03 nếu response thực tế chứng minh cross-user sensitive disclosure. Không ghi secret value để chứng minh.
- M-04/M-05 là denial controls, M-06 là `OBSERVATION`, M-07 là identity control; không nâng chúng thành BOLA.
- Không thêm bearer value, header, password, raw JSON hoặc raw error body.

Khi cả 7 time là numeric, parser sẽ tính:

- `status: "COMPLETED"`;
- `sample_case_count: 7`;
- `filled_case_count: 7`;
- `elapsed_minutes`: tổng bảy giây chia 60.

Nếu bắt buộc dừng giữa chừng, giữ file rõ phần incomplete và báo blocker; không xóa/ghi đè evidence của thành viên khác.

---

## 7. Cập nhật và kiểm tra comparison artifact

### 7.1 Trước khi build

Bạn chỉ được thay đổi evidence manual sau khi worksheet hoàn chỉnh. Rebuild comparison **không phải** permission để chạy BFLA destructive hoặc ZAP scan.

Xác nhận với người điều phối:

- script timing artifact đang dùng là của run đã được chấp nhận;
- BFLA receipt/run ID nào (nếu có) được phép dùng cho comparison;
- trạng thái ZAP phải lấy từ artifact hiện hành, không invent `COMPLETED`/`NOT_RUN`.

Trong repository hiện tại, [week4/comparison_builder.py](../week4/comparison_builder.py) tách độc lập 4 cột: script, manual, ZAP, BFLA disposable. Các total 12, 7, 15 và 2 **không hoán đổi trực tiếp**.

### 7.2 Cách đánh giá kết quả

Sau flow Week 4 mà người điều phối đã phê duyệt chạy xong, mở JSON redacted và xác nhận thủ công:

| Trường manual | Giá trị cần có |
| --- | --- |
| `status` | `COMPLETED` |
| `sample_case_count` | `7` |
| `filled_case_count` | `7` |
| `elapsed_minutes` | khác `null` |
| `confirmed_findings` | phản ánh đúng finding text, không phải số tự suy diễn |

Không ghi ZAP là xác nhận M-02/M-03. Theo [final-report-draft.md](final-report-draft.md), ZAP thực hiện endpoint/rule alignment; nó không so response cross-user với fresh owner baseline tại `$.secret`. BFLA disposable là workflow/tổ hợp target khác, verdict hiện có là `DENIED_CONTROL`, không phải sample BOLA thứ tám.

---

## 8. Đoạn so sánh phương pháp (~250 từ)

Viết đoạn tiếng Việt khoảng 250 từ cho người điều phối, sau khi có seven timings thật. Không cần sửa [final-report-draft.md](final-report-draft.md) trực tiếp nếu chưa được giao.

### Bắt buộc đề cập

1. **Script:** 12 case fixture-backed, read-only; có fresh owner baseline và so sánh `$.secret`; tái lập cao sau khi input/credential đúng; runtime còn gồm preflight/delay/artifact và phụ thuộc Docker/host.
2. **Manual Postman/curl:** 7 case chọn lọc; nhìn trực tiếp response theo từng actor; báo số seconds theo protocol ở phần 5; coverage nhỏ hơn và cần công sức analyst. Nêu rõ metric không gồm login/setup/report-writing.
3. **ZAP:** hiện là Access Control endpoint/user/rule evidence có containment nghiêm; không phải sensitive-field equality test và không xác nhận chính xác hai BOLA cross-user chỉ nhờ `ILLEGAL` row.
4. **BFLA disposable:** tách target/operation, dùng controls có cleanup; không đem count của nó so trực tiếp với BOLA.
5. **Kết luận:** bốn phương pháp bổ sung nhau; không xếp hạng “tốt nhất” bằng raw finding count hoặc case count khác scope.

### Không được viết

- Không gọi mọi `200` là BOLA.
- Không nói ZAP independent-confirmed M-02/M-03.
- Không suy timing Postman từ script runtime.
- Không nêu token/secret/password/raw body.
- Không đổi `POLICY_DEPENDENT` admin access thành confirmed BOLA.

Mở đầu/đóng đoạn có thể dùng số timing actual đã được redaction, ví dụ: “Bảy case thủ công có tổng **[X] giây** theo định nghĩa request/response interaction, không phải tổng effort vận hành.”

---

## 9. Nghiệm thu và handoff

### Checklist nghiệm thu

- [ ] Đã hoàn thành Giai đoạn nền tảng và sign-off.
- [ ] Đã nhận handoff hợp lệ từ Thành viên 1.
- [ ] Chỉ đúng 7 GET cases tại `127.0.0.1:5000` được gửi.
- [ ] Worksheet có đúng 7 row/7 cột/ID unique; mọi status và finding không rỗng.
- [ ] Có 7 timing numeric hợp lệ; không dùng `—` trừ blocker được phê duyệt.
- [ ] Không token/password/header/secret/raw body trong worksheet, JSON, ảnh hoặc đoạn so sánh.
- [ ] M-02/M-03 chỉ dùng `BOLA confirmed` nếu actual evidence hợp lệ; M-06 vẫn observation.
- [ ] Comparison manual status là `COMPLETED`; `elapsed_minutes` không null.
- [ ] Đoạn ~250 từ giữ tách biệt script/manual/ZAP/BFLA và scope/case totals.

### Mẫu handoff redacted

```text
Ngày/giờ:
Người thực hiện:
Dependency từ Thành viên 1: received | blocked
Target: 127.0.0.1:5000 confirmed
M-01..M-07: <completed count>/7
Numeric timings: <count>/7; total: <redacted aggregate seconds>
M-02/M-03: confirmed | not reproduced | blocked (không chứa secret)
Worksheet parser/comparison: COMPLETED | blocker
Token/body hygiene review: pass | blocker
Đoạn ~250 từ: attached | pending
Ghi chú/bước tiếp theo:
```
