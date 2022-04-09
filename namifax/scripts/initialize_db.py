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

    """
    INSERT INTO UserAccount SET name='AvantFAX Admin', username='admin', password='5f4dcc3b5aa765d61d8327deb882cf99', wasreset=TRUE, email='root@localhost', is_admin = TRUE, language = 'en', acc_enabled = TRUE, any_modem = TRUE, superuser = TRUE;
    INSERT INTO UserPasswords SET uid=1, pwdhash='5f4dcc3b5aa765d61d8327deb882cf99';

    INSERT INTO AddressBook SET company = 'XXXXXXX';
    INSERT INTO AddressBookFAX SET abook_id = 1, faxnumber = 'XXXXXXX';

    INSERT INTO CoverPages SET title='Generic A4', file='cover.ps';
    INSERT INTO CoverPages SET title='Generic Letter', file='cover-letter.ps';
    INSERT INTO CoverPages SET title='Generic HTML', file='coverpage.html';"""


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
