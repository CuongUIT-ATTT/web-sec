"""Stable non-sensitive finding grouping for repeated reproductions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from backend.app.domain.contracts import AuthorizationConclusion


@dataclass(frozen=True)
class FindingKey:
    project_id: int
    method: str
    path: str
    policy_id: int
    policy_version: int
    resource_type_id: int
    resource_pointer: str
    restricted_pointers: tuple[str, ...]
    conclusion: AuthorizationConclusion

    def fingerprint(self) -> str:
        payload = {
            "conclusion": self.conclusion,
            "method": self.method.upper(),
            "path": self.path,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "project_id": self.project_id,
            "resource_pointer": self.resource_pointer,
            "resource_type_id": self.resource_type_id,
            "restricted_pointers": sorted(self.restricted_pointers),
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
