# AUTOAUTH-MODEL-MATRIX-01 — bàn giao backend

Ngày 2026-11-16. HEAD nguồn `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`; working tree có sẵn nhiều diff của nhóm, được giữ nguyên. Thay đổi ticket chưa commit.

## Kết quả và giới hạn

Đã triển khai cấu hình quyền reusable cấp project, revision append-only, resolver thuần không network, sinh ma trận BOLA actor × resource và BFLA actor × operation, API cấu hình/preview. Không chỉnh runner/evaluator/frontend/CMP07. Không mở persistent SQLite, lab, Run #2, ZAP hoặc remote API.

**PASS local cho model/preview; chưa phải PASS execution automatic authorization.** Queue legacy vẫn dùng policy và snapshots legacy; không tự dùng config mới. Frontend/evaluator cần tích hợp contract mới trước khi queue case mới. Không được lấy `execution_eligible` làm bằng chứng một case đã chạy. Tất cả preview có `execution_status=NOT_RUN`.

## Audit nguồn

- `Policy` legacy chọn operation/resource type/identity hoặc role/resource; thiếu predicate OWNER/SHARED cấp project và revision toàn bộ cấu hình.
- Batch legacy chỉ mở rộng selected GET mappings, I + C + I×C; vẫn tái sử dụng và giữ nguyên.
- Parser legacy mặc định chỉ GET. Bổ sung opt-in inventory các method; import legacy không đổi.
- Hai users/role và mapping GET hẹp là cấu hình demo, không phải giới hạn đếm identities trong generator. Không sửa fixture lab để mở rộng demo.
- Model mới dùng một bảng mới; create_all + migration marker kiểm schema tương thích, không ALTER bảng legacy. Chỉ chạy migration trong SQLite tạm của tests.

## Contract frontend/evaluator

API admin có session hiện hữu; PUT/POST cần `X-CSRF-Token`:

- `GET /api/projects/{project_id}/authorization/config`: `{revision, configuration, legacy_unchanged}`; chưa cấu hình trả revision null và danh sách rỗng.
- `PUT .../config`: lưu `{rules,operations,sharing}`, trả `{revision,configuration}`. Revision SHA-256 cấu hình JSON canonical. PUT cùng head idempotent. Revert về revision đã tồn tại trả 409, không âm thầm đổi head. Reference khác project/không tồn tại trả 422. Mỗi operation chỉ có một mapping/kind; mapping trùng bị 422.
- `POST .../openapi`: `{document: OpenAPI JSON}`; inventory GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS, mặc định selected=false cho row mới. Không dispatch. Không thay đổi operation có sẵn. Muốn preview phải selected và approved rõ ràng; tên path không quyết định privilege.
- `GET .../preview?target_id=N`: đọc lại cấu hình/identity/resource/verification mỗi lần, không cache và không gửi request.

Ví dụ reusable config (các ID chỉ minh họa, phải thay bằng ID cùng project):

```json
{
  "operations": [
    {"operation_id": 1, "kind": "BOLA", "approved": true, "resource_type_id": 1},
    {"operation_id": 2, "kind": "BFLA", "approved": true}
  ],
  "sharing": [{"resource_id": 1, "identity_ids": [2]}],
  "rules": [
    {"key": "owner-read", "decision": "ALLOW", "relation": "OWNER"},
    {"key": "shared-read", "decision": "ALLOW", "relation": "SHARED"},
    {"key": "admin-permission", "decision": "ALLOW", "roles": ["admin"]},
    {"key": "forbidden-function", "decision": "DENY", "roles": ["user"], "operation_ids": [2]}
  ]
}
```

Rule selectors kết hợp AND: operation_ids, resource_type_id, identity_ids, roles, relation. Danh sách selector rỗng nghĩa là mọi giá trị; ANY mặc định. Precedence **DENY > UNKNOWN > ALLOW**, không match => UNKNOWN. Không tự suy cross-user DENY; operator cần rule DENY phù hợp. DENY khớp rộng cũng thắng SHARED/OWNER/admin; muốn ngoại lệ phải thu hẹp deny selector.

Case có `case_id`, `kind`, `operation_id`, `method`, `path_template`, actor ID/role, resource/owner ID nullable, relationship, expected_decision, matched_rule_keys, policy_revision, baseline_identity_id, baseline_kind, owner_baseline_available, reasons, execution_eligible. Không trả external resource IDs, tokens, ciphertext, expected principal hay body.

Stable case ID: `autoauth:v1:project:P:operation:O:KIND:resource:R-or-'-':actor:A`. Không đổi khi policy revision thay đổi. Namespace này khác case key legacy; adapter mới phải giữ nguyên ID qua snapshot/results/comparison, không thay case key của run cũ.

Baseline: ưu tiên owner verified với ALLOW, sau đó actor ALLOW có ID nhỏ nhất; không có => missing baseline, không executable. Owner không khả dụng được biểu thị `owner_baseline_available=false`; baseline thay thế chỉ là expectation, chưa chứng minh response hợp lệ.

Budget = số executable GET BOLA rows + unique baseline(operation,resource,identity) + unique identities cần xác minh. Trả request_limit và within_request_limit; không tự chọn bớt case theo cap. Đây là ngân sách adapter tương lai, không thay ngân sách queue legacy. Token và principal phải được xác minh lại lúc chạy theo queue snapshot contract; bản verification hiện có chỉ là precheck.

Mọi identity có case hoặc exclusion MISSING_CREDENTIAL / MISSING_PRINCIPAL_MAPPING / IDENTITY_NOT_VERIFIED / NO_VALID_APPROVED_OPERATION. Verification gần nhất theo target phải authentication_passed, principal_matched và COMPLETED_RESPONSE. Missing resource owner/path mapping không được suy đoán; row giữ lại reason. Param BFLA chưa resolve => NOT_RUN. NonGET => DISPOSABLE_WRITE_AUTHORIZATION_REQUIRED. GET BFLA => FUNCTION_EXECUTION_ADAPTER_REQUIRED (chưa có evaluator/business evidence contract). Unknown policy và missing baseline không executable.

## File ownership

- `backend/app/services/authorization_model.py`: config schema, resolver, reference validation, generator, baseline/budget.
- `backend/app/api/authorization_routes.py`: auth/CSRF config, inventory, preview.
- `backend/app/persistence/models.py`: chỉ append ProjectAuthorizationRevision.
- `backend/app/persistence/upgrades.py`: additive revision schema marker.
- `backend/app/scanner/openapi/parser.py`: opt-in nonGET inventory; default GET-only.
- `backend/app/main.py`: import/include router mới; giữ mọi thay đổi sẵn có.
- `backend/tests/test_authorization_model.py`: fixtures/tests API/model/migration.

## Verification

Commands từ repo, chỉ SQLite tạm do pytest tạo:

```sh
.venv/bin/python -m pytest backend/tests/test_authorization_model.py backend/tests/test_openapi_parser.py -q
.venv/bin/python -m pytest backend/tests -q
.venv/bin/python -m compileall -q backend/app/services/authorization_model.py backend/app/api/authorization_routes.py
 git diff --check
```

Fixture deterministic: 3 identities (user,user,admin), mỗi owner 2 resources, 1 BOLA + 3 BFLA operations => **18 BOLA + 9 BFLA = 27 cases**. Kiểm owner/shared/admin ALLOW, explicit DENY precedence, unknown, stable IDs/revision, baseline thay thế/missing, failed verification, missing credentials/principal, ambiguous mapping, exclusion accounting, cap, cross-project rejection, authentication/CSRF, idempotent inventory/config, legacy row/snapshot retention trên SQLite tạm.

Evidence nằm trong `results/autoauth-model-matrix-01/` (ignored). Full backend lần đầu 177 PASS; lượt cuối và hashes ghi trong execution.json/SHA256SUMS. Compile/diff-check cần xem exit thực trong execution.json.

## Handoff / phần chưa xác minh

- Evaluator: cần consumer expectation/matched rules/revision/baseline mới; không dùng policy_id legacy giả để ghi finding.
- Runner owner: cần snapshot/queue adapter giữ stable IDs, credentials snapshot và cap/cancel/journal; chưa được sửa trong ticket này.
- Frontend: đọc config/preview endpoint mới; không nối nút legacy queue vào ma trận mới vì đó vẫn là config khác.
- Browser E2E và thực nghiệm BOLA/BFLA NOT VERIFIED/NOT_RUN trong ticket; không tuyên bố từ unit/API tests.
- Proof DB persistent/Run #2 chưa thực hiện; chỉ chứng minh compatibility trên temp DB. Tổng thể T18 vẫn PARTIAL.
