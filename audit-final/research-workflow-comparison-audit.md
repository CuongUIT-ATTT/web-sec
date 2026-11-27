# Audit Phase 1 — R5/R8 manual / T18 / ZAP

Ngày 2026-11-15, workspace `/home/cuong/Dự án/Bảo mật web/Project`. HEAD xác minh `bdbba9933ca057cb2247c3a1de9b3ee239c452bd`. Working tree có thay đổi backend/frontend/tests từ trước; audit này không sửa chúng. Chỉ tạo báo cáo này. Không gọi lab, queue, ZAP, BFLA, DB, browser hoặc deploy; không chạy tests; không đọc credentials, ZAP context/session hay response bodies. Không commit/push/reset/xóa. Run #2 và snapshots không bị tác động.

## Kết luận và phân loại

| Phạm vi | Phân loại | Verdict nghiệm thu | Gap |
|---|---|---|---|
| R5 adapter CLI và artifact lịch sử | Đã triển khai, chưa nối web; có artifact tự khai COMPLETED | NOT VERIFIED cho thực nghiệm hiện tại | Không tái thực thi, chưa xác minh toàn bộ provenance/worksheet |
| R5 Compare web | Triển khai một phần | FAIL theo yêu cầu case-aligned | Bảng tĩnh NOT_RUN/NO_TIMING, không API comparison, không evidence từng case |
| R5 cùng tập case manual/T18/ZAP | Thiếu | NOT VERIFIED | Chưa có join canonical case_id, fixture/policy/version/run |
| R8 timing CLI | Đã triển khai, chưa hiện web | NOT VERIFIED cho demo hiện tại | Có timing lưu lịch sử; chưa chứng minh cùng cohort và cách đo giữa phương pháp |
| R8 TP/FP/FN và benchmark | Thiếu trong bộ tổng hợp đã kiểm tra | NOT VERIFIED | Không ground-truth manifest/case-level confusion matrix |
| ZAP chạy mới trên S01/Run #2 | Bị chặn bởi điều kiện thực nghiệm | NOT_RUN | Không có phê duyệt ZAP mới, chưa xác minh reviewed context, role set, auth/scope cho S01 |

Không suy ra chưa có backend chỉ từ UI. Không dùng code/tests mock làm bằng chứng thực nghiệm. R1–R4/R6–R7 thuộc audit chuyên trách; báo cáo này chỉ xét phụ thuộc stable case IDs, policy, redaction và evidence.

## Nguồn chính đã đọc

Đường dẫn dưới đây tương đối với workspace nói trên:

- `tools/authorization-lab/src/authz_lab/evaluation/comparison.py`: `_parse_manual_worksheet`, `_load_verification_counts`, `build_final_comparison`, `write_comparison`.
- `tools/authorization-lab/src/authz_lab/evaluation/timing.py`: `load_timing_evidence`, `_validate_timing_payload`.
- `tools/authorization-lab/src/authz_lab/evaluation/cli.py`: orchestration có thể thực thi ZAP; tuyệt đối không gọi từ web để lấy comparison.
- `tools/authorization-lab/src/authz_lab/zap/runner.py`: `_build_scan_report` dòng 179+, runner dòng 420+, gate chain dòng 463–558.
- `tools/authorization-lab/src/authz_lab/zap/context.py`: private file mode 0600 dòng 136, reviewed 3/5-role set dòng 187, exact include regex dòng 249+, auth state, history quiescence/snapshot/delta; `MAX_MESSAGES=1000` là giới hạn đọc history, không tự coi là hard request cap cho scan.
- `tools/authorization-lab/src/authz_lab/zap/allowlist.py`: manifest local-only, GET-only, exact pairs, duplicate rejection.
- `tools/authorization-lab/src/authz_lab/verification/manual_verifier.py`: verifier là chương trình tự fetch owner/cross responses; tên manual không chứng minh người thực hiện benchmark thủ công.
- `tools/authorization-lab/src/authz_lab/fixtures/manual_sample_cases.json`: M-01…M-07, gồm controls/public observation, chưa ánh xạ ID case web.
- `tools/authorization-lab/tests/evaluation/test_comparison.py`, `tests/zap/test_runner.py`, `test_context.py`, `test_allowlist.py`: có test contracts/gates; không chạy trong audit này.
- `frontend/src/App.tsx:86`: bốn hàng tĩnh Custom CLI/Manual/ZAP/Disposable BFLA, NOT_RUN và NO_TIMING; lời dẫn có phân biệt artifacts ngoài web.
- `frontend/src/api.ts`: chưa có comparison type/fetch; có Run/Result/Finding và external jobs riêng.
- `backend/app/api/workflow_routes.py`, `workflow_schemas.py`, `external_lab_routes.py`: chưa thấy comparison endpoint trong luồng được audit; external read-only bridge không đồng nghĩa comparison importer.
- `audit-final/requirements-traceability.md`, `audit-final/web-demo-e2e-recovered-s01-qa.md`: R5 web NOT_RUN; Run #2 QA lịch sử ghi 2 identity/1 role, chưa đạt gate 3/5 roles. Không tái xác minh DB/browser.

## Artifact hiện có và giới hạn bằng chứng

Chỉ trích metadata whitelist, không xuất body/resource paths. Đây là nội dung file lưu, không phải fresh execution hoặc chứng thực độc lập tác giả/thời điểm chạy.

| Artifact | Metadata quan sát |
|---|---|
| `results/week4_comparison_final.json` | CLI MEASURED, 12 cases, 2032.298 ms; manual COMPLETED_NO_TIMING, 2 confirmed; ZAP COMPLETED, finding_count 15; BFLA EXECUTED, DENIED_CONTROL, 2 cases |
| `results/zap/zap_access_control_report.json` | schema 3, COMPLETED, scan_result_count 15; 5 ILLEGAL rows; known_bola_count 2. Metadata chứa context/authenticated_users/quiescence/baseline/seed_delta/scan_delta/completion |
| `results/zap/zap_run_status.json` | schema 3, COMPLETED |
| `results/zap-debug-20261030-01/zap/{zap_run_status,zap_access_control_report}.json` | NOT_RUN |
| `results/zap-debug-20261030-02/zap/{zap_run_status,zap_access_control_report}.json` | COMPLETED, report 15 rows |
| `results/zap/zap_bootstrap_readiness.json` | BOOTSTRAP_REQUIRES_OPERATOR_AUTH_AND_RESET; khác status bootstrap hiện được comparison.py nhận biết |
| `results/rerun-week3/week3_script_timing.json` | MEASURED, 12 cases, 2032.298 ms |
| `results/week3_script_timing.json` | MEASURED, 12 cases, 1990.362 ms; không trộn hai timing |
| `results/{,rerun-week3/}week3_manual_verification.json` | Mỗi file 4 records: 2 CONFIRMED_USER_TO_USER_BOLA, 2 POLICY_DEPENDENT_ADMIN_ACCESS; đây là artifact verifier tự động |
| `results/week3_comparison.json` | manual COMPLETED nhưng elapsed_minutes null |
| `results/rerun-week3/week3_comparison.json` | manual PENDING_HUMAN_MEASUREMENT |

Không tìm thấy worksheet trong `results/` được liệt kê. Không thể xác minh lại 7 quan sát thủ công từ summary. Các trạng thái khác nhau có thể thuộc các lần chạy khác nhau; chưa đủ lineage để gọi là mâu thuẫn thực nghiệm. Không gán lịch sử CLI/ZAP cho Run #2. 15 scan rows không phải 15 lỗ hổng; 5 ILLEGAL không tự chứng minh protected-field BOLA hay TP.

SHA-256 được tính trong audit:

| File | SHA-256 |
|---|---|
| `results/zap/zap_access_control_report.json` | `20c550584f241af4aa142eb4e440dbdeb544407a88057d8b396427060a16d006` |
| `results/zap/zap_run_status.json` | `f9f78d3cbc6cb6ee332c62b55054d0d263ec56ff8c32c2d02c4e3c85018ae620` |
| `results/week4_comparison_final.json` | `7996043e9f8e4f04d9537c4dd00635eff79a59f94d5ebfa7f91be4b8aef3360b` |
| `results/rerun-week3/week3_script_timing.json` | `77326c7fe795e8ceeefdd5678c21487919cdeeb091fbc85f2ef4e7c9d2dc22bd` |
| `results/week3_manual_verification.json` | `f1dd6f13daac20a6b244a51fde1b65b3c401b908587962b44b767cf2354b5227` |
| `audit-final/web-demo-e2e-recovered-s01-qa.md` | `52ea1decbd1892ba0a50b018f9b07e9781589f08e2a9c978d478b7d4aff3a5b8` |

Hash chứng minh byte được đọc, không chứng minh thực nghiệm đúng.

## Gap cụ thể

1. `comparison.py` mặc định 12 cases, 2 BOLA và chuỗi khẳng định hidden exposure ngay khi không có functional artifact. `_load_verification_counts` cũng fallback 2 khi không tìm thấy verification. TIMING_NOT_AVAILABLE không làm các số này thành bằng chứng. Cần null/unknown khi thiếu nguồn.
2. Counts functional chỉ được load khi timing AVAILABLE: functional evidence và timing đang bị gắn sai phụ thuộc. Legacy `script_timing_path` tự dựng AVAILABLE không qua validator đầy đủ của timing.py.
3. Manual parser yêu cầu đúng 7 IDs nhưng bỏ endpoint/auth/expected khi parse, xác nhận bằng substring “BOLA confirmed”; không có artifact/hash/operator/run/fixture/policy để kiểm chứng hoặc join. Timing nhận float nhưng chưa chặn NaN/inf/âm; partial timing bị gộp vào no-timing.
4. ZAP `_build_scan_report` hardcode hai known paths/count, so sánh theo path thay vì actor × role × owner × policy; ILLEGAL là kết quả access-rule, không bảo đảm protected-field match. `assessment_id` tĩnh không phải execution ID duy nhất.
5. `build_final_comparison` nhánh ZAP còn lại mặc định COMPLETED nếu thiếu status; bootstrap RESET lịch sử không khớp nhánh QUIESCE hiện tại. BFLA bất kỳ dict được coi EXECUTED. Cần schema/status validation fail-closed cho import, không suy status từ sự hiện diện file.
6. Không có case-aligned TP/FP/FN, ground truth version hoặc denominator gồm cases thực sự chạy. Không được biến NOT_RUN, UNKNOWN, invalid baseline, skipped thành TN/FN.
7. Web không có nguồn comparison đã xác minh; nhãn NO_TIMING trên UI khác TIMING_NOT_AVAILABLE/COMPLETED_NO_TIMING. BFLA là experiment riêng, không trộn vào GET BOLA cohort.

## Thiết kế comparison đề xuất

Một case manifest bất biến theo cohort: `cohort_id`, `case_id`, operation template/method, actor alias/role, owner alias/category, fixture version/hash, policy ID/version/expected decision, ground-truth label/version/reviewer, snapshot reference. Case_id là opaque ID từ manifest không chứa raw resource ID/token và không đổi giữa các phương pháp. Thay fixture/policy tạo cohort/version mới; không sửa snapshot lịch sử. ID case web cũ được ánh xạ bằng mapping artifact có version, không rewrite Run #2.

Mỗi method observation: `case_id`, `method`, `execution_id`, `source_run_id` khi thực sự liên kết, execution status, conclusion, reason codes, tool/version/operator alias, timestamps nếu có, scope/cohort hash, baseline validity, protected-field comparison booleans, artifact reference/hash. Không nhập body/secret/raw identifier hoặc arbitrary filesystem paths từ browser. Evidence index chứa từng case → observation → artifact/hash.

Tách `execution_status` (NOT_RUN/COMPLETED/BLOCKED/INVALID), `conclusion` và `timing_status`. Manual chưa có quan sát: PENDING_HUMAN_MEASUREMENT; hoàn tất quan sát nhưng không bấm giờ: COMPLETED_NO_TIMING; thiếu timing tự động: TIMING_NOT_AVAILABLE. Không ghi 0 cho dữ liệu thiếu. Chỉ tính TP/FP/FN/TN khi có ground truth độc lập, valid execution, outcome quyết định và đúng cohort; công bố exclusions và denominator. Trường hợp mơ hồ là unscored. ZAP ILLEGAL giữ nguyên semantics, không tự map thành CONFIRMED BOLA.

Export dự kiến: `comparison.csv`, `comparison.md`, evidence index JSON, từng row case × method; summary chỉ cộng từ rows hợp lệ. Timing so sánh cùng cohort và nêu rõ bao gồm setup/auth/controls hay chỉ execution; không suy tốc độ từ timestamp summary cũ.

## Ticket có thể triển khai

| Ticket | Files đích | Dependencies | Acceptance |
|---|---|---|---|
| CMP-01 P0: bỏ số mặc định và validate adapters | `tools/authorization-lab/src/authz_lab/evaluation/comparison.py`, `timing.py`, `tests/evaluation/test_comparison.py` | Không | Không input → null counts/no exposure claim; functional complete không timing vẫn giữ kết quả; reject missing/unknown/bootstrap status, malformed BFLA; NaN/inf/âm bị từ chối; giữ legacy artifact nguyên trạng |
| CMP-02 P0: canonical cohort/case manifest | mới `tools/authorization-lab/src/authz_lab/evaluation/case_manifest.py`, tests tương ứng; web matrix DTO trong `backend/app/api/workflow_schemas.py` | Ticket stable case IDs của Matrix; CMP-01 | Cùng manifest cho cả 3 methods; đổi role/owner/policy đổi version; unknown/duplicate case rejected; Run #2 chỉ có mapping bổ sung, không rewrite |
| CMP-03 P1: provenance + manual/ZAP case adapters | mới `evaluation/observations.py`; `comparison.py`, `zap/runner.py`, manual fixture schema | CMP-02 | Same path khác actor không bị gộp; thiếu worksheet/source hash → chưa verified; không lấy verifier tự động làm human benchmark; ZAP ILLEGAL không thành confirmed; import lịch sử hiển thị nguồn và unlinked run rõ |
| CMP-04 P1: ground truth, metrics, exports | mới `evaluation/metrics.py`, `evaluation/exports.py`, tests; `comparison.py` | CMP-03; QA review ground truth | Dataset có TP/FP/FN/TN/NOT_RUN/INVALID/UNKNOWN kiểm đúng denominator; unsupported negatives không được tính; CSV/MD/evidence index cùng case IDs/hashes, không raw IDs/secret; công bố scope/timing exclusions |
| CMP-05 P1: API đọc comparison đã xác minh | mới `backend/app/services/comparison_evidence.py`, `backend/app/api/comparison_routes.py`, register router, DTO/tests | CMP-03; redacted run DTO từ Matrix | Web không import/call CLI; read authenticated scoped DTO từ artifact store cố định; reject traversal/cross-project/schema/hash mismatch; không side effect lab/queue; stale cohort không tự join current run |
| CMP-06 P1: Compare UI tối giản | `frontend/src/App.tsx`, `api.ts`, tests mới comparison | CMP-05 | Chọn cohort/run → case table Manual/T18/ZAP, source badge, NOT_RUN reason, evidence link, coverage/timing rõ; no fabricated zero; không nút auto ZAP/BFLA; labels nhất quán; fixture test chứa historical completed và current unexecuted |
| CMP-07 P2: acceptance thực nghiệm có kiểm soát | runbook mới trong `docs/`, report/evidence index ở output đã được duyệt; tests ZAP hiện có bổ sung khi được giao | CMP-04/06; phê duyệt explicit riêng; QA manual benchmark | 3/5-role reviewed context, 0600, fingerprint attestation, exact regex/GET scope, verified auth, history stable, request limits được review; thiếu bất kỳ gate → NOT_RUN. Browser E2E chứng minh table nguồn thật; QA ký cohort/ground truth, không coi mocked tests là lab proof |

Request limits là gate phải kiểm chứng riêng trước chạy mới; không suy rằng MAX_MESSAGES hoặc hậu kiểm history đã là cap chặn request tại thời điểm gửi. Không tạo/sửa context hay credentials giả. Giữ độc lập CLI/web và BFLA; không thêm write vào GET runner.

## Kiểm chứng audit và phần còn lại

Đã thực hiện git HEAD/status, đọc source/tests và metadata whitelist của artifact, tính hash các nguồn trên; không thực thi tests hay runtime. Không có automation nào của bot khi kiểm tra. Bằng chứng lịch sử tồn tại nhưng comparison demo R5/R8 hiện tại chưa nghiệm thu. Cần triển khai tickets, QA mapping/ground truth, rồi mới chạy acceptance được duyệt. Trạng thái tổng thể PARTIAL; full demo NOT VERIFIED.
