"""Synthetic only: no lab, DNS, network, process or credential access."""
import asyncio
from dataclasses import replace
import json
import os
import socket
import subprocess
from unittest.mock import patch

import pytest

from authz_lab.evaluation.bounded_adapter import (Approval, BoundedAdapter, Mapping,
                                                Principal, mapping_digest, principal_digest)
from authz_lab.evaluation.case_manifest import CaseDefinition, CaseManifest
from authz_lab.evaluation.importer import validate_envelope


@pytest.fixture(autouse=True)
def guards():
    def deny(*args, **kwargs):
        raise AssertionError('External I/O forbidden')
    with patch.multiple(socket, create_connection=deny, getaddrinfo=deny,
                        gethostbyname=deny, gethostbyname_ex=deny), \
         patch.object(socket.socket, 'connect', deny), \
         patch.object(socket.socket, 'connect_ex', deny), \
         patch.object(socket.socket, 'sendto', deny), \
         patch.object(subprocess, 'Popen', deny), \
         patch.multiple(os, system=deny, fork=deny, posix_spawn=deny, posix_spawnp=deny):
        yield


def setup():
    case = CaseDefinition('GET', '/books/v1/{book_title}', 'actor-'+'a'*32,
                          'userA', 'owner-'+'b'*32, 'OTHER', 'v1', 'c'*64,
                          'policy', 'v1', 'DENY')
    manifest = CaseManifest.build([case])
    mapping = Mapping(case.case_id, '/books/v1/bookA', 'a', 'b', ('id',),
                      'bookA', ('owner',), (('nested', 'secret'),))
    principals = (Principal('a', 'userA', 'alice', True), Principal('b', 'userB', 'bob', True))
    approval = Approval('http://localhost:5000', ('/me', '/books/v1/bookA'),
                        manifest.content_digest, mapping_digest([mapping]), principal_digest(principals),
                        'execution-'+'d'*32, 'e'*64, 4, (2, 1, 1), 1000)
    return manifest, (mapping,), principals, approval


def adapter(**changes):
    manifest, mappings, principals, approval = setup()
    return BoundedAdapter(manifest, mappings, principals, replace(approval, **changes), clock=lambda: 1)


BOOK = dict(id='bookA', owner='bob', nested=dict(secret='CANARY_PROTECTED_123'))
IDENTITIES = [dict(username='alice', role='userA'), dict(username='bob', role='userB')]


class Response:
    status = 200
    content_type = 'application/json'

    def __init__(self, body):
        self.data = json.dumps(body).encode()
        self.closed = False
        self.sizes = []

    async def read(self, size):
        self.sizes.append(size)
        chunk, self.data = self.data[:size], self.data[size:]
        return chunk

    async def close(self):
        self.closed = True


class Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def get(self, url, **kwargs):
        assert kwargs['follow_redirects'] is False and kwargs['retries'] == 0
        self.calls.append((url, kwargs))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def run(responses=None, **changes):
    t = Transport([Response(x) if type(x) is dict else x for x in (responses or IDENTITIES+[BOOK, BOOK])])
    result = asyncio.run(adapter(**changes).run(t))
    return result, t


def test_positive_redacted_schema2():
    result, t = run()
    assert result['evidence'][0]['conclusion'] == 'CONFIRMED'
    assert result['counts'] == (2, 1, 1) and len(t.calls) == 4
    assert 'CANARY_PROTECTED' not in json.dumps(result)
    assert 'alice' not in json.dumps(result) and 'bob' not in json.dumps(result)
    assert validate_envelope(result['envelope']) == result['envelope']
    assert result['evidence'][0]['timing'] is None


@pytest.mark.parametrize('bad', [None, '', {}, [], {'error': 'generic'}])
def test_sensitive_invalid(bad):
    body = dict(BOOK, nested=dict(secret=bad))
    result, _ = run(IDENTITIES+[body, body])
    assert result['evidence'][0]['conclusion'] != 'CONFIRMED'
    assert result['envelope']['observations'][0]['execution_status'] == 'INVALID'


@pytest.mark.parametrize('body', [{}, {'error': 'generic'}, {'message': 'ok'},
                                   dict(BOOK, owner='alice'), dict(BOOK, id='wrong'),
                                   dict(BOOK, nested={})])
def test_invalid_baselines(body):
    result, _ = run(IDENTITIES+[body, BOOK])
    assert result['evidence'][0]['reason'] == 'INVALID_TEST'


@pytest.mark.parametrize('status', [301, 302, 307, 401, 500])
def test_status_and_redirect_rejected(status):
    response = Response(BOOK)
    response.status = status
    result, t = run(IDENTITIES+[response, BOOK])
    assert response.closed and not response.sizes
    assert len(t.calls) == 4 and result['evidence'][0]['conclusion'] != 'CONFIRMED'


@pytest.mark.parametrize('data', [b'{', b'null', b'{"id":1,"id":2}', b'NaN'])
def test_malformed_json(data):
    response = Response(BOOK)
    response.data = data
    result, _ = run(IDENTITIES+[response, BOOK])
    assert result['evidence'][0]['reason'] == 'INVALID_TEST'


def test_body_limit():
    response = Response(BOOK)
    result, _ = run(IDENTITIES+[response, BOOK], body_limit=45)
    assert response.closed and max(response.sizes) <= 46
    assert result['evidence'][0]['conclusion'] != 'CONFIRMED'


def test_non_json_and_failure_redaction():
    response = Response(BOOK)
    response.content_type = 'text/html'
    result, _ = run(IDENTITIES+[response, RuntimeError('CANARY_PROTECTED')])
    assert result['counts'] == (2, 1, 1)
    assert 'CANARY_PROTECTED' not in json.dumps(result)


@pytest.mark.parametrize('changes,expected', [({'total_cap': 2}, (2,0,0)),
                                            ({'phase_caps': (1,1,1)}, (1,0,0)),
                                            ({'phase_caps': (2,0,1)}, (2,0,0))])
def test_count_before_dispatch_caps(changes, expected):
    result, t = run([RuntimeError('secret')]*4, **changes)
    assert result['counts'] == expected and len(t.calls) == sum(expected)
    assert result['stop'] == 'CAP_EXHAUSTED'
    assert result['envelope']['observations'][0]['execution_status'] == 'NOT_RUN'


def test_cancel_and_single_use():
    a = adapter()
    t = Transport([])
    result = asyncio.run(a.run(t, cancelled=lambda: True))
    assert not t.calls and result['counts'] == (0,0,0)
    with pytest.raises(ValueError):
        asyncio.run(a.run(t))


def test_timeout_closes_response():
    class Slow(Response):
        async def read(self, size):
            await asyncio.Event().wait()
    r = Slow(BOOK)
    result, _ = run(IDENTITIES+[r, BOOK], timeout=0.01)
    assert r.closed and result['evidence'][0]['conclusion'] != 'CONFIRMED'


def test_identity_mismatch():
    result, _ = run([dict(username='other', role='userA'), IDENTITIES[1], BOOK, BOOK])
    assert result['evidence'][0]['reason'] == 'INVALID_TEST'


def test_dry_plan():
    a = adapter()
    plan = a.dry_plan()
    assert plan['fits'] and plan['total'] == 4 and plan['phases'] == [2,1,1]
    assert plan['concurrency'] == 1 and plan['retries'] == 0
    assert a.counts == [0,0,0]


@pytest.mark.parametrize('changes', [dict(origin='http://evil/x'), dict(origin='http://u:p@localhost'),
    dict(paths=('/me','/')), dict(paths=('/me','/books/v1/bookA?x=1')),
    dict(paths=('/me','/books/v1/bookA#x')), dict(manifest_digest='f'*64),
    dict(mapping_digest='f'*64), dict(total_cap=True), dict(expires_at=0)])
def test_reject_approval(changes):
    with pytest.raises(ValueError):
        adapter(**changes)


@pytest.mark.parametrize('path', ['http://evil/books/v1/bookA', '/books/v1/../me',
                                  '/books/v1/%62ookA', '/books/v1/bookA?x=1'])
def test_mapping_scope(path):
    manifest, mappings, principals, approval = setup()
    mappings = (replace(mappings[0], path=path),)
    with pytest.raises(ValueError):
        BoundedAdapter(manifest, mappings, principals,
                       replace(approval, mapping_digest=mapping_digest(mappings)), clock=lambda: 1)


def test_missing_duplicate_mapping_principal():
    manifest, mappings, principals, approval = setup()
    for ms, ps in [((),principals), (mappings*2,principals),
                   (mappings,(replace(principals[0], verified=False), principals[1]))]:
        with pytest.raises(ValueError):
            BoundedAdapter(manifest, ms, ps, replace(approval, mapping_digest=mapping_digest(ms)), clock=lambda: 1)


def test_receipt_tamper_recomputed_digest_rejected():
    from authz_lab.evaluation.case_manifest import _digest
    result, _ = run()
    envelope = result['envelope']
    envelope['observations'][0]['execution_id'] = 'execution-'+'f'*32
    envelope['content_digest'] = _digest({k:v for k,v in envelope.items() if k != 'content_digest'})
    with pytest.raises(ValueError):
        validate_envelope(envelope)


def test_public_and_identity_are_not_bola():
    manifest, mappings, principals, approval = setup()
    for template, category, path in [('/me', 'NONE', '/me'),
                                     ('/users/v1/{username}', 'PUBLIC', '/users/v1/alice')]:
        c = replace(manifest.cases[0], operation_template=template, owner_category=category,
                    owner_alias=None, expected_decision='ALLOW')
        cohort = CaseManifest.build([c])
        ms = (Mapping(c.case_id, path, 'a'),)
        a = replace(approval, paths=tuple(sorted({'/me', path})), manifest_digest=cohort.content_digest,
                    mapping_digest=mapping_digest(ms))
        t = Transport([Response(IDENTITIES[0]), Response(IDENTITIES[0])])
        result = asyncio.run(BoundedAdapter(cohort, ms, principals, a, clock=lambda:1).run(t))
        assert result['evidence'][0]['conclusion'] != 'CONFIRMED'
        assert result['envelope']['observations'][0]['execution_status'] == 'COMPLETED'


def test_unresolved_admin_rejected():
    manifest, mappings, principals, approval = setup()
    c = replace(manifest.cases[0], actor_role='admin')
    cohort = CaseManifest.build([c])
    ms = (replace(mappings[0], case_id=c.case_id),)
    ps = (replace(principals[0], role='admin'), principals[1])
    with pytest.raises(ValueError):
        BoundedAdapter(cohort, ms, ps, replace(approval, manifest_digest=cohort.content_digest,
                       principal_digest=principal_digest(ps), mapping_digest=mapping_digest(ms)), clock=lambda:1)


def test_actor_null_missing_secret_never_confirms():
    for nested in ({}, {'secret': None}, {'secret': ''}):
        result, _ = run(IDENTITIES+[BOOK, dict(BOOK, nested=nested)])
        assert result['evidence'][0]['conclusion'] == 'INCONCLUSIVE'


def test_dynamic_changes_keep_identity_and_owner_required():
    result, _ = run(IDENTITIES+[dict(BOOK, timestamp='old'), dict(BOOK, timestamp='new')])
    assert result['evidence'][0]['conclusion'] == 'CONFIRMED'
    result, _ = run(IDENTITIES+[BOOK, dict(BOOK, owner='wrong')])
    assert result['evidence'][0]['conclusion'] == 'INCONCLUSIVE'
