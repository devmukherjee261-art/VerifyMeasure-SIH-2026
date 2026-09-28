from sqlalchemy import Column, Integer, String, Date, Text
from app.core.database import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, index=True)

    instrument_id = Column(String(50), unique=True, nullable=False, index=True)
    instrument_type = Column(String(100), nullable=False)
    manufacturer = Column(String(100), nullable=False)
    model_number = Column(String(100), nullable=False)
    serial_number = Column(String(100), unique=True, nullable=False, index=True)

    capacity = Column(String(100), nullable=False)
    location = Column(String(255), nullable=False)
    owner_name = Column(String(150), nullable=False)

    verification_date = Column(Date)
    next_due_date = Column(Date)

    status = Column(String(50), default="Pending")
    remarks = Column(Text)