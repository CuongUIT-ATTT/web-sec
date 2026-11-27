"""Revision-backed queue/evaluation with temp SQLite and independent loopback receipt counts."""
import asyncio
import ipaddress
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from backend.tests.test_authorization_model import lab, config
from backend.app.core.secrets import SecretBox
from backend.app.core.settings import Settings
from backend.app.domain.contracts import ExecutionStatus, AuthorizationConclusion
from backend.app.persistence.models import IdentitySecret, RunResult, RunExecutionStats, RunIdentitySecret
from backend.app.services.authorization_model import preview, revision, ResponseEvidence
from backend.app.services.authorization_execution import SelectedAuthorizationCases, selected_snapshot, queue_selected
from backend.app.workers.queue import claim_next_run
from backend.app.workers.runner import execute_run
from backend.app.scanner.classification.evaluator import Observation, evaluate_authorization_case


def selection(s,p,t,c):
    return SelectedAuthorizationCases(target_id=t.id, policy_revision=revision(c),
        case_ids=[x["case_id"] for x in preview(s,p.id,t,c)["cases"] if x["execution_eligible"]])


def test_selection_revision_duplicates_unknown_and_cap(lab):
    s,p,t,a,o,rt,r = lab
    c=config(a,o,rt,r)
    payload=selection(s,p,t,c)
    snapshot=selected_snapshot(s,p.id,t,c,payload)
    assert len(snapshot["cases"]) == 15
    assert len(snapshot["identities"]) == 3
    assert snapshot["request_plan"]["planned_attempts"] == 24
    for update, error in [({"policy_revision":"old"},"STALE"),
                          ({"case_ids":["missing"]},"UNKNOWN"),
                          ({"case_ids":[payload.case_ids[0]]*2},"DUPLICATE")]:
        with pytest.raises(ValueError,match=error):
            selected_snapshot(s,p.id,t,c,payload.model_copy(update=update))
    write=next(x for x in preview(s,p.id,t,c)["cases"] if x["method"]=="POST")
    with pytest.raises(ValueError,match="NON_EXECUTABLE"):
        selected_snapshot(s,p.id,t,c,payload.model_copy(update={"case_ids":[write["case_id"]]}))
    t.request_limit=1
    with pytest.raises(ValueError,match="REQUEST_LIMIT"):
        selected_snapshot(s,p.id,t,c,payload)


@pytest.mark.parametrize("kind",["BOLA","BFLA"])
@pytest.mark.parametrize("verification_failure",[None,"actor","baseline"])
def test_actual_loopback_snapshot_credentials_and_replay(lab, kind, verification_failure):
    s,p,t,a,o,rt,r=lab
    c=config(a,o,rt,r)
    c.operations[1].evidence=ResponseEvidence(result_pointer="/id",result_value="report",
        protected_pointers=["/secret"],denial_pointer="/denied",denial_value="yes")
    receipts=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            receipts.append(self.path)
            token=self.headers.get("Authorization","").removeprefix("Bearer ")
            actor=int(token.removeprefix("fixture-token-"))
            if self.path=="/me":
                body={"id":f"fixture-{actor}"}
                status=401 if (verification_failure=="actor" and actor==0) or (verification_failure=="baseline" and actor==2) else 200
            elif self.path=="/reports": body={"id":"report","secret":{"result":"fixture-private-result-742"}}; status=403 if actor==0 else 200
            else: body={"id":self.path.rsplit("/",1)[-1],"secret":{"result":"fixture-private-result-742"}}; status=403 if actor==0 else 200
            data=json.dumps(body).encode()
            self.send_response(status); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try:
        port=server.server_port
        t.base_url=f"http://127.0.0.1:{port}"; t.verification_path="/me"
        key=Fernet.generate_key().decode(); box=SecretBox.from_key(key)
        for index, actor in enumerate(a):
            secret=s.scalar(select(IdentitySecret).where(IdentitySecret.identity_id==actor.id))
            secret.ciphertext=box.encrypt_bearer(f"fixture-token-{index}")[0]
        s.commit()
        payload=selection(s,p,t,c)
        payload.case_ids=[x["case_id"] for x in preview(s,p.id,t,c)["cases"] if x["execution_eligible"] and x["kind"]==kind]
        snapshot=selected_snapshot(s,p.id,t,c,payload)
        run=queue_selected(s,p.id,snapshot)
        queued_secrets=list(s.scalars(select(RunIdentitySecret).where(RunIdentitySecret.run_id==run.id)))
        # Mutating live config, token and principal after queue must not affect this run.
        for actor in a:
            actor.expected_principal="changed"
            s.scalar(select(IdentitySecret).where(IdentitySecret.identity_id==actor.id)).ciphertext=box.encrypt_bearer("rotated")[0]
        c.rules=[]
        s.commit()
        settings=Settings(target_networks=(ipaddress.ip_network("127.0.0.1/32"),),allowed_ports=frozenset({port}),
            max_response_bytes=32768,default_timeout_seconds=2,database_path=s.bind.url.database,
            admin_password="fixture",session_secret="s"*32,secret_encryption_key=key)
        claimed=claim_next_run(s); s.commit()
        assert claimed.id==run.id
        assert asyncio.run(execute_run(s,run,settings)); s.commit(); s.refresh(run)
        assert run.status=="COMPLETED"
        results=list(s.scalars(select(RunResult).where(RunResult.run_id==run.id)))
        assert len(results)==len(payload.case_ids)
        assert {x.case_key for x in results}==set(payload.case_ids)
        if verification_failure is None:
            assert any(x.authorization_conclusion=="CONFIRMED_VIOLATION" and x.http_status==403 for x in results)
            assert any(x.authorization_conclusion=="POLICY_CONSISTENT_CASE" for x in results)
        else:
            assert any(x.authorization_conclusion=="INVALID_TEST" for x in results)
            if kind=="BFLA" and verification_failure=="baseline":
                assert not any(x.authorization_conclusion=="CONFIRMED_VIOLATION" for x in results)
        import os
        from pathlib import Path
        if evidence_dir:=os.environ.get("AUTOAUTH_EXEC_EVIDENCE_DIR"):
            Path(evidence_dir,f"loopback-{kind}-{verification_failure or 'valid'}.json").write_text(json.dumps(dict(
                kind=kind,fixture="isolated-numeric-loopback",verification_failure=verification_failure,
                run_id=run.id,case_ids=[x.case_key for x in results],policy_revision=snapshot["policy_revision"],
                planned=snapshot["request_plan"]["planned_attempts"],server_received=len(receipts),
                conclusions=[dict(case_id=x.case_key,status=x.http_status,conclusion=x.authorization_conclusion) for x in results]),indent=2))
        stats=s.scalar(select(RunExecutionStats).where(RunExecutionStats.run_id==run.id))
        assert stats.planned_attempts==stats.transport_attempts==stats.completed_responses==len(receipts)
        assert not asyncio.run(execute_run(s,run,settings))
        assert stats.transport_attempts==len(receipts)
        encoded=json.dumps([x.response_metadata for x in results])
        assert "fixture-private-result-742" not in encoded and "fixture-token" not in encoded
        assert len(queued_secrets)==3
    finally:
        server.shutdown(); server.server_close(); thread.join()


def eval_case(kind="BOLA"):
    return dict(kind=kind,expected_decision="DENY",resource=dict(external_id="book",resource_id_pointer="/id",restricted_pointers=["/secret"]),
        observation_contract=dict(result_pointer="/id",result_value="book",protected_pointers=["/secret"],denial_pointer="/denied",denial_value="yes"))


@pytest.mark.parametrize("kind",["BOLA","BFLA"])
@pytest.mark.parametrize("body,status,identity,baseline,expected",[
    ({"id":"book","secret":"private"},403,True,True,"CONFIRMED_VIOLATION"),
    ({"id":"book","secret":"private","denied":"yes"},403,True,True,"CONFIRMED_VIOLATION"),
    ({"denied":"yes"},200,True,True,"POLICY_CONSISTENT_CASE"),
    ({"id":"wrong","secret":"private"},200,True,True,"INSUFFICIENT_EVIDENCE"),
    ({"id":"book","secret":"private"},200,False,True,"INVALID_TEST"),
    ({"id":"book","secret":"private"},200,True,False,"INVALID_TEST"),
    ({"success":True},200,True,True,"INSUFFICIENT_EVIDENCE"),
])
def test_policy_response_negatives(kind,body,status,identity,baseline,expected):
    result=evaluate_authorization_case(case=eval_case(kind),identity_confirmed=identity,baseline_valid=baseline,
        baseline_body={"id":"book","secret":"private"},
        observation=Observation(ExecutionStatus.COMPLETED_RESPONSE,status,body))
    assert result.conclusion==expected


@pytest.mark.parametrize("raw,expected",[
    (b'{"id":"wrong","id":"book","secret":"private"}',"JSON_PARSE_ERROR"),
    (b'{"id":"book","secret":NaN}',"JSON_PARSE_ERROR"),
    (b'\xff',"JSON_PARSE_ERROR"),
    (b'{"id":"book"}',"COMPLETED_RESPONSE"),
])
def test_transport_ambiguous_json_and_proxy_isolation(monkeypatch,raw,expected):
    import httpx
    from backend.app.scanner.execution.http_client import get_json
    seen=[]
    original=httpx.AsyncClient
    def client(**kwargs):
        seen.append(kwargs)
        return original(**kwargs,transport=httpx.MockTransport(lambda request:httpx.Response(200,content=raw)))
    monkeypatch.setattr(httpx,"AsyncClient",client)
    settings=Settings(target_networks=(ipaddress.ip_network("127.0.0.1/32"),),allowed_ports=frozenset({9999}),max_response_bytes=32768,
        default_timeout_seconds=2,database_path="/tmp/unused-autoauth.sqlite",admin_password="fixture",session_secret="s"*32,
        secret_encryption_key=Fernet.generate_key().decode())
    result=asyncio.run(get_json(base_url="http://127.0.0.1:9999",api_path="/me",bearer_token=None,settings=settings))
    assert result.execution_status==expected
    assert seen[0]["trust_env"] is False and seen[0]["follow_redirects"] is False


def test_function_single_marker_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ResponseEvidence(result_pointer="/id",result_value="report",protected_pointers=["/id"])


@pytest.mark.parametrize("cancel_after",[0,1,4,5,6,24])
def test_selected_cancellation_preserves_durable_cases(lab,monkeypatch,cancel_after):
    from backend.app.scanner.execution.http_client import HttpObservation
    from backend.app.workers.queue import request_cancellation
    s,p,t,a,o,rt,r=lab
    c=config(a,o,rt,r)
    payload=selection(s,p,t,c)
    key=Fernet.generate_key().decode(); box=SecretBox.from_key(key)
    for index,actor in enumerate(a):
        s.scalar(select(IdentitySecret).where(IdentitySecret.identity_id==actor.id)).ciphertext=box.encrypt_bearer(str(index))[0]
    s.commit()
    run=queue_selected(s,p.id,selected_snapshot(s,p.id,t,c,payload))
    settings=Settings(target_networks=(ipaddress.ip_network("127.0.0.1/32"),),allowed_ports=frozenset({9999}),
        max_response_bytes=32768,default_timeout_seconds=2,database_path=s.bind.url.database,
        admin_password="fixture",session_secret="s"*32,secret_encryption_key=key)
    claimed=claim_next_run(s);s.commit()
    calls=[]
    async def response(**kwargs):
        calls.append(kwargs["api_path"])
        actor=int(kwargs["bearer_token"])
        body={"id":f"fixture-{actor}"} if kwargs["api_path"]=="/me" else {"id":kwargs["api_path"].rsplit("/",1)[-1],"secret":"protected"}
        if len(calls)==cancel_after:
            # Independent file-backed connection wins at a deterministic I/O checkpoint.
            from sqlalchemy.orm import Session
            with Session(s.bind) as other:
                assert request_cancellation(other,run.id);other.commit()
        return HttpObservation(ExecutionStatus.COMPLETED_RESPONSE,200,body,20,False,False,())
    monkeypatch.setattr("backend.app.workers.runner.get_json",response)
    if cancel_after==0:
        assert request_cancellation(s,run.id);s.commit()
    assert asyncio.run(execute_run(s,run,settings));s.commit();s.refresh(run)
    assert run.status=="CANCELLED"
    assert len(calls)==cancel_after
    results=list(s.scalars(select(RunResult).where(RunResult.run_id==run.id)))
    assert len(results)==len(payload.case_ids)
    assert len({x.case_key for x in results})==len(results)
    if cancel_after < 24:
        assert any(x.execution_status=="CANCELLED" for x in results)
        assert all(x.authorization_conclusion=="NOT_RUN" for x in results if x.execution_status=="CANCELLED")
    assert not request_cancellation(s,run.id)
    durable=[(x.id,x.authorization_conclusion) for x in results if x.execution_status!="CANCELLED"]
    assert not asyncio.run(execute_run(s,run,settings))
    assert durable==[(x.id,x.authorization_conclusion) for x in results if x.execution_status!="CANCELLED"]


def test_queue_and_results_api_auth_csrf_redaction(lab):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.middleware.sessions import SessionMiddleware
    from backend.app.api.routes import router as base_router, get_session
    from backend.app.api.authorization_routes import router
    from backend.app.persistence.models import ProjectAuthorizationRevision
    s,p,t,a,o,rt,r=lab
    c=config(a,o,rt,r)
    s.add(ProjectAuthorizationRevision(project_id=p.id,revision=revision(c),configuration=c.model_dump()));s.commit()
    app=FastAPI();app.add_middleware(SessionMiddleware,secret_key="s"*32)
    app.include_router(base_router);app.include_router(router)
    app.state.settings=Settings(target_networks=(ipaddress.ip_network("127.0.0.1/32"),),allowed_ports=frozenset({9999}),
        max_response_bytes=32768,default_timeout_seconds=2,database_path=s.bind.url.database,
        admin_password="fixture-password",session_secret="s"*32,secret_encryption_key=Fernet.generate_key().decode())
    def session():yield s
    app.dependency_overrides[get_session]=session
    root=f"/api/projects/{p.id}/authorization"
    payload=selection(s,p,t,c).model_dump()
    with TestClient(app) as client:
        assert client.post(root+"/runs",json=payload).status_code in {401,403}
        token=client.post("/api/auth/login",json={"password":"fixture-password"}).json()["csrf_token"]
        assert client.post(root+"/runs",json=payload).status_code==403
        response=client.post(root+"/runs",json=payload,headers={"X-CSRF-Token":token})
        assert response.status_code==201,response.text
        queued=response.json(); run_id=queued["id"]
        result=client.get(root+f"/runs/{run_id}/results")
        assert result.status_code==200
        assert {x["case_id"] for x in result.json()["cases"]}==set(payload["case_ids"])
        assert all(x["conclusion"]=="NOT_RUN" for x in result.json()["cases"])
        assert "fixture-encrypted" not in result.text and "external_id" not in result.text
        assert client.get(f"/api/projects/999/authorization/runs/{run_id}/results").status_code==404
        assert client.post(root+"/runs",json={**payload,"policy_revision":"stale"},headers={"X-CSRF-Token":token}).status_code==422


@pytest.mark.parametrize("truncated,parse_error,status",[(True,False,ExecutionStatus.BODY_TRUNCATED),
    (False,True,ExecutionStatus.JSON_PARSE_ERROR),(False,False,ExecutionStatus.TIMEOUT)])
def test_automatic_evaluation_bounded_failures(truncated,parse_error,status):
    result=evaluate_authorization_case(case=eval_case(),identity_confirmed=True,baseline_valid=True,
        baseline_body={"id":"book","secret":"private"},
        observation=Observation(status,200,None,truncated,parse_error))
    assert result.conclusion=="INSUFFICIENT_EVIDENCE"


def test_unknown_missing_function_and_suspected():
    case=eval_case()
    observation=Observation(ExecutionStatus.COMPLETED_RESPONSE,200,{"id":"book","secret":"different"})
    def result():
        return evaluate_authorization_case(case=case,identity_confirmed=True,baseline_valid=True,
            baseline_body={"id":"book","secret":"private"},observation=observation)
    assert result().conclusion=="SUSPECTED_VIOLATION"
    case["expected_decision"]="UNKNOWN"
    assert result().conclusion=="INSUFFICIENT_EVIDENCE"
    case=eval_case("BFLA");case["observation_contract"]={}
    assert result().conclusion=="INSUFFICIENT_EVIDENCE"


@pytest.mark.parametrize("tamper",["method","cap","plan","dispatch_checkpoint"])
def test_invalid_snapshot_or_prior_checkpoint_never_dispatches(lab,monkeypatch,tamper):
    from copy import deepcopy
    s,p,t,a,o,rt,r=lab
    c=config(a,o,rt,r)
    snapshot=selected_snapshot(s,p.id,t,c,selection(s,p,t,c))
    snapshot=deepcopy(snapshot)
    if tamper=="method":snapshot["cases"][0]["operation"]["method"]="POST"
    if tamper=="cap":snapshot["target"]["request_limit"]=1
    if tamper=="plan":snapshot["request_plan"]["planned_attempts"]+=1
    run=queue_selected(s,p.id,snapshot)
    if tamper=="dispatch_checkpoint":
        stats=s.scalar(select(RunExecutionStats).where(RunExecutionStats.run_id==run.id))
        stats.transport_attempts=1;s.commit()
    claim_next_run(s);s.commit()
    async def forbidden(**kwargs):raise AssertionError("No dispatch permitted")
    monkeypatch.setattr("backend.app.workers.runner.get_json",forbidden)
    settings=Settings(target_networks=(ipaddress.ip_network("127.0.0.1/32"),),allowed_ports=frozenset({9999}),
        max_response_bytes=32768,default_timeout_seconds=2,database_path=s.bind.url.database,
        admin_password="fixture",session_secret="s"*32,secret_encryption_key=Fernet.generate_key().decode())
    assert asyncio.run(execute_run(s,run,settings));s.commit();s.refresh(run)
    assert run.status=="FAILED"
    assert not asyncio.run(execute_run(s,run,settings))


def test_revision_backward_compatibility_without_function_evidence(lab):
    from hashlib import sha256
    s,p,t,a,o,rt,r=lab
    c=config(a,o,rt,r)
    original=c.model_dump()
    for operation in original["operations"]:operation.pop("evidence")
    legacy_digest=sha256(json.dumps(original,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    assert revision(c)==legacy_digest


@pytest.mark.parametrize("status,http_status,metadata,expected", [
    ("CANCELLED", None, {}, "NOT_RUN"),
    ("REQUEST_LIMIT_REACHED", None, {}, "NOT_RUN"),
    ("SCOPE_BLOCKED", None, {}, "NOT_RUN"),
    ("BODY_TRUNCATED", 200, {"body_truncated": True}, "INSUFFICIENT_EVIDENCE"),
    ("JSON_PARSE_ERROR", 200, {"json_parse_error": True}, "INSUFFICIENT_EVIDENCE"),
    ("TIMEOUT", None, {}, "INSUFFICIENT_EVIDENCE"),
    ("NETWORK_ERROR", None, {}, "INSUFFICIENT_EVIDENCE"),
    ("CANCELLED", 403, {"body_length": 12}, "INSUFFICIENT_EVIDENCE"),
])
def test_results_normalize_historical_taxonomy_without_mutation(lab, status, http_status, metadata, expected):
    from copy import deepcopy
    from backend.app.api.authorization_routes import authorization_results
    s,p,t,a,o,rt,r=lab
    c=config(a,o,rt,r)
    payload=selection(s,p,t,c)
    run=queue_selected(s,p.id,selected_snapshot(s,p.id,t,c,payload))
    snapshot=deepcopy(run.snapshot)
    row=RunResult(run_id=run.id, case_key=run.snapshot["cases"][0]["case_id"],
        execution_status=status, authorization_conclusion="NOT_EVALUATED",
        reason_codes=["execution.original_reason"], http_status=http_status,
        response_metadata=metadata)
    s.add(row);s.commit()
    dto=authorization_results(p.id,run.id,s)
    observed=next(x for x in dto["cases"] if x["result_id"]==row.id)
    assert observed["conclusion"]==expected
    assert observed["execution_status"]==status
    assert observed["reason_codes"]==["execution.original_reason"]
    assert all(x["conclusion"] in {"NOT_RUN", "INSUFFICIENT_EVIDENCE"} for x in dto["cases"])
    s.expire_all()
    assert s.get(RunResult,row.id).authorization_conclusion=="NOT_EVALUATED"
    assert run.snapshot==snapshot

@pytest.mark.parametrize("status", [ExecutionStatus.SCOPE_BLOCKED,
    ExecutionStatus.REQUEST_LIMIT_REACHED, ExecutionStatus.CANCELLED])
def test_automatic_pre_dispatch_case_is_not_run(status):
    result=evaluate_authorization_case(case=eval_case(), identity_confirmed=True,
        baseline_valid=True, baseline_body={"id":"book","secret":"private"},
        observation=Observation(status,None,None))
    assert result.conclusion=="NOT_RUN"
    assert result.reason_codes==(f"execution.{status.lower()}",)

@pytest.mark.parametrize('legacy', [False, True, 'partial', 'missing_role'])
def test_identity_labels_are_immutable_and_actual_baseline_is_observed(lab, legacy):
    from copy import deepcopy
    from backend.app.api.authorization_routes import authorization_results
    from backend.app.services.demo_presentation import public_snapshot
    s,p,t,a,o,rt,r=lab
    payload=selection(s,p,t,config(a,o,rt,r))
    snapshot=selected_snapshot(s,p.id,t,config(a,o,rt,r),payload)
    if legacy is True:
        snapshot.pop('display_metadata')
    elif legacy == 'partial':
        snapshot['display_metadata']['identities'] = snapshot['display_metadata']['identities'][1:]
    elif legacy == 'missing_role':
        for item in snapshot['display_metadata']['identities']:
            item.pop('role', None)
    run=queue_selected(s,p.id,snapshot)
    before=deepcopy(run.snapshot)
    case=run.snapshot['cases'][0]
    actual=a[-1].id  # deliberately different observation: DTO must not mask mismatch
    s.add(RunResult(run_id=run.id,case_key=case['case_id'],execution_status='COMPLETED_RESPONSE',
        authorization_conclusion='CONFIRMED_VIOLATION',http_status=200,reason_codes=['preserved'],
        response_metadata={'evidence':{'baseline_identity_id':actual,'baseline_valid':True,'private':'NEVER_EXPOSE'}}))
    for identity in a:
        identity.display_name='renamed-'+str(identity.id)
    s.commit()
    dto=authorization_results(p.id,run.id,s)
    presentation=dto['cases'][0]['presentation']
    # Current identities are unavailable in this archive presentation adapter.
    from types import SimpleNamespace
    from backend.app.persistence.models import Run
    def archived_get(model, key):
        assert model is Run and key == run.id
        return run
    archived = SimpleNamespace(get=archived_get, scalars=s.scalars)
    assert authorization_results(p.id,run.id,archived) == dto
    assert presentation['actual_baseline']['id']==actual
    assert presentation['planned_baseline']['id']==case['baseline_identity_id']
    assert presentation['baseline_provenance']=='OBSERVED_EVIDENCE'
    if legacy is True:
        assert presentation['actor']['display_name'] is None
        assert presentation['actor']['source']=='LEGACY_UNAVAILABLE'
    elif legacy is False:
        assert presentation['actor']['display_name'].startswith('actor-')
        assert presentation['actor']['role'] in {'user','admin'}
        assert presentation['resource_name'].startswith('resource-')
    assert all(x['presentation']['baseline_provenance']=='NOT_OBSERVED' for x in dto['cases'][1:])
    assert 'NEVER_EXPOSE' not in json.dumps(dto)
    assert 'renamed-' not in json.dumps(dto)
    assert public_snapshot(run.snapshot)['policy_revision']==snapshot['policy_revision']
    historical_roles = {i['id']: i['role'] for i in snapshot['identities']}
    summaries = public_snapshot(run.snapshot)['case_summaries']
    for row, summary in zip(dto['cases'], summaries, strict=True):
        for result_key, summary_key in [('actor', 'actor'), ('owner', 'owner'),
                                        ('planned_baseline', 'baseline')]:
            label = row['presentation'][result_key]
            assert label == summary[summary_key]
            assert label['role'] == historical_roles.get(label['id'])
    s.expire_all()
    assert run.snapshot==before
