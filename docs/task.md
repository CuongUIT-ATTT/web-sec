# Phân công hoàn thiện lab VAmPI / ZAP

## Chuẩn bị chung

- [ ] Đọc **OWASP API Top 10**, mục **BOLA (API1)** và **BFLA (API5)**; đọc **Phần 1** của `docs/final-report-draft.md`.
- [ ] Tự dựng lại VAmPI bằng Docker theo `docs/week-1-report.md`:
  1. Tạo 2 user mới.
  2. Mỗi user tạo 1 book fixture.
  3. Dùng token của user 1 gọi book của user 2 để trực tiếp xác nhận field `secret` bị lộ.
  4. Chụp màn hình gửi nhóm làm bằng chứng.
- [ ] Đọc 4 module trong `week2/`, chạy thử `week2/main.py`, rồi đọc lần lượt báo cáo **Tuần 1 → Tuần 4 → final draft** theo đúng thứ tự.
- [ ] Họp nhanh 15–20 phút: mỗi người trình bày miệng phần mình hiểu (không đọc slide) để kiểm tra trước khi giao việc chính thức.

---

## Thành viên 1 — An toàn & tái lập

- [ ] Rotate lại ZAP API key (**Tools → Options → API → Generate**); chỉ export vào shell, không gửi vào chat.
- [ ] Đổi mật khẩu hoặc tạo lại 3 user VAmPI (coi mật khẩu cũ đã lộ), sau đó cập nhật để các nguồn sau khớp nhau:
  - `roles_config.json`
  - `ownership.csv`
  - 3 user trong ZAP context
- [ ] Chạy lại toàn bộ test suite và xác nhận vẫn có **128 test pass**:

  ```bash
  .venv/bin/python -I -m unittest discover -s tests -v
  ```

- [ ] Chạy 4 lệnh CLI đã đóng gói (`check-inputs`, `run`, `verify`, `week3`), so sánh với kết quả script gốc và xác nhận không có sai lệch.
- [ ] Quét repo để tìm token/mật khẩu cũ còn sót; xác nhận `.gitignore` đủ chặt.

---

## Thành viên 2 — Đo lường thủ công & bảng so sánh

- [ ] Dùng Postman hoặc `curl` để đo lại đúng 7 case trong `week3/manual_sample_cases.json`; bấm giờ nhất quán cho mỗi case (từ lúc **Send** đến khi đọc xong response).
- [ ] Điền đầy đủ `results/week3_manual_worksheet.md`, gồm:
  - Status
  - Thời gian
  - Quan sát

  > Không ghi token, mật khẩu hoặc response chứa `secret` vào bảng.

- [ ] Cập nhật `week4_comparison_final.json` để không còn giá trị `PENDING`; xác nhận 2 case **M-02** và **M-03** vẫn cho thấy rò rỉ `secret` cross-user.
- [ ] Viết một đoạn ngắn khoảng **250 từ** so sánh thời gian giữa 3 phương pháp, gửi để chèn vào báo cáo.

---

## Thành viên 3 — Điều tra ZAP & hướng mở rộng

- [ ] Đọc lại lịch sử debug ZAP (9 gate đã vượt qua, 2 lỗi response-contract đã sửa) để hiểu bối cảnh trước khi vào GUI.
- [ ] Vào ZAP GUI và kiểm tra lại **Access Rules** của context `vampi-safe-authz`:
  - Rule cho owner tự đọc book.
  - Rule cho mỗi user tự xem `/me`.

  Xác nhận hai rule không bị đặt nhầm thành **Deny**, vì đây là nguyên nhân khả nghi khiến kết quả scan bị lệch actor.

- [ ] Đọc kỹ 3 bài tham khảo sau và viết 3 đoạn ngắn cho phần **“Hướng tiếp theo”** của báo cáo:
  - Barabanov & Dergunov (2022)
  - Le et al. (2022)
  - Zhang et al. (2024)
- [ ] Chuẩn bị phần kể lại ngắn gọn (2–3 phút) về hành trình debug ZAP để trình bày khi demo.
