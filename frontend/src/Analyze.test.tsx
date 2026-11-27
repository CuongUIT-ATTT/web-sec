import { afterEach, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { Evidence } from "./App";
import type { Result, ResultEvidence } from "./api";
afterEach(cleanup);
const evidence: ResultEvidence = { schema_version: 1, run_id: 2, case_key: "operation:1:resource:1:actor:2", actor_identity_id: 2, owner_identity_id: 1, owner_control_valid: true, owner_http_status: 200, owner_execution_status: "COMPLETED_RESPONSE", policy_id: 1, policy_version: 7, policy_decision: "DENY", policy_resolution: "RESOLVED", actor_resource_matches: true, restricted_fields_match_owner: true };
const result = (conclusion: string): Result => ({ case_key: evidence.case_key, execution_status: "COMPLETED_RESPONSE", authorization_conclusion: conclusion, reason_codes: ["evidence.synthetic"], http_status: 200, response_metadata: { evidence } });
it.each([
  ["CONFIRMED_VIOLATION", "CONFIRMED — policy DENY"],
  ["POLICY_CONSISTENT_CASE", "ALLOW sharing không phải vi phạm"],
  ["INVALID_TEST", "owner baseline không hợp lệ"],
  ["BLOCKED_POLICY_CONFLICT", "policy xung đột"],
  ["INSUFFICIENT_EVIDENCE", "chưa đủ căn cứ"],
  ["NOT_EVALUATED", "chưa có quan sát đủ"],
])("explains %s without inferring from HTTP", (conclusion, explanation) => {
  render(<Evidence result={result(conclusion)} />);
  expect(screen.getByText(new RegExp(explanation))).toBeTruthy();
  expect(screen.getByText(/metadata lịch sử/)).toBeTruthy();
  expect(screen.getByText(/identity-2 \/ identity-1/).textContent).toContain("UNAVAILABLE");
});
it("renders v2 aliases and typed checks only", () => {
  const row = result("CONFIRMED_VIOLATION");
  row.response_metadata.evidence = { ...evidence, schema_version: 2, actor_role: "reader", owner_role: "owner", ownership: "cross-role", protected_fields: [{ alias: "protected-1", owner_present: true, actor_present: false, owner_type: "dict", actor_type: null, matches_owner: false }] };
  render(<Evidence result={row} />);
  expect(screen.getByText(/protected-1: owner true/).textContent).toContain("actor false");
  expect(screen.getByText(/identity-2 \/ identity-1/).textContent).toContain("cross-role");
});
it("does not invent missing evidence", () => {
  const row = result("CONFIRMED_VIOLATION"); row.response_metadata.evidence = null;
  render(<Evidence result={row} />);
  expect(screen.getByText(/UNAVAILABLE/)).toBeTruthy();
});
