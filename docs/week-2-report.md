# Báo cáo thực hiện Tuần 2 — Tự động hóa kiểm thử authorization

**Thời điểm thực hiện:** 20/10/2026  
**Môi trường kiểm thử:** VAmPI Docker cục bộ tại `http://127.0.0.1:5000`  
**Phạm vi:** Chỉ các account và fixture đã tạo ở Tuần 1

## 1. Mục tiêu

Tuần 2 triển khai pipeline tự động hóa để:

1. Đọc OpenAPI specification của VAmPI.
2. Tạo endpoint inventory và phân loại candidate BOLA/BFLA một cách bảo thủ.
3. Sinh ma trận test từ endpoint × role × resource owner, chỉ với fixture đã biết.
4. Chạy các request chỉ-đọc trong lab local.
5. So sánh response của owner với cross-user response theo cấu trúc JSON lồng nhau.
6. Xuất artifact JSON không chứa Bearer token hoặc JWT.

## 2. Phạm vi và kiểm soát an toàn

Pipeline chỉ được phép hoạt động với base URL chính xác:

```text
http://127.0.0.1:5000
```

Các guardrail đã triển khai:

| Kiểm soát | Cách áp dụng |
| --- | --- |
| Local-only target | Runner từ chối `localhost`, HTTPS, port khác, IP khác, query, fragment hoặc URL chứa credential |
| Fixture-only identifiers | Matrix chỉ match endpoint template trùng hoàn toàn với `ownership.csv` |
| Không enumeration | Không tăng/giảm ID, không dùng wordlist, không lấy identifier từ API listing để sinh test |
| Read-only mặc định | Chỉ `GET`/`HEAD`/`OPTIONS` được phép; `POST`, `PUT`, `PATCH`, `DELETE` bị chặn trước khi gửi request |
| Database reset protection | `GET /createdb` bị cấm tuyệt đối vì endpoint này reset database fixture |
| Token hygiene | Header request không được ghi vào artifact; `roles_config.json` vẫn ở mode `0600`; có kiểm tra chặn chuỗi Bearer/JWT trước khi ghi report |
| Preflight | Kiểm tra `vulnerable=1`, từng token qua `/me`, và owner access của mỗi book fixture trước khi chạy matrix |

Không thực hiện kiểm thử trên hệ thống bên thứ ba, môi trường production hoặc resource ngoài `ownership.csv`.

## 3. Kiến trúc triển khai

| Module | Trách nhiệm |
| --- | --- |
| `week2/spec_parser.py` | Đọc OpenAPI JSON, merge path/operation parameters, trích xuất metadata endpoint, đánh dấu endpoint state-changing và `/createdb` |
| `week2/matrix_builder.py` | Đọc `ownership.csv`, match template chính xác, sinh owner-control/cross-user/anonymous/invalid-token cases |
| `week2/request_runner.py` | Validate target local, preflight lab, thực hiện request chỉ-đọc qua Python standard library `urllib` |
| `week2/response_comparator.py` | Normalize JSON đệ quy, bỏ dynamic fields, so sánh leaf paths/values và xác định sensitive-data exposure |
| `week2/main.py` | Điều phối pipeline, ghi JSON artifact có redaction check và in summary |

Không sử dụng thư viện HTTP bên thứ ba. Pipeline chạy isolated mode:

```bash
.venv/bin/python -I week2/main.py --base-url http://127.0.0.1:5000
```

## 4. Input và endpoint inventory

### 4.1. Input tái sử dụng từ Tuần 1

| Input | Vai trò |
| --- | --- |
| `vampi_spec.json` | OpenAPI 3.0.1 lấy trực tiếp từ local lab |
| `roles_config.json` | Token đã có prefix `Bearer ` cho `admin`, `userA`, `userB`; không được đưa vào report |
| `ownership.csv` | Bốn fixture hợp lệ: hai book và hai user profile |

### 4.2. Kết quả parser

Parser đã trích xuất **14 operations** từ OpenAPI. Các endpoint có path parameter được review theo metadata từ spec, không tự động xem tên endpoint là bằng chứng về lỗ hổng.

Điểm tương thích quan trọng của VAmPI:

- Book endpoint dùng `/books/v1/{book_title}`, không phải `{book_id}`.
- `GET /users/v1/{username}` là public trong spec và trong behavior của lab hiện tại; nó được ghi là observation riêng, không bị gán kỳ vọng authorization sai.
- `PUT /users/v1/{username}/email`, `PUT /users/v1/{username}/password`, `DELETE /users/v1/{username}` là state-changing nên bị loại khỏi execution mặc định.
- `/createdb` bị loại trừ vĩnh viễn.

## 5. Ma trận test đã chạy

Matrix được sinh tự động từ fixture có template khớp chính xác.

| Nhóm | Số case | Mô tả |
| --- | ---: | --- |
| Owner control book | 2 | Mỗi owner đọc book của chính họ để xác minh fixture/baseline |
| Cross-user book read | 4 | Mỗi book được đọc bằng mọi role không phải owner (`admin`, user còn lại) |
| Anonymous/invalid token book read | 4 | Hai negative control cho từng book |
| Public profile observation | 2 | Anonymous read với `userA` và `userB`; chỉ ghi nhận behavior public |
| **Tổng** | **12** | Tất cả là request chỉ-đọc |

Preflight đã thành công trước khi chạy: lab xác nhận `vulnerable=1`, ba role xác thực thành công qua `/me`, và hai owner control book fixture hoạt động.

## 6. Kết quả thực thi

Lệnh chạy:

```bash
.venv/bin/python -I week2/main.py --base-url http://127.0.0.1:5000
```

Tóm tắt pipeline:

```text
Completed 12 read-only cases against http://127.0.0.1:5000:
CONFIRMED=4, CONTROL_PASS=2, DENIED=4, OBSERVATION=2
```

| Verdict | Số lượng | Ý nghĩa |
| --- | ---: | --- |
| `CONTROL_PASS` | 2 | Owner đọc thành công fixture của chính họ |
| `CONFIRMED` | 4 | Cross-user read trả lại sensitive owner-baseline data |
| `DENIED` | 4 | Anonymous hoặc invalid-token request bị từ chối bằng HTTP 401 |
| `OBSERVATION` | 2 | Profile read public theo OpenAPI/implementation; không kết luận như một auth failure |

## 7. Finding — Broken Object Level Authorization

### W2-01 — Cross-user access exposes another user’s book secret

| Thuộc tính | Giá trị |
| --- | --- |
| Loại | BOLA (Broken Object Level Authorization) |
| Endpoint | `GET /books/v1/{book_title}` |
| Điều kiện | Token hợp lệ của một role không sở hữu book fixture |
| Scope bằng chứng | Chỉ `week1-userA-book` và `week1-userB-book` trong local Docker lab |
| Kết quả mong đợi | Request cross-user bị từ chối hoặc ẩn resource |
| Kết quả quan sát | HTTP 200 và JSON chứa secret của owner |

Comparator chỉ đánh dấu `CONFIRMED` khi thỏa cả hai điều kiện:

1. Request cross-user trả status thành công.
2. Response chứa field sensitive khớp với owner baseline tại JSON path `$.secret`.

Các case được xác nhận:

| Actor | Resource owner | Book fixture | Evidence |
| --- | --- | --- | --- |
| `userB` | `userA` | `week1-userA-book` | `$.secret` khớp owner baseline |
| `userA` | `userB` | `week1-userB-book` | `$.secret` khớp owner baseline |
| `admin` | `userA` | `week1-userA-book` | `$.secret` khớp owner baseline |
| `admin` | `userB` | `week1-userB-book` | `$.secret` khớp owner baseline |

Hai case giữa `userA` và `userB` chứng minh missing object-level ownership check giữa các user thường. Hai case admin được ghi nhận theo cùng rule matrix; chính sách sản phẩm thực tế có thể cho phép admin đọc resource, vì vậy cần xác định rõ authorization policy mong muốn trước khi coi admin access là defect độc lập.

### Tác động

Một user đã đăng nhập có thể đọc secret của book do user khác tạo, nếu biết book title của resource fixture. Trong VAmPI lab, response trả cả `book_title`, `owner` và `secret` thay vì xác minh book thuộc authenticated subject.

### Khuyến nghị

Khi truy xuất book, lookup cần đồng thời ràng buộc owner với identity trong token, ví dụ theo nguyên tắc:

```text
book = find(book_title=<path value>, owner=<authenticated subject>)
```

Nếu không có resource thuộc owner đó, API nên trả response denial/hidden nhất quán, chẳng hạn `404` hoặc `403` theo policy đã chọn. Authorization logic nên được kiểm thử bằng owner control và cross-user regression tests như matrix ở đây.

## 8. Observation — Public user profile read

`GET /users/v1/{username}` trả profile của fixture `userA`/`userB` khi không gửi token. Đây là behavior khớp với OpenAPI hiện tại: operation không khai báo `security`; pipeline do đó phân loại là `OBSERVATION` thay vì tự động kết luận BOLA.

Nếu product policy yêu cầu profile chỉ owner hoặc admin được xem, endpoint này cần được đánh giá lại bằng một test matrix riêng. Trong phạm vi báo cáo này, không suy rộng kết luận từ việc nó public.

## 9. Artifact đầu ra

Pipeline đã tạo các file dưới `results/`:

| File | Nội dung |
| --- | --- |
| `endpoint_inventory.json` | 14 operation với metadata parser và execution note |
| `ownership_map.json` | Bản normalized, không chứa token, từ ownership CSV |
| `test_matrix.json` | 12 case fixture-backed |
| `preflight.json` | Kết quả kiểm tra target, role và owner fixture |
| `raw_results.json` | Status, content type, bounded response data, không có header/token |
| `final_report.json` | Verdict và evidence path của từng case |

Tất cả artifact JSON đã được parse lại để xác minh hợp lệ. Kiểm tra redaction không phát hiện chuỗi `Bearer ` hoặc signature JWT (`eyJ`) trong report.

## 10. Verification kỹ thuật

Unit test không gọi Docker/API. Sau khi cài package vào virtual environment, chạy qua interpreter của môi trường đó; `-I` cố ý loại checkout khỏi `sys.path`, nên system `python3 -I` không import package từ source tree:

```bash
.venv/bin/python -I -m unittest discover -s tests -v
```

Kết quả lịch sử tại thời điểm Tuần 2: **13 tests passed**.

Các test bao phủ:

- Merge path-level và operation-level OpenAPI parameters.
- Candidate/exclusion của `/createdb` và state-changing endpoints.
- Fixture template matching, không sinh ID ngoài ownership map.
- Base URL strict allowlist.
- Chặn `PUT` và `/createdb` trước khi gửi network request.
- Recursive JSON normalization và structural similarity.
- Xác nhận verdict BOLA chỉ khi cross-user response có sensitive owner-baseline data.

Pipeline cũng được kiểm tra bằng base URL không hợp lệ:

```bash
.venv/bin/python -I week2/main.py --base-url http://localhost:5000
```

Kết quả: pipeline dừng an toàn và từ chối target vì URL không đúng `http://127.0.0.1:5000`.

## 11. Giới hạn và công việc tiếp theo

- Parser dựa trên OpenAPI metadata; spec có thể thiếu security declaration, do đó inventory phải được review thủ công.
- Hệ thống chỉ test fixture đã biết, không chứng minh tất cả authorization path đều an toàn hoặc không an toàn.
- Không chạy BFLA destructive endpoint, password/email mutation, create/delete operation vì mode mặc định chỉ-đọc.
- Nếu token hết hạn hoặc container reset, preflight sẽ dừng pipeline; cần tạo lại role token/fixture và đồng bộ `roles_config.json` với `ownership.csv`.
- Bước sau có thể thêm mode state-changing tách biệt, yêu cầu explicit opt-in, fixture disposable riêng và cơ chế reset/cleanup rõ ràng.
