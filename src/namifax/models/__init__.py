"""NamiFAX SQLAlchemy Models and Pyramid Session Factory Integration."""

from __future__ import annotations

import os
import zope.sqlalchemy
from sqlalchemy.orm import configure_mappers, sessionmaker

from namifax.models.meta import Base  # noqa: F401

from namifax.models.syslog import SysLog  # noqa: F401
from namifax.models.systemconfig import SystemConfig  # noqa: F401
from namifax.models.addressbook import AddressBook, AddressBookEmail, AddressBookFAX  # noqa: F401
from namifax.models.coverpages import CoverPages  # noqa: F401
from namifax.models.distrolist import DistroList  # noqa: F401
from namifax.models.dynconf import DynConf  # noqa: F401
from namifax.models.faxcategory import FaxCategory  # noqa: F401
from namifax.models.networkprinters import NetworkPrinters  # noqa: F401
from namifax.models.modems import Modems  # noqa: F401
from namifax.models.didroute import DIDRoute  # noqa: F401
from namifax.models.barcoderoute import BarcodeRoute  # noqa: F401
from namifax.models.systemsettings import SystemSettings  # noqa: F401
from namifax.models.useraccount import UserAccount  # noqa: F401
from namifax.models.faxarchive import FaxArchive  # noqa: F401
from namifax.models.usertotp import UserTOTP  # noqa: F401
from namifax.models.userwebauthn import UserWebAuthnCredentials  # noqa: F401
from namifax.models.userpasswords import UserPasswords  # noqa: F401

configure_mappers()


def get_engine(settings=None, prefix="sqlalchemy."):
    """Create SQLAlchemy engine from settings or environment (spec 48)."""
    from namifax.db.provider import create_sa_engine, resolve_database_url

    return create_sa_engine(resolve_database_url(settings, os.environ))


def get_session_factory(engine):
    """Create session factory bound to engine."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_tm_session(session_factory, transaction_manager, request=None):
    """Get a ``sqlalchemy.orm.Session`` joined to ``transaction_manager``.

    With ``pyramid_tm`` the session is committed or aborted with the request. Scripts must
    wrap it themselves::

        import transaction

        with transaction.manager:
            dbsession = get_tm_session(session_factory, transaction.manager)

    The active request, if any, is stored in ``session.info["request"]``.
    """
    dbsession = session_factory(info={"request": request})
    zope.sqlalchemy.register(dbsession, transaction_manager=transaction_manager)
    return dbsession


def includeme(config):
    """Pyramid extension hook: config.include('namifax.models')."""
    settings = config.get_settings()

    # Use ``pyramid_tm`` to hook the transaction lifecycle to the request. The manager hook must
    # be set before the include because pyramid_tm reads it while being configured.
    settings["tm.manager_hook"] = "pyramid_tm.explicit_manager"
    config.include("pyramid_tm")

    # Retry a request when transient exceptions (e.g. serialization failures) occur.
    config.include("pyramid_retry")

    # hook to share the dbengine fixture in testing
    engine = settings.get("dbengine")
    if not engine:
        engine = get_engine(settings)

    settings["dbengine"] = engine
    config.registry["dbengine"] = engine
    session_factory = get_session_factory(engine)
    config.registry["dbsession_factory"] = session_factory

    # make request.dbsession available for use in Pyramid
    def dbsession(request):
        # hook to share the dbsession fixture in testing
        session = request.environ.get("app.dbsession")
        if session is None:
            # request.tm is the transaction manager used by pyramid_tm
            session = get_tm_session(session_factory, request.tm, request=request)
        return session

    config.add_request_method(dbsession, reify=True)
