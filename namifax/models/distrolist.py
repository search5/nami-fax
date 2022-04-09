from sqlalchemy import Column, Integer,  BigInteger, Identity, String, Text, TIMESTAMP

from .meta import Base


class DistroListModel(Base):
    """Distribution Lists"""
    __tablename__ = 'DistroList'

    dl_id = Column(BigInteger, Identity(start=1), primary_key=True)
    listname = Column(String(255), nullable=False)
    listdata = Column(Text)
    lastmod_date = Column(TIMESTAMP)
    lastmod_user = Column(Integer)

# Index('my_index', MyModel.name, unique=True, mysql_length=255)
