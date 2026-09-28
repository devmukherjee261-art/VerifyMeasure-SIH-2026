from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.application import Application
from app.models.inspection import Inspection
from app.models.instrument import Instrument
from app.models.user import User
from app.schemas.application import (
    ApplicationCreate,
    ApplicationDecisionRequest,
    ApplicationResponse,
    ApplicationScheduleRequest,
)


router = APIRouter(prefix="/applications", tags=["Applications"])


def application_response(application: Application, instrument: Instrument) -> dict:
    return {**{column.name: getattr(application, column.name) for column in Application.__table__.columns}, "instrument": instrument}


def get_application_or_404(application_id: int, db: Session) -> Application:
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def authorize_application_view(application: Application, user: User):
    if user.role == "applicant" and application.applicant_id != user.id:
        raise HTTPException(status_code=403, detail="You may only access your own applications")
    if user.role == "inspector" and application.assigned_inspector_id != user.id:
        raise HTTPException(status_code=403, detail="Application is not assigned to you")


@router.post("/", response_model=ApplicationResponse)
def create_application(
    request: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("applicant", "administrator")),
):
    instrument = db.query(Instrument).filter(Instrument.id == request.instrument_id).first()
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")

    application_number = f"APP-{instrument.id}-{db.query(Application).count() + 1:04d}"
    application = Application(
        application_number=application_number,
        instrument_id=instrument.id,
        application_type=request.application_type,
        status="submitted",
        remarks=request.remarks,
        applicant_id=current_user.id,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application_response(application, instrument)


@router.get("/", response_model=list[ApplicationResponse])
def get_applications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Application)
    if current_user.role == "applicant":
        query = query.filter(Application.applicant_id == current_user.id)
    elif current_user.role == "inspector":
        query = query.filter(Application.assigned_inspector_id == current_user.id)
    applications = query.order_by(Application.id.desc()).all()
    instruments = {item.id: item for item in db.query(Instrument).filter(Instrument.id.in_([a.instrument_id for a in applications])).all()} if applications else {}
    return [application_response(application, instruments[application.instrument_id]) for application in applications]


@router.get("/assigned/pending", response_model=list[ApplicationResponse])
def get_assigned_pending_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("inspector", "administrator")),
):
    query = db.query(Application).filter(Application.status == "scheduled")
    if current_user.role == "inspector":
        query = query.filter(Application.assigned_inspector_id == current_user.id)
    applications = query.order_by(Application.scheduled_for.asc().nullslast()).all()
    instruments = {item.id: item for item in db.query(Instrument).filter(Instrument.id.in_([a.instrument_id for a in applications])).all()} if applications else {}
    return [application_response(application, instruments[application.instrument_id]) for application in applications]


@router.post("/{application_id}/schedule", response_model=ApplicationResponse)
def schedule_application(
    application_id: int,
    request: ApplicationScheduleRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("approving_officer", "administrator")),
):
    application = get_application_or_404(application_id, db)
    if application.status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted applications can be scheduled")
    inspector = db.query(User).filter(User.id == request.inspector_id, User.role == "inspector", User.is_active == True).first()
    if not inspector:
        raise HTTPException(status_code=400, detail="Assigned user must be an active inspector")
    application.assigned_inspector_id = inspector.id
    application.scheduled_for = request.scheduled_for
    application.scheduling_notes = request.scheduling_notes
    application.status = "scheduled"
    db.commit()
    db.refresh(application)
    return application_response(application, db.query(Instrument).filter(Instrument.id == application.instrument_id).first())


@router.post("/{application_id}/decision", response_model=ApplicationResponse)
def decide_application(
    application_id: int,
    request: ApplicationDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("approving_officer", "administrator")),
):
    application = get_application_or_404(application_id, db)
    if application.status != "inspected":
        raise HTTPException(status_code=409, detail="Only inspected applications can be approved or rejected")
    inspection = db.query(Inspection).filter(Inspection.application_id == application.id).order_by(Inspection.id.desc()).first()
    if not inspection:
        raise HTTPException(status_code=409, detail="A completed inspection is required")
    if request.decision == "approved" and inspection.result != "Pass":
        raise HTTPException(status_code=409, detail="Only a passed inspection can be approved")
    application.status = request.decision
    application.decision_reason = request.reason
    application.decision_by = current_user.id
    application.decision_at = datetime.utcnow()
    db.commit()
    db.refresh(application)
    return application_response(application, db.query(Instrument).filter(Instrument.id == application.instrument_id).first())


@router.get("/{application_id}", response_model=ApplicationResponse)
def get_application(application_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    application = get_application_or_404(application_id, db)
    authorize_application_view(application, current_user)
    return application_response(application, db.query(Instrument).filter(Instrument.id == application.instrument_id).first())
