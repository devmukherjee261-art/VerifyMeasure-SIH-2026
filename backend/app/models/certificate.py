from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)

    # Unique identifier for the certificate (e.g. CERT-2026-00001)
    certificate_number = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )

    # Cryptographically unique token for public QR code verification
    qr_token = Column(
        String(64),
        unique=True,
        nullable=False,
        index=True
    )

    # Foreign Keys linking to core entities
    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=False,
        index=True
    )

    instrument_id = Column(
        Integer,
        ForeignKey("instruments.id"),
        nullable=False,
        index=True
    )

    inspection_id = Column(
        Integer,
        ForeignKey("inspections.id"),
        unique=True,
        nullable=False,
        index=True
    )

    # Instrument Legal Metrology Snapshot at issuance
    instrument_identifier = Column(String(50), nullable=False, index=True)
    instrument_type = Column(String(100), nullable=False)
    manufacturer = Column(String(100), nullable=False)
    model_number = Column(String(100), nullable=False)
    serial_number = Column(String(100), nullable=False)
    capacity = Column(String(100), nullable=False)
    location = Column(String(255), nullable=False)
    owner_name = Column(String(150), nullable=False)

    # Inspection Snapshot
    standard_value = Column(Float, nullable=False)
    measured_value = Column(Float, nullable=False)
    error = Column(Float, nullable=False)
    result = Column(String(20), default="Pass", nullable=False)

    # Legal Metrology Validity & Dates
    verification_date = Column(Date, default=date.today, nullable=False)
    valid_from = Column(Date, default=date.today, nullable=False)
    valid_until = Column(Date, nullable=False)
    validity_months = Column(Integer, default=12, nullable=False)

    # Authority & Verification metadata
    issuing_authority = Column(
        String(150),
        default="Legal Metrology Department",
        nullable=False
    )
    qr_code_url = Column(String(255), nullable=True)
    status = Column(String(50), default="Active", nullable=False)  # Active, Expired, Revoked
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # SQLAlchemy Relationships
    application = relationship("Application", backref="certificate")
    instrument = relationship("Instrument", backref="certificates")
    inspection = relationship("Inspection", backref="certificate")
