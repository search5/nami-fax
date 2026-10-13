from pyramid.view import view_config


@view_config(route_name='home', renderer='namifax:templates/home.jinja2', permission='public')
def my_view(request):
    return {
        'project': 'namifax',
        'current_route': 'home',
        'user': request.identity,
    }
