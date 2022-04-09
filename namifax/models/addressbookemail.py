from sqlalchemy import Column, Integer,  BigInteger, Identity, String

from .meta import Base


class AddressBookEmailModel(Base):
    """AddressBookEmail"""
    __tablename__ = 'AddressBookEmail'

    abookemail_id = Column(BigInteger, Identity(start=1), primary_key=True)
    abook_id = Column(Integer)
    contact_name = Column(String(255))
    contact_email = Column(String(255), nullable=False)
