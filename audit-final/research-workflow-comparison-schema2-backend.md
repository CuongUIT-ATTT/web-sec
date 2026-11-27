# CMP05-D — backend schema 2

**PASS regression người triển khai; chờ QA độc lập. Tổng thể PARTIAL.**
T18 OpenAPI Matrix, 2026-11-15. HEAD xác minh:
`bdbba9933ca057cb2247c3a1de9b3ee239c452bd`.

Đã đọc README root, contract CMP05-C và contracts backend/importer liên quan.
Không có AGENTS.md trong repository hoặc các thư mục cha đã kiểm tra
(/, /home, /home/cuong, /home/cuong/Dự án, /home/cuong/Dự án/Bảo mật web).
Giữ mọi diff có sẵn. Chỉ sửa `backend/app/comparison/validation.py`,
`backend/tests/test_comparison_store_api.py` và tạo báo cáo này.
Không cần sửa service: API ingress và service read đã gọi validator chung.

## Kết quả triển khai

Validator backend độc lập, chỉ import contracts backend, không import CLI.
Schema 2 nhận receipt base64 standard strict: 1..11 chunks, chunk trước cuối
đúng 512 ký tự, cuối 1..512; tổng encoded <=5464, decoded 1..4096.
Decode rồi encode lại phải trùng, loại nonzero padding bits và encoding sai.
Giữ giới hạn envelope 2,000,000 bytes trước parse và canonical; tổng receipt
2,000,000 bytes; 1000 items, depth 12, string 512, abs integer <=2**53,
không float/NaN, duplicate key, invalid UTF-8 hoặc BOM.

SHA-256 tính trên exact decoded original bytes; size integer strict phải đúng
length. Receipt exact fields và schema integer 1; ràng buộc manifest
digest/version, case_id, method, execution, status, signal. Manifest/case digest
và exact revision được kiểm trước qua contracts backend. Cùng ref khác hash
hoặc binding bị reject. Catalog đúng tập provenance, unique và sorted; giữ
canonical observation/selection/legacy ordering và producer compatibility.

Schema 1 chỉ nhận provenance/catalog rỗng; không strip/downgrade dữ liệu.
Legacy có provenance hợp lệ nhận ở schema 2, luôn UNLINKED/UNKNOWN.
Mọi envelope/catalog giữ UNVERIFIED. Không thêm truth, review hay attestation.

## Fresh regression

Lượt cuối sau thay đổi source cuối: **9 tests PASS, pytest exit 0**.
Lệnh chạy `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -`, trong Python:
`pytest.main(['backend/tests/test_comparison_store_api.py', '-q', '-p',
'no:cacheprovider', '--basetemp', temp+'/pytest'])`.
`temp` là TemporaryDirectory riêng prefix cmp05d-final-.

Exit pytest được thu trực tiếp rồi script SystemExit cùng mã; hash trước/sau
9 file đều trùng. Không dùng kết quả cũ để thay fresh exit.
Hai lượt phát triển trước đạt 6 rồi 9 tests, đều exit 0.
Warning hiện có: pytest-asyncio chưa đặt scope và Starlette/httpx deprecation.

Guards toàn process lượt cuối và autouse fixture chặn:
socket.socket.connect/connect_ex/sendto, socket.create_connection,
socket.getaddrinfo/gethostbyname/gethostbyname_ex, subprocess.Popen,
os.system/posix_spawn/posix_spawnp/fork. Worker loop được thay async no-op.
SQLite chỉ là temp database do TestClient tạo, không mở database thật.
Guards là Python mocks, không phải OS sandbox.

Tests:
- DTO synthetic đầy đủ từ contract CMP05-C; test-only import importer để chứng
  minh output trùng DTO. Runtime backend không import CLI.
- DTO đó qua POST/API, inventory/detail, idempotency và reload app/SQLite.
- Session/login, CSRF thiếu/sai, project isolation, pagination, media type và
  payload size; canary lỗi không lọt API response; corrupt stored JSON trả 409.
- Đổi execution rồi recompute digest bị reject ở validator và API.
- Status/signal/method/cohort/revision bị sửa; rebuild revision/cohort hợp lệ
  nhưng giữ receipt cũ vẫn reject bằng receipt binding.
- Hash exact bytes với JSON whitespace khác vẫn roundtrip; detached DTO.
- Forged/unknown fields, duplicate receipt key, bool version, invalid UTF-8/BOM,
  NaN, malformed/duplicate/missing catalog; sai hash/size/encoding và chunks.
- Canonical base64 padding bits (hai trường hợp), depth/items/scalar/string
  limits và total receipt cap (hạ constant bằng patch).
- Legacy provenance positive UNLINKED/UNKNOWN và negative binding/linkage/
  conclusion/schema downgrade. Schema 1 provenance rỗng positive giữ hoạt động.

## Compatibility và giới hạn

API path, persistence schema và immutable project/digest behavior giữ nguyên.
Những bundle schema 1 có provenance trước đây đã fail-closed, nay vẫn reject.
Importer chỉ được dùng làm producer trong test; không có đường runtime web→CLI.
Hash chứng minh consistency, không xác thực nguồn; người gửi thay toàn bộ receipt,
hash và digest vẫn có thể tạo dữ liệu giả nhất quán. Allowlist không phát hiện
secret giả dạng symbolic label hợp lệ; upstream cần review/redaction.

Chưa chạy toàn bộ backend suite; phạm vi này kiểm comparison ingress/store và
contracts đi qua validator. Chưa QA độc lập; không claim nghiệm thu thực nghiệm.
CMP06/UI và CMP07 vẫn dependency của Lead. Manual/ZAP/BFLA/3+ roles NOT_RUN;
Browser E2E BLOCKED. Không lab/network/runtime/DB thật/Run #2/Docker/browser/
login thực/deploy/commit/push/reset/xóa evidence.

Automation kiểm 2026-11-15T16:33:29.333Z: không có automation.
`git diff --check` sau source/tests exit 0; kiểm lại sau ghi báo cáo trong bàn giao.

## SHA-256 trước = sau lượt xác minh cuối

- `audit-final/research-workflow-comparison-receipt-contract.md`: `cb18c9103583bff17f6c41339cffb0325c12115edb022341af8c3c58d0f8afae`
- `backend/app/api/comparison_routes.py`: `af6b26e6776c9e142b2aa33e23a7411f7c4a168d498903eecaf898e6cdfc39b4`
- `backend/app/comparison/__init__.py`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- `backend/app/comparison/case_manifest.py`: `38fb21fecc9b6a40dbc558a38b0f9e99956e76dfc1701903de0d638b9d8f9fb3`
- `backend/app/comparison/observations.py`: `72cda5b6d69603672392ef913382e3920ddf7213d5fb9f9432263f17823bcf69`
- `backend/app/comparison/validation.py`: `e58060e4ad4163a9f5cde793f5d38a3c6c4af1ae85570d8d04ed89a58b570cdd`
- `backend/app/services/comparison_evidence.py`: `a5011c34da0ea131ee26b51d2e4cff486fae2bfc9903b2b73ec2cdbeabd1c865`
- `backend/tests/test_comparison_store_api.py`: `e2b65e638aec769b1b9eaff27d763eb327d1202e1f4c736077e84bfa811b9807`
- `tools/authorization-lab/src/authz_lab/evaluation/importer.py`: `a9fa83363b8a6d6be2acb04ef83728bdedf681cfd971a77c7854612993b085b1`
