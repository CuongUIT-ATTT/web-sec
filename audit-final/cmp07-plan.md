# CMP07-PLAN-01 — kế hoạch offline, revision 1

2026-11-16 UTC+07. Owner T18 ZAP Comparison. HEAD đã xác minh `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`; giữ toàn bộ diff trước lượt này. Chỉ tạo `audit-final/cmp07-plan*`. Không request, runtime, login, ZAP, mutation, tests runtime hoặc đọc credentials. Không có AGENTS.md trong danh sách repo đã khảo sát; bàn giao QA cũng ghi không có ở ancestors.

**Chuẩn bị đã hoàn thành; thực nghiệm NOT_RUN; tổng thể PARTIAL.** Manifest là proposal đóng băng, không phải approved execution manifest. Policy/truth cần review; thay đổi semantic phải tạo revision/cohort mới.

## Artifacts và identity

- `cmp07-plan-manifest.json`: HEAD, SHA-256 của 12 nguồn, fixture bundle, per-resource fixture bindings, role/alias registry, policy draft và trạng thái.
- `cmp07-plan-cohort.json`: canonical contract roundtrip thành công; **13 cases**, revision `sha256:0120305688bcb028091ff4274fad0b38e58a17ba9289fa8139977218dff802bc`.
- `cmp07-plan-truth.csv`: **15 ô** 3 roles × 5 paths; 13 canonical candidates, 2 ô admin/book policy-dependent chưa cấp canonical ID. Không ép policy-dependent thành ALLOW/DENY.
- `cmp07-plan-5roles.csv`: **25 ô** riêng cho userA/userB/admin/userC/admin2. Hai role bổ sung chưa có policy trong allowlist-v2; chưa là cohort execution 5 roles.

Fixture hash là digest metadata bundle của ownership/OpenAPI/manual fixtures đóng gói, không phải runtime snapshot. Mỗi fixture slot có digest ràng buộc bundle + slot trong manifest. Public profiles dùng actor alias theo scenario để canonical contract không gộp hai public resources cùng template/null owner; role vẫn map cùng planned principal. Reviewer phải duyệt mapping này hoặc yêu cầu upstream hỗ trợ fixture discriminator và tạo revision mới. Alias opaque chỉ là planning registry, không xác minh danh tính.

## Truth và selections

Nguồn policy draft: `tools/authorization-lab/src/authz_lab/fixtures/zap/allowlist-v2.json`; ownership và OpenAPI có hash trong manifest. Owner book ALLOW, cross-user DENY; admin book chưa quyết định. Public profile ALLOW theo policy nguồn; `/me` là identity control, không tự coi là negative BOLA. Expected policy decision khác nhãn vulnerability truth: **mọi truth_label UNKNOWN, PENDING_REVIEW**, reviewer/source observation trống. Không suy vulnerable từ mong muốn DENY hoặc finding lịch sử.

BOLA Evaluator + QA cần review độc lập: owner baseline hợp lệ, protected-field comparison đã sanitized, actor/owner mapping, policy admin và sharing. Không có sharing fixture/policy được xác minh: loại sharing khỏi revision này với lý do MISSING_SHARING_POLICY_FIXTURE, không suy public là shared-private.

Manual/T18/ZAP cùng 13 cases planned; cả 15 ô vẫn ghi nguồn/exclusions. Anonymous và invalid-token (M-04/M-05) là controls riêng, không nằm trong exact enabled role set hoặc cohort 13. M-07 map `/me` userA chỉ sau review; M-01/M-02/M-03 cần mapping explicit theo owner/actor/fixture. Không tự join M-ID, kết quả lịch sử hoặc Run #2. Anonymous public M-06 là observation ngoài cohort. 5-role phải có allowlist policy/context/attestation mới được review; không tái sử dụng 3-role approval.

## Allowlist và commands

Đề xuất target **exact `http://127.0.0.1:5000`**, ZAP listener `http://127.0.0.1:8080`; chưa xác minh listener hiện tại. Chỉ GET, không query/fragment, đúng 5 paths trong allowlist-v2: `/books/v1/week1-userA-book`, `/books/v1/week1-userB-book`, `/users/v1/userA`, `/users/v1/userB`, `/me`. Regex từng absolute URL phải anchor `^`/`$`, escape dots; ví dụ `^http://127\.0\.0\.1:5000/me$`. Không wildcard, redirect sang origin/path khác, enumeration, spider, active scan, fuzzing, full OpenAPI import hoặc writes.

Command offline cho người nhận (chưa chạy trong lượt này):

```sh
PYTHONPATH=tools/authorization-lab/src .venv/bin/python -m authz_lab.cli check-zap-allowlist --manifest tools/authorization-lab/src/authz_lab/fixtures/zap/allowlist-v2.json
```

Lưu ý module CLI có thể cần entrypoint package; câu lệnh tương đương được xác minh từ source là gọi `authz_lab.cli.main([...])` bằng Python. Chỉ nhánh check-zap-allowlist không network. Không dùng check-inputs để đọc role credentials trong bước docs này.

Manual sau approval: operator thực hiện đúng từng GET của worksheet, đối chiếu owner baseline cùng execution; không phát lệnh curl chứa token vào transcript. T18 có `run`, `verify`, `verify-workflow` trong `cli.py`, nhưng pipeline này không nhận cohort/case allowlist hoặc transport budget qua CLI: **chưa cấp command runtime**, tránh chạy rộng hơn cohort. Lead giao adapter bounded trước, cần dry-plan exact cases/requests rồi review. Verifier tự động không phải manual human measurement.

ZAP entrypoint thật là `authz_lab.zap.runner.run_zap_access_control(...)`, không có ZAP CLI runtime được phép trong ticket. Future invocation phải pin allowlist/context/attestation/output mới và timeout, qua operator được giao sau gates. Không cung cấp command có thể vô tình kích hoạt scan khi các input chưa chốt.

Budget proposal cần review: manual/T18 mỗi method tối đa 30 target GET (15 cells + tối đa 15 fresh controls/baselines), concurrency 1, retry 0; không tự tăng cap. ZAP seed đúng 5 requests; scan budget **chưa được duyệt/thi hành ở transport**, do add-on fan-out chưa được đo. Source `MAX_MESSAGES=1000` chỉ là history count guard, không phải hard request cap; timeout 120s không thay thế budget. Muốn chạy phải có enforced cap gồm auth/bootstrap/seed/scan/polls được tách kế toán hoặc containment được reviewer chấp nhận; không tự chọn cap giả.

## Timing, receipts và acceptance

Execution IDs mới tách theo method/cohort/revision; không reuse historical output. Manual human: ghi operator alias, start/end và monotonic elapsed cùng phạm vi; setup/auth ghi riêng. Chưa đo: PENDING_HUMAN_MEASUREMENT; hoàn tất thiếu timing: COMPLETED_NO_TIMING. T18/ZAP thiếu elapsed: TIMING_NOT_AVAILABLE; không ghi 0. Cùng cohort, same fixture snapshot; thứ tự dự kiến manual → T18 → ZAP, record cache/order effects, không tuyên bố speedup từ một lần chạy.

Mỗi case × method cần execution status, conclusion, baseline validity, timing status, sanitized artifact ref/hash và bounded schema2 receipt bytes có exact execution/cohort/source binding. Không xuất raw body/token/header hoặc ZAP HTML. Hash/binding không phải source attestation. Import/API/store chỉ sau ticket giao output/project scope; QA độc lập roundtrip trước xuất comparison.csv/md/evidence index.

TP/FP/FN/TN chỉ sau reviewed independent truth, valid same-cohort executed observation và prediction quyết định. POLICY_DEPENDENT, controls không hỗ trợ scoring, UNKNOWN, NOT_RUN, invalid baseline, unlinked history đều công bố exclusions; denominator hiện tại **0 eligible**, metrics null, không có TN/FN được suy từ chưa chạy. ZAP ILLEGAL không tự map CONFIRMED BOLA.

## Quyền hiện có và điều kiện còn thiếu

Nguồn: bàn giao pagination QA, E2E authorized-lab, approval/attestation QA, receipt contract (đã pin hash). Assignment hiện tại chỉ cho tạo plan docs; không cấp request/lab/login/mutation. E2E lịch sử chỉ nêu `100.106.64.21:5003`, hai identities role user và connection refusal ngày 13; **khác target loopback:5000 của runner**, không chứng minh quyền hay reachability hôm nay. Không tự đổi target, recover listener hoặc seed roles.

Tồn tại `zap/imported-context-attestation.json` mode 0600 qua stat thư mục; không đọc secret context, không kiểm hash-binding của file thực, không coi tên file, timestamps hay metadata reviewer là approval hiện tại. Example attestation trong fixtures chỉ là example. Còn thiếu:

1. Lead/operator artifact xác nhận target/operations/exact roles, thời hạn, budgets, mới run/output IDs; giữ runtime/Run #2.
2. Runtime fixture snapshot/OpenAPI equivalence và >=3 verified principals, owner baseline; policy/truth/alias review ký độc lập. Nếu seed/credential thay đổi cần ticket quyền riêng.
3. Reviewed actual context 0600 + fingerprint attestation và exact 3 hoặc 5 enabled users; exact regex/rules, verified auth, history stable hai lần cách 1s tối đa 10s, actual paginated history containment. Gates này chưa chạy.
4. Bounded T18 transport adapter và ZAP request accounting/cap được review; không suy guard history là preemptive limit.
5. BFLA chạy nhánh riêng disposable: approval pin run/digest/stage/scope/expiry cho từng prepare/execute/extended/teardown; cap9/cap22 theo contract. Không trộn vào GET cohort. DB proof UNKNOWN cho tới contract + authorized sanitized before/after collection; không suy unchanged từ labels/cleanup.
6. Browser E2E vẫn BLOCKED theo bàn giao; không tự login lại hoặc gọi mock/UI test là E2E.

## Bước tiếp giao Lead

Giao BOLA Evaluator + QA review worksheet/policy/alias mapping ngay; song song giao owner T18 adapter bounded và operator lập scope/target/budget artifact, **chưa start/recover lab**. Sau các gate này, Lead giao CMP07-RUN-01 read-only execution mới; ZAP chỉ chạy theo approval riêng và protections đầy đủ. Nếu chưa đủ, report từng gate BLOCKED/NOT_RUN, không đóng nghiệm thu.

Kiểm tra offline: canonical serialization roundtrip PASS; 13 unique cases, 15 truth rows, 25 matrix rows; 12 source hashes trước/sau khớp. Lần build đầu gặp duplicate public-template scenario, dừng trước khi ghi file; đã tách mapping theo scenario và ghi rõ cần review, không che sửa schema. Không chạy suites vì chỉ tạo tài liệu kế hoạch. Bot không có automation tại kiểm tra 2026-11-15T17:01:36Z.
