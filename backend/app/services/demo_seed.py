"""Explicit synthetic project bootstrap. Never opens a database or queues a run."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from backend.app.core.secrets import SecretBox
from backend.app.persistence.models import (Project, Target, Identity, IdentitySecret,
    OpenApiOperation, ResourceType, Resource, ProjectAuthorizationRevision)
from backend.app.scanner.execution.scope import validate_base_url
from backend.app.services.authorization_model import AuthorizationConfig, revision

NAME = "T18 Synthetic GET Demo v1"
DESCRIPTION = "SYNTHETIC v1 — dữ liệu mô phỏng BOLA/BFLA; không phải evidence nghiên cứu."


def seed_demo(session, settings):
    """One atomic creation; subsequent calls return existing IDs without edits.

    BEGIN IMMEDIATE serializes concurrent seed calls, including the read before
    insert. A user-created name collision fails closed instead of being adopted.
    Identity verification is intentionally left to real GET /me requests.
    """
    if not settings.demo_target_url:
        raise ValueError("Demo chưa được cấu hình. Chạy web bằng deploy/compose.yaml.")
    url = validate_base_url(settings.demo_target_url, settings)
    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    project = session.scalar(select(Project).where(Project.name == NAME))
    if project:
        if project.description != DESCRIPTION:
            raise ValueError("Tên dự án mẫu đã được dùng; dữ liệu hiện có được giữ nguyên.")
        session.commit()
        return project, False
    project = Project(name=NAME, description=DESCRIPTION)
    session.add(project)
    session.flush()
    session.add(Target(project_id=project.id, base_url=url, timeout_seconds=2,
                       request_limit=100, verification_path="/me"))
    box = SecretBox.from_key(settings.secret_encryption_key)
    actors = []
    for name, role in (("userA", "user"), ("userB", "user"), ("admin", "admin")):
        actor = Identity(project_id=project.id, display_name=name, role=role,
                         principal_pointer="/id", expected_principal=name)
        session.add(actor)
        session.flush()
        encrypted, fingerprint = box.encrypt_bearer(f"t18-synthetic-v1-{name}")
        session.add(IdentitySecret(identity_id=actor.id, ciphertext=encrypted, fingerprint=fingerprint))
        actors.append(actor)
    resource_type = ResourceType(project_id=project.id, name="synthetic-book",
                                 resource_id_pointer="/id", restricted_pointers=["/secret"])
    session.add(resource_type)
    operations = [OpenApiOperation(project_id=project.id, operation_key=f"GET:{path}",
                  method="GET", path=path, selected=True)
                  for path in ("/books/{id}", "/reports")]
    session.add_all(operations)
    session.flush()
    for actor in actors:
        session.add(Resource(resource_type_id=resource_type.id, external_id=f"{actor.display_name}-book",
                             owner_identity_id=actor.id, path_parameter="id"))
    config = AuthorizationConfig.model_validate(dict(operations=[
        dict(operation_id=operations[0].id, kind="BOLA", approved=True, resource_type_id=resource_type.id),
        dict(operation_id=operations[1].id, kind="BFLA", approved=True,
             evidence=dict(result_pointer="/id", result_value="report", protected_pointers=["/secret"]))],
        rules=[dict(key="owner", decision="ALLOW", relation="OWNER", operation_ids=[operations[0].id]),
               dict(key="admin", decision="ALLOW", roles=["admin"]),
               dict(key="cross-user", decision="DENY", relation="NON_OWNER", roles=["user"], operation_ids=[operations[0].id]),
               dict(key="reports-admin-only", decision="DENY", roles=["user"], operation_ids=[operations[1].id])]))
    session.add(ProjectAuthorizationRevision(project_id=project.id, revision=revision(config), configuration=config.model_dump()))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ValueError("Không thể tạo mẫu vì cấu hình trùng; dữ liệu hiện có được giữ nguyên.") from None
    return project, True
