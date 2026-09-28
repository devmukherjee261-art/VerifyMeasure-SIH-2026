from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from datetime import date, datetime

from app.core.database import Base


class Inspection(Base):
    __tablename__ = "inspections"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=False,
        index=True
    )

    standard_value = Column(
        Float,
        nullable=False
    )

    measured_value = Column(
        Float,
        nullable=False
    )

    error = Column(
        Float,
        nullable=False
    )

    result = Column(
        String(20),
        nullable=False
    )

    inspection_date = Column(
        Date,
        default=date.today,
        nullable=False
    )

    inspector_remarks = Column(Text)
    measurement_unit = Column(String(50), nullable=True)
    test_information = Column(Text, nullable=True)
    observations = Column(Text, nullable=True)
    evidence_reference = Column(Text, nullable=True)
    inspector_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    inspector_email = Column(String(255), nullable=True)
    submitted_at = Column(DateTime, nullable=True, default=datetime.utcnow)
