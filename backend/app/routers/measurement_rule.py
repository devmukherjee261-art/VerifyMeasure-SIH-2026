from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_roles
from app.models.measurement_rule import MeasurementRule
from app.schemas.measurement_rule import MeasurementRuleCreate, MeasurementRuleResponse


router = APIRouter(prefix="/measurement-rules", tags=["Measurement Rules"])


@router.get("/", response_model=list[MeasurementRuleResponse])
def get_measurement_rules(instrument_type: str | None = None, db: Session = Depends(get_db)):
    query = db.query(MeasurementRule).filter(MeasurementRule.active == True)
    if instrument_type:
        query = query.filter(MeasurementRule.instrument_type.ilike(instrument_type))
    return query.all()


@router.post("/", response_model=MeasurementRuleResponse)
def create_measurement_rule(
    rule: MeasurementRuleCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("administrator")),
):
    new_rule = MeasurementRule(**rule.model_dump())
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return new_rule
