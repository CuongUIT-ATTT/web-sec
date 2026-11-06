from pathlib import Path
import ipaddress

import httpx
import pytest

from backend.app.core.settings import Settings
from backend.app.domain.contracts import ExecutionStatus
from backend.app.scanner.execution import http_client


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_path=Path("test.sqlite3"),
        admin_password="password",
        session_secret="s" * 32,
        secret_encryption_key="unused",
        target_networks=(ipaddress.ip_network("127.0.0.1/32"),),
        allowed_ports=frozenset({5000}),
        max_response_bytes=32,
        default_timeout_seconds=5.0,
    )


@pytest.mark.asyncio
async def test_http_response_status_is_completed_even_for_403(monkeypatch, settings: Settings) -> None:
    class Client:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        def stream(self, method, url, headers):
            assert method == "GET"
            assert headers["Authorization"] == "Bearer isolated-token"
            assert self.kwargs["follow_redirects"] is False
            return Response()

    class Response:
        status_code = 403
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def aiter_bytes(self):
            yield b'{"error":"denied"}'

    monkeypatch.setattr(http_client.httpx, "AsyncClient", Client)

    observation = await http_client.get_json(base_url="http://127.0.0.1:5000", api_path="/books/1", bearer_token="isolated-token", settings=settings)

    assert observation.execution_status == ExecutionStatus.COMPLETED_RESPONSE
    assert observation.status_code == 403
    assert observation.json_body == {"error": "denied"}


@pytest.mark.asyncio
async def test_client_marks_oversized_body_without_storing_content(monkeypatch, settings: Settings) -> None:
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        def stream(self, method, url, headers):
            return Response()

    class Response:
        status_code = 200
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def aiter_bytes(self):
            yield b"x" * 100

    monkeypatch.setattr(http_client.httpx, "AsyncClient", Client)

    observation = await http_client.get_json(base_url="http://127.0.0.1:5000", api_path="/books/1", bearer_token=None, settings=settings)

    assert observation.execution_status == ExecutionStatus.BODY_TRUNCATED
    assert observation.json_body is None
    assert observation.body_length == 32


@pytest.mark.asyncio
async def test_redirect_is_observed_once_and_never_followed(monkeypatch, settings: Settings) -> None:
    calls = 0

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        def stream(self, method, url, headers):
            nonlocal calls
            calls += 1
            return Response()

    class Response:
        status_code = 302
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def aiter_bytes(self): yield b"{}"

    monkeypatch.setattr(http_client.httpx, "AsyncClient", Client)
    observation = await http_client.get_json(base_url="http://127.0.0.1:5000", api_path="/books/1", bearer_token=None, settings=settings)
    assert observation.execution_status == ExecutionStatus.COMPLETED_RESPONSE
    assert observation.status_code == 302
    assert calls == 1
