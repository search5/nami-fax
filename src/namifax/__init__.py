"""NamiFAX Modern Enterprise Fax Platform Package with Pyramid, SQLAlchemy, and Security Policy."""

from __future__ import annotations

import os

__version__ = "4.0.0"


def create_app(global_config=None, **settings):
    """Pyramid application factory configuring SQLAlchemy, SecurityPolicy, routes, and views."""
    from pyramid.config import Configurator
    import namifax
    from namifax.security import NamiFaxSecurityPolicy, RootContext

    tpl_dir = os.path.join(os.path.dirname(__file__), "templates")
    settings.setdefault("jinja2.directories", tpl_dir)
    settings.setdefault("pyramid.default_locale_name", "en")
    settings.setdefault("jinja2.i18n.domain", "namifax")

    from namifax.i18n import custom_locale_negotiator

    with Configurator(package=namifax, settings=settings, root_factory=RootContext) as config:
        # Set modern Pyramid Security Policy
        policy = NamiFaxSecurityPolicy()
        config.set_security_policy(policy)
        config.registry.namifax_policy = policy

        # Short-lived signed cookie for flow state (the 2FA step, passkey challenges). Login itself is the
        # token cookie of the security policy, not this one.
        config.set_session_factory(_session_factory(settings))

        from namifax.common.secretbox import set_default_key
        set_default_key(settings.get("secret.key"))

        # Include i18n translation directories & negotiator
        config.add_translation_dirs("namifax:locale")
        config.set_locale_negotiator(custom_locale_negotiator)

        # Include Jinja2 and SQLAlchemy models (creates the single engine, spec 48)
        config.include("pyramid_jinja2")
        config.include(".models")

        # The admin menu follows the settings (the original's $ENABLE_DID_ROUTING / ENABLE_BARDECODE_SUPPORT)
        from namifax.services.fax_access import _did_routing_enabled, barcode_enabled
        import socket

        from pyramid.events import BeforeRender

        from namifax.common.settings import flag, text

        def add_switches(event):
            event["did_routing_enabled"] = _did_routing_enabled()
            event["barcode_enabled"] = barcode_enabled()
            event["dl_tiff_enabled"] = flag("ENABLE_DL_TIFF", False)
            event["show_server_name"] = flag("SHOWSERVER_DETAILS", False)
            event["focus_on_new_fax"] = flag("FOCUS_ON_NEW_FAX", False)
            event["popup_on_new_fax"] = flag("FOCUS_ON_NEW_FAX_POPUP", False)
            event["server_name"] = text("AVANTFAX_SERVERNAME", socket.gethostname())
            _add_page_counters(event)

        config.add_subscriber(add_switches, BeforeRender)

        # Initialize DB tables and seed data on the injected engine
        from namifax.db.bootstrap import ensure_schema
        ensure_schema(config.registry["dbengine"], settings)

        config.include(".routes")
        config.add_tween("namifax.origin_guard.origin_guard_factory")

        # Scan views for @view_config decorators
        config.scan(".views")

        return config.make_wsgi_app()


def _add_page_counters(event) -> None:
    """The unread count and the user's modems for the header of every page (the inbox page already brings its own count)."""
    request = event.get("request")
    if request is None or not getattr(request, "identity", None):
        return
    try:
        from namifax.views.fax_rights import fax_access

        access = fax_access(request)
        if event.get("num_inbox") is None:
            from namifax.services.archive_in import ArchiveIn

            count = ArchiveIn(db=request.dbsession).get_num_faxes(access.devices, access.categories, access.did_routing)
            event["num_inbox"] = count or None
        if event.get("user_full_name") is None:
            from sqlalchemy import select

            from namifax.models import UserAccount

            who = request.identity or {}
            event["user_full_name"] = request.dbsession.execute(
                select(UserAccount.name).where(UserAccount.uid == (who.get("user_id") or who.get("uid") or 0))).scalar()
        if event.get("modem_devices") is None:
            event["modem_devices"] = list((access.configured_modems if access.superuser else access.modems) or [])
    except Exception:
        pass


def _session_factory(settings):
    """Signed-cookie session; the secret comes from ``session.secret`` or ``NAMIFAX_SESSION_SECRET``.

    Without one a random secret is used, which is fine for a single process but means that a restart, or a
    request answered by another worker, loses the flow state. Production should set a fixed secret.
    """
    import logging
    import secrets

    from pyramid.session import SignedCookieSessionFactory

    secret = settings.get("session.secret") or os.environ.get("NAMIFAX_SESSION_SECRET")
    if not secret:
        secret = secrets.token_hex(32)
        logging.getLogger("namifax").warning(
            "No session.secret / NAMIFAX_SESSION_SECRET configured: using a random one for this process only")
    # the ini wins; without it NAMIFAX_SESSION_SECURE (for a deployment that has no ini) decides
    flag = settings.get("session.secure")
    if flag is None:
        flag = os.environ.get("NAMIFAX_SESSION_SECURE", "false")
    secure = str(flag).strip().lower() in ("1", "true", "yes")
    return SignedCookieSessionFactory(
        secret,
        cookie_name="namifax_flow",
        httponly=True,
        samesite="Lax",
        secure=secure,
        timeout=1800,
    )


main = create_app

