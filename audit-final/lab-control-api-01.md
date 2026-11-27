# LAB-CONTROL-API-01 — Đặc tả đề xuất

Ngày: 2026-11-17. Trạng thái: SPECIFICATION ONLY; triển khai, deploy, SSH và acceptance runtime: NOT_RUN.

## Căn cứ audit

HEAD local `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`; working tree có nhiều thay đổi có sẵn, không dùng làm baseline sạch. Đã đọc README.md, tools/authorization-lab/README.md, ../VAmPI/docs/bola-lab.md, public OpenAPI và hướng dẫn operator được cung cấp trong ticket. Không tìm thấy AGENTS.md trong cây project và các thư mục cha đã kiểm tra. Chỉ tạo tài liệu này; không đọc private state/token, không truy cập SSH, cổng 8000 hay lab runtime. Automation của bot: không có.

Bootstrap hiện tại dùng target 100.106.64.21:5003 và nhận token qua prompt terminal; chưa có bằng chứng management API đã tồn tại. Health ready không chứng minh token hợp lệ. 401 có thể do thiếu/sai/hết hạn token; không suy luận option startup sai.

## Kiến trúc

Machine B vận hành management service và Management Console riêng, cùng origin HTTPS, tách process, identity và cổng khỏi public lab. Bind loopback qua proxy Tailscale được kiểm soát hoặc IP Tailscale cụ thể; cổng quản trị do operator cấu hình khi deploy, không mặc định mở LAN. ACL chỉ nhóm operator; TLS và xác thực ứng dụng vẫn bắt buộc. Không bind wildcard hay tin forwarding header từ client.

Public lab giữ nguyên GET /health, /me, /books/{book_id}; không thêm login/reset/token API. Web Control Room hiện tại chỉ gửi GET đến target, không import/call CLI và không nhận lifecycle writes mới. Người dùng mở Management Console riêng để thao tác; tích hợp credential backend riêng chỉ được triển khai sau review, không giả định đã có.

Management worker gọi adapter nội bộ có kiểu dữ liệu cố định/controller library hoặc supervisor với unit cố định. Không nhận command, argv, shell, path state, tên unit, target URL, callback URL hay Docker socket từ request. Một state root được pin bởi operator; sandbox UID riêng, filesystem 0700/0600. Không trả answer-sheet, marker, SQLite, file private hoặc nội dung controller stdout.

## Quyền và contract endpoint

Prefix `/management/v1`; mọi endpoint yêu cầu management identity, hoàn toàn không chấp nhận bearer token test. Reader chỉ xem; operator thực hiện lifecycle; credential-broker riêng giao token. Browser dùng cookie HttpOnly/Secure/SameSite=Strict, CSRF và kiểm Origin cho writes. M2M dùng mTLS identity giới hạn audience. Rate limit và audit redacted áp dụng cả lỗi xác thực.

| Method/path | Quyền | Nội dung |
|---|---|---|
| GET /status | reader | lifecycle, initialized, state_version, health, token_expires_at, credential_generation, evaluation lease summary; không run ID private |
| GET /scenarios | reader | enum S01–S12 và mô tả công khai; không answer/policy bí mật |
| POST /init | operator | scenario, token_ttl_seconds; chỉ state chưa có |
| POST /validate | operator | kiểm tra read-only dưới lock; trả valid + mã lỗi đã sanitize |
| POST /start | operator | chỉ state validated, token chưa hết hạn; start unit cố định |
| POST /stop | operator | graceful stop; evaluation đang hoạt động thì từ chối |
| POST /reset | operator | scenario, token_ttl_seconds, confirm_invalidate_tokens=true; chỉ STOPPED |
| GET /operations/{operation_id} | reader | pending/running/succeeded/failed/interrupted, safe error code |
| POST /credential-handoffs | credential-broker | tool_id được đăng ký, generation, principal enum; giao server-to-server, trả receipt không token |
| POST /evaluation-leases | evaluator | generation, thời hạn lease hữu hạn; chỉ RUNNING |
| POST /evaluation-leases/{lease_id}/renew | evaluator | gia hạn hữu hạn, cùng identity |
| DELETE /evaluation-leases/{lease_id} | evaluator | kết thúc lease của chính evaluator |

Init/reset TTL đề xuất mặc định 3600 giây, min 300 max 86400; đây là giới hạn đề xuất, phải đối chiếu controller khi triển khai. Không có token TTL vô hạn. TTL tính từ phát hành, không từ start. Reset thay toàn bộ token/marker, tăng generation, thu hồi handoff cũ; không tự reset khi hết hạn. Management identity không hết hạn theo token test.

## Lifecycle, concurrency và lỗi

UNINITIALIZED → init → STOPPED → validate → STOPPED(validated) → start → RUNNING → stop → STOPPED. Reset chỉ STOPPED, không lease active, không operation active. Validation mất hiệu lực sau thay state. FAILED/INTERRUPTED cần reconcile thực trạng trước writes; không tự retry reset sau crash. Start/stop phải xác minh process identity và health, không chỉ PID hay exit code launcher.

Mọi mutation trả 202 + Location operation; GET operation trả 200. Worker tuần tự theo state root, lock liên process và journal bền vững; check điều kiện và ghi generation cùng critical section. Init/reset cần atomic staging/swap và recovery journal; failure không được quảng cáo state hợp lệ. Không dùng shell lock trong RAM làm khóa duy nhất.

Yêu cầu Idempotency-Key + If-Match state_version cho mutation. Cùng identity/key/body trả operation cũ, key khác body trả 409; key lưu tối thiểu 24 giờ và không chứa secret. Replay key được resolve trước kiểm version. Missing precondition 428, stale version 412; unknown field/schema 422, malformed 400, unauthenticated 401, forbidden 403, state exists/running/evaluation busy 409, rate limit 429, supervisor unavailable 503. Error envelope: code, message an toàn, request_id; không stack/path/secret. Operation ID là mã public opaque độc lập private run ID.

Lease là interlock bắt buộc: tất cả evaluator được cấp token phải acquire/renew lease; lease hết hạn chuyển UNKNOWN/BLOCKED, không mặc nhiên cho reset cho đến xác nhận worker đã dừng. Client ngoài luồng/manual không có lease không thể được phát hiện chắc chắn: khi chưa kiểm soát hết token consumer, reset phải bị chặn hoặc operator xác nhận đã quiesce theo quy trình riêng. Không tuyên bố lease đơn thuần chứng minh không có evaluation.

## Luồng Web không terminal

1. Đăng nhập Management Console bằng management identity; xem health, expiry và generation.
2. State mới: chọn S01 và TTL → init → validate → start; giao diện theo dõi operation và chỉ bật bước tiếp khi succeeded.
3. Chọn tool đã đăng ký → handoff token qua mTLS tới credential receiver; receiver mã hóa lưu và xác minh /me cho từng principal, chỉ trả identity/expiry/generation. Không token trong DOM, URL, clipboard, browser storage, logs hoặc chat. Receiver chưa tồn tại thì tính năng BLOCKED, không fallback hiển thị token.
4. Tool pin base URL, public spec, generation, policy/pointers được phép và owner fixtures: admin/userA/userB, book-A1/A2 của A, book-B1/B2 của B. Policy admin mặc định UNKNOWN ngoài S11 control; không lấy policy từ response hay answer sheet.
5. Tool acquire lease, chạy GET evaluation rồi release. Đổi scenario: kết thúc evaluation → stop → explicit reset (UI thông báo token cũ vô hiệu) → validate → start → handoff mới. Không tự queue run hay retry token cũ sau 401.

## OpenAPI phác thảo

OpenAPI 3.1; bảng endpoint ở trên là contract đầy đủ về scope, đoạn YAML sau minh họa reset. Khi triển khai cần xuất spec máy đọc đầy đủ cho mọi endpoint, enum và schema lỗi; đoạn này chưa phải spec đầy đủ để generate client.

```yaml
openapi: 3.1.0
info: {title: Controlled BOLA Management, version: 0.1.0-proposal}
paths:
  /management/v1/reset:
    post:
      security: [{managementSession: [], csrf: []}, {managementMTLS: []}]
      parameters:
        - {in: header, name: Idempotency-Key, required: true, schema: {type: string, minLength: 16, maxLength: 128}}
        - {in: header, name: If-Match, required: true, schema: {type: string}}
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              additionalProperties: false
              required: [scenario, token_ttl_seconds, confirm_invalidate_tokens]
              properties:
                scenario: {type: string, enum: [S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11, S12]}
                token_ttl_seconds: {type: integer, minimum: 300, maximum: 86400, default: 3600}
                confirm_invalidate_tokens: {const: true}
      responses:
        '202': {description: Accepted; operation_id and Location; no secrets}
        '401': {description: Management authentication required}
        '403': {description: Role or CSRF rejected}
        '409': {description: Running or busy or idempotency conflict}
        '412': {description: Stale state version}
        '422': {description: Invalid request}
        '428': {description: Precondition required}
components:
  securitySchemes:
    managementSession: {type: apiKey, in: cookie, name: management_session}
    csrf: {type: apiKey, in: header, name: X-CSRF-Token}
    managementMTLS: {type: mutualTLS}
```

## Migration và nghiệm thu

Deploy riêng sau phê duyệt; inventory supervisor/state path tại Machine B do operator thực hiện. Không tự import private state sang Machine A. Adopt state hiện có read-only trước; không init/reset khi deploy. Pin binary/version, backup operator-local được bảo vệ, reconcile running process; rollback service quản trị không rollback token generation hay khôi phục token cũ. Receiver và lease enforcement phải sẵn sàng trước khi cho phép reset qua console. Giữ public API/spec không đổi; không sửa web runtime để gọi CLI.

| Case ID | Kiểm tra chấp nhận | Hiện trạng |
|---|---|---|
| LCA-01 | Test token không vào management; reader không write; CSRF/origin/ACL negative | NOT_RUN |
| LCA-02 | Init lần hai 409; không thay state/generation | NOT_RUN |
| LCA-03 | Reset khi RUNNING/lease active/unknown bị chặn; race start/reset chỉ một thắng | NOT_RUN |
| LCA-04 | Idempotent replay không phát token lần hai; stale version 412 | NOT_RUN |
| LCA-05 | Crash tại staging/swap/supervisor restart reconcile an toàn | NOT_RUN |
| LCA-06 | S01–S12 validate/start; owner fixtures giữ đúng; không lộ đáp án | NOT_RUN |
| LCA-07 | TTL boundary; token cũ 401 sau reset, token mới /me đúng; không raw token evidence | NOT_RUN |
| LCA-08 | Handoff sai tool/audience/generation từ chối; receipt không secret | NOT_RUN |
| LCA-09 | URL/log/error/export/browser không secret, marker, private run ID/path | NOT_RUN |
| LCA-10 | Public chỉ ba GET; Web không CLI/import/lifecycle writes; /createdb bị chặn | NOT_RUN |
| LCA-11 | Console init→start→handoff→lease→stop→reset không terminal; expiry hiển thị rõ | NOT_RUN |
| LCA-12 | Client ngoài ACL bị chặn; spoof forwarding header không vượt ACL | NOT_RUN |

Evidence QA cần operation_id, case_id, generation public, role management, fixture public, expected/actual và hash artifact đã redacted; không dùng answer sheet trên Machine A. Spec không chứng minh lab hoạt động hay tìm thấy BOLA.

Quyết định trước triển khai: chốt management identity provider/cổng và ACL; credential receiver identity/secret storage; supervisor/atomic state recovery; cơ chế quiescence với manual clients. Mặc định đề xuất console riêng + mTLS broker + fail-closed lease; không có quyết định nào đòi reset state hiện tại ở giai đoạn này.
