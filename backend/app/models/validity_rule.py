from sqlalchemy import Column, Integer, String, Boolean
from app.core.database import Base


class ValidityRule(Base):
    __tablename__ = "validity_rules"

    id = Column(Integer, primary_key=True, index=True)

    instrument_type = Column(
        String(100),
        nullable=False,
        index=True
    )

    validity_months = Column(
        Integer,
        nullable=False
    )

    active = Column(
        Boolean,
        default=True,
        nullable=False
    )

    description = Column(String(255))