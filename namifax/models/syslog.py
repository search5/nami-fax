from sqlalchemy import Column,  BigInteger, Identity, Text, TIMESTAMP

from .meta import Base


class SysLogModel(Base):
    """AvantFAX System Log"""
    __tablename__ = 'SysLog'

    syslogid = Column(BigInteger, Identity(start=1), primary_key=True)
    logdate = Column(TIMESTAMP)
    logtext = Column(Text)
