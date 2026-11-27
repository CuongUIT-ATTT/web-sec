"""Independent synthetic acceptance; only tmp_path and dedicated loopback."""
import asyncio
import json
from dataclasses import replace
import pytest
from authz_lab.evaluation.adapter_journal import ExecutionJournal
from authz_lab.evaluation.bounded_adapter import BoundedAdapter
from tests.evaluation.test_bounded_adapter import setup, adapter, Transport, Response, IDENTITIES, BOOK, run


def test_403_disclosure_is_evaluated():
    response = Response(BOOK)
    response.status = 403
    result, _ = run(IDENTITIES + [BOOK, response])
    assert result['evidence'][0]['conclusion'] == 'CONFIRMED'
    assert result['evidence'][0]['body_observation']['http_status'] == 403


def test_journal_temp_symlink_cannot_overwrite(tmp_path):
    target = tmp_path / 'preserved'
    target.write_text('preserve')
    path = tmp_path / 'journal'
    journal = ExecutionJournal(path, 'synthetic')
    journal.reserve()
    path.with_name('journal.next').symlink_to(target)
    journal.write('ATTEMPTING', [1, 0, 0])
    assert target.read_text() == 'preserve'


def test_wholebody_utf8_and_comparison():
    baseline = dict(BOOK, timestamp='old', note='Tiếng Việt', array=[1, 2])
    actor = dict(baseline, timestamp='new', array=[2, 1])
    result, _ = run(IDENTITIES + [baseline, actor])
    obs = result['evidence'][0]['body_observation']
    assert obs['complete'] is True and obs['json_valid'] is True
    assert obs['bytes_observed'] == len(json.dumps(actor).encode('utf-8'))
    assert obs['wholebody_equal'] is False
    assert obs['normalization'] == 'json-typed-v1-no-fields-ignored'
    assert result['evidence'][0]['conclusion'] == 'CONFIRMED'
    assert 'CANARY' not in json.dumps(result) and 'Tiếng' not in json.dumps(result)


def test_recovery_rejects_wrong_execution(tmp_path):
    path = tmp_path / 'correlation'
    j = ExecutionJournal(path, 'first')
    j.reserve()
    j.write('COMPLETED', [0, 0, 0])
    before = path.read_bytes()
    with pytest.raises(ValueError):
        ExecutionJournal(path, 'different').recover()
    assert path.read_bytes() == before


def test_recovery_rejects_live_execution(tmp_path):
    path = tmp_path / 'live'
    j = ExecutionJournal(path, 'first')
    j.reserve()
    before = path.read_bytes()
    with pytest.raises(BlockingIOError):
        ExecutionJournal(path, 'first').recover()
    assert path.read_bytes() == before


@pytest.mark.parametrize('index', [1, 2, 3, 4])
def test_cancel_each_http_phase_reconciles(tmp_path, index):
    from authz_lab.evaluation.bounded_http import BoundedHTTP
    async def scenario():
        reached, closed = asyncio.Event(), asyncio.Event()
        server_count = 0
        completed_responses = 0
        async def handler(reader, writer):
            nonlocal server_count, completed_responses
            try:
                await reader.readuntil(b'\r\n\r\n')
                server_count += 1
                current = server_count
                if current == index:
                    reached.set()
                    await reader.read()  # deterministic pending headers checkpoint
                    closed.set()
                else:
                    raw = json.dumps((IDENTITIES + [BOOK, BOOK])[current-1]).encode()
                    writer.write(f'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(raw)}\r\n\r\n'.encode()+raw)
                    await writer.drain()
                    completed_responses += 1
            finally:
                writer.close()
                await writer.wait_closed()
        server = await asyncio.start_server(handler, '127.0.0.1', 0)
        async with server:
            m, maps, ps, a = setup()
            origin = f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}'
            a = replace(a, origin=origin)
            t = BoundedHTTP(origin, a.paths, {'a':'synthetic', 'b':'synthetic'}, cap=4)
            obj = BoundedAdapter(m, maps, ps, a, clock=lambda:1)
            j = ExecutionJournal(tmp_path/'cancel', a.execution_id)
            task = asyncio.create_task(obj.run(t, journal=j))
            await asyncio.wait_for(reached.wait(), 2)
            task.cancel()
            task.cancel()  # repeated cancellation at the same controlled boundary
            with pytest.raises(asyncio.CancelledError):
                await task
            await asyncio.wait_for(closed.wait(), 2)
            assert not task.cancel()  # terminal is idempotent
            receipt = j.recover()
            assert receipt['state'] == 'CANCELLED'
            assert sum(receipt['counts']) == server_count == t.count == index
            assert completed_responses == index-1 and not t.active
            assert 4-index == 4-sum(receipt['counts'])
    asyncio.run(scenario())


@pytest.mark.parametrize('data,ctype,complete,json_valid', [
    (b'{', 'application/json', True, False),
    (b'\xff', 'application/json', True, False),
    (b'{"x":1,"x":2}', 'application/json', True, False),
    (b'null', 'application/json', True, True),
    (b'<html>denied</html>', 'text/html', True, False),
    (b'x'*300, 'application/json', False, False),
])
def test_body_negative_observation(data, ctype, complete, json_valid):
    r = Response(BOOK)
    r.data, r.content_type = data, ctype
    result, _ = run(IDENTITIES+[BOOK, r], body_limit=128)
    obs = result['evidence'][0]['body_observation']
    assert obs['complete'] is complete and obs['json_valid'] is json_valid
    assert obs['bytes_observed'] <= 129
    assert result['evidence'][0]['conclusion'] == 'INCONCLUSIVE'
    assert r.closed


def test_utf8_actual_bytes_and_ordered_typed_comparison():
    r = Response(BOOK)
    r.data = json.dumps(dict(BOOK, note='Tiếng Việt'), ensure_ascii=False).encode()
    size = len(r.data)
    result, _ = run(IDENTITIES+[BOOK, r])
    obs = result['evidence'][0]['body_observation']
    assert obs['bytes_observed'] == size
    assert obs['shape_counts']['object'] == 2
    assert obs['wholebody_equal'] is False
    result, _ = run()
    assert result['evidence'][0]['body_observation']['wholebody_equal'] is True


def test_shared_policy_cannot_confirm():
    from authz_lab.evaluation.case_manifest import CaseManifest
    from authz_lab.evaluation.bounded_adapter import mapping_digest
    m, maps, ps, a = setup()
    case = replace(m.cases[0], expected_decision='ALLOW')
    m = CaseManifest.build([case])
    maps = (replace(maps[0], case_id=case.case_id),)
    a = replace(a, manifest_digest=m.content_digest, mapping_digest=mapping_digest(maps))
    t = Transport([Response(x) for x in IDENTITIES+[BOOK, BOOK]])
    result = asyncio.run(BoundedAdapter(m, maps, ps, a, clock=lambda:1).run(t))
    assert result['evidence'][0]['conclusion'] == 'INCONCLUSIVE'


@pytest.mark.parametrize('state', ['RESERVED', 'ATTEMPTING', 'RESPONSE_OBSERVED', 'RESULT_PERSISTED', 'COMPLETED'])
def test_interruption_recovery_preserves_counts_no_dispatch(tmp_path, state):
    m, maps, ps, a = setup()
    path = tmp_path/'interruption'
    j = ExecutionJournal(path, a.execution_id)
    j.reserve()
    if state != 'RESERVED':
        j.write(state, [2,1,1], 'f'*64 if state == 'COMPLETED' else None)
    j._release()  # isolated simulation of OS lock release on crash
    recovered = ExecutionJournal(path, a.execution_id).recover()
    assert recovered['state'] == ('COMPLETED' if state == 'COMPLETED' else 'CRASH_RECOVERED')
    assert recovered['counts'] == ([0,0,0] if state == 'RESERVED' else [2,1,1])
    if state == 'COMPLETED':
        assert recovered['content_digest'] == 'f'*64
    before = path.read_bytes()
    t = Transport([])
    with pytest.raises(FileExistsError):
        asyncio.run(BoundedAdapter(m, maps, ps, a, clock=lambda:1).run(t, journal=ExecutionJournal(path, a.execution_id)))
    assert t.calls == [] and path.read_bytes() == before


@pytest.mark.parametrize('mode', ['normal', 'cap', 'redirect', 'timeout', 'disconnect', 'scope', 'connection'])
def test_independent_reconciliation(tmp_path, mode):
    from authz_lab.evaluation.bounded_http import BoundedHTTP
    import os
    from pathlib import Path
    async def scenario():
        seen = written = headers = complete = 0
        handlers = set()
        async def handler(reader, writer):
            nonlocal seen, written
            handlers.add(asyncio.current_task())
            try:
                await reader.readuntil(b'\r\n\r\n')
                seen += 1
                if mode == 'timeout':
                    await reader.read()
                    return
                if mode == 'disconnect':
                    return
                raw = json.dumps((IDENTITIES+[BOOK,BOOK])[min(seen-1,3)]).encode()
                code = 302 if mode == 'redirect' else 200
                writer.write(f'HTTP/1.1 {code} Test\r\nContent-Type: application/json\r\nContent-Length: {len(raw)}\r\nLocation: /me\r\n\r\n'.encode()+raw)
                await writer.drain()
                written += 1
            finally:
                writer.close()
                await writer.wait_closed()
                handlers.discard(asyncio.current_task())
        server = await asyncio.start_server(handler, '127.0.0.1', 0)
        port = server.sockets[0].getsockname()[1]
        if mode == 'connection':
            server.close()
            await server.wait_closed()
        async with server:
            m, maps, ps, a = setup()
            a = replace(a, origin=f'http://127.0.0.1:{port}', total_cap=2 if mode=='cap' else 4, timeout=.2)
            t = BoundedHTTP(a.origin, ('/me',) if mode=='scope' else a.paths, {'a':'synthetic','b':'synthetic'}, cap=a.total_cap, timeout=.05)
            class Tracking:
                async def get(self, *args, **kw):
                    nonlocal headers
                    r = await t.get(*args, **kw)
                    headers += 1
                    original = r.read
                    async def read(n):
                        nonlocal complete
                        chunk = await original(n)
                        if chunk == b'':
                            complete += 1
                        return chunk
                    r.read = read
                    return r
            j = ExecutionJournal(tmp_path/'reconcile', a.execution_id)
            obj = BoundedAdapter(m, maps, ps, a, clock=lambda:1)
            result = await obj.run(Tracking(), journal=j)
            if handlers:
                await asyncio.wait_for(asyncio.gather(*list(handlers)), 1)
            receipt = j.recover()
            attempts = sum(result['counts'])
            blocked = attempts-t.count
            errors = t.count-headers
            assert attempts == blocked + errors + headers
            assert attempts == sum(receipt['counts']) <= a.total_cap
            assert t.count <= a.total_cap and not t.active
            assert seen == (0 if mode=='connection' else t.count)
            assert complete == (attempts if mode in ('normal','cap') else 2 if mode=='scope' else 0)
            row = dict(case_id='CMP07-QA-'+mode,planned=4,adapter_attempts=attempts,
                transport_reservations=t.count,client_headers=headers,client_complete_bodies=complete,
                scope_blocked=blocked,transport_errors=errors,server_requests=seen,
                server_responses_written=written,journal_attempts=sum(receipt['counts']),
                terminal_receipts=1,terminal=receipt['state'],cap=a.total_cap)
            directory = os.environ.get('CMP07_QA_RECORDS')
            if directory:
                Path(directory, 'reconcile-'+mode+'.json').write_text(json.dumps(row,indent=2))
    asyncio.run(scenario())


def test_cooperative_cancel_on_final_actor_is_terminal_cancelled(tmp_path):
    cancelled = False
    class Cancelling(Response):
        async def read(self, n):
            nonlocal cancelled
            cancelled = True
            return await super().read(n)
    obj = adapter()
    transport = Transport([Response(x) for x in IDENTITIES+[BOOK]]+[Cancelling(BOOK)])
    journal = ExecutionJournal(tmp_path/'final-cancel', obj.approval.execution_id)
    result = asyncio.run(obj.run(transport, cancelled=lambda:cancelled, journal=journal))
    assert result['stop'] == 'CANCELLED_OR_EXPIRED'
    assert obj.terminal_receipt['state'] == journal.recover()['state'] == 'CANCELLED'
    assert len(transport.calls) == 4


def test_predispatch_cancel_receipt_is_durable(tmp_path):
    obj = adapter()
    j = ExecutionJournal(tmp_path/'predispatch', obj.approval.execution_id)
    t = Transport([])
    result = asyncio.run(obj.run(t, cancelled=lambda:True, journal=j))
    assert result['stop'] == 'CANCELLED_OR_EXPIRED' and t.calls == []
    assert j.recover()['state'] == 'CANCELLED' and j.recover()['counts'] == [0,0,0]


def test_completion_cancellation_keeps_completed_observation(tmp_path):
    cancelled = False
    class CloseCancelling(Response):
        async def close(self):
            nonlocal cancelled
            await super().close()
            cancelled = True
    obj = adapter()
    t = Transport([Response(x) for x in IDENTITIES+[BOOK]]+[CloseCancelling(BOOK)])
    j = ExecutionJournal(tmp_path/'close-cancel', obj.approval.execution_id)
    result = asyncio.run(obj.run(t, cancelled=lambda:cancelled, journal=j))
    assert result['stop'] == 'CANCELLED_OR_EXPIRED'
    assert result['evidence'][0]['conclusion'] == 'CONFIRMED'
    assert result['envelope']['observations'][0]['execution_status'] == 'COMPLETED'
    assert j.recover()['state'] == 'CANCELLED'
    assert j.recover()['content_digest'] == result['content_digest']


def test_truncated_response_never_confirms():
    class Truncated(Response):
        async def read(self, n):
            if self.data:
                chunk, self.data = self.data[:10], b''
                return chunk
            raise ValueError('synthetic premature EOF')
    r = Truncated(BOOK)
    result, _ = run(IDENTITIES+[BOOK, r])
    obs = result['evidence'][0]['body_observation']
    assert obs['complete'] is False and obs['bytes_observed'] == 10
    assert result['evidence'][0]['conclusion'] == 'INCONCLUSIVE' and r.closed


@pytest.mark.parametrize('damage', ['empty', 'bad-count', 'wrong-id'])
def test_recovery_rejects_or_preserves_uncertainty(tmp_path, damage):
    path = tmp_path/'damaged'
    j = ExecutionJournal(path, 'synthetic')
    j.reserve()
    j._release()
    path.write_text('' if damage=='empty' else json.dumps(dict(execution_id='other' if damage=='wrong-id' else 'synthetic', counts=[-1,0,0])))
    if damage=='empty':
        assert j.recover()['state'] == 'CRASH_RECOVERED'
    else:
        before = path.read_bytes()
        with pytest.raises(ValueError):
            j.recover()
        assert path.read_bytes() == before


def test_journal_persistence_failure_cannot_replay(tmp_path, monkeypatch):
    import authz_lab.evaluation.adapter_journal as module
    path = tmp_path/'fsync-failure'
    j = ExecutionJournal(path, 'synthetic')
    j.reserve()
    before = path.read_bytes()
    original = module.os.fsync
    def fail(fd):
        raise OSError('synthetic disk failure')
    monkeypatch.setattr(module.os, 'fsync', fail)
    with pytest.raises(OSError):
        j.write('ATTEMPTING', [1,0,0])
    assert path.read_bytes() == before
    monkeypatch.setattr(module.os, 'fsync', original)
    assert ExecutionJournal(path, 'synthetic').recover()['state'] == 'CRASH_RECOVERED'
    with pytest.raises(FileExistsError):
        j.reserve()


def test_overflow_json_is_insufficient_evidence():
    r = Response(BOOK)
    r.data = b'{"id":"bookA","owner":"bob","nested":{"secret":"CANARY_PROTECTED_123"},"number":1e999}'
    result, _ = run(IDENTITIES+[BOOK,r])
    assert result['evidence'][0]['body_observation']['json_valid'] is False
    assert result['evidence'][0]['conclusion'] == 'INCONCLUSIVE'


def test_process_crash_during_real_http_no_replay(tmp_path):
    import sys
    async def scenario():
        seen, closed = asyncio.Event(), asyncio.Event()
        count = 0
        async def handler(reader, writer):
            nonlocal count
            try:
                await reader.readuntil(b'\r\n\r\n')
                count += 1
                seen.set()
                await reader.read()
            finally:
                writer.close()
                await writer.wait_closed()
                closed.set()
        server = await asyncio.start_server(handler, '127.0.0.1', 0)
        async with server:
            origin = f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}'
            path = tmp_path/'killed-io'
            code = '''import sys, asyncio
sys.path.insert(0, 'tools/authorization-lab')
from dataclasses import replace
from tests.evaluation.test_bounded_adapter import setup
from authz_lab.evaluation.bounded_adapter import BoundedAdapter
from authz_lab.evaluation.bounded_http import BoundedHTTP
from authz_lab.evaluation.adapter_journal import ExecutionJournal
m, maps, ps, a = setup()
a = replace(a, origin=sys.argv[1], timeout=30)
t = BoundedHTTP(a.origin, a.paths, {'a':'synthetic','b':'synthetic'}, cap=4, timeout=30)
asyncio.run(BoundedAdapter(m,maps,ps,a,clock=lambda:1).run(t,journal=ExecutionJournal(sys.argv[2],a.execution_id)))
'''
            proc = await asyncio.create_subprocess_exec(sys.executable,'-c',code,origin,str(path),
                stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
            try:
                await asyncio.wait_for(seen.wait(), 5)
            finally:
                if proc.returncode is None:
                    proc.kill()
                await asyncio.wait_for(proc.wait(), 5)
            await asyncio.wait_for(closed.wait(), 2)
            assert proc.returncode < 0 and count == 1
            m, maps, ps, a = setup()
            j = ExecutionJournal(path,a.execution_id)
            receipt = j.recover()
            assert receipt['state'] == 'CRASH_RECOVERED' and receipt['counts'] == [1,0,0]
            t = Transport([])
            with pytest.raises(FileExistsError):
                await BoundedAdapter(m,maps,ps,a,clock=lambda:1).run(t,journal=j)
            assert t.calls == [] and count == 1
    asyncio.run(scenario())


def test_interruption_after_atomic_terminal_replace_preserves_receipt(tmp_path, monkeypatch):
    j = ExecutionJournal(tmp_path/'terminal', 'synthetic')
    j.reserve()
    def fail():
        raise OSError('synthetic interruption after rename before directory sync')
    monkeypatch.setattr(j, '_sync_directory', fail)
    with pytest.raises(OSError):
        j.write('COMPLETED',[2,1,1],'f'*64)
    before = j.path.read_bytes()
    recovered = ExecutionJournal(j.path,'synthetic').recover()
    assert recovered['state'] == 'COMPLETED' and recovered['content_digest'] == 'f'*64
    assert j.path.read_bytes() == before
    # Process interruption proof only; no assertion about power-loss durability.
