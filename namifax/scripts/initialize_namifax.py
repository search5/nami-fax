import click
import yaml
from pathlib import Path


@click.command()
@click.argument('config_uri')
def main(config_uri):
    fax_setting = yaml.load(open(config_uri), yaml.Loader)

    # Create a directory to store fax files
    with Path(fax_setting['FAX_DIR']) as FAX_ROOT_DIR:
        FAX_ROOT_DIR.mkdir(exist_ok=True)

        (FAX_ROOT_DIR / 'recvd').mkdir(exist_ok=True)
        (FAX_ROOT_DIR / 'sent').mkdir(exist_ok=True)
