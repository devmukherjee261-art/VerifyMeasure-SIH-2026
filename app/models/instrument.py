from sqlalchemy import Column, Integer, String, Date, Text
from app.core.database import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, index=True)
    instrument_name = Column(String(150), nullable=False)
    instrument_type = Column(String(100), nullable=False)
    manufacturer = Column(String(100))
    model_number = Column(String(100))
    serial_number = Column(String(100), unique=True, index=True)
    owner_name = Column(String(150))
    verification_date = Column(Date)
    next_due_date = Column(Date)
    status = Column(String(50), default="Pending")
    remarks = Column(Text)