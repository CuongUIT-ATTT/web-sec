"""Small RFC 6901 JSON Pointer implementation; JSONPath is intentionally unsupported."""

from __future__ import annotations

from typing import Any


class JsonPointerError(ValueError):
    """Raised for unsupported or unresolved JSON Pointers."""


def validate_pointer(pointer: str) -> str:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise JsonPointerError("Chỉ hỗ trợ JSON Pointer tuyệt đối RFC 6901, ví dụ /data/id.")
    if "//" in pointer:
        raise JsonPointerError("JSON Pointer không được có phân đoạn rỗng.")
    for segment in pointer.split("/")[1:]:
        if "~" in segment:
            index = 0
            while index < len(segment):
                if segment[index] == "~":
                    if index + 1 >= len(segment) or segment[index + 1] not in "01":
                        raise JsonPointerError("JSON Pointer có escape không hợp lệ.")
                    index += 2
                else:
                    index += 1
    return pointer


def _unescape(segment: str) -> str:
    return segment.replace("~1", "/").replace("~0", "~")


def resolve_pointer(document: Any, pointer: str) -> Any:
    validate_pointer(pointer)
    value = document
    for raw_segment in pointer.split("/")[1:]:
        segment = _unescape(raw_segment)
        if isinstance(value, dict) and segment in value:
            value = value[segment]
        elif isinstance(value, list) and segment.isdigit() and int(segment) < len(value):
            value = value[int(segment)]
        else:
            raise JsonPointerError(f"Không tìm thấy JSON Pointer: {pointer}")
    return value
