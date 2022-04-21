from pyramid.security import ALL_PERMISSIONS, Allow

class RootACL(object):
    __acl__ = [
        (Allow, 'admin', ALL_PERMISSIONS),
        (Allow, 'reports', ['reports'])
    ]

    def __init__(self, request=None):
        print(request)
        pass

def includeme(config):
    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_route('index', '/')
    config.add_route('addressbook', '/addressbook')
    config.add_route('check_login', '/check_login')
    config.add_route('logout', '/logout')
    config.add_route('forgot', '/forgot')
    config.add_route('settings', '/settings')
    config.add_route('email', '/email')
    config.add_route('file', '/file')
    config.add_route('rotate', '/rotate')
    config.add_route('setcompany', '/setcompany')
    config.add_route('viewfax', '/viewfax')
    config.add_route('addressbook_edit', '/addressbook_edit')
    config.add_route('distrocontacts', '/distrocontacts')
    config.add_route('emailbook', '/emailbook')
    config.add_route('outbox', '/outbox')
    config.add_route('rubrica', '/rubrica')
    config.add_route('archive', '/archive')
    config.add_route('distrolist', '/distrolist')
    config.add_route('emailbook_edit', '/emailbook_edit')
    config.add_route('inbox', '/inbox')
    config.add_route('pdf', '/pdf')
    config.add_route('rubrica_edit', '/rubrica_edit')
    config.add_route('txreport', '/txreport')
    config.add_route('assign', '/assign')
    config.add_route('distrolist_edit', '/distrolist_edit')
    config.add_route('emailcontacts', '/emailcontacts')
    config.add_route('pwdexpired', '/pwdexpired')
    config.add_route('search', '/search')
    config.add_route('upload_contacts', '/upload_contacts')
    config.add_route('assignx', '/assignx')
    config.add_route('distrolist_helper', '/distrolist_helper')
    config.add_route('faxcontacts', '/faxcontacts')
    config.add_route('refax', '/refax')
    config.add_route('sendfax', '/sendfax')
    config.add_route('upload_faxcontacts', '/upload_faxcontacts')
