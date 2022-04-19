import argparse
import sys

from pyramid.paster import bootstrap, setup_logging
from sqlalchemy.exc import OperationalError

from .. import models


def setup_models(dbsession):
    """
    Add or update models / fixtures in the database.

    """
    model_new_record = []

    model = models.UserAccountModel(name='NamiFAX Admin',
                                    username='admin',
                                    password='5f4dcc3b5aa765d61d8327deb882cf99',
                                    wasreset=True,
                                    email='root@localhost',
                                    is_admin=True, 
                                    language='ko',
                                    acc_enabled=True,
                                    any_modem=True,
                                    superuser=True)
    model_new_record.append(model)
    
    model = models.UserPasswordsModel(uid=1, pwdhash='5f4dcc3b5aa765d61d8327deb882cf99')
    model_new_record.append(model)

    model = models.AddressBookModel(company='XXXXXXX')
    model_new_record.append(model)

    model = models.AddressBookFAXModel(abook_id=1, faxnumber='XXXXXXX')
    model_new_record.append(model)

    model = models.CoverPagesModel(title='Generic A4', file='cover.ps')
    model_new_record.append(model)
    
    model = models.CoverPagesModel(title='Generic Letter', file='cover-letter.ps')
    model_new_record.append(model)
    
    model = models.CoverPagesModel(title='Generic HTML', file='coverpage.html')
    model_new_record.append(model)

    for item in model_new_record:
        dbsession.add(item)


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'config_uri',
        help='Configuration file, e.g., development.ini',
    )
    return parser.parse_args(argv[1:])


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
