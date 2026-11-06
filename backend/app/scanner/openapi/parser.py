"""Conservative OpenAPI JSON parser for the declared MVP subset."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SUPPORTED_METHODS = {"get"}


@dataclass(frozen=True)
class OperationInventory:
    operation_id: str
    method: str
    path: str
    path_parameters: tuple[str, ...]
    security_mode: str
    diagnostics: tuple[str, ...]


class OpenApiError(ValueError):
    """Raised when the submitted OpenAPI JSON document is outside the MVP subset."""


def parse_openapi_json(spec: Any) -> list[OperationInventory]:
    if not isinstance(spec, dict) or not isinstance(spec.get("openapi"), str) or not isinstance(spec.get("paths"), dict):
        raise OpenApiError("Cần OpenAPI JSON có trường openapi và paths.")
    global_security = spec.get("security")
    inventory: list[OperationInventory] = []
    for path, path_item in spec["paths"].items():
        if not isinstance(path, str) or not path.startswith("/") or not isinstance(path_item, dict):
            continue
        shared_parameters = path_item.get("parameters", [])
        shared_parameters = shared_parameters if isinstance(shared_parameters, list) else []
        for method, operation in path_item.items():
            if method.lower() not in SUPPORTED_METHODS or not isinstance(operation, dict):
                continue
            parameters = [*shared_parameters, *(operation.get("parameters", []) if isinstance(operation.get("parameters", []), list) else [])]
            names = tuple(
                parameter["name"]
                for parameter in parameters
                if isinstance(parameter, dict) and parameter.get("in") == "path" and isinstance(parameter.get("name"), str)
            )
            security = operation["security"] if "security" in operation else global_security
            security_mode = "none" if security == [] else "required" if isinstance(security, list) and security else "unspecified"
            diagnostics: list[str] = []
            if "$ref" in operation:
                diagnostics.append("Operation $ref chưa được hỗ trợ trong MVP.")
            if "requestBody" in operation:
                diagnostics.append("Request body không được thực thi trong MVP GET-only.")
            inventory.append(OperationInventory(
                operation_id=str(operation.get("operationId") or f"GET:{path}"),
                method="GET",
                path=path,
                path_parameters=names,
                security_mode=security_mode,
                diagnostics=tuple(diagnostics),
            ))
    return sorted(inventory, key=lambda item: (item.path, item.operation_id))
