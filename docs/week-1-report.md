# Báo cáo thực hiện Tuần 1 — Dựng lab và phân tích mục tiêu

**Thời điểm thực hiện:** 20/10/2026  
**Môi trường:** Docker local trên Linux  
**Phạm vi:** Chỉ API VAmPI chạy trong Docker tại `127.0.0.1:5000`

## 1. Mục tiêu

Tuần 1 tập trung xây dựng môi trường thực hành API an toàn, tạo các vai trò người dùng phục vụ kiểm thử phân quyền ở tuần tiếp theo, lấy OpenAPI specification và ghi nhận quyền sở hữu các resource test.

Các mục tiêu đã hoàn thành:

- Dựng VAmPI trong Docker ở chế độ có chủ đích chứa lỗ hổng.
- Giới hạn API vào loopback, không công khai sang mạng LAN hoặc Internet.
- Khởi tạo cơ sở dữ liệu và tạo ba vai trò: `admin`, `userA`, `userB`.
- Lấy OpenAPI specification từ API đang chạy.
- Tạo fixture book cho từng người dùng và lập bảng ownership.
- Chuẩn bị đầu vào chuẩn hóa cho ma trận kiểm thử BOLA/BFLA của Tuần 2.

## 2. Phạm vi, ủy quyền và nguyên tắc an toàn

Đây là môi trường **lab Docker cô lập, chạy cục bộ** nhằm phục vụ học tập và kiểm thử có ủy quyền. Không có request nào được gửi tới hệ thống bên thứ ba, hệ thống production hoặc tài nguyên ngoài phạm vi.

Các biện pháp áp dụng:

- Cổng container chỉ được publish ở `127.0.0.1:5000`, thay vì `0.0.0.0:5000`.
- Mã nguồn VAmPI tải từ bên ngoài được giữ trong thư mục riêng `VAmPI-source/` và được xem là dữ liệu không tin cậy.
- Token xác thực được lưu cục bộ trong `roles_config.json`, permission `0600`, và đã được thêm vào `.gitignore`.
- Chỉ sử dụng các user và resource fixture do lab tạo ra.

## 3. Dựng VAmPI bằng Docker

### 3.1. Chuẩn bị mã nguồn

VAmPI được clone vào thư mục tách biệt:

```text
VAmPI-source/
```

Image local được build với tag:

```text
vampi-week1:local
```

### 3.2. Khởi chạy container

Container được chạy với cấu hình sau:

```bash
docker run --detach \
  --name vampi-week1 \
  --publish 127.0.0.1:5000:5000 \
  --env vulnerable=1 \
  --env tokentimetolive=3600 \
  vampi-week1:local
```

| Thuộc tính | Giá trị |
| --- | --- |
| Container | `vampi-week1` |
| Image | `vampi-week1:local` |
| API base URL | `http://127.0.0.1:5000` |
| Swagger UI | `http://127.0.0.1:5000/ui/` |
| Vulnerable mode | `vulnerable=1` |
| Token lifetime | `3600` giây |
| Network exposure | Chỉ loopback (`127.0.0.1`) |

> **Lưu ý tương thích:** Phiên bản VAmPI hiện dùng biến môi trường `vulnerable` viết thường. Endpoint gốc đã trả về `"vulnerable": 1`, xác nhận lab chạy ở chế độ có lỗ hổng.

### 3.3. Khởi tạo cơ sở dữ liệu

Database của lab được khởi tạo bằng endpoint local:

```bash
curl http://127.0.0.1:5000/createdb
```

Kết quả nhận được:

```json
{ "message": "Database populated." }
```

## 4. Kiểm tra hoạt động của lab

Các kiểm tra sau đã thành công:

| Kiểm tra | Kết quả |
| --- | --- |
| Container đang chạy | Pass |
| Port `127.0.0.1:5000` đang lắng nghe | Pass |
| `GET /` trả HTTP 200 | Pass |
| `GET /createdb` khởi tạo database | Pass |
| Swagger UI `/ui/` trả HTTP 200 | Pass |
| API xác nhận `vulnerable: 1` | Pass |

Response từ endpoint gốc xác nhận trạng thái API:

```json
{
  "message": "VAmPI the Vulnerable API",
  "vulnerable": 1
}
```

## 5. OpenAPI specification và mục tiêu ban đầu

OpenAPI specification được lấy trực tiếp từ lab đang chạy:

```bash
curl http://127.0.0.1:5000/openapi.json -o vampi_spec.json
```

File tạo ra:

```text
vampi_spec.json
```

Các endpoint đáng chú ý cho giai đoạn kiểm thử authorization sau này gồm:

| Method | Endpoint | Nhận định ban đầu |
| --- | --- | --- |
| `GET` | `/users/v1/{username}` | Có path parameter username; cần review đối tượng/user profile |
| `PUT` | `/users/v1/{username}/email` | Có path parameter; candidate cho kiểm thử object-level authorization |
| `PUT` | `/users/v1/{username}/password` | Có path parameter; candidate BOLA có thay đổi state |
| `DELETE` | `/users/v1/{username}` | Operation đặc quyền, chỉ admin theo mô tả API; candidate BFLA |
| `GET` | `/books/v1/{book_title}` | Truy xuất book và secret; candidate BOLA trọng tâm |
| `POST` | `/books/v1` | Tạo fixture book cho user hiện tại |

Danh sách trên chỉ là inventory ban đầu từ OpenAPI. Kết luận lỗ hổng chỉ được đưa ra ở Tuần 2 sau khi so sánh positive control (owner access) với cross-user/role access trong lab.

## 6. Tạo vai trò và token xác thực

Ba role được chuẩn bị để tạo ma trận authorization:

| Role | Username | Trạng thái xác minh |
| --- | --- | --- |
| Administrator | `admin` | Token hợp lệ, trường `admin=True` |
| Người dùng A | `userA` | Token hợp lệ, trường `admin=False` |
| Người dùng B | `userB` | Token hợp lệ, trường `admin=False` |

Token được lấy qua `POST /users/v1/login` và kiểm tra riêng bằng `GET /me`.

Thông tin token được lưu trong:

```text
roles_config.json
```

Định dạng được chuẩn hóa cho Tuần 2:

```json
{
  "admin": {"token": "Bearer <redacted>", "username": "admin"},
  "userA": {"token": "Bearer <redacted>", "username": "userA"},
  "userB": {"token": "Bearer <redacted>", "username": "userB"}
}
```

File thực tế không được đưa vào báo cáo hoặc version control; nó có permission `0600` và `.gitignore` loại trừ file này.

## 7. Ánh xạ resource ownership

Mỗi user đã tạo một book fixture riêng thông qua `POST /books/v1`, sử dụng token tương ứng. Sau đó owner của từng fixture được xác minh bằng request đọc với token của chính owner.

Bảng ownership được lưu tại `ownership.csv`:

| Resource type | Resource ID / title | Owner role | Owner username | Path template |
| --- | --- | --- | --- | --- |
| book | `week1-userA-book` | `userA` | `userA` | `/books/v1/{book_title}` |
| book | `week1-userB-book` | `userB` | `userB` | `/books/v1/{book_title}` |
| user profile | `userA` | `userA` | `userA` | `/users/v1/{username}` |
| user profile | `userB` | `userB` | `userB` | `/users/v1/{username}` |

Positive control đã được xác minh:

| Actor | Resource | Kết quả |
| --- | --- | --- |
| `userA` | `week1-userA-book` | Đọc thành công, owner trả về là `userA` |
| `userB` | `week1-userB-book` | Đọc thành công, owner trả về là `userB` |

Các fixture này là input được kiểm soát cho cross-user test ở Tuần 2. Không cần và không được dò/quét ID hoặc username ngoài danh sách ownership.

## 8. Deliverables

| Deliverable | Trạng thái | Vị trí |
| --- | --- | --- |
| Lab VAmPI hoạt động tại localhost | Hoàn thành | Docker container `vampi-week1` |
| OpenAPI specification | Hoàn thành | `vampi_spec.json` |
| Role configuration | Hoàn thành | `roles_config.json` — local secret, `0600` |
| Resource-to-owner mapping | Hoàn thành | `ownership.csv` |
| Hướng dẫn vận hành và scope | Hoàn thành | `README.md` |
| Báo cáo Tuần 1 | Hoàn thành | `docs/week-1-report.md` |
| crAPI | Chưa thực hiện | Ngoài phạm vi Tuần 1; tùy chọn cho giai đoạn sau |

## 9. Hướng dẫn vận hành lab

```bash
# Kiểm tra trạng thái container
docker ps --filter name=^/vampi-week1$

# Xem log gần nhất
docker logs --tail 50 vampi-week1

# Dừng lab nhưng giữ image và artifact
docker stop vampi-week1

# Chạy lại lab đã dừng
docker start vampi-week1
```

Sau khi restart container, chỉ tiếp tục dùng token khi chúng còn hiệu lực. Nếu token hết hạn hoặc database bị reset, cần tạo mới account/fixture và cập nhật đồng bộ `roles_config.json` cùng `ownership.csv`.

## 10. Kế hoạch Tuần 2

Tuần 2 sẽ sử dụng ba input đã chuẩn bị:

1. `vampi_spec.json` để lập endpoint inventory và nhận diện candidate BOLA/BFLA.
2. `roles_config.json` để gán authorization context cho mỗi test case.
3. `ownership.csv` để chỉ dùng known fixtures trong positive-control và cross-user test.

Runner của Tuần 2 phải giới hạn target ở `http://127.0.0.1:5000`, không ghi token ra kết quả, không enumeration identifier và mặc định tránh các request thay đổi state.
