from sqlalchemy import Column, Integer,  BigInteger, Identity, String, TIMESTAMP

from .meta import Base


class DIDRouteModel(Base):
    """DID Routing"""
    __tablename__ = 'DIDRoute'

    didr_id = Column(BigInteger, Identity(start=1), primary_key=True)
    routecode = Column(String(10), nullable=False)
    alias = Column(String(40))
    contact = Column(String(100))
    printer = Column(String(100))
    faxcatid = Column(Integer)
