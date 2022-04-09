from sqlalchemy import Column, BigInteger, Identity, String

from .meta import Base


class CoverPagesModel(Base):
    """CoverPages"""
    __tablename__ = 'CoverPages'

    cover_id = Column(BigInteger, Identity(start=1), primary_key=True)    
    title = Column(String(64), nullable=False)
    file = Column(String(255), nullable=False)
