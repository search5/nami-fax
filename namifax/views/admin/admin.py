from io import StringIO

from markupsafe import Markup
from pyramid.httpexceptions import HTTPFound, HTTPCreated
from pyramid.view import view_config
from cerberus import Validator


@view_config(route_name='admin_login')
def admin_login(request):
    return {}


@view_config(route_name='admin_index', renderer='namifax:templates/admin/index.jinja2')
def admin_index(request):
    if request.method == 'POST':
        schema = {'username': {'type': 'string', 'minlength': 4}, 'password': {'type': 'string', 'minlength': 4}}
        document = {key: request.POST.get(key) for key in schema.keys()}

        v = Validator()
        is_valid = v.validate(document, schema)

        if is_valid:
            return HTTPFound(location=request.route_path('index'))
        else:
            errors = StringIO()
            errors.write('<ul>')
            for key, val in v.errors.items():
                errors.write(f'<li>{key}: {"<br>".join(val)}</li>')
            errors.write('</ul>')

            # if ($ALTERNATE_AUTH_ENABLE) {
            #     if ($_SESSION[USERSESSION]->login_alternate_auth($formdata->username, $formdata->password, true)) {
            #         header("Location: admin.php");
            #         exit;
            #     }
            # }
            #
            # if (!$ALTERNATE_AUTH_ENABLE || ($ALTERNATE_AUTH_ENABLE && $ALTERNATE_AUTH_FALLBACK)) {
            #     if ($_SESSION[USERSESSION]->login($formdata->username, $formdata->password, true)) {
            #         if ($_SESSION[USERSESSION]->is_expired()) {
            #             header("Location: pwdexpired.php");
            #         } else {
            #             header("Location: admin.php");
            #         }
            #         exit;
            #     }
            # }
            #
            # $error = $_SESSION[USERSESSION]->get_error();

            return dict(error=Markup(errors.getvalue()))

    return {}
