from sqlalchemy import Column, Integer,  BigInteger, Identity, String

from .meta import Base


class AddressBookFAXModel(Base):
    """AddressBookFAX"""
    __tablename__ = 'AddressBookFAX'

    abookfax_id = Column(BigInteger, Identity(start=1), primary_key=True)
    abook_id = Column(Integer)
    faxnumber = Column(String(20), nullable=False)
    email = Column(String(100))
    description = Column(String(30))
    to_person = Column(String(150))
    to_location = Column(String(150))
    to_voicenumber = Column(String(150))
    faxcatid = Column(Integer)
    faxfrom = Column(Integer, default=0)
    faxto = Column(Integer, default=0)
    printer = Column(String(100))
