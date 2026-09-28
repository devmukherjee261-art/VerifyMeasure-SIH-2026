from datetime import date, datetime
from pydantic import BaseModel, Field


class ValidityCalculateRequest(BaseModel):
    instrument_type: str = Field(..., description="Instrument category or model description")
    verification_date: date | None = Field(default=None, description="Date of verification (defaults to today)")
    custom_months: int | None = Field(default=None, description="Optional custom validity period in months")


class ValidityCalculateResponse(BaseModel):
    instrument_type: str
    category_id: str
    category: str
    valid_from: date
    valid_until: date
    validity_months: int
    grace_period_days: int
    legal_reference: str
    description: str
    reverification_guidelines: str


class ValidityAlertItem(BaseModel):
    instrument_id: int
    instrument_identifier: str
    instrument_type: str
    owner_name: str
    location: str
    status: str
    verification_date: date | None = None
    next_due_date: date | None = None
    days_until_due: int | None = None
    urgency: str  # Overdue, Critical, Upcoming, Normal
    is_renewal_eligible: bool
    statutory_compliance: str
    penalty_risk: str
    latest_certificate_number: str | None = None
    open_application_number: str | None = None


class ValiditySummaryResponse(BaseModel):
    total_instruments: int
    verified_compliant: int
    expiring_within_30_days: int
    expiring_within_60_days: int
    expired_overdue: int
    pending_initial_verification: int
    reverification_in_progress: int
    check_timestamp: datetime


class InstrumentValidityStatusResponse(BaseModel):
    instrument_id: int
    instrument_identifier: str
    instrument_type: str
    owner_name: str
    location: str
    current_status: str
    verification_date: date | None = None
    next_due_date: date | None = None
    days_until_due: int | None = None
    urgency: str
    is_expired: bool
    is_renewal_eligible: bool
    statutory_compliance: str
    penalty_risk: str
    applicable_rule: dict
    active_certificate: dict | None = None
    open_reverification_application: dict | None = None
