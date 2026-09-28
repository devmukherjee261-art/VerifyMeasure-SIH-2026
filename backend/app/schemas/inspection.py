from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class InspectionCreate(BaseModel):
    application_id: int
    standard_value: float
    measured_value: float
    measurement_unit: str = Field(min_length=1, max_length=50)
    test_information: str = Field(min_length=1)
    observations: str | None = None
    evidence_reference: str | None = None
    result: Literal["Pass", "Fail"]
    inspection_date: date | None = None
    inspector_remarks: str | None = None


class InspectionResponse(InspectionCreate):
    id: int
    error: float
    inspector_id: int | None = None
    inspector_email: str | None = None
    submitted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
