# Phase 1 — Audit disposable BFLA và thiết kế workflow riêng

Ngày: 2026-11-15. HEAD kiểm tra: `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`.
Phạm vi: chỉ đọc source và sanitized artifact; không sửa production/tests, không chạy test, Docker, HTTP/lab, queue, browser, deploy, ZAP hoặc BFLA. Chỉ tạo báo cáo này. Working tree đã có thay đổi backend/frontend/tests/audit-final từ trước, giữ nguyên. Không truy cập file secret, DB hay response body. Run #2 và snapshot không bị tác động.

## Kết luận và phân loại

Nguồn tên requirement: `audit-final/requirements-traceability.md`; không tự định nghĩa lại R1–R8.

| Requirement/phạm vi | Phân loại implementation | Evidence và verdict nghiệm thu |
|---|---|---|
| R4 BFLA vertical | Partially implemented; CLI có, web chưa nối evidence | Artifact lịch sử DELETE là DENIED_CONTROL, không xác nhận lỗ hổng; demo web BFLA NOT_RUN, nghiệm thu NOT VERIFIED |
| R4 write-BOLA/mass assignment | Implemented but not visible on web, còn gap correctness/safety | Có code và test mock; không tìm thấy extended receipt trong results; execution NOT_RUN trong audit, runtime NOT VERIFIED |
| R6 reusable tool, phần disposable | Partially implemented | CLI độc lập, không mở GET runner; approval/lifecycle chưa thành state machine hoàn chỉnh; NOT VERIFIED runtime |
| R7 evidence, phần disposable | Partially implemented | Có manifest/execution/teardown cũ, thiếu preflight trong bộ run lịch sử và traceability mới; NOT VERIFIED end-to-end |
| R5/R8 comparison, phần BFLA | Missing integration | UI placeholder NOT_RUN; không có case-aligned comparison được xác minh ở đây |
| R1/R2/R3 phần web | Ngoài ownership audit này | Không kết luận thay bot phụ trách; không dùng disposable 2 role để nghiệm thu 3+ roles |

Experimental gate: chạy mới cần disposable localhost:5003, manifest đầy đủ, preflight, isolated project/volume, fixture và phê duyệt riêng cho execute/execute-extended. Hiện không được giao thực thi. Không coi approved S01 GET recovery là phê duyệt destructive BFLA.

## Source paths và capabilities có sẵn

Các đường dẫn dưới đây tương đối với `/home/cuong/Dự án/Bảo mật web/Project`.

- `tools/authorization-lab/src/authz_lab/disposable/manifest.py`: fixed origin `http://127.0.0.1:5003`, run ID, project `vampi-bfla-<run_id>`, direct-child run directory, exact DELETE targets, create-manifest từ chối overwrite. Manifest chỉ mô tả 2 DELETE; không mô tả đầy đủ extended PUT/register/admin-delete.
- `.../disposable/preflight.py`: port phải trống trước Compose, project không có container/volume cũ, private directory rỗng, shared container running và image ID; receipt gắn run/project; execute kiểm tra lại shared identity/state và image. Đây là implementation, chưa chạy xác minh hiện tại.
- `deploy/labs/vampi-bfla-disposable.compose.yaml`: loopback port, dedicated named volume, project labels, no restart, drop capabilities/no-new-privileges. Có cả internal network và host_access `internal: false`: không được tuyên bố egress bị cô lập hoàn toàn.
- `.../disposable/runner.py::_assert_disposable_runtime`: đúng 1 container/volume theo project, workflow label, image và loopback binding. Chưa xác minh volume inspect/mount thực tế chỉ từ số lượng volume.
- `.../disposable/runner.py::prepare`: tạo fixture run-scoped, reset DB riêng và lưu secret local mode hạn chế; đây là bước thay đổi trạng thái, không phải preflight read-only. Không đọc secret trong audit.
- `.../disposable/cli.py`: create-manifest → preflight → prepare → execute hoặc execute-extended → teardown; Compose up phải do operator riêng. Không có target/method/path override tổng quát. Không có approval receipt/expiry/hash/one-use gate được enforce trong CLI.
- `.../disposable/teardown.py`: project-scoped down --volumes, kiểm tra container/volume còn lại, xóa secret run directory riêng, receipt cleanup và shared before/after. Cleanup này chỉ dành dữ liệu disposable đã duyệt, không xóa persistent/shared data hay evidence lịch sử. Fallback thiếu preflight vẫn cho scoped teardown: không tương đương đủ chain-of-custody.
- `tools/authorization-lab/src/authz_lab/evaluation/bfla_evidence.py`: thực tế đọc receipt đã có, không tự chạy lifecycle dù docstring gọi orchestrator. Output path cố định có nguy cơ overwrite; validation receipt/run/project/teardown chưa đủ. Không thay code module này trong lượt audit.
- `backend/app/api/workflow_routes.py`: mapping/queue chỉ operation GET đã chọn. `backend/app/workers/runner.py`: từ chối snapshot method khác GET. `frontend/src/App.tsx`: external read-only lab panel nói rõ không BFLA/ZAP/Docker; comparison BFLA chỉ placeholder NOT_RUN. Không đề xuất thêm write capability vào những đường chạy này.

## Gap correctness và safeguards cụ thể

1. `runner.py::execute` dùng `protected_status == 200 or not protected_exists` để CONFIRMED. HTTP 200 với victim vẫn tồn tại cũng bị xác nhận. `_profile_exists` trả false cho mọi status khác 200, nên 401/403/5xx không phân biệt với absent 404. Không có pre-mutation existence/principal/role proof ở mỗi case. Đây là lỗi có thể false positive, cần sửa trước demo khai thác.
2. `execute_extended`: email kiểm tra victim/self change, password kiểm tra login mới, mass assignment kiểm tra admin flag + delete hậu điều kiện — tốt hơn status đơn lẻ. Nhưng email chưa bắt buộc GET baseline/status/principal hợp lệ; password chưa chứng minh login token thuộc đúng victim; absence vẫn dùng helper mơ hồ. Nếu chạy sau DELETE đã xóa victim sẽ mất precondition. Không thể coi test mock là exploit proof.
3. Extended không reject receipt đã tồn tại trước writes, có thể rerun/overwrite. `prepare` chỉ chặn bằng secret file sau khi setup thành công: crash giữa reset/setup và lưu secret có thể cho reset lại. Không có exclusive lock/atomic stage marker ngăn race/replay hoặc chạy chồng port 5003.
4. `_request` dùng urllib `urlopen` mặc định có thể follow redirects. Fixed initial origin không đủ bảo đảm no-redirect, không có redirect rejection test trong disposable tests đã đọc. Không thấy retry loop nhưng không được suy ra đã thực nghiệm no-retry. Request budget chưa là cap enforce độc lập.
5. Manifest chưa ràng buộc extended methods/paths, expected access/policy version, fixture/principal/role attestation, approved payload shape và number-of-attempts. Actor username lấy từ secret chưa validate exact run fixture trong extended. Low-level path allowlist rộng hơn exact manifest targets.
6. `evaluation/bfla_evidence.py::_build_findings` biến missing/falsy target_survived thành BFLA_CONFIRMED; không bảo toàn unknown. Aggregator chưa reject receipt mismatch hoặc incomplete cleanup, và raw disposable fixture username trong findings cần DTO alias trước khi hiện web.
7. Teardown chứng minh container ID/state bất biến, không chứng minh DB upstream không đổi. `shared_unchanged` có thể yếu khi thiếu preflight; phải hiện coverage thiếu, không biến thiếu evidence thành PASS. Compose path checker kiểm tra tên/thư mục, chưa hash nội dung. Runtime count volume chưa chứng minh mounted volume đúng project.

## Bằng chứng thực thi thực sự có sẵn

Đã đọc đúng các artifact sanitized sau, không gọi lại lab:

- `results/bfla-disposable/bf1a2026/destructive-target-manifest.json` (đường dẫn có sẵn; source validation schema đã audit).
- `results/bfla-disposable/bf1a2026/execution-receipt.json`: run `bf1a2026`, unprivileged DELETE 401, target_survived true; admin control 200, target_absent true; overall DENIED_CONTROL. Đây là lịch sử control đúng, không phải BFLA confirmed.
- `results/bfla-disposable/bf1a2026/teardown-receipt.json`: TEARDOWN_COMPLETE, down exit 0, không còn project container/volume, secret directory removed, shared ID/state before/after giống nhau. Receipt cũ không có preflight linkage mới; không chứng minh phù hợp code hiện tại hoặc DB upstream bất biến.
- `results/week4_bfla_findings.json`: cùng run, DENIED và POSITIVE_CONTROL, overall DENIED_CONTROL; là summary cùng nguồn, không phải độc lập tái hiện.

Inventory `results/` không tìm thấy `bfla-disposable/bf1a2026/preflight-receipt.json` hay `extended-state-receipt.json`. Không kết luận chúng chưa từng được chạy ở nơi khác. Không đánh đồng S01/Run #2 với run disposable trên. Current host/runtime/image/DB chưa kiểm tra.

## Thiết kế workflow độc lập

Web chỉ xem plan và import sanitized evidence; không gọi/import CLI, không Docker socket, không mở write trên queue GET hay bridge. Hiện BFLA vẫn NOT_RUN trên web cho đến có evidence validated. UI phân biệt lịch sử DENIED_CONTROL với chưa chạy và confirmed exploit.

Lifecycle đề xuất: DRAFT → MANIFEST_FROZEN → AWAITING_PREPARE_AUTHORIZATION → PREFLIGHT_ATTESTED → ISOLATED_READY → PREPARED → AWAITING_EXECUTION_AUTHORIZATION → EXECUTING → EVIDENCE_SEALED → CLEANUP_REQUIRED → CLEANED hoặc CLEANUP_FAILED. Failure ở bất kỳ bước nào phải giữ sanitized error receipt và cleanup path; không tự retry/reset. Bước prepare/Compose/cleanup là state change được duyệt theo scope riêng; execute và execute-extended cần phê duyệt riêng, không kế thừa từ GET recovery. Thiết kế này không tự triển khai hay chạy trong audit.

Approval record gắn run_id, manifest hash, stage, exact methods/targets/payload schema, request cap, fixture, policy/version, approver provenance, thời hạn và one-use nonce; stale/tampered/replayed approval phải bị chặn trước network. Approval không lấy từ bot message hay file text tự nhận đã duyệt.

Mỗi case có stable definition ID và execution ID run-scoped, family BFLA_VERTICAL/WRITE_BOLA/MASS_ASSIGNMENT, expected DENY/ALLOW, required/effective role, ownership alias, policy/version/hash, baseline validity, before/after booleans, attempt counters, verdict/reason, artifact digest và cleanup linkage. Không xuất token/password/email probe/raw ID/raw body; chỉ alias và field names/boolean comparison. CONFIRMED đòi target/principal/baseline/postcondition hợp lệ; lỗi đọc state là INVALID_TEST hoặc INSUFFICIENT_EVIDENCE, không coi absent. HTTP 204 self-update là FALSE_POSITIVE_HTTP_204_SELF_UPDATE, không phải write-BOLA. SUSPECTED chỉ là dấu hiệu chưa đủ proof, không tạo finding confirmed.

## Ticket đề xuất có dependencies và acceptance

| ID / ưu tiên | Files dự kiến (không chỉnh trong audit) | Thay đổi và acceptance bắt buộc |
|---|---|---|
| BFLA-01 P0 | disposable/runner.py; tests/disposable/test_runner.py | Postcondition tri-state và fresh preconditions, role/principal checks. Tests: 200+victim tồn tại không CONFIRMED; GET 401/500/malformed không absent; chỉ exact 404 sau baseline hợp lệ mới deletion proof; password principal mismatch invalid; 204 self-update đúng nhãn. Dependency: none |
| BFLA-02 P0 | disposable/manifest.py, cli.py, runner.py; tests/disposable/test_manifest.py, test_cli.py, test_runner.py | Manifest version mới cho DELETE và extended tách scope; approval verifier fail-closed bound stage/hash/run/expiry/one-use, runtime request cap và exact fixture validation. Tests reject thiếu/stale/wrong-stage/tampered approval trước request, extended ngoài approved scope bị chặn; giữ tương thích đọc lịch sử không sửa artifact. Dependency: agreed approval provenance |
| BFLA-03 P0 | disposable/runner.py, preflight.py; tests/disposable/test_runner.py, test_preflight.py | No redirects, no retries; atomic exclusive stage claims và append-only receipts kể cả crash; chặn repeat extended, prepare crash replay, execute/extended race. Tests redirect 30x không request thứ hai, interrupted setup không reset lại, receipt tồn tại không network, budget overflow stops. Dependency: 02 |
| BFLA-04 P1 | disposable/preflight.py, teardown.py, runner.py; tests/disposable/test_preflight.py, test_teardown.py, test_compose.py | Attest actual volume mount/project/image/compose digest; cleanup luôn scoped, preserve artifacts; missing preflight không thành full proof. Tests wrong mount/hash rejects, cleanup failure receipt retained; upstream DB proof chỉ metadata/digest sanitized khi được duyệt và không thu credential. Dependency: 02–03 |
| BFLA-05 P1 | evaluation/bfla_evidence.py; tests/evaluation/test_bfla_evidence.py (owner khác cần Lead giao); sanitized import DTO/backend và frontend/src/App.tsx (Lead giao) | Validate manifest/receipt run/workflow/schema/hash/cleanup; unknown không confirmed; run-scoped output; read-only evidence view dùng alias. UI shows NOT_RUN khi thiếu, DENIED_CONTROL lịch sử, không hiển thị nút chạy write. Tests mismatch/tampered/incomplete receipt rejected, redaction canaries, lịch sử Run #2 không đổi. Dependency: 01–04, ownership riêng |
| BFLA-06 P1 | disposable tests và audit-final acceptance report được giao riêng | Chạy deterministic tests sau sửa; sau phê duyệt riêng mới thực nghiệm disposable và browser read-only evidence drilldown. Pack gồm run/case/fixture/policy/manifest/preflight/approval/attempts/postconditions/cleanup/digests. No execution = NOT_RUN; test mock PASS không nâng experimental verdict. Dependency: 01–05 và lab/authorization |

Đường dẫn rút gọn `disposable/` và `evaluation/` thuộc `tools/authorization-lab/src/authz_lab/`; `tests/` thuộc `tools/authorization-lab/tests/`. Ticket ngoài disposable/tests là đề xuất cho Lead phân công, không mở rộng quyền sửa của bot này.

## Verification boundary

Đã đọc test sources: `tools/authorization-lab/tests/disposable/test_manifest.py`, `test_preflight.py`, `test_runner.py`, `test_teardown.py`, `test_cli.py`, `test_compose.py` được inventory/search; đọc chi tiết runner/teardown tests. `tools/authorization-lab/tests/evaluation/test_bfla_evidence.py` được search về confirmed mapping. Không chạy bất kỳ suite nào. Không có browser E2E hay lab reproduction mới. Source audit hoàn tất; overall BFLA acceptance NOT VERIFIED, current demo execution NOT_RUN. Related automations của bot đã kiểm tra: không có. Không commit/push/reset/xóa evidence.

### SHA-256 artifact đã đọc

- `results/bfla-disposable/bf1a2026/execution-receipt.json`: `b6742ab017e60cd04660bb1a97aafc9d98f2c2004fd2edfc9d92467144382f6d`
- `results/bfla-disposable/bf1a2026/teardown-receipt.json`: `ea1e1b292722970b3281aeae18ac90cb751ae61929b17c15e45612c2dd1a8aa6`
- `results/week4_bfla_findings.json`: `cb36499abee88f9df1d5f572665c2f78af54da655e6cc4c5a9a99a588252af1d`
