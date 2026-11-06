from cryptography.fernet import Fernet

from backend.app.core.secrets import SecretBox
from backend.app.persistence.database import create_session_factory
from backend.app.persistence.models import Identity, IdentitySecret, Project, Run, RunResult
from backend.app.services.serializers import serialize_identity, serialize_result


def test_sqlite_persists_secret_ciphertext_but_serializers_never_return_it(tmp_path) -> None:
    session_factory = create_session_factory(tmp_path / "app.sqlite3")
    box = SecretBox.from_key(Fernet.generate_key().decode("ascii"))
    ciphertext, fingerprint = box.encrypt_bearer("private-token")

    with session_factory.begin() as session:
        project = Project(name="Lab", description="")
        session.add(project)
        session.flush()
        identity = Identity(project_id=project.id, display_name="Alice", role="reader")
        session.add(identity)
        session.flush()
        session.add(IdentitySecret(identity_id=identity.id, ciphertext=ciphertext, fingerprint=fingerprint, key_version=1))
        run = Run(project_id=project.id, snapshot={"target": "safe"})
        session.add(run)
        session.flush()
        result = RunResult(run_id=run.id, case_key="case-1", execution_status="COMPLETED_RESPONSE", authorization_conclusion="INSUFFICIENT_EVIDENCE", reason_codes=["evidence.example"], http_status=403, response_metadata={"body_length": 10})
        session.add(result)

    with session_factory() as session:
        identity = session.query(Identity).one()
        result = session.query(RunResult).one()
        identity_view = serialize_identity(identity)
        result_view = serialize_result(result)

    assert identity_view["has_secret"] is True
    assert "ciphertext" not in identity_view
    assert "private-token" not in repr(identity_view)
    assert result_view["response_metadata"] == {"body_length": 10}
