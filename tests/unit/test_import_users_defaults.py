"""import_users gives the new accounts the sender defaults of the installation (FROM_*), the default language and an empty
signature, and a short line is reported instead of skipped without a word (the original tools/import_users.php)."""

from __future__ import annotations

from sqlalchemy import select

from namifax.cli import import_users
from namifax.models import UserAccount


def _import(session, tmp_path, text):
    path = tmp_path / "users.txt"
    path.write_text(text, encoding="utf-8")
    import io
    from contextlib import redirect_stdout

    out = io.StringIO()
    with redirect_stdout(out):
        import_users.main([str(path)], session=session)
    return out.getvalue()


def _user(session, username):
    session.expire_all()
    return session.execute(select(UserAccount).where(UserAccount.username == username)).scalar_one_or_none()


def test_the_sender_defaults_are_filled_in(dbsession, tmp_path, monkeypatch):
    monkeypatch.setenv("FROM_COMPANY", "Corp Inc")
    monkeypatch.setenv("FROM_LOCATION", "Seoul")
    monkeypatch.setenv("FROM_VOICENUMBER", "+82-2-1")
    monkeypatch.setenv("FROM_FAXNUMBER", "+82-2-2")
    _import(dbsession, tmp_path, "Jane Roe\tjroe\tSecret123!\tjroe@corp.test\n")
    user = _user(dbsession, "jroe")
    assert (user.from_company, user.from_location, user.from_voicenumber, user.from_faxnumber) == ("Corp Inc", "Seoul", "+82-2-1", "+82-2-2")


def test_a_short_line_is_reported(dbsession, tmp_path):
    out = _import(dbsession, tmp_path, "Only Name\tonly\n")
    assert "Error>" in out and "Only Name" in out and _user(dbsession, "only") is None


def test_a_blank_line_is_ignored(dbsession, tmp_path):
    out = _import(dbsession, tmp_path, "\n\nJim Poe\tjpoe\tSecret123!\tjpoe@corp.test\n")
    assert "Jim Poe: User details saved" in out and _user(dbsession, "jpoe") is not None


def test_the_default_language_is_used(dbsession, tmp_path, monkeypatch):
    monkeypatch.setenv("NAMIFAX_DEFAULT_LANGUAGE", "ko")
    _import(dbsession, tmp_path, "Kim\tkim1\tSecret123!\tkim1@corp.test\n")
    assert _user(dbsession, "kim1").language == "ko"
