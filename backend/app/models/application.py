from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from datetime import date

from app.core.database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)

    application_number = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )

    instrument_id = Column(
        Integer,
        ForeignKey("instruments.id"),
        nullable=False,
        index=True
    )

    application_type = Column(
        String(30),
        nullable=False
    )

    application_date = Column(
        Date,
        default=date.today,
        nullable=False
    )

    status = Column(
        String(50),
        default="Submitted",
        nullable=False
    )

    remarks = Column(Text)
    applicant_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    assigned_inspector_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    scheduled_for = Column(DateTime, nullable=True)
    scheduling_notes = Column(Text, nullable=True)
    decision_reason = Column(Text, nullable=True)
    decision_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decision_at = Column(DateTime, nullable=True)
