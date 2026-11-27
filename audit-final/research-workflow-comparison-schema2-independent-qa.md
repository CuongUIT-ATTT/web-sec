# CMP05-C/D — QA độc lập schema 2

**PASS regression độc lập; tổng thể PARTIAL.** T18 QA Evidence, 2026-11-15, Asia/Ho_Chi_Minh (UTC+07). HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Giữ mọi diff. Đã đọc README root/lab, receipt-contract và schema2-backend handoff; không có AGENTS.md trong repo hoặc các thư mục cha đã kiểm tra. Không sửa production/tests.

## Fresh execution

Lệnh: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python audit-final/cmp05-independent-run.py > audit-final/cmp05-independent-run.log 2>&1` — **exit 0**. Python 3.14.8. Runner lưu toàn bộ pytest argv, timestamp có timezone, toolchain và SHA-256 trước/sau trong `cmp05-independent-evidence.json`; log fresh tại `cmp05-independent-run.log`. Đây là bằng chứng synthetic, không phải run lab.

- Importer, case_manifest, observations, metrics, exports, comparison, timing: **74 tests + 368 subtests PASS**, pytest exit 0.
- Backend comparison_store_api, research_comparison, research_matrix_contract: **19 tests PASS**, pytest exit 0. Riêng comparison_store_api có 9 cases theo bàn giao; kết quả 19 là cả ba suite, không coi là 19 API cases.
- Tổng **93 tests + 368 subtests PASS**; **32/32 hashes trước–sau khớp**. Inventory bao gồm source/contracts/tests, OpenAPI fixture `vampi_spec.json`, ownership fixture và disposable Compose digest; exact hashes trong JSON. Không đọc/hash DB thật hoặc artifact riêng của Run #2.
- Socket connect/connect_ex/sendto/create_connection, DNS getaddrinfo/gethostbyname/gethostbyname_ex, subprocess.Popen, os.system/posix_spawn/posix_spawnp/fork bị chặn bằng mocks trong process trước pytest; worker_loop async no-op. SQLite của TestClient và pytest basetemp dùng TemporaryDirectory riêng. Đây không phải OS sandbox.
- Warnings: pytest-asyncio scope chưa đặt, anyio đã import trước assert rewriting, Starlette/httpx deprecated; không có failure.

## Review và mapping bằng chứng

| Contract/case | Evidence | Verdict |
|---|---|---|
| Strict bounded base64, chunks/padding bits, size/hash exact bytes | `test_schema2_bytes_and_importer_compatibility`, `test_base64_padding_canonicality`, `test_schema2_exact_bindings_and_forged_receipts`; importer suite | PASS |
| Exact receipt/execution binding, recomputed digest không bỏ qua receipt | `test_schema2_exact_bindings_and_forged_receipts`, `test_rebuilt_revision_cohort_cannot_reuse_receipt`; API forged execution trả 422 | PASS |
| Schema 1 fail-closed, explicit empty provenance compatibility | `test_receipt_catalog_claim_fails_closed`, compatibility test; importer regression | PASS |
| Legacy provenance positive giữ UNLINKED/UNKNOWN; attestation UNVERIFIED | `test_legacy_positive_provenance_and_exact_binding`, negative status/trust mutations | PASS |
| Session/CSRF, project isolation, limits, detached DTO | `test_auth_scope_idempotency_reload_and_limits`, validation negatives | PASS |
| Persistence project/digest unique, idempotent, reload và corruption detect | cùng case API: post hai lần chỉ một row, app mới đọc cùng SQLite tạm, corrupt JSON trả 409 | PASS |
| Web không import/call CLI | Review comparison_routes, services/comparison_evidence, comparison/validation và backend-owned contracts: không CLI/subprocess; importer chỉ làm producer trong test | PASS review |

Source review: validator đối chiếu canonical base64 bằng decode/re-encode; SHA-256 dùng decoded bytes nguyên bản trước parse. Expected receipt dựng lại từ observation/legacy đã validate; catalog phải đúng tập refs, hash và binding, không suy provenance từ filename. Case/cohort digest/revision kiểm độc lập bằng contracts backend. API kiểm auth/CSRF trước ingress; đọc detail theo cả project_id và digest. Service không overwrite canonical_json khi cùng key và phát hiện conflict; read revalidate DTO và row digest. Không có update/delete API cho bundle. Immutability ở tầng ứng dụng, không phải SQLite append-only chống sửa ngoài ứng dụng. Chưa kiểm multiprocess race/power-loss hoặc storage corruption ngoài ca synthetic.

Không phát hiện regression failure trong phạm vi này; không mở ticket sửa production. Hash consistency không phải attestation: người gửi thay toàn bộ receipt/hash/digest vẫn có thể tạo dữ liệu giả nhất quán. Allowlist symbolic labels không chứng minh không có secret; upstream vẫn cần review/redaction.

## Gate còn lại

CMP05-C/D đủ regression gate để Lead tiếp CMP06/UI và CMP07; không tuyên bố toàn chuỗi nghiệm thu. CMP06/UI/CMP07 chưa nghiệm thu. Provenance DB vẫn dependency, upstream proof UNKNOWN. Manual/ZAP/BFLA thực nghiệm và 3+/5 roles **NOT_RUN**; Browser E2E **BLOCKED**, không yêu cầu login lại. Không lab/network thật/runtime/DB thật/Run #2/Docker/browser/login/deploy/commit/push/reset/xóa evidence.

Automation kiểm 2026-11-15T16:35:42.056Z: bot không có automation. `git diff --check` trước chạy exit 0; sau báo cáo được kiểm và ghi trong bàn giao. Ba docs trạng thái được bổ sung cập nhật mới nhất, giữ nguyên lịch sử.
