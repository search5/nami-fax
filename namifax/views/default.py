from pyramid.view import view_config
from pyramid.response import Response
from sqlalchemy.exc import SQLAlchemyError

from .. import models


@view_config(route_name='home', renderer='namifax:templates/mytemplate.jinja2')
def my_view(request):
    # try:
    #     query = request.dbsession.query(models.MyModel)
    #     one = query.filter(models.MyModel.name == 'one').one()
    # except SQLAlchemyError:
    #     return Response(db_err_msg, content_type='text/plain', status=500)
    return {'one': "one", 'project': 'nami-fax'}


db_err_msg = """\
Pyramid is having a problem using your SQL database.  The problem
might be caused by one of the following things:

1.  You may need to initialize your database tables with `alembic`.
    Check your README.txt for descriptions and try to run it.

2.  Your database server may not be running.  Check that the
    database server referred to by the "sqlalchemy.url" setting in
    your "development.ini" file is running.

After you fix the problem, please restart the Pyramid application to
try it again.
"""

@view_config(route_name='login', request_method='POST', renderer='json')
def login(request):
    print(request)
    login = request.POST['login']
    password = request.POST['password']
    # user_id = authenticate(login, password)  # You will need to implement this.
    user_id = 'search5'
    if user_id:
        return {
            'result': 'ok',
            'token': request.create_jwt_token(user_id, roles=['admin'],
                                            userName='이지호')
        }
    else:
        return {
            'result': 'error'
        }


@view_config(route_name='view_a', request_method='GET', permission="admin", renderer='json')
def view_a(request):
    return {'success': True}