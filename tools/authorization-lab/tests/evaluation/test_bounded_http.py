"""Integration uses only an ephemeral numeric-loopback server, never lab."""
import asyncio
from dataclasses import replace
import json
import pytest
from authz_lab.evaluation.bounded_http import BoundedHTTP
from authz_lab.evaluation.adapter_journal import ExecutionJournal
from authz_lab.evaluation.bounded_adapter import BoundedAdapter
from tests.evaluation.test_bounded_adapter import setup, BOOK, IDENTITIES


def test_server_caps_and_statuses(tmp_path, monkeypatch):
    # Environment proxy settings cannot reroute the numeric direct connection.
    for key in ('HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'ALL_PROXY'):
        monkeypatch.setenv(key, 'http://192.0.2.1:1')
    async def scenario(status=200, cap=4, phase=(2, 1, 1)):
        count = 0
        async def handler(reader, writer):
            nonlocal count
            await reader.readuntil(b'\r\n\r\n')
            count += 1
            body = json.dumps((IDENTITIES + [BOOK, BOOK])[min(count-1, 3)]).encode()
            writer.write(f'HTTP/1.1 {status} Test\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nLocation: /me\r\n\r\n'.encode() + body)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        server = await asyncio.start_server(handler, '127.0.0.1', 0)
        async with server:
            origin = f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}'
            m, maps, ps, a = setup()
            a = replace(a, origin=origin, total_cap=cap, phase_caps=phase)
            transport = BoundedHTTP(origin, a.paths, {'a': 'Bearer synthetic', 'b': 'Bearer synthetic'}, cap=cap)
            adapter = BoundedAdapter(m, maps, ps, a, clock=lambda: 1)
            result = await adapter.run(transport, journal=ExecutionJournal(tmp_path / f'{status}-{cap}-{phase}', a.execution_id))
            assert count == transport.count == sum(result['counts'])
            assert count <= cap and not transport.active
            assert result['counts'][0] <= phase[0]
            if status != 200:
                assert result['evidence'][0]['conclusion'] != 'CONFIRMED'
            return result
    for status in (200, 204, 301, 302, 303, 307, 308, 401, 403, 500):
        asyncio.run(scenario(status))
    assert asyncio.run(scenario(cap=2))['stop'] == 'CAP_EXHAUSTED'
    assert asyncio.run(scenario(phase=(1, 1, 1)))['counts'] == (1, 0, 0)


@pytest.mark.parametrize('mode', ['chunked', 'gzip', 'oversize', 'headers', 'read', 'disconnect', 'error'])
def test_bounds(mode):
    async def scenario():
        count = 0
        handlers = set()
        async def handler(reader, writer):
            nonlocal count
            task = asyncio.current_task()
            handlers.add(task)
            try:
                await reader.readuntil(b'\r\n\r\n')
                count += 1
                if mode == 'headers':
                    await reader.read()
                    return
                if mode == 'disconnect':
                    return
                extra = {'chunked': 'Transfer-Encoding: chunked\r\n', 'gzip': 'Content-Encoding: gzip\r\n'}.get(mode, '')
                length = 10000 if mode == 'oversize' else 20
                writer.write(f'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n{extra}Content-Length: {length}\r\n\r\n'.encode())
                if mode == 'error':
                    writer.write(b'{"error":"denied"}   ')
                await writer.drain()
                await reader.read()
            finally:
                writer.close()
                await writer.wait_closed()
                handlers.discard(task)
        server = await asyncio.start_server(handler, '127.0.0.1', 0)
        async with server:
            origin = f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}'
            m, maps, ps, a = setup()
            a = replace(a, origin=origin, timeout=.1)
            transport = BoundedHTTP(origin, a.paths, {'a': 'synthetic', 'b': 'synthetic'}, cap=4, timeout=.05, body_limit=100)
            result = await BoundedAdapter(m, maps, ps, a, clock=lambda: 1).run(transport)
            assert count == 4 and transport.count == 4 and not transport.active
            assert result['evidence'][0]['conclusion'] != 'CONFIRMED'
            if handlers:
                await asyncio.wait_for(asyncio.gather(*list(handlers)), .5)
    asyncio.run(scenario())


def test_rejections():
    for kwargs in ({'proxy': 'http://127.0.0.1'}, {'retries': 1}):
        with pytest.raises(ValueError):
            BoundedHTTP('http://127.0.0.1:1', ['/me'], {'a': 'x'}, cap=1, **kwargs)
    async def scenario():
        t = BoundedHTTP('http://127.0.0.1:1', ['/me'], {'a': 'x'}, cap=1)
        for url, kw in [('http://127.0.0.1:2/me', {}), ('http://127.0.0.1:1/me', {'retries': 1}), ('http://127.0.0.1:1/me', {'follow_redirects': True})]:
            with pytest.raises(ValueError):
                await t.get(url, principal='a', **kw)
        assert t.count == 0
    asyncio.run(scenario())


@pytest.mark.parametrize('stage', ['get', 'read', 'close'])
def test_cancel_receipt_and_recovery(tmp_path, stage):
    async def scenario():
        entered = asyncio.Event()
        class Response:
            status = 200
            content_type = 'application/json'
            async def read(self, n):
                if stage == 'read':
                    entered.set()
                    await asyncio.Future()
                return b''
            async def close(self):
                if stage == 'close':
                    entered.set()
                    await asyncio.Future()
        class Transport:
            async def get(self, *args, **kwargs):
                if stage == 'get':
                    entered.set()
                    await asyncio.Future()
                return Response()
        m, maps, ps, a = setup()
        adapter = BoundedAdapter(m, maps, ps, a, clock=lambda: 1)
        journal = ExecutionJournal(tmp_path / stage, a.execution_id)
        task = asyncio.create_task(adapter.run(Transport(), journal=journal))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert adapter.terminal_receipt['state'] == 'CANCELLED'
        assert journal.recover()['counts'] == [1, 0, 0]
        with pytest.raises(FileExistsError):
            await BoundedAdapter(m, maps, ps, a, clock=lambda: 1).run(Transport(), journal=journal)
    asyncio.run(scenario())
    crash = ExecutionJournal(tmp_path / (stage + '-crash'), 'synthetic')
    crash.reserve()
    crash.write('ATTEMPTING', [1, 0, 0])
    assert crash.recover()['state'] == 'CRASH_RECOVERED'
    assert crash.recover()['counts'] == [1, 0, 0]
    with pytest.raises(FileExistsError):
        crash.reserve()


def test_real_socket_cancel(tmp_path):
    async def scenario():
        seen = asyncio.Event()
        closed = asyncio.Event()
        count = 0
        async def handler(reader, writer):
            nonlocal count
            try:
                await reader.readuntil(b'\r\n\r\n')
                count += 1
                writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 20\r\n\r\n')
                await writer.drain()
                seen.set()
                await reader.read()
            finally:
                writer.close()
                await writer.wait_closed()
                closed.set()
        server = await asyncio.start_server(handler, '127.0.0.1', 0)
        async with server:
            m, maps, ps, a = setup()
            origin = f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}'
            a = replace(a, origin=origin)
            t = BoundedHTTP(origin, a.paths, {'a': 'synthetic', 'b': 'synthetic'}, cap=4)
            adapter = BoundedAdapter(m, maps, ps, a, clock=lambda: 1)
            journal = ExecutionJournal(tmp_path / 'real-cancel', a.execution_id)
            task = asyncio.create_task(adapter.run(t, journal=journal))
            await asyncio.wait_for(seen.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await asyncio.wait_for(closed.wait(), 1)
            assert count == t.count == 1 and not t.active
            assert journal.recover()['state'] == 'CANCELLED'
    asyncio.run(scenario())


def test_process_crash_no_replay(tmp_path):
    import os
    import subprocess
    import sys
    path = tmp_path / 'killed-execution'
    code = '''import os, sys
from authz_lab.evaluation.adapter_journal import ExecutionJournal
j = ExecutionJournal(sys.argv[1], sys.argv[2])
j.reserve()
j.write('ATTEMPTING', [1, 0, 0])
os._exit(73)
'''
    m, maps, ps, a = setup()
    result = subprocess.run([sys.executable, '-c', code, str(path), a.execution_id],
                            env=dict(os.environ), capture_output=True, timeout=5)
    assert result.returncode == 73
    journal = ExecutionJournal(path, a.execution_id)
    assert journal.recover()['state'] == 'CRASH_RECOVERED'
    class NoDispatch:
        async def get(self, *args, **kwargs):
            raise AssertionError('Replay attempted')
    with pytest.raises(FileExistsError):
        asyncio.run(BoundedAdapter(m, maps, ps, a, clock=lambda: 1).run(NoDispatch(), journal=journal))
