"""A friendly page for a database that cannot be reached (the original no-database.php); it tries again every ten seconds."""

import logging

from pyramid.view import exception_view_config
from sqlalchemy.exc import DBAPIError, OperationalError

log = logging.getLogger("namifax")


@exception_view_config(OperationalError, renderer="namifax:templates/no_database.jinja2")
@exception_view_config(DBAPIError, renderer="namifax:templates/no_database.jinja2")
def no_database_view(exc, request):
    log.error("database unavailable: %s", exc.__class__.__name__)       # the details stay in the log, not on the page
    request.response.status = 503
    return {}
