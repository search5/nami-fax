from sqlalchemy import Column,  BigInteger, Identity, String

from .meta import Base


class FaxCategoryModel(Base):
    """FaxCategory Lists"""
    __tablename__ = 'FaxCategory'

    catid = Column(BigInteger, Identity(start=1), primary_key=True)
    name = Column(String(30))
