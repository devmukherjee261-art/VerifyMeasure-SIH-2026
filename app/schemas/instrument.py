from datetime import date
from pydantic import BaseModel


class InstrumentCreate(BaseModel):
    instrument_id: str
    instrument_type: str
    manufacturer: str
    model_number: str
    serial_number: str
    capacity: str
    location: str
    owner_name: str

    verification_date: date | None = None
    next_due_date: date | None = None
    status: str = "Pending"
    remarks: str | None = None


class InstrumentResponse(InstrumentCreate):
    id: int

    class Config:
        from_attributes = True