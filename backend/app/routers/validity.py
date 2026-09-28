from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.instrument import Instrument
from app.models.certificate import Certificate
from app.models.application import Application
from app.schemas.validity import (
    ValidityCalculateRequest,
    ValidityCalculateResponse,
    ValidityAlertItem,
    ValiditySummaryResponse,
    InstrumentValidityStatusResponse
)
from app.services.validity_service import (
    calculate_validity,
    get_validity_rule_for_instrument,
    get_all_rules,
    assess_instrument_due_status,
    sync_database_expiry_statuses
)

router = APIRouter(
    prefix="/validity",
    tags=["Validity & Due-Date Management"]
)


@router.get("/rules")
def get_validity_rules():
    """Returns the statutory Legal Metrology validity rules configuration."""
    return get_all_rules()


@router.post("/calculate", response_model=ValidityCalculateResponse)
def calculate_instrument_validity(request: ValidityCalculateRequest):
    """
    Dry-run test calculation of validity dates and statutory period for an instrument.
    Enforces rule-based Legal Metrology periodicity.
    """
    rule = get_validity_rule_for_instrument(request.instrument_type)
    v_from, v_until, months, legal_ref = calculate_validity(
        instrument_type=request.instrument_type,
        verification_date=request.verification_date,
        custom_months=request.custom_months
    )

    return ValidityCalculateResponse(
        instrument_type=request.instrument_type,
        category_id=rule.get("category_id", "CAT-GENERAL"),
        category=rule.get("category", "General Metrology"),
        valid_from=v_from,
        valid_until=v_until,
        validity_months=months,
        grace_period_days=rule.get("grace_period_days", 30),
        legal_reference=legal_ref,
        description=rule.get("description", ""),
        reverification_guidelines=rule.get("reverification_guidelines", "")
    )


@router.post("/sync-expiry")
def trigger_expiry_synchronization(db: Session = Depends(get_db)):
    """
    Batch synchronizes expired statuses across instruments and certificates in PostgreSQL.
    Safely transitions active records whose validity has elapsed into 'Expired'.
    """
    result = sync_database_expiry_statuses(db)
    return {
        "status": "success",
        "message": "Validity and expiry statuses synchronized successfully",
        "updated": result,
        "sync_timestamp": datetime.utcnow()
    }


@router.get("/dashboard-summary", response_model=ValiditySummaryResponse)
def get_validity_summary(db: Session = Depends(get_db)):
    """Returns real-time aggregate Legal Metrology validity and due-date metrics."""
    # Ensure database statuses are synchronized
    sync_database_expiry_statuses(db)
    
    today = date.today()
    in_30_days = today + timedelta(days=30)
    in_60_days = today + timedelta(days=60)

    total = db.query(Instrument).count()

    # Expired / Overdue: status == "Expired" or next_due_date < today
    expired = db.query(Instrument).filter(
        (Instrument.status == "Expired") | (Instrument.next_due_date < today)
    ).count()

    # Expiring within 30 days
    exp_30 = db.query(Instrument).filter(
        Instrument.status == "Verified",
        Instrument.next_due_date >= today,
        Instrument.next_due_date <= in_30_days
    ).count()

    # Expiring within 60 days
    exp_60 = db.query(Instrument).filter(
        Instrument.status == "Verified",
        Instrument.next_due_date >= today,
        Instrument.next_due_date <= in_60_days
    ).count()

    # Currently Verified & Compliant
    verified_compliant = db.query(Instrument).filter(
        Instrument.status == "Verified",
        Instrument.next_due_date >= today
    ).count()

    # Pending Initial Verification
    pending = db.query(Instrument).filter(
        Instrument.status == "Pending"
    ).count()

    # Re-verification Applications currently open
    reverif_in_prog = db.query(Application).filter(
        Application.application_type == "Re-verification",
        Application.status.in_(["Submitted", "Scheduled", "Under Review"])
    ).count()

    return ValiditySummaryResponse(
        total_instruments=total,
        verified_compliant=verified_compliant,
        expiring_within_30_days=exp_30,
        expiring_within_60_days=exp_60,
        expired_overdue=expired,
        pending_initial_verification=pending,
        reverification_in_progress=reverif_in_prog,
        check_timestamp=datetime.utcnow()
    )


@router.get("/alerts", response_model=list[ValidityAlertItem])
def get_validity_alerts(
    window_days: int = Query(45, ge=1, le=365, description="Lookahead window in days for upcoming renewals"),
    filter_type: str = Query("all", description="'all', 'expiring_soon', or 'overdue'"),
    db: Session = Depends(get_db)
):
    """
    Returns instruments requiring attention due to impending expiry or overdue verification.
    Provides data foundation for dashboard reminder badges, notification cards, and email/SMS alerts.
    """
    sync_database_expiry_statuses(db)
    today = date.today()
    cutoff_date = today + timedelta(days=window_days)

    query = db.query(Instrument)
    if filter_type == "overdue":
        query = query.filter(
            (Instrument.status == "Expired") | (Instrument.next_due_date < today)
        )
    elif filter_type == "expiring_soon":
        query = query.filter(
            Instrument.status == "Verified",
            Instrument.next_due_date >= today,
            Instrument.next_due_date <= cutoff_date
        )
    else:  # "all" alerts (both upcoming within window and already expired)
        query = query.filter(
            (Instrument.next_due_date <= cutoff_date) | (Instrument.status == "Expired")
        )

    instruments = query.order_by(Instrument.next_due_date.asc().nullslast()).all()
    alerts = []

    for inst in instruments:
        assessment = assess_instrument_due_status(inst.next_due_date, inst.status, today)
        
        # Latest certificate number if exists
        latest_cert = db.query(Certificate).filter(
            Certificate.instrument_id == inst.id
        ).order_by(Certificate.id.desc()).first()

        # Open application if exists
        open_app = db.query(Application).filter(
            Application.instrument_id == inst.id,
            Application.status.in_(["Submitted", "Scheduled", "Under Review"])
        ).first()

        alerts.append(ValidityAlertItem(
            instrument_id=inst.id,
            instrument_identifier=inst.instrument_id,
            instrument_type=inst.instrument_type,
            owner_name=inst.owner_name,
            location=inst.location,
            status=inst.status,
            verification_date=inst.verification_date,
            next_due_date=inst.next_due_date,
            days_until_due=assessment["days_until_due"],
            urgency=assessment["urgency"],
            is_renewal_eligible=assessment["is_renewal_eligible"],
            statutory_compliance=assessment["statutory_compliance"],
            penalty_risk=assessment["penalty_risk"],
            latest_certificate_number=latest_cert.certificate_number if latest_cert else None,
            open_application_number=open_app.application_number if open_app else None
        ))

    return alerts


@router.get("/instrument/{instrument_id}/status", response_model=InstrumentValidityStatusResponse)
def get_instrument_validity_status(
    instrument_id: int,
    db: Session = Depends(get_db)
):
    """Provides complete Legal Metrology validity assessment, re-verification eligibility, and history for an instrument."""
    inst = db.query(Instrument).filter(Instrument.id == instrument_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Instrument not found")

    today = date.today()
    assessment = assess_instrument_due_status(inst.next_due_date, inst.status, today)
    rule = get_validity_rule_for_instrument(inst.instrument_type)

    # Active certificate
    active_cert = db.query(Certificate).filter(
        Certificate.instrument_id == inst.id,
        Certificate.status == "Active"
    ).order_by(Certificate.id.desc()).first()

    cert_info = None
    if active_cert:
        cert_info = {
            "certificate_number": active_cert.certificate_number,
            "qr_token": active_cert.qr_token,
            "valid_from": str(active_cert.valid_from),
            "valid_until": str(active_cert.valid_until),
            "issuing_authority": active_cert.issuing_authority,
            "pdf_url": f"/certificates/token/{active_cert.qr_token}/pdf"
        }

    # Open re-verification application
    open_app = db.query(Application).filter(
        Application.instrument_id == inst.id,
        Application.application_type == "Re-verification",
        Application.status.in_(["Submitted", "Scheduled", "Under Review"])
    ).first()

    app_info = None
    if open_app:
        app_info = {
            "application_number": open_app.application_number,
            "application_type": open_app.application_type,
            "status": open_app.status,
            "application_date": str(open_app.application_date)
        }

    return InstrumentValidityStatusResponse(
        instrument_id=inst.id,
        instrument_identifier=inst.instrument_id,
        instrument_type=inst.instrument_type,
        owner_name=inst.owner_name,
        location=inst.location,
        current_status=inst.status,
        verification_date=inst.verification_date,
        next_due_date=inst.next_due_date,
        days_until_due=assessment["days_until_due"],
        urgency=assessment["urgency"],
        is_expired=assessment["is_expired"],
        is_renewal_eligible=assessment["is_renewal_eligible"],
        statutory_compliance=assessment["statutory_compliance"],
        penalty_risk=assessment["penalty_risk"],
        applicable_rule=rule,
        active_certificate=cert_info,
        open_reverification_application=app_info
    )
@router.get("/instrument/{instrument_id}/due-status")
def get_instrument_due_status(
    instrument_id: int,
    db: Session = Depends(get_db)
):
    from app.models.instrument import Instrument

    instrument = db.query(Instrument).filter(
        Instrument.id == instrument_id
    ).first()

    if not instrument:
        raise HTTPException(
            status_code=404,
            detail="Instrument not found"
        )

    return assess_instrument_due_status(
        next_due_date=instrument.next_due_date,
        current_status=instrument.status
    )
