from sqlalchemy import Column, Integer,  BigInteger, Identity, String

from .meta import Base


class ModemsModel(Base):
    """Modems"""
    __tablename__ = 'Modems'

    devid = Column(BigInteger, Identity(start=1), primary_key=True)
    device = Column(String(10), nullable=False)
    alias = Column(String(40))
    contact = Column(String(100))
    printer = Column(String(100))
    faxcatid = Column(Integer)
