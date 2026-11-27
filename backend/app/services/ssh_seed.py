"""Explicit SSH lab profile; configuration only, no HTTP or credential creation.

Historical resources, revisions and evidence remain append-only. Applying to an
existing synthetic project deliberately replaces its *active* authorization rules.
"""
from sqlalchemy import select
from backend.app.persistence.models import (
    Project, Target, Identity, IdentityVerification, OpenApiOperation,
    ResourceType, Resource, ProjectAuthorizationRevision, Run,
)
from backend.app.scanner.execution.scope import validate_base_url
from backend.app.services.authorization_model import AuthorizationConfig, revision
from backend.app.services.demo_seed import NAME, DESCRIPTION

SSH_URL = "http://100.106.64.21:5003"
SSH_NAME = "T18 SSH GET Lab v1"
SSH_DESCRIPTION = "SSH v1 — contract fixtures; scenario policy remains operator supplied."


def seed_ssh(session, settings, *, project_id=None, transaction_started=False):
    """Create SSH project or explicitly migrate the known synthetic seed.

    Caller owns commit/rollback. No secrets are read or changed. Reapplication is
    idempotent; verification is invalidated only if its target/principal changes.
    """
    url = validate_base_url(SSH_URL, settings)
    if not transaction_started:
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    project = session.get(Project, project_id) if project_id is not None else session.scalar(
        select(Project).where(Project.name == SSH_NAME))
    if project_id is not None and project is None:
        raise ValueError("Không tìm thấy dự án.")
    if project and (project.name, project.description) not in (
        (NAME, DESCRIPTION), (SSH_NAME, SSH_DESCRIPTION)
    ):
        raise ValueError("Chỉ áp dụng cho dự án mẫu đã biết; giữ nguyên dự án khác.")
    if project and session.scalar(select(Run.id).where(
        Run.project_id == project.id, Run.status.in_(["QUEUED", "RUNNING", "CANCELLING"])).limit(1)):
        raise ValueError("Dự án còn run chưa kết thúc; chưa đổi cấu hình.")
    if project is None:
        project = Project(name=SSH_NAME, description=SSH_DESCRIPTION)
        session.add(project)
        session.flush()
    targets = list(session.scalars(select(Target).where(Target.project_id == project.id)))
    if len(targets) > 1:
        raise ValueError("Dự án có nhiều target; chưa đổi cấu hình.")
    target = targets[0] if targets else Target(project_id=project.id, base_url=url)
    session.add(target)
    changed_target = target.base_url != url or target.verification_path != "/me"
    target.base_url, target.verification_path = url, "/me"
    actors = {a.display_name: a for a in session.scalars(select(Identity).where(Identity.project_id == project.id))}
    if set(actors) - {"userA", "userB", "admin"}:
        raise ValueError("Có danh tính ngoài profile; chưa đổi cấu hình.")
    session.flush()
    for name, role in (("userA", "user"), ("userB", "user"), ("admin", "admin")):
        actor = actors.get(name)
        if actor is None:
            actor = Identity(project_id=project.id, display_name=name, role=role)
            session.add(actor)
            actors[name] = actor
        changed = changed_target or actor.principal_pointer != "/principal/username" or actor.expected_principal != name
        actor.principal_pointer, actor.expected_principal = "/principal/username", name
        session.flush()
        if changed:
            session.add(IdentityVerification(identity_id=actor.id, target_id=target.id,
                authentication_passed=False, principal_matched=False, execution_status="NOT_RUN",
                reason_codes=["SSH_PROFILE_REQUIRES_REVERIFICATION"]))
    operations = list(session.scalars(select(OpenApiOperation).where(OpenApiOperation.project_id == project.id)))
    for old in operations:
        old.selected = False
    operation = next((o for o in operations if o.operation_key == "GET:/books/{book_id}"), None)
    if operation is None:
        operation = OpenApiOperation(project_id=project.id, operation_key="GET:/books/{book_id}",
                                    method="GET", path="/books/{book_id}")
        session.add(operation)
    operation.selected = True
    resource_type = session.scalar(select(ResourceType).where(ResourceType.project_id == project.id, ResourceType.name == "ssh-book"))
    if resource_type is None:
        resource_type = ResourceType(project_id=project.id, name="ssh-book")
        session.add(resource_type)
    resource_type.resource_id_pointer, resource_type.restricted_pointers = "/data/id", ["/data/secret"]
    session.flush()
    for name, prefix in (("userA", "A"), ("userB", "B")):
        for suffix in (1, 2):
            external_id = f"book-{prefix}{suffix}"
            resource = session.scalar(select(Resource).where(Resource.resource_type_id == resource_type.id, Resource.external_id == external_id))
            if resource is None:
                resource = Resource(resource_type_id=resource_type.id, external_id=external_id)
                session.add(resource)
            resource.owner_identity_id, resource.path_parameter = actors[name].id, "book_id"
    config = AuthorizationConfig.model_validate(dict(operations=[dict(operation_id=operation.id,
        kind="BOLA", approved=True, resource_type_id=resource_type.id)], rules=[dict(
        key="ssh-owner", decision="ALLOW", relation="OWNER", operation_ids=[operation.id])]))
    digest = revision(config)
    latest = session.scalar(select(ProjectAuthorizationRevision).where(
        ProjectAuthorizationRevision.project_id == project.id).order_by(ProjectAuthorizationRevision.id.desc()).limit(1))
    if latest is None or latest.revision != digest:
        if session.scalar(select(ProjectAuthorizationRevision.id).where(
            ProjectAuthorizationRevision.project_id == project.id, ProjectAuthorizationRevision.revision == digest)):
            raise ValueError("Profile đã có trong lịch sử nhưng policy mới hơn đang hoạt động; không ghi đè.")
        session.add(ProjectAuthorizationRevision(project_id=project.id, revision=digest, configuration=config.model_dump()))
    session.flush()
    return project, target


def main():
    import argparse
    from backend.app.core.settings import Settings
    from backend.app.persistence.database import create_session_factory
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", type=int, help="Existing synthetic project ID; omit to create SSH profile")
    args = parser.parse_args()
    settings = Settings.from_environment()
    with create_session_factory(settings.database_path)() as session:
        try:
            project, target = seed_ssh(session, settings, project_id=args.project_id)
            session.commit()
        except Exception:
            session.rollback()
            raise
        print(f"project_id={project.id} target_id={target.id}; xác minh lại danh tính; policy cross-owner/admin UNKNOWN")


if __name__ == "__main__":
    main()
