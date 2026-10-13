"""Refuse state-changing requests that a browser sends from another site (cross-site request forgery).

The login cookie is ``SameSite=Lax``, which already keeps it off cross-site POSTs in current browsers; this adds the check the
standard headers allow: a POST, PUT, PATCH or DELETE that says where it comes from (``Origin``, else ``Referer``) must come
from this site. A request that says nothing (a script, a test client) passes, and a safe request is never looked at.

"This site" is the host of the request, the host a reverse proxy forwarded (``X-Forwarded-Host``) and the origins listed in
the ``csrf.trusted_origins`` setting (comma separated, ``https://fax.example.com``). The identity provider posts its SAML
answer from its own site, so those callbacks are exempt.
"""

from __future__ import annotations

from typing import Callable
from urllib.parse import urlsplit

from pyramid.httpexceptions import HTTPForbidden

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
EXEMPT_PATHS = {"/auth/saml/acs", "/auth/saml/sls"}


def _netloc(value: str) -> str:
    value = value.strip()
    return urlsplit(value if "//" in value else f"//{value}").netloc.lower()


def origin_guard_factory(handler: Callable, registry) -> Callable:
    settings = registry.settings or {}
    trusted = {_netloc(v) for v in str(settings.get("csrf.trusted_origins", "")).split(",") if v.strip()}

    def tween(request):
        if request.method in UNSAFE_METHODS and request.path not in EXEMPT_PATHS:
            origin = request.headers.get("Origin") or request.headers.get("Referer")
            if origin is not None:
                allowed = {request.host.lower(), *trusted}
                forwarded = request.headers.get("X-Forwarded-Host")
                if forwarded:
                    allowed.add(forwarded.split(",")[0].strip().lower())
                if _netloc(origin) not in allowed or origin.strip().lower() == "null":
                    return HTTPForbidden("This request came from another site.")
        return handler(request)

    return tween
