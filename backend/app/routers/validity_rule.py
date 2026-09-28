from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.validity_rule import ValidityRule
from app.schemas.validity_rule import (
    ValidityRuleCreate,
    ValidityRuleResponse
)
from app.core.security import require_roles

router = APIRouter(
    prefix="/validity-rules",
    tags=["Validity Rules"]
)


@router.post("/", response_model=ValidityRuleResponse)
def create_validity_rule(
    rule: ValidityRuleCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("administrator"))
):
    new_rule = ValidityRule(**rule.model_dump())

    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)

    return new_rule


@router.get("/", response_model=list[ValidityRuleResponse])
def get_validity_rules(
    db: Session = Depends(get_db)
):
    return db.query(ValidityRule).all()


@router.get("/{instrument_type}", response_model=ValidityRuleResponse)
def get_validity_rule(
    instrument_type: str,
    db: Session = Depends(get_db)
):
    rule = db.query(ValidityRule).filter(
        ValidityRule.instrument_type == instrument_type,
        ValidityRule.active == True
    ).first()

    if not rule:
        raise HTTPException(
            status_code=404,
            detail="No active validity rule found"
        )

    return rule
