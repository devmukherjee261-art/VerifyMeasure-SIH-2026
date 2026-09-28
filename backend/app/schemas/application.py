from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict

from app.schemas.instrument import InstrumentResponse


ApplicationStatus = Literal["submitted", "scheduled", "inspected", "approved", "rejected", "certified"]


class ApplicationCreate(BaseModel):
    instrument_id: int
    application_type: str = Field(min_length=1, max_length=30)
    remarks: str | None = None


class ApplicationScheduleRequest(BaseModel):
    inspector_id: int
    scheduled_for: datetime | None = None
    scheduling_notes: str | None = None


class ApplicationDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str | None = None


class ApplicationResponse(BaseModel):
    id: int
    application_number: str
    instrument_id: int
    application_type: str
    application_date: date
    status: ApplicationStatus
    remarks: str | None = None
    applicant_id: int | None = None
    assigned_inspector_id: int | None = None
    scheduled_for: datetime | None = None
    scheduling_notes: str | None = None
    decision_reason: str | None = None
    decision_by: int | None = None
    decision_at: datetime | None = None
    instrument: InstrumentResponse | None = None

    model_config = ConfigDict(from_attributes=True)
