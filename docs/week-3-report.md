# Báo cáo thực hiện Tuần 3 — Xác minh, phân loại và so sánh phương pháp

**Phạm vi:** VAmPI Docker local tại `http://127.0.0.1:5000`  
**Ngày thực hiện:** 20/10/2026; bổ sung kết quả đo thủ công 22/10/2026  
**Mục tiêu:** xác minh độc lập kết quả Tuần 2, phân loại BOLA/BFLA, đo thời gian pipeline và đánh giá khả năng dùng OWASP ZAP trong phạm vi an toàn.

> Báo cáo này theo nội dung Tuần 3 đã được xác nhận. Nội dung Tuần 4 nằm trong `docs/week-4-report.md`.

## 1. Phạm vi và nguyên tắc

Chỉ sử dụng:

- API VAmPI đang chạy trong Docker ở `127.0.0.1:5000`.
- Ba role của lab: `admin`, `userA`, `userB`.
- Các fixture đã biết trong `ownership.csv`.
- Request `GET` cho phần xác minh và so sánh.

Không thực hiện:

- Enumeration hoặc fuzzing identifier.
- Kiểm thử hệ thống bên thứ ba/production.
- `GET /createdb`, vì endpoint này reset database.
- `POST`, `PUT`, `PATCH`, `DELETE` trên fixture thật.

JWT của ba role được làm mới bằng `POST /users/v1/login` chỉ tới API local theo ủy quyền của người dùng. File `roles_config.json` được thay thế atomically và giữ permission `0600`; token không xuất hiện trong output hoặc báo cáo.

## 2. Hướng dẫn tái hiện — Tuần 3

### 2.1. Điều kiện tiên quyết

- Docker đã cài đặt.
- Container `vampi-week1` đã được tạo trong Tuần 1 (xem mục 2.1 của hướng dẫn Tuần 1).
- Python ≥ 3.10.
- Các file input: `vampi_spec.json`, `ownership.csv`, `roles_config.json`.

### 2.2. Khởi động lab

```bash
docker start vampi-week1
# Xác nhận lab chạy:
curl -s http://127.0.0.1:5000/ | head -5
```

### 2.3. Cài đặt package

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
```

### 2.4. Chạy pipeline xác minh độc lập

```bash
python3 -I week3/run_week3.py
```

Pipeline sẽ:
1. Gọi endpoint bằng token owner để lấy baseline mới.
2. Gọi lại bằng role khác owner.
3. So sánh trực tiếp response JSON.
4. Ghi artifact vào `results/`.

### 2.5. Chạy đo thủ công 7 case bằng Postman

1. Tạo Postman Environment `VAmPI Local` với biến:
   - `baseUrl` = `http://127.0.0.1:5000`
   - `tokenUserA` = (Current Value only, lấy từ login)
   - `tokenUserB` = (Current Value only, lấy từ login)

2. Đăng nhập lấy token:
   - `POST {{baseUrl}}/users/v1/login` với body `{"username":"userA","password":"<mật khẩu>"}`.
   - Copy `auth_token` từ response vào Current Value của `tokenUserA`.
   - Lặp lại cho `userB`.

3. Tạo 7 request GET theo `week3/manual_sample_cases.json`:
   - M-01: `GET {{baseUrl}}/books/v1/week1-userA-book` — Bearer `{{tokenUserA}}`
   - M-02: `GET {{baseUrl}}/books/v1/week1-userA-book` — Bearer `{{tokenUserB}}`
   - M-03: `GET {{baseUrl}}/books/v1/week1-userB-book` — Bearer `{{tokenUserA}}`
   - M-04: `GET {{baseUrl}}/books/v1/week1-userA-book` — No Auth
   - M-05: `GET {{baseUrl}}/books/v1/week1-userA-book` — Bearer `invalid-token-value`
   - M-06: `GET {{baseUrl}}/users/v1/userA` — No Auth
   - M-07: `GET {{baseUrl}}/me` — Bearer `{{tokenUserA}}`

4. Gửi từng request, đọc response, ghi status và ghi chú vào `results/week3_manual_worksheet.md`.

5. Sau khi xong, xóa Current Value của token trong Environment. Không export environment hoặc collection nếu vẫn chứa token.

### 2.6. Chạy unit test

```bash
python3 -I -m unittest discover -s tests -v
```

## 3. Quy trình xác minh độc lập (script)

Module `week3/manual_verifier.py` được viết tách khỏi comparator Tuần 2. Với mỗi book fixture, module:

1. Gọi endpoint bằng token của owner để lấy baseline mới.
2. Kiểm tra baseline có đúng `book_title`, `owner` và `secret` không rỗng.
3. Gọi lại cùng endpoint bằng role khác owner.
4. So sánh trực tiếp response JSON với baseline mới, không đọc verdict/evidence của `final_report.json`.
5. Ghi status, response shape, secret match và thời gian request; không ghi token.

## 4. Kết quả xác minh (script)

Pipeline Tuần 3 đã xác minh lại độc lập bốn cross-user case của Tuần 2:

| Actor | Resource owner | Endpoint | Status | Secret khớp baseline owner | Kết luận |
| --- | --- | --- | ---: | --- | --- |
| `userB` | `userA` | `GET /books/v1/week1-userA-book` | 200 | Có | BOLA xác nhận |
| `userA` | `userB` | `GET /books/v1/week1-userB-book` | 200 | Có | BOLA xác nhận |
| `admin` | `userA` | `GET /books/v1/week1-userA-book` | 200 | Có | Phụ thuộc policy admin |
| `admin` | `userB` | `GET /books/v1/week1-userB-book` | 200 | Có | Phụ thuộc policy admin |

Kết quả được lưu tại: `results/week3_manual_verification.json`

## 5. Kết quả đo thủ công (Postman)

Bảy case đã được thực hiện bằng Postman trên VAmPI local:

| Sample | Endpoint | Auth | Status | Phát hiện |
| --- | --- | --- | ---: | --- |
| M-01 | `GET /books/v1/week1-userA-book` | userA | 200 | Owner control pass |
| M-02 | `GET /books/v1/week1-userA-book` | userB | 200 | **BOLA confirmed**: cross-user, sensitive field lộ |
| M-03 | `GET /books/v1/week1-userB-book` | userA | 200 | **BOLA confirmed**: cross-user, sensitive field lộ |
| M-04 | `GET /books/v1/week1-userA-book` | None | 401 | Negative control: anonymous bị từ chối |
| M-05 | `GET /books/v1/week1-userA-book` | Invalid | 401 | Negative control: invalid token bị từ chối |
| M-06 | `GET /users/v1/userA` | None | 200 | Public profile; không phải BOLA |
| M-07 | `GET /me` | userA | 200 | Identity control pass |

Kết quả thủ công tái xác nhận hai BOLA user-to-user (M-02, M-03) khớp với kết quả script. Negative control (M-04, M-05) xác nhận hệ thống có kiểm tra authentication; vấn đề nằm ở object-level authorization. Thời gian thao tác thủ công không được đo vì chỉ phục vụ so sánh phương pháp, không ảnh hưởng đến kết luận bảo mật.

Chi tiết: `results/week3_manual_worksheet.md`

## 6. Phân loại lỗ hổng

### W3-01 — BOLA: cross-user đọc secret của book

| Thuộc tính | Kết quả |
| --- | --- |
| Loại | BOLA |
| Endpoint | `/books/v1/{book_title}` |
| Method | `GET` |
| Cơ chế | Direct full sensitive-field exposure |
| Field bằng chứng | `$.secret` |
| Impact | Read-only data disclosure |
| Severity trong lab | Medium |
| Số case user-to-user | 2 |
| Xác minh script | Confirmed (Tuần 2 + Tuần 3 independent) |
| Xác minh thủ công | Confirmed (Postman M-02, M-03) |
| Trạng thái | **Confirmed bởi cả hai phương pháp** |

Khuyến nghị: giới hạn truy vấn book theo identity trong token; nếu object không thuộc actor, trả response denial/hidden nhất quán (`403` hoặc `404` theo policy).

### W3-02 — Admin access: cần xác định policy

| Thuộc tính | Kết quả |
| --- | --- |
| Loại | Policy-dependent admin access |
| Trạng thái | Policy-dependent |
| Severity | Chưa xếp hạng |
| Cần làm rõ | Admin có được phép bypass object ownership hay không |

### W3-03 — BFLA candidate tại thời điểm Tuần 3

| Thuộc tính | Kết quả |
| --- | --- |
| Loại | BFLA candidate |
| Endpoint | `DELETE /users/v1/{username}` |
| Trạng thái của artifact Tuần 3 | Not executed |
| Lý do khi đó | State-changing; safe runner chặn mặc định |

Artifact Tuần 3 giữ nguyên trạng thái lịch sử `NOT_EXECUTED`. Thử nghiệm BFLA disposable sau đó cho kết quả `DENIED_CONTROL` — xem báo cáo Tuần 4.

### Public profile observation

`GET /users/v1/{username}` trả profile khi không có token. Đây là behavior được OpenAPI hiện tại khai báo public, nên được ghi là observation chứ không tự động gán BOLA.

## 7. Hiệu năng script tự phát triển

```text
12 read-only cases
elapsed: 2032.298 ms
configured inter-case delay: 150 ms
```

Artifact: `results/rerun-week3/week3_script_timing.json`

Thời gian bao gồm preflight, request matrix, delay giữa request và việc ghi artifact; con số phụ thuộc môi trường Docker/host.

## 8. OWASP ZAP

| Hạng mục | Kết quả |
| --- | --- |
| Image | `zaproxy/zap-stable` |
| ZAP version | 2.17.0 |
| Access Control Testing | 13.0.0, đã cài |
| Listener | `127.0.0.1:8080` |
| Access Control scan | **Không chạy** |

Artifact lịch sử: `results/zap/zap_run_status.json` ghi `NOT_RUN`. Lần thử cũ dừng khi runner cũ nhầm node parent cấu trúc trong Site Tree với HTTP message ngoài scope; artifact này không là finding ZAP và không chứng minh không có lỗ hổng. Quy trình imported Context/history-based containment thay thế nằm trong báo cáo Tuần 4.

## 9. So sánh ba phương pháp

| Tiêu chí | Script tự phát triển | Thủ công Postman | OWASP ZAP |
| --- | --- | --- | --- |
| Số case | 12 | 7 | 0 (NOT_RUN) |
| BOLA user-to-user confirmed | 2 | 2 | — |
| Thời gian | 2032 ms (tự động) | Không đo (bỏ qua) | — |
| Phát hiện data leak qua HTTP 200 | Có, so sánh `$.secret` baseline | Có, đọc response body | — |
| Tái sử dụng | Đổi spec + ownership | Thao tác lại từng case | Cần cấu hình context/user/rules |

## 10. Artifact

- `week3/manual_verifier.py`
- `week3/analyze_findings.py`
- `week3/run_week3.py`
- `week3/manual_sample_cases.json`
- `results/week3_manual_verification.json`
- `results/week3_findings.json`
- `results/week3_script_timing.json`
- `results/week3_comparison.json`
- `results/week3_manual_worksheet.md`
- `results/zap/zap_run_status.json`

## 11. Kiểm thử kỹ thuật

```bash
python3 -I -m unittest discover -s tests -v
```

Kết quả cập nhật ngày 23/10/2026: **91 tests passed**.

Không có Bearer token hoặc JWT signature trong artifact Tuần 3.
