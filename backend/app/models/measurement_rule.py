from sqlalchemy import Boolean, Column, Integer, String, Text

from app.core.database import Base


class MeasurementRule(Base):
    """Authoritative measurement/tolerance criteria supplied by administrators."""
    __tablename__ = "measurement_rules"

    id = Column(Integer, primary_key=True, index=True)
    instrument_type = Column(String(100), nullable=False, index=True)
    measurement_unit = Column(String(50), nullable=True)
    test_method = Column(Text, nullable=False)
    acceptance_criteria = Column(Text, nullable=False)
    legal_reference = Column(String(255), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
