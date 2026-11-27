"""Synthetic DTO API checks; CLI importer is used only as a test producer."""
import base64
import hashlib
from pathlib import Path
import ipaddress
import json
from copy import deepcopy
from contextlib import ExitStack
from unittest.mock import patch
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from backend.app.core.settings import Settings
from backend.app.main import create_app
from backend.app.comparison.case_manifest import CaseDefinition, CaseManifest, _digest
from backend.app.comparison.validation import validate_dto


def fixture():
    c = CaseDefinition('GET', '/books/{id}', 'actor-'+'1'*32, 'userA',
                       'owner-'+'2'*32, 'OTHER', 'v1', 'a'*64, 'policy', 'v1', 'DENY')
    m = CaseManifest.build([c])
    p = dict(artifact_ref='artifact-'+'3'*32, artifact_hash='b'*64,
             producer_kind='AUTOMATED_VERIFIER', producer_version='v1', operator_alias=None)
    d = dict(schema_version=1, manifest=m.to_dict(), observations=[dict(method='T18',
        manifest_digest=m.content_digest, manifest_version=m.version, case_revision=c.to_dict(),
        execution_id='execution-'+'4'*32, execution_status='COMPLETED', signal='ACCESS_DENIED', provenance=p)],
        selections=[dict(method='T18', execution_id='execution-'+'4'*32)],
        legacy=[dict(method='ZAP', source_alias='source-'+'5'*32, provenance=None,
                     linkage_status='UNLINKED', conclusion='UNKNOWN')],
        artifacts=[dict(artifact_ref=p['artifact_ref'], artifact_hash=p['artifact_hash'], size_bytes=300,
                        integrity_status='HASH_MATCHED', attestation_status='UNVERIFIED')], attestation_status='UNVERIFIED')
    d['observations'][0]['provenance'] = None
    d['artifacts'] = []
    return sign(d)


def sign(d):
    d.pop('content_digest', None)
    return d | dict(content_digest=_digest(d))


@pytest.fixture(autouse=True)
def guards():
    async def noop(*args):
        return
    with ExitStack() as stack:
        stack.enter_context(patch('backend.app.main.worker_loop', noop))
        for name in ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.socket.sendto',
                     'socket.create_connection', 'socket.getaddrinfo', 'socket.gethostbyname',
                     'socket.gethostbyname_ex', 'subprocess.Popen', 'os.system',
                     'os.posix_spawn', 'os.posix_spawnp', 'os.fork'):
            stack.enter_context(patch(name, side_effect=AssertionError('Forbidden external activity')))
        yield


def test_validation_negatives():
    original = fixture()
    assert validate_dto(json.dumps(original).encode()) == original
    mutations = [lambda d: d.update(schema_version=True), lambda d: d.update(secret='CANARY-SECRET'),
        lambda d: d.update(attestation_status='VERIFIED'), lambda d: d.update(selections=[]),
        lambda d: d['observations'].append(deepcopy(d['observations'][0])),
        lambda d: d['observations'][0].update(manifest_digest='0'*64),
        lambda d: d['observations'][0]['case_revision'].update(policy_version='v2'),
        lambda d: d['observations'][0].update(provenance={'secret':'CANARY'}),
        lambda d: d.update(artifacts=[{}]),
        lambda d: d.update(artifacts=[{'size_bytes':4097}]),
        lambda d: d['legacy'].append(deepcopy(d['legacy'][0])),
        lambda d: d.update(selections=d['selections']*2), lambda d: d['legacy'][0].update(linkage_status='LINKED'),
        lambda d: d['selections'][0].update(execution_id='/tmp/private'),
        lambda d: d.update(observations=[None]), lambda d: d.update(metrics_eligible=True)]
    for mutation in mutations:
        d = deepcopy(original)
        mutation(d)
        with pytest.raises(ValueError):
            validate_dto(sign(d))
    d = deepcopy(original)
    d['selections'][0]['execution_id'] = 'execution-'+'8'*32
    with pytest.raises(ValueError):
        validate_dto(d)
    for raw in (b'{"x":1,"x":2}', b'\xff', b'NaN', b' '*2_000_001):
        with pytest.raises(ValueError):
            validate_dto(raw)


def test_auth_scope_idempotency_reload_and_limits(tmp_path):
    settings = Settings(database_path=tmp_path/'isolated.sqlite3', admin_password='password',
        session_secret='s'*32, secret_encryption_key=Fernet.generate_key().decode(),
        target_networks=(ipaddress.ip_network('127.0.0.1/32'),), allowed_ports=frozenset({5000}),
        max_response_bytes=32768, default_timeout_seconds=5.0)
    dto = schema2_fixture()
    with TestClient(create_app(settings)) as client:
        url = '/api/projects/1/comparisons'
        assert client.get(url).status_code == 401
        assert client.post(url, json=dto).status_code == 401
        assert client.post('/api/auth/login', json={'password':'wrong'}).status_code == 401
        csrf = {'X-CSRF-Token': client.post('/api/auth/login', json={'password':'password'}).json()['csrf_token']}
        for name in ('one', 'two'):
            assert client.post('/api/projects', json={'name':name}, headers=csrf).status_code == 201
        assert client.post(url, json=dto).status_code == 403
        assert client.post(url, json=dto, headers={'X-CSRF-Token':'wrong'}).status_code == 403
        forged = deepcopy(dto)
        forged['observations'][0]['execution_id'] = 'execution-'+'8'*32
        assert client.post(url, json=sign(forged), headers=csrf).status_code == 422
        for _ in range(2):
            assert client.post(url, json=dto, headers=csrf).status_code == 201
        assert len(client.get(url).json()) == 1
        assert client.get(url+'/'+dto['content_digest']).json() == dto
        assert client.get('/api/projects/2/comparisons/'+dto['content_digest']).status_code == 404
        assert client.get('/api/projects/999/comparisons').status_code == 404
        assert client.get(url+'?limit=101').status_code == 422
        assert client.post(url, content=b' '*2_000_001, headers=csrf | {'Content-Type':'application/json'}).status_code == 413
        assert client.post(url, content='{}', headers=csrf).status_code == 415
        bad = sign(dto | {'secret':'CANARY-SECRET'})
        response = client.post(url, json=bad, headers=csrf)
        assert response.status_code == 422 and 'CANARY' not in response.text
    with TestClient(create_app(settings)) as client:
        client.post('/api/auth/login', json={'password':'password'})
        assert client.get(url+'/'+dto['content_digest']).json() == dto
        from backend.app.persistence.models import ComparisonBundle
        with client.app.state.session_factory() as session:
            row = session.get(ComparisonBundle, 1)
            row.canonical_json = '{}'
            session.commit()
        assert client.get(url+'/'+dto['content_digest']).status_code == 409


def test_receipt_catalog_claim_fails_closed():
    d = fixture()
    p = dict(artifact_ref='artifact-'+'3'*32, artifact_hash='b'*64,
             producer_kind='AUTOMATED_VERIFIER', producer_version='v1', operator_alias=None)
    d['observations'][0]['provenance'] = p
    d['artifacts'] = [dict(artifact_ref=p['artifact_ref'], artifact_hash=p['artifact_hash'],
        size_bytes=300, integrity_status='HASH_MATCHED', attestation_status='UNVERIFIED')]
    with pytest.raises(ValueError, match='Receipt binding unavailable'):
        validate_dto(sign(d))


def schema2_fixture():
    # Complete synthetic importer DTO frozen in the reviewed receipt contract.
    report = Path('audit-final/research-workflow-comparison-receipt-contract.md').read_text()
    return json.loads(report.split('```json\n', 1)[1].split('\n```', 1)[0])


def replace_receipt(dto, raw, index=0):
    entry = dto['artifacts'][index]
    old_hash = entry['artifact_hash']
    digest = hashlib.sha256(raw).hexdigest()
    encoded = base64.b64encode(raw).decode('ascii')
    entry.update(artifact_hash=digest, size_bytes=len(raw),
                 receipt_base64_chunks=[encoded[i:i+512] for i in range(0, len(encoded), 512)])
    for item in dto['observations'] + dto['legacy']:
        if item['provenance'] and item['provenance']['artifact_hash'] == old_hash:
            item['provenance']['artifact_hash'] = digest
    return sign(dto)


def test_schema2_bytes_and_importer_compatibility(monkeypatch):
    dto = schema2_fixture()
    assert validate_dto(json.dumps(dto).encode()) == dto
    monkeypatch.syspath_prepend(str(Path('tools/authorization-lab/src').resolve()))
    from authz_lab.evaluation.importer import import_bundle
    source = {key: deepcopy(dto[key]) for key in
              ('manifest', 'observations', 'selections', 'legacy')}
    source['schema_version'] = 1
    catalog = {a['artifact_ref']: base64.b64decode(''.join(a['receipt_base64_chunks']))
               for a in dto['artifacts']}
    assert import_bundle(source, catalog) == dto
    # Whitespace changes original-byte hash, while receipt semantics stay equal.
    raw = b'  ' + next(iter(catalog.values())) + b'\n'
    changed = replace_receipt(deepcopy(dto), raw)
    assert validate_dto(changed) == changed
    detached = validate_dto(changed)
    detached['artifacts'][0]['receipt_base64_chunks'][0] = 'changed'
    assert validate_dto(changed) == changed
    assert validate_dto(fixture())['schema_version'] == 1


def test_schema2_exact_bindings_and_forged_receipts():
    dto = schema2_fixture()
    mutations = [
        lambda d: d['observations'][0].update(execution_id='execution-'+'8'*32),
        lambda d: d['observations'][0].update(signal='ACCESS_ALLOWED'),
        lambda d: d['observations'][0].update(execution_status='NOT_RUN', signal='UNKNOWN'),
        lambda d: d['observations'][0].update(method='T18'),
        lambda d: d['observations'][0].update(manifest_digest='0'*64),
        lambda d: d['observations'][0]['case_revision'].update(policy_version='v2'),
        lambda d: d.update(schema_version=1),
        lambda d: d['artifacts'].append(deepcopy(d['artifacts'][0])),
        lambda d: d['artifacts'].clear(),
        lambda d: d['artifacts'][0].update(artifact_hash='0'*64),
        lambda d: d['artifacts'][0].update(size_bytes=True),
        lambda d: d['artifacts'][0].update(size_bytes=4097),
        lambda d: d['artifacts'][0].update(receipt_encoding='utf-8'),
        lambda d: d['artifacts'][0].update(receipt_base64_chunks=['!!!!']),
        lambda d: d['artifacts'][0].update(receipt_base64_chunks=[]),
        lambda d: d['artifacts'][0].update(receipt_base64_chunks=['a'*512]*12),
        lambda d: d['artifacts'][0].update(receipt_base64_chunks=['a', 'aaaa']),
        lambda d: d['artifacts'][0].update(receipt_base64_chunks=['/x==']),
        lambda d: d['artifacts'][0].update(attestation_status='VERIFIED'),
    ]
    for mutate in mutations:
        changed = deepcopy(dto)
        mutate(changed)
        with pytest.raises(ValueError):
            validate_dto(sign(changed))
    receipt = json.loads(base64.b64decode(''.join(dto['artifacts'][0]['receipt_base64_chunks'])))
    for raw in (b'{}', b'\xff', b'NaN', b'\xef\xbb\xbf{}', b' '*4097,
                json.dumps(receipt | {'body': 'CANARY-SECRET'}).encode(),
                json.dumps(receipt | {'execution_id': 'execution-'+'8'*32}).encode(),
                json.dumps(receipt | {'schema_version': True}).encode(),
                b'{"schema_version":1,' + json.dumps(receipt)[1:].encode()):
        with pytest.raises(ValueError):
            validate_dto(replace_receipt(deepcopy(dto), raw))
    for value in ({'x': 'a'*513}, {'x': [None]*1001}, {'x': 1.5}, {'x': 2**54}):
        with pytest.raises(ValueError):
            validate_dto(value)
    nested = {}
    for _ in range(14):
        nested = {'x': nested}
    with pytest.raises(ValueError):
        validate_dto(nested)
    with patch('backend.app.comparison.validation.MAX_ARTIFACT_TOTAL_BYTES', 1):
        with pytest.raises(ValueError):
            validate_dto(dto)


def test_legacy_positive_provenance_and_exact_binding():
    dto = schema2_fixture()
    alias, ref = 'source-'+'9'*32, 'artifact-'+'7'*32
    raw = json.dumps(dict(schema_version=1, kind='LEGACY_INVENTORY', method='ZAP',
                         source_alias=alias, linkage_status='UNLINKED')).encode()
    digest = hashlib.sha256(raw).hexdigest()
    encoded = base64.b64encode(raw).decode()
    dto['legacy'] = [dict(method='ZAP', source_alias=alias, linkage_status='UNLINKED',
        conclusion='UNKNOWN', provenance=dict(artifact_ref=ref, artifact_hash=digest,
        producer_kind='ZAP', producer_version='v1', operator_alias=None))]
    dto['artifacts'].append(dict(artifact_ref=ref, artifact_hash=digest, size_bytes=len(raw),
        integrity_status='HASH_MATCHED', attestation_status='UNVERIFIED',
        receipt_encoding='base64', receipt_base64_chunks=[encoded]))
    dto['artifacts'].sort(key=lambda a: a['artifact_ref'])
    dto = sign(dto)
    assert validate_dto(dto) == dto
    for key, value in [('source_alias', 'source-'+'6'*32), ('method', 'T18'),
                       ('linkage_status', 'LINKED'), ('conclusion', 'ACCESS_ALLOWED')]:
        changed = deepcopy(dto)
        changed['legacy'][0][key] = value
        with pytest.raises(ValueError):
            validate_dto(sign(changed))
    for version in (1, True, 3):
        with pytest.raises(ValueError):
            validate_dto(sign(dto | {'schema_version': version}))


def test_rebuilt_revision_cohort_cannot_reuse_receipt():
    dto = schema2_fixture()
    definition = deepcopy(dto['manifest']['cases'][0])
    definition.pop('case_id')
    definition['policy_version'] = 'v2'
    case = CaseDefinition(**definition)
    manifest = CaseManifest.build([case])
    dto['manifest'] = manifest.to_dict()
    dto['observations'][0].update(manifest_digest=manifest.content_digest,
        manifest_version=manifest.version, case_revision=case.to_dict())
    with pytest.raises(ValueError, match='Receipt binding mismatch'):
        validate_dto(sign(dto))


@pytest.mark.parametrize('raw', [b'a', b'aa'])
def test_base64_padding_canonicality(raw):
    dto = schema2_fixture()
    dto = replace_receipt(dto, raw)
    encoded = dto['artifacts'][0]['receipt_base64_chunks'][0]
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
    pos = len(encoded.rstrip('=')) - 1
    # Change unused padding bits without changing decoded bytes.
    changed = encoded[:pos] + alphabet[alphabet.index(encoded[pos])+1] + encoded[pos+1:]
    assert base64.b64decode(changed) == raw
    dto['artifacts'][0]['receipt_base64_chunks'] = [changed]
    with pytest.raises(ValueError, match='Noncanonical receipt encoding'):
        validate_dto(sign(dto))
