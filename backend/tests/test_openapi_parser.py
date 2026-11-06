from backend.app.scanner.openapi.parser import parse_openapi_json


def test_openapi_honors_operation_security_override_and_get_only() -> None:
    inventory = parse_openapi_json({
        "openapi": "3.0.3",
        "security": [{"bearerAuth": []}],
        "paths": {
            "/books/{id}": {
                "parameters": [{"name": "id", "in": "path"}],
                "get": {"operationId": "readBook", "security": []},
                "post": {"operationId": "changeBook"},
            }
        },
    })

    assert len(inventory) == 1
    assert inventory[0].security_mode == "none"
    assert inventory[0].path_parameters == ("id",)
