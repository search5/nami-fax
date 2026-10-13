"""NamiFAX Security Policy and Authorization using pyramid.authorization."""

from __future__ import annotations

from typing import Any, List, Optional

try:
    from pyramid.authorization import (
        ACLAllowed,
        ACLDenied,
        ACLHelper,
        Allow,
        Authenticated,
        Deny,
        Everyone,
    )
    from pyramid.interfaces import ISecurityPolicy
    from zope.interface import implementer
except ImportError:
    Everyone = "system.Everyone"
    Authenticated = "system.Authenticated"
    Allow = "Allow"
    Deny = "Deny"

    class ACLAllowed(int):
        def __bool__(self) -> bool:
            return True

    class ACLDenied(int):
        def __bool__(self) -> bool:
            return False

    class ACLHelper:
        def permits(self, context: Any, principals: List[str], permission: str) -> Any:
            acl = getattr(context, "__acl__", None)
            if callable(acl):
                acl = acl()
            for ace in (acl or []):
                action, ace_principal, ace_permission = ace
                if ace_permission == permission and ace_principal in principals:
                    return ACLAllowed() if action == Allow else ACLDenied()
            return ACLDenied()

    class ISecurityPolicy:
        pass

    def implementer(*args: Any) -> Any:
        def decorator(cls: Any) -> Any:
            return cls
        return decorator

from namifax.services.user_account import NFUserAccount
from namifax.sessions import SessionManager


class RootContext:
    """Root ACL Context defining application permissions."""

    def __init__(self, request: Any) -> None:
        self.request = request

    def __acl__(self) -> List[tuple[str, str, str]]:
        return [
            (Allow, Everyone, "public"),
            (Allow, Authenticated, "view"),
            (Allow, Authenticated, "send_fax"),
            (Allow, "role:admin", "admin"),
            (Deny, Everyone, "admin"),
        ]


@implementer(ISecurityPolicy)
def _cookie_secure(request: Any) -> bool:
    """Whether the login cookie carries ``Secure``: ``session.secure`` (ini) wins, else ``NAMIFAX_SESSION_SECURE`` (same rule as the flow cookie)."""
    import os

    settings = getattr(getattr(request, "registry", None), "settings", None) or {}
    flag = settings.get("session.secure")
    if flag is None:
        flag = os.environ.get("NAMIFAX_SESSION_SECURE", "false")
    return str(flag).strip().lower() in ("1", "true", "yes")


class NamiFaxSecurityPolicy:
    """Modern Pyramid Security Policy managing authentication and authorization."""

    def __init__(self, session_manager: Optional[SessionManager] = None) -> None:
        self.session_manager = session_manager or SessionManager()
        self.acl_helper = ACLHelper()

    def _extract_token(self, request: Any) -> Optional[str]:
        """Extract auth token from Authorization header, request session, or cookies."""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()

        # Cookie fallback
        token = request.cookies.get("namifax_session") or request.cookies.get("avantfax_session")
        if token:
            return token

        # Request session fallback
        if hasattr(request, "session") and "token" in request.session:
            return request.session["token"]

        return None

    def identity(self, request: Any) -> Optional[dict[str, Any]]:
        """Return identity dict if authenticated, else None."""
        token = self._extract_token(request)
        if not token:
            return None

        sess = self.session_manager.get_session(token)
        if not sess:
            return None

        # Return cached session identity
        return {
            "token": sess.token,
            "user_id": sess.user_id,
            "username": sess.username,
            "is_admin": sess.is_admin,
            "superuser": sess.superuser,
        }

    def authenticated_userid(self, request: Any) -> Optional[str]:
        """Return username of the authenticated user, or None."""
        ident = self.identity(request)
        return str(ident["username"]) if ident else None

    def effective_principals(self, request: Any) -> List[str]:
        """Resolve principals (roles and user identifiers) for the request."""
        principals = [Everyone]
        ident = self.identity(request)

        if ident:
            principals.append(Authenticated)
            principals.append(f"user:{ident['user_id']}")
            principals.append(f"username:{ident['username']}")

            if ident.get("is_admin") or ident.get("superuser"):
                principals.append("role:admin")
            else:
                principals.append("role:user")

        return principals

    def permits(self, request: Any, context: Any, permission: str) -> Any:
        """Check if request identity has the requested permission in context."""
        principals = self.effective_principals(request)
        # Use Pyramid ACLHelper to evaluate context __acl__
        return self.acl_helper.permits(context, principals, permission)

    def remember(self, request: Any, userid: str, **kw: Any) -> List[tuple[str, str]]:
        """Set cookie headers on login."""
        token = kw.get("token", "")
        if not token:
            user = NFUserAccount(db=request.dbsession)
            if user.load_username(userid):
                sess = self.session_manager.create_session(
                    user_id=user.get_uid(),
                    username=user.dbdata.get("username", userid),
                    is_admin=bool(user.dbdata.get("is_admin", False)),
                    superuser=bool(user.dbdata.get("superuser", False)),
                )
                token = sess.token
            else:
                sess = self.session_manager.create_session(
                    user_id=None,
                    username=userid,
                    is_admin=False,
                    superuser=False,
                )
                token = sess.token

        headers = [
            ("Set-Cookie", f"namifax_session={token}; Path=/; HttpOnly; SameSite=Lax" + ("; Secure" if _cookie_secure(request) else ""))
        ]
        return headers

    def forget(self, request: Any, **kw: Any) -> List[tuple[str, str]]:
        """Remove cookie headers on logout."""
        token = self._extract_token(request)
        if token:
            self.session_manager.destroy_session(token)

        headers = [
            ("Set-Cookie", "namifax_session=; Path=/; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT" + ("; Secure" if _cookie_secure(request) else ""))
        ]
        return headers
