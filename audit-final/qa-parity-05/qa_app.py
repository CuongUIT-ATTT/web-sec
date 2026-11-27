"""QA-PARITY-05 only. Synthetic fixture; never execute scanners."""
import ipaddress
import os
import secrets
import socket
from contextlib import asynccontextmanager
from pathlib import Path

from cryptography.fernet import Fernet
from starlette.responses import JSONResponse
from backend.app.core.settings import Settings
from backend.app.main import create_app
from backend.app.persistence.database import create_session_factory
from backend.app.persistence.models import (Project, Identity, OpenApiOperation, ResourceType,
    Resource, OperationResourceMapping, Policy, Run, RunResult)


def deny_connect(*args, **kwargs):
    raise PermissionError('QA-PARITY-05: outbound disabled')


def seed(factory):
    with factory.begin() as s:
        if s.get(Project, 1):
            raise RuntimeError('QA requires a fresh isolated database')
        s.add(Project(id=1, name='SYNTHETIC QA-PARITY-05', description='Synthetic UI fixture, not laboratory evidence'))
        for i, role in enumerate(('admin', 'userA', 'userB'), 1):
            s.add(Identity(id=i, project_id=1, display_name='SYNTHETIC '+role, role=role))
        s.add(OpenApiOperation(id=1, project_id=1, operation_key='synthetic-get-item', method='GET', path='/synthetic/items/{id}', selected=True))
        s.add(ResourceType(id=1, project_id=1, name='SYNTHETIC item', resource_id_pointer='/id', restricted_pointers=['/protected']))
        s.flush()
        s.add(OperationResourceMapping(project_id=1, operation_id=1, resource_type_id=1, selected=True))
        for rid, owner in ((1, 2), (2, 3)):
            s.add(Resource(id=rid, resource_type_id=1, external_id=f'synthetic-item-{rid}', owner_identity_id=owner, path_parameter='id'))
        s.flush()
        s.add(Run(id=1, project_id=1, status='COMPLETED', snapshot={'provenance':'QA-PARITY-05 synthetic fixture v1; no transport executed'}))
        s.flush()
        for rid, owner in ((1, 2), (2, 3)):
            for actor in (1, 2, 3):
                pid = (rid-1)*3+actor
                allowed = actor in (1, owner)
                s.add(Policy(id=pid, version=1, operation_id=1, resource_type_id=1, identity_id=actor, resource_id=rid, decision='ALLOW' if allowed else 'DENY'))
                key=f'operation:1:resource:{rid}:actor:{actor}'
                evidence=dict(schema_version=2, engine='web-evaluator-v1', run_id=1, case_key=key,
                    resource_id=rid, actor_identity_id=actor, owner_identity_id=owner,
                    actor_role=('admin','userA','userB')[actor-1], owner_role=('admin','userA','userB')[owner-1],
                    ownership='self' if actor==owner else 'cross-role', protected_fields=[],
                    owner_control_valid=True, owner_http_status=200, owner_execution_status='COMPLETED_RESPONSE',
                    owner_body_truncated=False, owner_json_parse_error=False, owner_principal_matches=True,
                    actor_principal_matches=True, owner_resource_matches=True, actor_resource_matches=allowed,
                    owner_restricted_evidence_valid=True, restricted_fields_match_owner=allowed,
                    policy_id=pid, policy_version=1, policy_decision='ALLOW' if allowed else 'DENY', policy_resolution='RESOLVED')
                s.add(RunResult(run_id=1, case_key=key, execution_status='COMPLETED_RESPONSE',
                    authorization_conclusion='POLICY_CONSISTENT_CASE', http_status=200 if allowed else 403,
                    reason_codes=['SYNTHETIC_QA_FIXTURE_NO_TRANSPORT'], response_metadata={'evidence':evidence}))


def build_app(database_path, password):
    settings=Settings(database_path=database_path, admin_password=password, session_secret=secrets.token_urlsafe(40),
        secret_encryption_key=Fernet.generate_key().decode(), target_networks=(ipaddress.ip_network('127.0.0.1/32'),),
        allowed_ports=frozenset({9}), max_response_bytes=32768, default_timeout_seconds=1, external_lab_bridge_enabled=False)
    app=create_app(settings)
    factory=create_session_factory(database_path)
    seed(factory)
    @asynccontextmanager
    async def qa_lifespan(app):
        app.state.settings=settings
        app.state.session_factory=factory
        yield
    # Replace original lifespan entirely: zero worker/dispatcher tasks created.
    app.router.lifespan_context=qa_lifespan
    @app.middleware('http')
    async def reject_execution(request, call_next):
        path=request.url.path
        if request.method != 'GET' and path not in ('/api/auth/login','/api/auth/logout'):
            return JSONResponse({'detail':'SYNTHETIC QA: mutations/execution disabled'}, status_code=403)
        return await call_next(request)
    return app


def application():
    socket.socket.connect=deny_connect
    socket.socket.connect_ex=deny_connect
    socket.create_connection=deny_connect
    socket.getaddrinfo=deny_connect
    return build_app(Path('/qa-state/synthetic.sqlite3'), os.environ['QA_ADMIN_PASSWORD'])
