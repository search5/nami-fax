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
    config.add_route('home', '/')
    config.add_route('login', '/login')
    config.add_route('view_a', '/view_a', factory=RootACL)
