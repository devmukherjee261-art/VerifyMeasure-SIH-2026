import uuid
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models.certificate import Certificate
from app.models.application import Application
from app.models.inspection import Inspection
from app.models.instrument import Instrument
from app.schemas.certificate import (
    CertificateIssueRequest,
    CertificateResponse,
    ValidityRuleResponse,
    PublicCertificateVerificationResponse
)
from app.services.validity_service import calculate_validity, get_all_rules
from app.services.pdf_service import generate_certificate_pdf
from app.services.qr_service import generate_qr_code_png, mask_stakeholder_name, build_verification_url
from app.core.security import require_roles


router = APIRouter(
    prefix="/certificates",
    tags=["Certificates"]
)


def generate_certificate_number(db: Session, year: int) -> str:
    """Generates a sequential and unique certificate number for the given year."""
    prefix = f"CERT-{year}-"
    # Find highest sequence for this year
    count = db.query(Certificate).filter(
        Certificate.certificate_number.like(f"{prefix}%")
    ).count()
    
    seq = count + 1
    candidate = f"{prefix}{seq:05d}"
    
    # Ensure collision-free
    while db.query(Certificate).filter(Certificate.certificate_number == candidate).first():
        seq += 1
        candidate = f"{prefix}{seq:05d}"
        
    return candidate


@router.post("/issue", response_model=CertificateResponse)
def issue_certificate(
    request: CertificateIssueRequest,
    db: Session = Depends(get_db),
    _=Depends(require_roles("approving_officer", "administrator"))
):
    """
    Issues an official Legal Metrology verification certificate.
    
    Requirements:
    1. A valid Inspection record must exist.
    2. The Inspection result must strictly be 'Pass'.
    3. The associated Application must be 'Approved'.
    4. An active Certificate must not already have been issued for this inspection.
    5. Instrument validity period is determined by Legal Metrology rules.
    """
    # 1. Resolve Inspection
    inspection: Inspection | None = None
    if request.inspection_id is not None:
        inspection = db.query(Inspection).filter(
            Inspection.id == request.inspection_id
        ).first()
        if not inspection:
            raise HTTPException(
                status_code=404,
                detail=f"Inspection with ID {request.inspection_id} not found"
            )
    elif request.application_id is not None:
        inspection = db.query(Inspection).filter(
            Inspection.application_id == request.application_id
        ).order_by(Inspection.id.desc()).first()
        if not inspection:
            raise HTTPException(
                status_code=404,
                detail=f"No inspection records found for Application ID {request.application_id}"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Either 'application_id' or 'inspection_id' must be provided"
        )

    # 2. Validate Inspection result strictly equals 'Pass'
    if inspection.result != "Pass":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot issue certificate: Inspection #{inspection.id} result is "
                f"'{inspection.result}'. Only instruments with a 'Pass' result can be certified."
            )
        )

    # 3. Check if certificate already exists for this inspection
    existing_cert = db.query(Certificate).filter(
        Certificate.inspection_id == inspection.id
    ).first()
    if existing_cert:
        raise HTTPException(
            status_code=400,
            detail=(
                f"A certificate has already been issued for Inspection #{inspection.id}: "
                f"{existing_cert.certificate_number}"
            )
        )

    # 4. Resolve and validate Application
    application = db.query(Application).filter(
        Application.id == inspection.application_id
    ).first()
    if not application:
        raise HTTPException(
            status_code=404,
            detail=f"Application #{inspection.application_id} associated with inspection not found"
        )

    # Certificate issuance is the final workflow transition and requires an officer decision.
    if application.status != "approved":
        raise HTTPException(
            status_code=409,
            detail="Certificate issuance requires an approved application"
        )

    # 5. Resolve and validate Instrument
    instrument = db.query(Instrument).filter(
        Instrument.id == application.instrument_id
    ).first()
    if not instrument:
        raise HTTPException(
            status_code=404,
            detail=f"Instrument #{application.instrument_id} associated with application not found"
        )

    # 6. Calculate rule-based validity period
    verification_dt = inspection.inspection_date or date.today()
    valid_from, valid_until, validity_months, legal_ref = calculate_validity(
        instrument_type=instrument.instrument_type,
        verification_date=verification_dt,
        custom_months=request.custom_validity_months
    )

    # 7. Generate unique Certificate Number and secure QR token
    year = verification_dt.year
    cert_number = generate_certificate_number(db, year)
    qr_token = uuid.uuid4().hex

    # Construct QR public verification URL
    qr_code_url = build_verification_url(qr_token)

    combined_remarks = request.remarks or inspection.inspector_remarks
    if combined_remarks:
        combined_remarks = f"{combined_remarks} | Rule: {legal_ref}"
    else:
        combined_remarks = f"Rule: {legal_ref}"

    # 8. Create Certificate snapshot
    new_certificate = Certificate(
        certificate_number=cert_number,
        qr_token=qr_token,
        application_id=application.id,
        instrument_id=instrument.id,
        inspection_id=inspection.id,

        # Snapshot of Instrument at time of certification
        instrument_identifier=instrument.instrument_id,
        instrument_type=instrument.instrument_type,
        manufacturer=instrument.manufacturer,
        model_number=instrument.model_number,
        serial_number=instrument.serial_number,
        capacity=instrument.capacity,
        location=instrument.location,
        owner_name=instrument.owner_name,

        # Snapshot of Inspection results
        standard_value=inspection.standard_value,
        measured_value=inspection.measured_value,
        error=inspection.error,
        result=inspection.result,

        # Validity dates
        verification_date=verification_dt,
        valid_from=valid_from,
        valid_until=valid_until,
        validity_months=validity_months,

        # Authority and metadata
        issuing_authority=request.issuing_authority or "Legal Metrology Department",
        qr_code_url=qr_code_url,
        status="Active",
        remarks=combined_remarks
    )

    db.add(new_certificate)

    # 9. Synchronize Instrument state
    instrument.status = "Verified"
    instrument.verification_date = valid_from
    instrument.next_due_date = valid_until
    application.status = "certified"

    db.commit()
    db.refresh(new_certificate)

    return new_certificate


@router.get("/", response_model=list[CertificateResponse])
def get_certificates(
    instrument_id: int | None = None,
    status: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Lists certificates with optional filtering by instrument ID or status."""
    query = db.query(Certificate)
    if instrument_id is not None:
        query = query.filter(Certificate.instrument_id == instrument_id)
    if status is not None:
        query = query.filter(Certificate.status.ilike(status))
    return query.order_by(Certificate.id.desc()).offset(skip).limit(limit).all()


@router.get("/rules", response_model=list[ValidityRuleResponse])
def get_rules():
    """Returns the legal metrology rule table for instrument validity periods."""
    return get_all_rules()


@router.get("/number/{certificate_number}", response_model=CertificateResponse)
def get_certificate_by_number(
    certificate_number: str,
    db: Session = Depends(get_db)
):
    """Retrieves a certificate by its unique certificate number."""
    cert = db.query(Certificate).filter(
        Certificate.certificate_number == certificate_number
    ).first()
    if not cert:
        raise HTTPException(
            status_code=404,
            detail=f"Certificate '{certificate_number}' not found"
        )
    return cert


@router.get("/token/{qr_token}", response_model=CertificateResponse)
def get_certificate_by_qr_token(
    qr_token: str,
    db: Session = Depends(get_db)
):
    """Public verification lookup by cryptographically secure QR token."""
    cert = db.query(Certificate).filter(
        Certificate.qr_token == qr_token
    ).first()
    if not cert:
        raise HTTPException(
            status_code=404,
            detail="Invalid or unverified QR certificate token"
        )
    return cert


@router.get("/application/{application_id}", response_model=CertificateResponse)
def get_certificate_by_application(
    application_id: int,
    db: Session = Depends(get_db)
):
    """Retrieves the certificate issued for a given application ID."""
    cert = db.query(Certificate).filter(
        Certificate.application_id == application_id
    ).order_by(Certificate.id.desc()).first()
    if not cert:
        raise HTTPException(
            status_code=404,
            detail=f"No certificate found for Application ID {application_id}"
        )
    return cert


@router.get("/instrument/{instrument_id}", response_model=list[CertificateResponse])
def get_certificates_by_instrument(
    instrument_id: int,
    db: Session = Depends(get_db)
):
    """Retrieves all certificate records for a given instrument."""
    return db.query(Certificate).filter(
        Certificate.instrument_id == instrument_id
    ).order_by(Certificate.id.desc()).all()


@router.get("/{certificate_id}", response_model=CertificateResponse)
def get_certificate(
    certificate_id: int,
    db: Session = Depends(get_db)
):
    """Retrieves a certificate by its primary key ID."""
    cert = db.query(Certificate).filter(
        Certificate.id == certificate_id
    ).first()
    if not cert:
        raise HTTPException(
            status_code=404,
            detail=f"Certificate with ID {certificate_id} not found"
        )
    return cert


@router.get("/{certificate_id}/pdf")
def download_certificate_pdf(
    certificate_id: int,
    db: Session = Depends(get_db)
):
    """Generates and streams the official Legal Metrology verification certificate PDF by ID."""
    cert = db.query(Certificate).filter(
        Certificate.id == certificate_id
    ).first()
    if not cert:
        raise HTTPException(
            status_code=404,
            detail=f"Certificate with ID {certificate_id} not found"
        )

    pdf_bytes = generate_certificate_pdf(cert)
    filename = f"{cert.certificate_number}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )


@router.get("/number/{certificate_number}/pdf")
def download_certificate_pdf_by_number(
    certificate_number: str,
    db: Session = Depends(get_db)
):
    """Generates and streams the official Legal Metrology verification certificate PDF by certificate number."""
    cert = db.query(Certificate).filter(
        Certificate.certificate_number == certificate_number
    ).first()
    if not cert:
        raise HTTPException(
            status_code=404,
            detail=f"Certificate '{certificate_number}' not found"
        )

    pdf_bytes = generate_certificate_pdf(cert)
    filename = f"{cert.certificate_number}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )


@router.get("/token/{qr_token}/pdf")
def download_certificate_pdf_by_token(
    qr_token: str,
    db: Session = Depends(get_db)
):
    """Generates and streams the official Legal Metrology verification certificate PDF by public QR token."""
    cert = db.query(Certificate).filter(
        Certificate.qr_token == qr_token
    ).first()
    if not cert:
        raise HTTPException(
            status_code=404,
            detail="Invalid or unverified QR certificate token"
        )

    pdf_bytes = generate_certificate_pdf(cert)
    filename = f"{cert.certificate_number}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )


@router.get("/verify/{qr_token}", response_model=PublicCertificateVerificationResponse)
def verify_certificate_public(
    qr_token: str,
    db: Session = Depends(get_db)
):
    """
    Public QR certificate verification endpoint.
    Accessible to anyone scanning the QR code on a measuring instrument or verification certificate.
    Validates authenticity against PostgreSQL database in real time.
    Masks stakeholder PII and excludes internal database IDs and credentials.
    """
    cert = db.query(Certificate).filter(
        Certificate.qr_token == qr_token
    ).first()

    if not cert:
        raise HTTPException(
            status_code=404,
            detail="Invalid QR verification token. Certificate not found in Legal Metrology records."
        )

    today = date.today()
    is_valid = (cert.status == "Active" and cert.valid_from <= today <= cert.valid_until)
    days_remaining = (cert.valid_until - today).days

    status_display = cert.status
    if cert.status == "Active" and days_remaining < 0:
        status_display = "Expired"

    return PublicCertificateVerificationResponse(
        is_authentic=True,
        status=status_display,
        is_valid_currently=is_valid,
        days_remaining=days_remaining,
        certificate_number=cert.certificate_number,
        qr_token=cert.qr_token,
        instrument_identifier=cert.instrument_identifier,
        instrument_type=cert.instrument_type,
        manufacturer=cert.manufacturer,
        model_number=cert.model_number,
        serial_number=cert.serial_number,
        capacity=cert.capacity,
        location=cert.location,
        owner_masked=mask_stakeholder_name(cert.owner_name),
        verification_date=cert.verification_date,
        valid_from=cert.valid_from,
        valid_until=cert.valid_until,
        validity_months=cert.validity_months,
        result=cert.result,
        issuing_authority=cert.issuing_authority,
        pdf_download_url=f"/certificates/token/{cert.qr_token}/pdf",
        verification_timestamp=datetime.utcnow()
    )


@router.get("/token/{qr_token}/qr")
def get_certificate_qr_image(
    qr_token: str,
    db: Session = Depends(get_db)
):
    """Generates and streams the official QR code PNG image for a certificate by QR token."""
    cert = db.query(Certificate).filter(
        Certificate.qr_token == qr_token
    ).first()
    if not cert:
        raise HTTPException(
            status_code=404,
            detail="Certificate with specified QR token not found"
        )

    verify_url = build_verification_url(cert.qr_token)
    qr_png = generate_qr_code_png(verify_url)

    return Response(
        content=qr_png,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400"
        }
    )


@router.get("/number/{certificate_number}/qr")
def get_certificate_qr_image_by_number(
    certificate_number: str,
    db: Session = Depends(get_db)
):
    """Generates and streams the official QR code PNG image for a certificate by certificate number."""
    cert = db.query(Certificate).filter(
        Certificate.certificate_number == certificate_number
    ).first()
    if not cert:
        raise HTTPException(
            status_code=404,
            detail=f"Certificate '{certificate_number}' not found"
        )

    verify_url = build_verification_url(cert.qr_token)
    qr_png = generate_qr_code_png(verify_url)

    return Response(
        content=qr_png,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400"
        }
    )


@router.get("/{certificate_id}/qr")
def get_certificate_qr_image_by_id(
    certificate_id: int,
    db: Session = Depends(get_db)
):
    """Generates and streams the official QR code PNG image for a certificate by ID."""
    cert = db.query(Certificate).filter(
        Certificate.id == certificate_id
    ).first()
    if not cert:
        raise HTTPException(
            status_code=404,
            detail=f"Certificate with ID {certificate_id} not found"
        )

    verify_url = build_verification_url(cert.qr_token)
    qr_png = generate_qr_code_png(verify_url)

    return Response(
        content=qr_png,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400"
        }
    )
