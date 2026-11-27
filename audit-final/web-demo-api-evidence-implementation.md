# API-EVIDENCE-03

HEAD kiểm tra: bdbba9933ca057cb2247c3a1de9b3ee239c452bd; ngày 2026-11-13.

## Contract cho frontend

GET /api/runs/{run_id}/results, require_admin; run không tồn tại trả 404. Query chỉ lấy RunResult.run_id tương ứng; không trộn result run/project khác. Đây là global admin API hiện có, không phải tenant ACL mới.

Giữ tên response_metadata và các fields result cũ. Metadata chỉ trả body_length (int >=0 hoặc null), body_truncated/json_parse_error (bool hoặc null), evidence (object typed hoặc null). Unknown keys bị bỏ ở cả metadata và evidence. Không trả raw metadata, response body, token hay trường phụ.

Evidence yêu cầu đầy đủ các fields schema_version=1 và engine=web-evaluator-v1, type strict, các ID/version >0, HTTP status 100..599 hoặc null, enums hợp lệ. schema_version bool bị từ chối. run_id/case_key phải khớp chính row result. Missing/historical/malformed/unsupported/provenance mismatch => evidence=null, không tự suy ra false. Observation fields malformed được null riêng từng field; evidence không bị ép kiểu.

JSON dưới là ví dụ synthetic, không phải kết quả live:

```json
[
  {
    "case_key": "resource:1:actor:2",
    "execution_status": "COMPLETED_RESPONSE",
    "authorization_conclusion": "CONFIRMED_VIOLATION",
    "reason_codes": [
      "evidence.example"
    ],
    "http_status": 403,
    "response_metadata": {
      "body_length": 42,
      "body_truncated": false,
      "json_parse_error": false,
      "evidence": {
        "schema_version": 1,
        "engine": "web-evaluator-v1",
        "run_id": 1,
        "case_key": "resource:1:actor:2",
        "resource_id": 1,
        "actor_identity_id": 2,
        "owner_identity_id": 1,
        "owner_control_valid": true,
        "owner_http_status": 200,
        "owner_execution_status": "COMPLETED_RESPONSE",
        "owner_body_truncated": false,
        "owner_json_parse_error": false,
        "owner_principal_matches": true,
        "actor_principal_matches": true,
        "owner_resource_matches": true,
        "actor_resource_matches": true,
        "owner_restricted_evidence_valid": true,
        "restricted_fields_match_owner": true,
        "policy_id": 1,
        "policy_version": 7,
        "policy_decision": "DENY",
        "policy_resolution": "RESOLVED"
      }
    }
  }
]
```

Các policy fields nullable nhưng bắt buộc có trong evidence. UNKNOWN được giữ nguyên; NO_MATCH/conflict có thể không có policy được chọn. API không tự tạo verdict từ comparison booleans. Frontend đọc authorization_conclusion/reason_codes cùng owner_control_valid. Không backfill evidence hay tạo provenance cho lịch sử.

## Files/functions

- backend/app/api/workflow_schemas.py: ResultEvidenceView, ResultMetadataView, RunResultView.
- backend/app/api/workflow_routes.py: _result_metadata, list_results response_model; giữ finding reproduction linkage.
- backend/tests/test_web_demo_contracts.py: synthetic SQLite API tests, không app lifespan/worker/traffic lab.

## Verification

- Targeted trước case schema_version bool: .venv/bin/python -m pytest -q backend/tests/test_web_demo_contracts.py backend/tests/test_web_demo_evidence.py: 65 passed, exit 0.
- Full suite và final diff check: kết quả bên dưới.
- Tests kiểm tra typed OpenAPI schema, canary ở cả hai tầng, run/case mismatch, version/engine/type/enum malformed, historical/missing/incomplete, UNKNOWN/NO_MATCH, run/project isolation và missing run.
- Không sửa runner/evaluator/frontend/CLI; không commit/push/reset hoặc chạy lab/runtime. Browser/live demo NOT_RUN. Không có automation cần dừng.

- Full backend: .venv/bin/python -m pytest -q backend/tests > audit-final/web-demo-api-evidence-tests.log 2>&1; pytest summary **140 passed, 1 warning in 15.85s**, shell command exit 0 (tail chạy sau pytest; không lưu riêng pytest exit code).
- Final git diff --check: exit 0. Log: audit-final/web-demo-api-evidence-tests.log.
