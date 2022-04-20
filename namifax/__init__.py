from pyramid.config import Configurator
from pyramid.authorization import ACLAuthorizationPolicy






def add_role_principals(userid, request):
    return request.jwt_claims.get('roles', [])



def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    with Configurator(settings=settings) as config:
        config.include('pyramid_jinja2')
        config.include('.routes')
        config.include('.routes_admin', route_prefix='/admin')
        config.include('.models')
        # Pyramid requires an authorization policy to be active.
        config.set_authorization_policy(ACLAuthorizationPolicy())
        # Enable JWT authentication.
        config.include('pyramid_jwt')
        config.set_jwt_authentication_policy('secret', auth_type='Bearer',
                                             callback=add_role_principals)
        config.scan()
    return config.make_wsgi_app()
