# QA độc lập — LAB-RECOVER-01 / E2E run #2

Verdict: **PASS cho đối chiếu persisted metadata; PARTIAL cho nghiệm thu tổng thể**.

QA thực hiện ngày 2026-11-13, khoảng 21:47–21:49 UTC+07:00 (Asia/Ho_Chi_Minh). Quan sát Browser thuộc Lead; QA không quan sát lại Browser, không queue run, không gọi lab, không thay đổi runtime hoặc production code. Chỉ báo cáo này được tạo. Không đọc/in token, response body hoặc marker.

## Inventory và nguồn

- Git HEAD: `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`; working tree có thay đổi sẵn ở backend/frontend/tests và các artifact chưa track. Giữ nguyên.
- Công cụ: host Python 3.14.8, Git 2.56.0; container Python 3.11.18; SQLite qua Python, kết nối URI `mode=ro`.
- Container: `deploy-authz-web-1`; image digest `sha256:ecabf68c551ec31c29df6cee7f22db9d164753ead1eb1e61d7e83147d3b47f5d`.
- AUTHZ_DATABASE_PATH: `/var/lib/authz/authz-web.sqlite3`. Chỉ SELECT metadata cho run/case/policy/finding/resource/identity và schema; không truy vấn bảng secrets.
- Báo cáo Lead: `audit-final/web-demo-e2e-recovered-s01.md`, SHA-256 `59553be792db0823443b139d03ec6768ba2748bfcbe6cc952cd925553fa7ea29`.
- Fixture persisted: resource #1 `book-B1`, path parameter `book_id`, owner identity #2 `userB`; actor #1 `userA`. Cả hai role `user`.
- SQLite container 3.46.1. Fixture repository SHA-256: `tools/authorization-lab/src/authz_lab/fixtures/vampi_spec.json` = `dfff32264cc1eaf1714a18fe063399664d726d70b437866904e4d8f2f075810b`; `ownership.csv` cùng thư mục = `a799ce97a89a89acb03b543b9a33def3f869c4bb3835e6810c197e14ab41c72f`.
- Digest lab từ xa và hash OpenAPI thực tế của run chưa xác minh độc lập; không đọc snapshot rộng vì có thể chứa bí mật. Hash fixture repository, nếu có, không chứng minh input runtime.

## Kết quả đối chiếu

`runs.id=2`: `COMPLETED`, created_at `2026-11-13 14:46:12`, updated_at `2026-11-13 14:46:13`. DB trả timestamp không có offset; không tự khẳng định timezone của trường này. Lead ghi thời điểm Browser khoảng 21:46 giờ Việt Nam.

`run_execution_stats.run_id=2`: planned_attempts=5, transport_attempts=5, completed_responses=5, scope_blocked=0, transport_errors=0, cancelled_cases=0. **PASS**: counters persisted khớp Lead. Đây là đối chiếu counters, không phải packet capture hay tái thực thi HTTP.

| run_result_id | case_key | execution / HTTP | conclusion | reason |
|---|---|---|---|---|
| 3 | operation:1:resource:1:actor:1 | COMPLETED_RESPONSE / 200 | CONFIRMED_VIOLATION | evidence.restricted_fields_match_owner |
| 4 | operation:1:resource:1:actor:2 | COMPLETED_RESPONSE / 200 | POLICY_CONSISTENT_CASE | policy.allow_observed |

Metadata evidence cả hai case: run_id=2, resource_id=1, owner_identity_id=2; owner_control_valid=true, owner_execution_status=COMPLETED_RESPONSE, owner_http_status=200, owner_body_truncated=false, owner_json_parse_error=false. owner_principal_matches, actor_principal_matches, owner_resource_matches, actor_resource_matches, owner_restricted_evidence_valid và restricted_fields_match_owner đều true.

Case #3: actor_identity_id=1; policy_id=2, version=1, decision=DENY, resolution=RESOLVED. Bảng policies xác nhận #2 v1 áp dụng operation #1, identity #1, decision DENY. **PASS**: violation có owner baseline valid và explicit deny persisted, không suy từ HTTP 200 đơn thuần.

Case #4: actor_identity_id=2 là owner; metadata policy #1 v1 ALLOW / RESOLVED; bảng policies cũng xác nhận #1 v1 ALLOW. **PASS**: owner case consistent theo metadata.

Join `finding_reproductions → findings → run_results`: finding #1 CONFIRMED_VIOLATION, GET `/books/{book_id}`, policy #2 v1; reproduction #1 → run_result #3 → run #2 / actor #1 / resource #1 / đúng case_key vi phạm. Có đúng một reproduction liên kết run #2 trong kết quả truy vấn. **PASS**, không phát hiện sai lệch với báo cáo Lead.

## Giới hạn nghiệm thu

- QA xác nhận metadata đã lưu; không tái xác minh nội dung response, freshness qua trace HTTP, trạng thái lab từ xa, hoặc Browser rendering.
- Unit/regression: NOT_RUN trong lượt audit này. Live runtime và Browser E2E: Lead thực hiện, QA đối chiếu persisted evidence. Không ghi nhận suite PASS khi chưa chạy.
- Mới có hai identity, một role; chưa đạt 3/5-role gate. R5 manual/ZAP comparison NOT_RUN. Cancel/duplicate-click E2E và BFLA chưa xác minh.
- Không mở rộng kết luận thành full acceptance. Không có automation của QA liên quan; danh sách kiểm tra trả về rỗng.
