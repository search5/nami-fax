from sqlalchemy import Column, Integer,  BigInteger, Identity, String, Text, TIMESTAMP, BOOLEAN, DATE

from .meta import Base


class UserAccountModel(Base):
    """USER INFORMATION
    password is md5 hash and always 32 chars"""
    __tablename__ = 'UserAccount'

    uid = Column(BigInteger, Identity(start=1), primary_key=True)
    name = Column(String(40))
    username = Column(String(40), nullable=False)
    password = Column(String(60), nullable=False)
    email = Column(String(99), nullable=False)
    email_sig = Column(Text)
    user_tsi = Column(String(100))
    from_company = Column(String(150))
    from_location = Column(String(150))
    from_voicenumber = Column(String(150))
    from_faxnumber = Column(String(150))
    coverpage_id = Column(Integer)
    faxperpageinbox = Column(Integer)
    faxperpagearchive = Column(Integer)
    superuser = Column(BOOLEAN, default=False)
    can_del = Column(BOOLEAN, default=False)
    last_mod = Column(TIMESTAMP)
    last_login = Column(TIMESTAMP)
    last_ip = Column(String(15))
    language = Column(String(5))
    modemdevs = Column(Text)
    didrouting = Column(Text)
    faxcats = Column(Text)
    pwdexpire = Column(DATE)
    pwdcycle = Column(Integer, default=0)
    pwd_reuse = Column(BOOLEAN, default=False)
    is_admin = Column(BOOLEAN, default=False)
    wasreset = Column(BOOLEAN, default=False)
    acc_enabled = Column(BOOLEAN, default=True)
    deleted = Column(BOOLEAN, default=False)
    any_modem = Column(BOOLEAN, default=False)
