import pytest

from backend.app.scanner.classification.json_pointer import JsonPointerError, resolve_pointer, validate_pointer


def test_resolves_object_array_and_escaped_tokens() -> None:
    document = {"data": {"a/b": [{"~key": "value"}]}}

    assert resolve_pointer(document, "/data/a~1b/0/~0key") == "value"


@pytest.mark.parametrize("pointer", ["", "$..id", "/data//id", "/data/~2id"])
def test_rejects_unsupported_pointer_syntax(pointer: str) -> None:
    with pytest.raises(JsonPointerError):
        validate_pointer(pointer)
