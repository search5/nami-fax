from sqlalchemy import Column, Integer,  BigInteger, Identity, String, Text, TIMESTAMP, BOOLEAN

from .meta import Base


class FaxArchiveModel(Base):
    """ARCHIVE: companyid for outgoing faxes"""
    __tablename__ = 'FaxArchive'

    fid = Column(BigInteger, Identity(start=1), primary_key=True)
    faxnumid = Column(Integer)
    companyid = Column(Integer)
    faxpath = Column(String(255) , nullable=False)
    pages = Column(Integer)
    faxcatid = Column(Integer)
    didr_id = Column(Integer)
    description = Column(Text)
    lastoperation = Column(TIMESTAMP)
    lastmoduser = Column(Integer)
    lastmoddate = Column(TIMESTAMP)
    archstamp = Column(TIMESTAMP)
    modemdev = Column(String(10))
    userid = Column(Integer)
    origfaxnum = Column(String(20))
    faxcontent = Column(Text)
    inbox = Column(BOOLEAN, default=True)

