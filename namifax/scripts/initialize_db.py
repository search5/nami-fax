import argparse
import sys

from pyramid.paster import bootstrap, setup_logging
from sqlalchemy.exc import OperationalError

from .. import models


def setup_models(dbsession):
    """
    Add or update models / fixtures in the database.

    """
    #model = models.mymodel.MyModel(name='one', value=1)
    #dbsession.add(model)

    model = models.UserAccountModel(name='AvantFAX Admin', username='admin', password='5f4dcc3b5aa765d61d8327deb882cf99', wasreset=True, email='root@localhost', is_admin=True, language = 'en', acc_enabled=True, any_modem=True, superuse0r=True)
    dbsession.add(model)
    
    model = models.UserPasswordsModel(uid=1, pwdhash='5f4dcc3b5aa765d61d8327deb882cf99')
    dbsession.add(model)

    model = models.AddressBookModel(company='XXXXXXX')
    dbsession.add(model)

    model = models.AddressBookFAXModel(abook_id = 1, faxnumber='XXXXXXX')
    dbsession.add(model)

    model1 = models.CoverPagesModel(title='Generic A4', file='cover.ps')
    model2 = models.CoverPagesModel(title='Generic Letter', file='cover-letter.ps')
    model3 = models.CoverPagesModel(title='Generic HTML', file='coverpage.html')

    dbsession.add(model1)
    dbsession.add(model2)
    dbsession.add(model3)


def main(argv=sys.argv):
    args = parse_args(argv)
    setup_logging(args.config_uri)
    env = bootstrap(args.config_uri)

    try:
        with env['request'].tm:
            dbsession = env['request'].dbsession
            setup_models(dbsession)
    except OperationalError:
        print('''
Pyramid is having a problem using your SQL database.  The problem
might be caused by one of the following things:

1.  You may need to initialize your database tables with `alembic`.
    Check your README.txt for description and try to run it.

2.  Your database server may not be running.  Check that the
    database server referred to by the "sqlalchemy.url" setting in
    your "development.ini" file is running.
            ''')
