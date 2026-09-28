from pydantic import BaseModel, ConfigDict


class ValidityRuleCreate(BaseModel):
    instrument_type: str
    validity_months: int
    active: bool = True
    description: str | None = None


class ValidityRuleResponse(ValidityRuleCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)