from sqlalchemy import Column, Integer,  BigInteger, Identity, String, Text

from .meta import Base


class BarcodeRouteModel(Base):
    """Barcode Route"""
    __tablename__ = 'BarcodeRoute'

    barcode_id = Column(BigInteger, Identity(start=1), primary_key=True)
    barcode = Column(Text)
    alias = Column(String(40))
    contact = Column(String(100))
    printer = Column(String(100))
    faxcatid = Column(Integer)
