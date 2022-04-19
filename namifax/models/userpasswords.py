from sqlalchemy import Column, Integer,  BigInteger, Identity, String, TIMESTAMP

from .meta import Base


class UserPasswordsModel(Base):
    """store hashes of passwords already used for a user"""
    __tablename__ = 'UserPasswords'

    upid = Column(BigInteger, Identity(start=1), primary_key=True)
    uid = Column(Integer, nullable=False)
    pwdhash = Column(String(60), nullable=False)
