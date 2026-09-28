from pydantic import BaseModel, Field, ConfigDict


class MeasurementRuleCreate(BaseModel):
    instrument_type: str = Field(min_length=1, max_length=100)
    measurement_unit: str | None = Field(default=None, max_length=50)
    test_method: str = Field(min_length=1)
    acceptance_criteria: str = Field(min_length=1)
    legal_reference: str = Field(min_length=1, max_length=255)
    active: bool = True


class MeasurementRuleResponse(MeasurementRuleCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)
