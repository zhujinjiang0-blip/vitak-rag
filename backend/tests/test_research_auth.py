from app.schemas import UserRole
from app.services.auth import AuthStore, password_digest, password_matches


def test_password_hash_is_salted_and_verifiable():
    first = password_digest("research-pass")
    second = password_digest("research-pass")

    assert first != second
    assert password_matches("research-pass", first)
    assert not password_matches("wrong-password", first)


def test_session_expiry_disable_and_revoke(tmp_path):
    store = AuthStore(tmp_path / "auth.sqlite3", session_ttl_hours=24)
    user = store.create_user(
        "researcher",
        "research-pass",
        display_name="研究员",
        role=UserRole.RESEARCHER,
    )
    authenticated = store.authenticate("researcher", "research-pass")

    assert authenticated is not None
    current, token = authenticated
    assert current.id == user.id
    assert store.resolve_session(token).username == "researcher"

    assert store.revoke_sessions("researcher") == 1
    assert store.resolve_session(token) is None

    _, second_token = store.authenticate("researcher", "research-pass")
    assert store.set_active("researcher", False)
    assert store.resolve_session(second_token) is None
    assert store.authenticate("researcher", "research-pass") is None


def test_password_reset_revokes_existing_sessions(tmp_path):
    store = AuthStore(tmp_path / "auth.sqlite3", session_ttl_hours=24)
    store.create_user("researcher", "research-pass")
    _, token = store.authenticate("researcher", "research-pass")

    assert store.reset_password("researcher", "new-research-pass")
    assert store.resolve_session(token) is None
    assert store.authenticate("researcher", "research-pass") is None
    assert store.authenticate("researcher", "new-research-pass") is not None
