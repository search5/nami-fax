from sqlalchemy import Column,  BigInteger, Identity, String

from .meta import Base


class DynConfModel(Base):
    """DynConf table for Blacklisting"""
    __tablename__ = 'DynConf'

    dynconf_id = Column(BigInteger, Identity(start=1), primary_key=True)
    device = Column(String(20))
    callid = Column(String(100))
