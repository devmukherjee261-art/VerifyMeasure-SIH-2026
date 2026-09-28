from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict


class CertificateIssueRequest(BaseModel):
    """Request payload to issue a new verification certificate."""
    application_id: int | None = Field(
        default=None,
        description="ID of the approved verification application"
    )
    inspection_id: int | None = Field(
        default=None,
        description="ID of the passed inspection record"
    )
    issuing_authority: str | None = Field(
        default="Legal Metrology Department",
        description="Name of the issuing centre or authority"
    )
    custom_validity_months: int | None = Field(
        default=None,
        description="Optional custom validity period in months (overrides default rules if provided)"
    )
    remarks: str | None = Field(
        default=None,
        description="Optional remarks or notes"
    )


class CertificateResponse(BaseModel):
    """Full certificate response payload."""
    id: int
    certificate_number: str
    qr_token: str
    application_id: int
    instrument_id: int
    inspection_id: int

    instrument_identifier: str
    instrument_type: str
    manufacturer: str
    model_number: str
    serial_number: str
    capacity: str
    location: str
    owner_name: str

    standard_value: float
    measured_value: float
    error: float
    result: str

    verification_date: date
    valid_from: date
    valid_until: date
    validity_months: int
    issuing_authority: str
    qr_code_url: str | None = None
    status: str
    remarks: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ValidityRuleResponse(BaseModel):
    category: str
    keywords: list[str]
    validity_months: int
    legal_reference: str
    description: str


class PublicCertificateVerificationResponse(BaseModel):
    """
    Public-safe verification response for citizens and inspectors scanning QR codes.
    Excludes sensitive stakeholder PII, database credentials, and internal database IDs.
    """
    is_authentic: bool = True
    status: str  # Active, Expired, Revoked
    is_valid_currently: bool
    days_remaining: int

    certificate_number: str
    qr_token: str

    instrument_identifier: str
    instrument_type: str
    manufacturer: str
    model_number: str
    serial_number: str
    capacity: str
    location: str
    owner_masked: str

    verification_date: date
    valid_from: date
    valid_until: date
    validity_months: int
    result: str
    issuing_authority: str

    pdf_download_url: str
    verification_timestamp: datetime

