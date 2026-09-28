from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.application import Application
from app.models.inspection import Inspection
from app.models.user import User
from app.schemas.inspection import InspectionCreate, InspectionResponse


router = APIRouter(prefix="/inspections", tags=["Inspections"])


@router.post("/", response_model=InspectionResponse)
def create_inspection(
    request: InspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("inspector", "administrator")),
):
    application = db.query(Application).filter(Application.id == request.application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.status != "scheduled":
        raise HTTPException(status_code=409, detail="Only scheduled applications can be inspected")
    if current_user.role == "inspector" and application.assigned_inspector_id != current_user.id:
        raise HTTPException(status_code=403, detail="Application is not assigned to you")
    if db.query(Inspection).filter(Inspection.application_id == application.id).first():
        raise HTTPException(status_code=409, detail="An inspection has already been submitted for this application")

    inspection = Inspection(
        application_id=application.id,
        standard_value=request.standard_value,
        measured_value=request.measured_value,
        error=abs(request.standard_value - request.measured_value),
        measurement_unit=request.measurement_unit,
        test_information=request.test_information,
        observations=request.observations,
        evidence_reference=request.evidence_reference,
        result=request.result,
        inspection_date=request.inspection_date,
        inspector_remarks=request.inspector_remarks,
        inspector_id=current_user.id,
        inspector_email=current_user.email,
        submitted_at=datetime.utcnow(),
    )
    db.add(inspection)
    application.status = "inspected"
    db.commit()
    db.refresh(inspection)
    return inspection


@router.get("/", response_model=list[InspectionResponse])
def get_inspections(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Inspection)
    if current_user.role == "inspector":
        query = query.filter(Inspection.inspector_id == current_user.id)
    elif current_user.role == "applicant":
        query = query.join(Application).filter(Application.applicant_id == current_user.id)
    return query.order_by(Inspection.id.desc()).all()


@router.get("/{inspection_id}", response_model=InspectionResponse)
def get_inspection(inspection_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    application = db.query(Application).filter(Application.id == inspection.application_id).first()
    if current_user.role == "applicant" and application.applicant_id != current_user.id:
        raise HTTPException(status_code=403, detail="You may only access inspections for your applications")
    if current_user.role == "inspector" and inspection.inspector_id != current_user.id:
        raise HTTPException(status_code=403, detail="Inspection was not submitted by you")
    return inspection
