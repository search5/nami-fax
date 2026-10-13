"""P5 (F): there is no process-wide default database; domain objects need an injected session."""

from __future__ import annotations

import pytest

from namifax.db.missing import MissingDatabase
from namifax.db.repository import MDBOData, Repository
from namifax.services.addressbook import NFAddressBook
from namifax.services.archive_in import ArchiveIn
from namifax.services.did import DIDRouting
from namifax.services.user_account import NFUserAccount


def test_repository_uses_injected_session(seeded_db):
    repo = Repository("DynConf", db=seeded_db)
    assert repo.session is seeded_db


@pytest.mark.parametrize("factory", [Repository, MDBOData], ids=["Repository", "MDBOData"])
def test_repository_without_db_is_a_loud_placeholder(factory):
    repo = factory("UserAccount")
    assert isinstance(repo.session, MissingDatabase)
    with pytest.raises(RuntimeError, match="database"):
        repo.load(1)


@pytest.mark.parametrize("factory", [NFUserAccount, NFAddressBook, DIDRouting, ArchiveIn], ids=lambda f: f.__name__)
def test_domain_class_without_db_does_not_silently_use_another_database(factory):
    obj = factory()
    with pytest.raises(RuntimeError, match="database"):
        # every domain class reaches the database through its repository on first load
        for attr in ("load", "load_fax", "load_route", "loadbycid"):
            if hasattr(obj, attr):
                getattr(obj, attr)(1)
                break


def test_domain_class_with_db_reads_from_that_db(seeded_db):
    user = NFUserAccount(db=seeded_db)
    assert user.load(1) is True


def test_the_legacy_engine_modules_are_gone():
    import importlib

    for name in ("namifax.db.engine", "namifax.db.query", "namifax.db.base"):
        with pytest.raises(ImportError):
            importlib.import_module(name)
