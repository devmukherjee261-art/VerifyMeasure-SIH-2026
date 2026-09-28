from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.instrument import Instrument
from app.schemas.instrument import InstrumentCreate, InstrumentResponse
from app.core.security import require_roles

router = APIRouter(
    prefix="/instruments",
    tags=["Instruments"]
)


@router.post("/", response_model=InstrumentResponse)
def create_instrument(
    instrument: InstrumentCreate,
    db: Session = Depends(get_db)
):
    new_instrument = Instrument(**instrument.model_dump())

    db.add(new_instrument)
    db.commit()
    db.refresh(new_instrument)

    return new_instrument

@router.get("/", response_model=list[InstrumentResponse])
def get_instruments(
    db: Session = Depends(get_db)
):
    instruments = db.query(Instrument).all()
    return instruments


@router.get("/dashboard/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db)
):
    total = db.query(Instrument).count()

    verified = db.query(Instrument).filter(
        Instrument.status == "Verified"
    ).count()

    pending = db.query(Instrument).filter(
        Instrument.status == "Pending"
    ).count()

    expired = db.query(Instrument).filter(
        Instrument.status == "Expired"
    ).count()

    return {
        "total_instruments": total,
        "verified": verified,
        "pending": pending,
        "expired": expired
    }


@router.get("/search", response_model=InstrumentResponse)
def search_instrument_by_identifier(
    instrument_id: str,
    db: Session = Depends(get_db)
):
    instrument = db.query(Instrument).filter(
        Instrument.instrument_id == instrument_id.strip()
    ).first()

    if not instrument:
        raise HTTPException(
            status_code=404,
            detail="Instrument not found"
        )

    return instrument


@router.get("/{instrument_id}", response_model=InstrumentResponse)
def get_instrument(
    instrument_id: int,
    db: Session = Depends(get_db)
):
    instrument = db.query(Instrument).filter(
        Instrument.id == instrument_id
    ).first()

    if not instrument:
        raise HTTPException(
            status_code=404,
            detail="Instrument not found"
        )

    return instrument

@router.put("/{instrument_id}", response_model=InstrumentResponse)
def update_instrument(
    instrument_id: int,
    instrument: InstrumentCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("administrator"))
):
    existing = db.query(Instrument).filter(
        Instrument.id == instrument_id
    ).first()

    if not existing:
        raise HTTPException(
            status_code=404,
            detail="Instrument not found"
        )

    for key, value in instrument.model_dump().items():
        setattr(existing, key, value)

    db.commit()
    db.refresh(existing)

    return existing

@router.delete("/{instrument_id}")
def delete_instrument(
    instrument_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("administrator"))
):
    instrument = db.query(Instrument).filter(
        Instrument.id == instrument_id
    ).first()

    if not instrument:
        raise HTTPException(
            status_code=404,
            detail="Instrument not found"
        )

    db.delete(instrument)
    db.commit()

    return {
        "message": "Instrument deleted successfully",
        "instrument_id": instrument_id
    }
