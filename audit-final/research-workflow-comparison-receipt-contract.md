# CMP05-C — hợp đồng receipt serialized cho backend

**PASS regression người triển khai; tổng thể PARTIAL.** T18 ZAP Comparison, 2026-11-15. HEAD `bdbba9933ca057cb2247c3a1de9b3ee239c452bd` đúng mốc. Đã đọc README root/lab, importer handoff/QA, API/store handoff, backend validation và contracts liên quan. Không thấy AGENTS.md trong repository; báo cáo QA trước cũng xác nhận các thư mục cha đã kiểm tra không có. Giữ các diff mọi owner.

Chỉ thay đổi `tools/authorization-lab/src/authz_lab/evaluation/importer.py`, `tools/authorization-lab/tests/evaluation/test_importer.py` và báo cáo mới này. Không sửa backend/frontend/ba docs QA. Không lab/network/Docker/runtime/DB/Run #2/browser/deploy/commit/push/reset/xóa evidence.

## Version và compatibility

`import_bundle(bundle, artifact_bytes, *, output_schema_version=2)` vẫn nhận input bundle schema 1 và receipt schema 1. Mặc định trả serialized envelope schema 2. `output_schema_version=1` tường minh giữ output cũ cho consumer offline đã kiểm bytes tại import. Không mặc định downgrade, không strip provenance để di trú. `validate_envelope(raw)` là reference validator thuần cho downstream; backend phải implement độc lập, không import CLI.

Envelope schema 1 **chỉ** được downstream chấp nhận nếu provenance và catalog đều rỗng. Có provenance (kể cả legacy) hoặc catalog thì reject vì không có preimage để tái kiểm. Version bool/unknown reject. Cả hai version luôn attestation UNVERIFIED. Không nâng hash match, producer HUMAN hoặc metadata operator thành trusted/human attestation. Client tự thay toàn bộ receipt và hash vẫn có thể tạo bộ dữ liệu nhất quán giả; contract không xác thực nguồn và không cấp trust.

## Encoding, giới hạn và digest

Top-level exact fields: schema_version, manifest, observations, selections, legacy, artifacts, attestation_status, content_digest. Catalog schema 2 exact fields: artifact_ref, artifact_hash, size_bytes, integrity_status, attestation_status, receipt_encoding, receipt_base64_chunks. Hai trường mới là `receipt_encoding="base64"` và list string `receipt_base64_chunks`.

Receipt JSON bytes phải UTF-8 strict, schema 1 allowlisted; không BOM, duplicate keys, unknown fields, raw body/secrets/resource IDs/arbitrary paths. SHA-256 artifact tính trên **bytes caller đưa ban đầu**, không trên JSON serialize lại. Base64 RFC 4648 standard alphabet, padding chuẩn; encode bytes nguyên bản rồi chia trái sang phải mỗi 512 ký tự, đoạn cuối 1..512. List 1..11 đoạn; các đoạn trước cuối phải đủ 512; tổng encoded <=5464, decoded 1..4096 bytes. Strict decode và encode lại phải khớp y nguyên, loại whitespace/URL alphabet/bad padding/nonzero pad bits. Chia đoạn giữ giới hạn string hiện có 512, không mở rộng tùy tiện.

Tổng decoded receipts <=2,000,000 bytes; toàn bộ JSON envelope trước parse và canonical sau serialize <=2,000,000 bytes (base64 overhead có thể làm chạm giới hạn sớm hơn). Tối đa 1000 items mỗi list/object, depth 12, integer abs <=2**53, không floats/constants, string <=512. Canonical JSON: sorted keys, separators `(',', ':')`, ensure_ascii=True, ASCII bytes; content_digest = SHA-256 canonical object bỏ duy nhất content_digest. JSON transport không cần cùng whitespace/key ordering; array ordering và semantic DTO phải canonical.

## Thuật toán backend handoff

1. Giới hạn raw bytes trước parse, UTF-8 strict; reject duplicate keys/NaN và cấu trúc quá giới hạn. Exact fields và integer version 1/2; kiểm content_digest bằng canonical algorithm trên và attestation UNVERIFIED.
2. Kiểm lại manifest content digest/version, từng case_id là SHA-256 toàn bộ CaseDefinition (bỏ case_id), membership và exact revision. Vì case_id bao trùm mọi revision field, receipt schema 1 không cần thêm field revision riêng. Manifest digest ràng buộc toàn bộ cohort.
3. Kiểm observation exact fields, cohort, revision, method/execution/status/signal và producer/method compatibility. Unique(method, execution, case); selections explicit unique method, không suy latest, selection rỗng observations không chứng minh đã chạy.
4. Với mỗi provenance xây expected receipt; cùng artifact_ref nhưng hash hoặc receipt binding khác nhau reject. Catalog phải đúng tập referenced, không duplicate/missing/unreferenced. Decode schema-2 chunks strict, size đúng decoded length (integer, không bool), tổng bytes đúng cap. Hash bytes phải khớp cả catalog và provenance.
5. Parse decoded receipt bằng cùng JSON guards. Observation receipt exact fields/value: schema_version=1, kind=OBSERVATION, manifest_digest, manifest_version, case_id, method, execution_id, execution_status, signal. Legacy receipt exact: schema_version=1, kind=LEGACY_INVENTORY, method, source_alias, linkage_status=UNLINKED; legacy output conclusion=UNKNOWN, không gán case/cohort/run. Hash đúng nhưng binding sai vẫn reject.
6. Rebuild canonical DTO từ validated contracts + decoded receipts, so sánh toàn bộ DTO và digest với supplied. Catalog sorted artifact_ref, legacy sorted(method,source_alias), selections sorted method, observations theo ObservationSet. Reject extra status/trust/size/noncanonical ordering. Trả detached DTO, không I/O/path resolution/history lookup/truth/metrics/execution.

Backend hiện vẫn schema 1 và sẽ reject envelope mới: đây là dependency cần Lead giao backend owner nối schema 2 rồi QA độc lập. Không claim API integration đã PASS.

## DTO synthetic có thể tái kiểm

Toàn bộ alias, fixture hash, policy và receipt dưới đây là synthetic, không phải evidence lab hay 3+ roles. Đây là DTO hoàn chỉnh, không có placeholder; `validate_envelope` đã xác minh roundtrip trước khi ghi. Catalog base64 decode ra receipt JSON bên dưới; transport formatting không ảnh hưởng digest canonical.

```json
{
  "artifacts": [
    {
      "artifact_hash": "6511a54c3399ebcbaee587665544f7fe46be19d5e039142a6f472e180f30dbe1",
      "artifact_ref": "artifact-eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
      "attestation_status": "UNVERIFIED",
      "integrity_status": "HASH_MATCHED",
      "receipt_base64_chunks": [
        "eyJjYXNlX2lkIjoiY2FzZS02ZmE4MTg2MDQ2OGJhMzFkNmU0ZmM1MmRlZWFiMTA4YjdiN2JkNmMxMWE3YjRjYjhkMzA5ODY1NDNkZDM2MjkyIiwiZXhlY3V0aW9uX2lkIjoiZXhlY3V0aW9uLWRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkIiwiZXhlY3V0aW9uX3N0YXR1cyI6IkNPTVBMRVRFRCIsImtpbmQiOiJPQlNFUlZBVElPTiIsIm1hbmlmZXN0X2RpZ2VzdCI6IjI2MzAxYjk5ZTcxZWNkZGE1MTYyODI2ZTQ4ZWMzZDcxYmZmZDU1ZDc2ZGI5ZDllM2IzMmE3OWRlZjg5NTdkY2EiLCJtYW5pZmVzdF92ZXJzaW9uIjoic2hhMjU2OjI2MzAxYjk5ZTcxZWNkZGE1MTYyODI2ZTQ4ZWMzZDcxYmZmZDU1ZDc2ZGI5ZDllM2IzMmE3OWRlZjg5NTdkY2EiLCJtZXRob2QiOiJN",
        "QU5VQUwiLCJzY2hlbWFfdmVyc2lvbiI6MSwic2lnbmFsIjoiQUNDRVNTX0RFTklFRCJ9"
      ],
      "receipt_encoding": "base64",
      "size_bytes": 435
    }
  ],
  "attestation_status": "UNVERIFIED",
  "content_digest": "5aa19fb6f8eb7cd47adb2384bd159b6afae2d44a46946f3842490b9dd221c5d0",
  "legacy": [],
  "manifest": {
    "cases": [
      {
        "actor_alias": "actor-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "actor_role": "userA",
        "case_id": "case-6fa81860468ba31d6e4fc52deeab108b7b7bd6c11a7b4cb8d30986543dd36292",
        "expected_decision": "DENY",
        "fixture_hash": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "fixture_version": "v1",
        "method": "GET",
        "operation_template": "/users/{username}",
        "owner_alias": "owner-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "owner_category": "OTHER",
        "policy_id": "cross_user",
        "policy_version": "v1"
      }
    ],
    "content_digest": "26301b99e71ecdda5162826e48ec3d71bffd55d76db9d9e3b32a79def8957dca",
    "schema_version": 1,
    "version": "sha256:26301b99e71ecdda5162826e48ec3d71bffd55d76db9d9e3b32a79def8957dca"
  },
  "observations": [
    {
      "case_revision": {
        "actor_alias": "actor-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "actor_role": "userA",
        "case_id": "case-6fa81860468ba31d6e4fc52deeab108b7b7bd6c11a7b4cb8d30986543dd36292",
        "expected_decision": "DENY",
        "fixture_hash": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        "fixture_version": "v1",
        "method": "GET",
        "operation_template": "/users/{username}",
        "owner_alias": "owner-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "owner_category": "OTHER",
        "policy_id": "cross_user",
        "policy_version": "v1"
      },
      "execution_id": "execution-dddddddddddddddddddddddddddddddd",
      "execution_status": "COMPLETED",
      "manifest_digest": "26301b99e71ecdda5162826e48ec3d71bffd55d76db9d9e3b32a79def8957dca",
      "manifest_version": "sha256:26301b99e71ecdda5162826e48ec3d71bffd55d76db9d9e3b32a79def8957dca",
      "method": "MANUAL",
      "provenance": {
        "artifact_hash": "6511a54c3399ebcbaee587665544f7fe46be19d5e039142a6f472e180f30dbe1",
        "artifact_ref": "artifact-eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        "operator_alias": "operator-11111111111111111111111111111111",
        "producer_kind": "HUMAN",
        "producer_version": "1.0"
      },
      "signal": "ACCESS_DENIED"
    }
  ],
  "schema_version": 2,
  "selections": [
    {
      "execution_id": "execution-dddddddddddddddddddddddddddddddd",
      "method": "MANUAL"
    }
  ]
}
```

Receipt decoded:

```json
{
  "schema_version": 1,
  "kind": "OBSERVATION",
  "manifest_digest": "26301b99e71ecdda5162826e48ec3d71bffd55d76db9d9e3b32a79def8957dca",
  "manifest_version": "sha256:26301b99e71ecdda5162826e48ec3d71bffd55d76db9d9e3b32a79def8957dca",
  "case_id": "case-6fa81860468ba31d6e4fc52deeab108b7b7bd6c11a7b4cb8d30986543dd36292",
  "method": "MANUAL",
  "execution_id": "execution-dddddddddddddddddddddddddddddddd",
  "execution_status": "COMPLETED",
  "signal": "ACCESS_DENIED"
}
```

Legacy positive receipt trong test: `{schema_version:1, kind:LEGACY_INVENTORY, method:ZAP, source_alias:source-99999999999999999999999999999999, linkage_status:UNLINKED}` (minh họa object, không phải JSON transport). Hash từ exact json.dumps UTF-8 bytes; catalog encoding giữ bytes nguyên bản. Test đổi alias/method/linkage/conclusion đều reject sau recompute envelope digest.

## Fresh verification

`.venv/bin/python` với `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools/authorization-lab/src`; pytest `-q -p no:cacheprovider --basetemp <TemporaryDirectory riêng>/pytest`. Cả năm suite importer/case_manifest/observations/metrics/exports: **44 tests + 364 subtests PASS, fresh exit 0**. Trước đó từng suite riêng cũng exit 0 (13/10/11/6/4 tests). Lần cuối sau thay đổi source cuối cùng chạy toàn bộ cùng process; 16/16 SHA-256 trước/sau bằng nhau. Guards trong process chặn socket connect/connect_ex/sendto/create_connection, DNS getaddrinfo/gethostbyname/gethostbyname_ex, subprocess.Popen, os.system/posix_spawn/posix_spawnp/fork. Temp riêng; không phải OS sandbox. Warning pytest-asyncio unset scope hiện có.

Tests mới: bytes exact roundtrip/deterministic, schema1 explicit compatibility/fail-closed provenance, đổi execution rồi recompute envelope digest vẫn reject bởi receipt mismatch; sửa status/signal/cohort/method/revision; rebuild cohort/revision nhất quán nhưng receipt cũ vẫn reject; legacy provenance positive UNLINKED/UNKNOWN và mutation negatives; tamper/hash/duplicate/unknown/missing/encoding/size/status; duplicate/unknown/invalid UTF-8 receipt ngay cả khi hash và digest đều tính lại. Existing suites tiếp tục kiểm malformed/depth/items/scalars/canaries và metrics excluded khi thiếu review. Structural allowlists không phát hiện secret giả dạng symbolic label hợp lệ; upstream vẫn phải review/redact, hash không là attestation.

Automation kiểm 2026-11-15T16:30:01.496Z: không có automation. `git diff --check` được kiểm sau khi ghi báo cáo (exit ghi trong bàn giao).

Thực nghiệm manual/ZAP/BFLA và 3+ roles NOT_RUN; E2E BLOCKED; tổng thể PARTIAL. Bước tiếp: backend owner nối schema, sau đó QA độc lập.

## Hash trước = sau lần chạy cuối

- `tools/authorization-lab/src/authz_lab/evaluation/timing.py`: `f7635d43394b0ae3a03299a1c9e775b586c0cd1d88a9421539cebe84611bad92`
- `tools/authorization-lab/src/authz_lab/evaluation/comparison.py`: `b68e948c19c8b125d8f7aa4557e6e17f1ee7a2d3b0fadaa31623e46a0377bcfe`
- `tools/authorization-lab/src/authz_lab/evaluation/importer.py`: `a9fa83363b8a6d6be2acb04ef83728bdedf681cfd971a77c7854612993b085b1`
- `tools/authorization-lab/src/authz_lab/evaluation/bfla_evidence.py`: `fdca67d22a5ba010ae21ff01b4338d2071f4cf202a022e7c87a42c988d4fae88`
- `tools/authorization-lab/src/authz_lab/evaluation/metrics.py`: `8993b5d23ed004f60ceea8807d744adb6cf32cc273a4cc31af785d7f5b687642`
- `tools/authorization-lab/src/authz_lab/evaluation/__init__.py`: `5415841b389d2a6c452602c70a6abe68b600d4dad573b1d3dac483bb681db7fa`
- `tools/authorization-lab/src/authz_lab/evaluation/exports.py`: `ec4b03631399a6db3810e0261eb0c51a806cbaf5e04c0480ea313f1cf9145b1b`
- `tools/authorization-lab/src/authz_lab/evaluation/case_manifest.py`: `38fb21fecc9b6a40dbc558a38b0f9e99956e76dfc1701903de0d638b9d8f9fb3`
- `tools/authorization-lab/src/authz_lab/evaluation/cli.py`: `2c6b7930a2b8ae8a9332c56a4164e1c7d957b9e139f71ea869fccd5fef19fc4e`
- `tools/authorization-lab/src/authz_lab/evaluation/observations.py`: `72cda5b6d69603672392ef913382e3920ddf7213d5fb9f9432263f17823bcf69`
- `tools/authorization-lab/tests/evaluation/test_importer.py`: `bdb702916e21e871f8aa211f209154b164e2f3d3eb64f42b870d70d196a6e0a9`
- `tools/authorization-lab/tests/evaluation/test_case_manifest.py`: `be03ad6c3a672c1c606067c67d6a0942870598b39f77db54854116c14368c5ea`
- `tools/authorization-lab/tests/evaluation/test_observations.py`: `1228e6dbebeb01d13a39a910d954aefe464a9744f4d9fe82ce5ba237671158ee`
- `tools/authorization-lab/tests/evaluation/test_metrics.py`: `4b4a7d4c1cb56eb374c35be5ef1ccd53ee99d9a7bac8121740f1976c1e12b58b`
- `tools/authorization-lab/tests/evaluation/test_exports.py`: `1d09b1710d8d9007bdbc1b5a6f58382b041d6931a615d06eef38f6e66a0cc795`
- `backend/app/comparison/validation.py`: `eed2172643da55a4e1fafe03787d1b90054258205cbe650dd1855f2c15e40048`
