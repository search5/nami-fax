"""NamiFAX Forbidden / Unauthorized view handler."""

from __future__ import annotations

from pyramid.httpexceptions import HTTPForbidden, HTTPFound
from pyramid.view import forbidden_view_config


@forbidden_view_config(renderer="json")
def forbidden_view(request):
    """Handle 401/403 errors based on authentication status and client request type."""
    accept = request.headers.get("Accept", "")
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    is_html_request = "text/html" in accept and not is_ajax

    # Check if request is authenticated
    if not request.authenticated_userid:
        if is_html_request:
            login_url = request.route_url("login")
            if request.path and request.path not in ("/", "/login", "/logout"):
                login_url = request.route_url("login", _query={"next": request.url})
            return HTTPFound(location=login_url)

        request.response.status_code = 401
        return {
            "status": "error",
            "code": 401,
            "message": "Authentication required. Please log in.",
        }

    if is_html_request:
        return HTTPFound(location=request.route_url("inbox"))

    request.response.status_code = 403
    return {
        "status": "error",
        "code": 403,
        "message": "Access forbidden: insufficient permissions.",
    }
