from pyramid.config import Configurator
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.events import subscriber, NewRequest

from namifax.lib.constant import Constants


@subscriber(NewRequest)
def new_request(event):
    const = Constants({})
    request = event.request

    request.set_property(lambda req: const.NAMIFAX_VERSION, 'NAMIFAX_VERSION', reify=True)
    request.set_property(lambda req: const.NAMIFAX_SERVERNAME, 'NAMIFAX_SERVERNAME', reify=True)


def add_role_principals(userid, request):
    return request.jwt_claims.get('roles', [])


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    settings.setdefault('jinja2.i18n.domain', 'namifax')

    with Configurator(settings=settings) as config:
        config.include('pyramid_jinja2')
        config.include('.routes')
        config.include('.routes_admin', route_prefix='/admin')
        config.include('.models')
        config.add_translation_dirs('namifax:locale/')
        # Pyramid requires an authorization policy to be active.
        config.set_authorization_policy(ACLAuthorizationPolicy())
        # Enable JWT authentication.
        config.include('pyramid_jwt')
        config.set_jwt_authentication_policy('secret', auth_type='Bearer',
                                             callback=add_role_principals)
        config.scan()
    return config.make_wsgi_app()
