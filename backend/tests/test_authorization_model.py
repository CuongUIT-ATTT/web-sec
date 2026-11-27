"""Deterministic isolated fixtures; never opens configured persistent databases."""
import pytest
from pydantic import ValidationError
from sqlalchemy import select, text
from backend.app.persistence.database import create_session_factory
from backend.app.persistence.models import (Project, Target, Identity, IdentitySecret,
    IdentityVerification, OpenApiOperation, ResourceType, Resource, Run)
from backend.app.services.authorization_model import (AuthorizationConfig, preview, decision)


@pytest.fixture
def lab(tmp_path):
    factory = create_session_factory(tmp_path / "isolated.sqlite")
    with factory() as s:
        p = Project(name="isolated")
        s.add(p)
        s.flush()
        target = Target(project_id=p.id, base_url="http://127.0.0.1:9999", request_limit=100)
        s.add(target)
        actors = [Identity(project_id=p.id, display_name=f"actor-{i}", role=role,
                  principal_pointer="/id", expected_principal=f"fixture-{i}") for i, role in enumerate(["user", "user", "admin"])]
        s.add_all(actors)
        s.flush()
        for actor in actors:
            s.add(IdentitySecret(identity_id=actor.id, ciphertext="fixture-encrypted", fingerprint=f"fixture-{actor.id}"))
            s.add(IdentityVerification(identity_id=actor.id, target_id=target.id, authentication_passed=True,
                  principal_matched=True, execution_status="COMPLETED_RESPONSE"))
        rt = ResourceType(project_id=p.id, name="book", resource_id_pointer="/id", restricted_pointers=["/secret"])
        s.add(rt)
        operations = [OpenApiOperation(project_id=p.id, operation_key=str(i), method=m, path=path, selected=True)
                      for i, (m, path) in enumerate([("GET", "/books/{id}"), ("GET", "/reports"), ("POST", "/reports"), ("GET", "/admin/public")])]
        s.add_all(operations)
        s.flush()
        resources = [Resource(resource_type_id=rt.id, external_id=f"fixture-{a.id}-{i}", owner_identity_id=a.id, path_parameter="id") for a in actors for i in range(2)]
        s.add_all(resources)
        s.add(Run(project_id=p.id, status="COMPLETED", snapshot={"legacy": "immutable"}))
        s.commit()
        yield s, p, target, actors, operations, rt, resources


def config(actors, ops, rt, resources):
    return AuthorizationConfig.model_validate(dict(operations=[
        dict(operation_id=ops[0].id, kind="BOLA", approved=True, resource_type_id=rt.id),
        dict(operation_id=ops[1].id, kind="BFLA", approved=True),
        dict(operation_id=ops[2].id, kind="BFLA", approved=True),
        dict(operation_id=ops[3].id, kind="BFLA", approved=True)],
        sharing=[dict(resource_id=resources[0].id, identity_ids=[actors[1].id])],
        rules=[dict(key="owner", decision="ALLOW", relation="OWNER"),
               dict(key="shared", decision="ALLOW", relation="SHARED"),
               dict(key="admin", decision="ALLOW", roles=["admin"]),
               dict(key="cross-deny", decision="DENY", relation="NON_OWNER", roles=["user"], identity_ids=[actors[0].id]),
               dict(key="function-deny", decision="DENY", roles=["user"], operation_ids=[ops[1].id,ops[2].id])]))


def test_complete_counts_stability_and_budget(lab):
    s,p,t,a,o,rt,r = lab
    c = config(a,o,rt,r)
    result = preview(s,p.id,t,c)
    assert result["actor_case_count"] == 27  # 3*6 + 3*3 functions
    assert result["identity_count"] == 3 and result["exclusions"] == []
    assert len({x["case_id"] for x in result["cases"]}) == 27
    assert result == preview(s,p.id,t,c)
    bola = [x for x in result["cases"] if x["kind"] == "BOLA"]
    assert len(bola) == 18
    assert sum(x["relationship"] == "OWNER" for x in bola) == 6
    assert all(x["expected_decision"] == "ALLOW" for x in bola if x["relationship"] == "OWNER")
    shared = next(x for x in bola if x["actor_identity_id"]==a[1].id and x["resource_id"]==r[0].id)
    assert shared["relationship"] == "SHARED" and shared["expected_decision"] == "ALLOW"
    denied = next(x for x in bola if x["actor_identity_id"]==a[0].id and x["resource_id"]==r[2].id)
    assert denied["expected_decision"] == "DENY"
    assert all(x["expected_decision"] == "ALLOW" for x in bola if x["actor_role"] == "admin")
    assert result["authorized_baselines"] == 6
    assert result["planned_attempts"] == result["executable_case_count"] + 6 + 3
    assert result["within_request_limit"]
    t.request_limit = 1
    assert not preview(s,p.id,t,c)["within_request_limit"]
    assert s.scalar(select(Run)).snapshot == {"legacy":"immutable"}
    # Policy edits preserve case identity but change the policy revision.
    changed = c.model_copy(deep=True)
    changed.rules[0].decision = "UNKNOWN"
    updated = preview(s,p.id,t,changed)
    assert updated["policy_revision"] != result["policy_revision"]
    assert [x["case_id"] for x in updated["cases"]] == [x["case_id"] for x in result["cases"]]


def test_function_roles_unknown_and_write_not_dispatched(lab):
    s,p,t,a,o,rt,r = lab
    result = preview(s,p.id,t,config(a,o,rt,r))
    functions = [x for x in result["cases"] if x["kind"] == "BFLA"]
    assert len(functions)==9
    assert all(x["resource_id"] is None and x["execution_status"]=="NOT_RUN" and not x["execution_eligible"] for x in functions)
    assert all(x["expected_decision"]=="DENY" for x in functions if x["actor_role"]=="user" and x["operation_id"]!=o[3].id)
    # A path containing admin confers no privilege or implicit policy.
    assert all(x["expected_decision"]=="UNKNOWN" for x in functions if x["actor_role"]=="user" and x["operation_id"]==o[3].id)
    assert all("DISPOSABLE_WRITE_AUTHORIZATION_REQUIRED" in x["reasons"] for x in functions if x["method"]=="POST")


def test_explicit_deny_overrides_owner_share_admin(lab):
    s,p,t,a,o,rt,r = lab
    c=config(a,o,rt,r)
    c.rules.append(type(c.rules[0])(key="override",decision="DENY",identity_ids=[a[2].id]))
    assert decision(c,c.operations[0],a[2],r[4])[0]=="DENY"
    c.rules.append(type(c.rules[0])(key="share-deny",decision="DENY",identity_ids=[a[1].id]))
    assert decision(c,c.operations[0],a[1],r[0])[0]=="DENY"


def test_missing_baseline_token_failure_exclusions_mapping(lab):
    s,p,t,a,o,rt,r=lab
    c=config(a,o,rt,r)
    s.add(IdentityVerification(identity_id=a[2].id,target_id=t.id,authentication_passed=False,principal_matched=False,execution_status="COMPLETED_RESPONSE"))
    r[0].path_parameter="wrong"
    s.commit()
    result=preview(s,p.id,t,c)
    assert result["actor_case_count"]==18
    assert result["exclusions"]==[{"identity_id":a[2].id,"reason":"IDENTITY_NOT_VERIFIED"}]
    assert all("AMBIGUOUS_RESOURCE_MAPPING" in x["reasons"] for x in result["cases"] if x["resource_id"]==r[0].id)
    empty=c.model_copy(deep=True)
    empty.rules=[]
    assert all(x["baseline_identity_id"] is None for x in preview(s,p.id,t,empty)["cases"])
    assert preview(s,p.id,t,AuthorizationConfig())["actor_case_count"]==0
    assert len(preview(s,p.id,t,AuthorizationConfig())["exclusions"])==3


def test_ambiguous_mapping_rejected(lab):
    s,p,t,a,o,rt,r=lab
    c=config(a,o,rt,r).model_dump()
    c["operations"].append(c["operations"][0])
    with pytest.raises(ValidationError):
        AuthorizationConfig.model_validate(c)


def test_additive_table_preserves_legacy_file(tmp_path):
    from backend.app.persistence.database import create_sqlite_engine
    path=tmp_path/"legacy.sqlite"
    engine=create_sqlite_engine(path)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE projects (id INTEGER PRIMARY KEY, name VARCHAR(120), description TEXT, created_at DATETIME, updated_at DATETIME)"))
        conn.execute(text("INSERT INTO projects(id,name,description) VALUES(2,'old','preserve')"))
    factory=create_session_factory(path)
    with factory() as s:
        assert s.get(Project,2).description=="preserve"
        assert s.execute(text("SELECT count(*) FROM project_authorization_revisions")).scalar()==0
    create_session_factory(path)  # repeat upgrade is idempotent


def test_config_api_auth_csrf_revision_preview_and_inventory(tmp_path):
    from cryptography.fernet import Fernet
    from fastapi.testclient import TestClient
    from backend.app.core.settings import Settings
    from backend.app.main import create_app
    import ipaddress
    settings=Settings(target_networks=(ipaddress.ip_network("127.0.0.1/32"),),allowed_ports=frozenset({9999}),max_response_bytes=32768,default_timeout_seconds=5.0,database_path=tmp_path/"api.sqlite",admin_password="fixture-password",session_secret="s"*32,secret_encryption_key=Fernet.generate_key().decode())
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/projects/1/authorization/config").status_code==401
        login=client.post("/api/auth/login",json={"password":"fixture-password"})
        headers={"X-CSRF-Token":login.json()["csrf_token"]}
        p=client.post("/api/projects",json={"name":"API fixture"},headers=headers).json()
        root=f"/api/projects/{p['id']}/authorization"
        assert client.put(root+"/config",json={}).status_code==403
        assert client.get(root+"/config").json()["revision"] is None
        stored=client.put(root+"/config",json={},headers=headers)
        assert stored.status_code==200
        assert client.put(root+"/config",json={},headers=headers).json()==stored.json()
        assert client.get(root+"/config").json()["revision"]==stored.json()["revision"]
        target=client.post(f"/api/projects/{p['id']}/targets",json={"base_url":"http://127.0.0.1:9999"},headers=headers).json()
        generated=client.get(root+f"/preview?target_id={target['id']}")
        assert generated.status_code==200
        assert generated.json()["cases"]==[] and generated.json()["planned_attempts"]==0
        assert client.get(root+"/preview?target_id=999").status_code==404
        assert client.put(root+"/config",json={"operations":[{"operation_id":999,"kind":"BFLA"}]},headers=headers).status_code==422
        doc={"openapi":"3.0.0","paths":{"/function":{"get":{},"post":{}}}}
        inventory=client.post(root+"/openapi",json={"document":doc},headers=headers)
        assert inventory.status_code==200
        assert {o['method'] for o in inventory.json()}=={"GET","POST"}
        assert all(not o['selected'] for o in inventory.json())
        assert client.post(root+"/openapi",json={"document":doc},headers=headers).json()==inventory.json()


def test_missing_credentials_mapping_and_owner_fallback(lab):
    s,p,t,a,o,rt,r=lab
    c=config(a,o,rt,r)
    s.delete(s.get(IdentitySecret,a[0].id))
    a[1].principal_pointer=None
    s.commit()
    result=preview(s,p.id,t,c)
    assert {e["reason"] for e in result["exclusions"]}=={"MISSING_CREDENTIAL","MISSING_PRINCIPAL_MAPPING"}
    assert {x["actor_identity_id"] for x in result["cases"]}=={a[2].id}
    row=next(x for x in result["cases"] if x["resource_id"]==r[0].id)
    assert row["baseline_identity_id"]==a[2].id
    assert row["baseline_kind"]=="AUTHORIZED_ACTOR" and not row["owner_baseline_available"]


def test_cross_project_references_rejected(lab):
    from backend.app.services.authorization_model import validate_references, configuration_rows
    s,p,t,a,o,rt,r=lab
    c=config(a,o,rt,r)
    c.rules[0].identity_ids=[99999]
    with pytest.raises(ValueError,match="belong to project"):
        validate_references(c,*configuration_rows(s,p.id))
