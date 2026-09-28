"""Legal Metrology Rule-based Validity & Due-Date Management Service.

Under The Legal Metrology Act, 2009 and The Legal Metrology (General) Rules, 2011,
verification periodicity is NOT universal. Different categories and types of
weighing and measuring instruments have distinct statutory verification validity periods.
"""

from datetime import date, timedelta
from typing import Any
from sqlalchemy.orm import Session


# Configuration rules mapping instrument categories / types to statutory validity periods
LEGAL_METROLOGY_VALIDITY_RULES: list[dict[str, Any]] = [
    {
        "category_id": "CAT-TANKS",
        "category": "Storage Tanks & Bulk Calibration",
        "keywords": ["storage tank", "tank", "bulk tank", "calibration chart", "horizontal tank", "vertical tank"],
        "validity_months": 60,
        "grace_period_days": 60,
        "legal_reference": "Legal Metrology (General) Rules, 2011 - Part VII (Storage Tanks)",
        "description": "Calibration of vertical and horizontal cylindrical storage tanks (5 years)",
        "reverification_guidelines": "Re-verification and re-calibration mandatory every 5 years or upon structural alteration."
    },
    {
        "category_id": "CAT-UTILITY",
        "category": "Water & Gas Utility Meters",
        "keywords": ["water meter", "gas meter", "utility meter"],
        "validity_months": 60,
        "grace_period_days": 30,
        "legal_reference": "Legal Metrology (General) Rules, 2011 - Schedule IX",
        "description": "Domestic and industrial water meters and piped gas utility meters (5 years)",
        "reverification_guidelines": "Bench test or in-situ verification required every 60 months."
    },
    {
        "category_id": "CAT-MEASURES",
        "category": "Weights & Standard Measures",
        "keywords": ["weight", "cast iron", "brass weight", "bullion", "carat", "linear measure", "tape", "capacity measure", "conical measure"],
        "validity_months": 24,
        "grace_period_days": 30,
        "legal_reference": "Legal Metrology (General) Rules, 2011 - Schedule IX (Weights & Measures)",
        "description": "Standard weights, bullion/carat weights, linear measures, and capacity measures (2 years)",
        "reverification_guidelines": "Physical re-stamping by Legal Metrology Officer every 24 months."
    },
    {
        "category_id": "CAT-DISPENSERS",
        "category": "Fuel Dispensers & Flow Meters",
        "keywords": ["fuel dispenser", "petrol pump", "diesel pump", "flow meter", "lpg dispenser", "dispensing unit"],
        "validity_months": 12,
        "grace_period_days": 15,
        "legal_reference": "Legal Metrology (General) Rules, 2011 - Schedule IX",
        "description": "Petroleum/diesel dispensing units and commercial liquid flow meters (1 year)",
        "reverification_guidelines": "Mandatory annual totalizer check and delivery volume re-verification."
    },
    {
        "category_id": "CAT-INDUSTRIAL",
        "category": "Weighbridges & Industrial Scales",
        "keywords": ["weighbridge", "platform scale", "automatic weighing", "checkweigher", "hopper", "crane scale"],
        "validity_months": 12,
        "grace_period_days": 30,
        "legal_reference": "Legal Metrology (General) Rules, 2011 - Schedule IX",
        "description": "Weighbridges, heavy platform scales, and automatic weighing machines (1 year)",
        "reverification_guidelines": "Annual re-verification with standard weights and eccentric load tests."
    },
    {
        "category_id": "CAT-COMMERCIAL",
        "category": "Commercial Weighing Scales",
        "keywords": ["weighing scale", "electronic scale", "counter scale", "beam scale", "balance", "analytical balance", "precision balance"],
        "validity_months": 24,
        "grace_period_days": 30,
        "legal_reference": "Legal Metrology (General) Rules, 2011 - Schedule IX",
        "description": "Non-automatic commercial weighing instruments and precision balances (1 year)",
        "reverification_guidelines": "Annual statutory verification and security seal affixation."
    },
    {
        "category_id": "CAT-FARE",
        "category": "Fare Meters",
        "keywords": ["fare meter", "taxi meter", "auto meter"],
        "validity_months": 12,
        "grace_period_days": 15,
        "legal_reference": "Legal Metrology (General) Rules, 2011 - Schedule IX",
        "description": "Auto-rickshaw and taxi distance/time fare meters (1 year)",
        "reverification_guidelines": "Road test or bench simulation required annually."
    }
]

DEFAULT_VALIDITY_MONTHS = 12


def add_months(source_date: date, months: int) -> date:
    """Safely adds months to a given date handling varying month lengths and leap years."""
    new_year = source_date.year + (source_date.month - 1 + months) // 12
    new_month = (source_date.month - 1 + months) % 12 + 1
    
    if new_month in [1, 3, 5, 7, 8, 10, 12]:
        max_days = 31
    elif new_month in [4, 6, 9, 11]:
        max_days = 30
    else:  # February
        is_leap = (new_year % 4 == 0 and new_year % 100 != 0) or (new_year % 400 == 0)
        max_days = 29 if is_leap else 28
        
    new_day = min(source_date.day, max_days)
    return date(new_year, new_month, new_day)


def get_validity_rule_for_instrument(instrument_type: str) -> dict[str, Any]:
    """Finds the applicable legal metrology rule based on instrument type string."""
    norm_type = (instrument_type or "").strip().lower()
    
    for rule in LEGAL_METROLOGY_VALIDITY_RULES:
        for keyword in rule["keywords"]:
            if keyword in norm_type:
                return rule
                
    return {
        "category_id": "CAT-GENERAL",
        "category": "General Legal Metrology Instrument",
        "keywords": ["default"],
        "validity_months": DEFAULT_VALIDITY_MONTHS,
        "grace_period_days": 30,
        "legal_reference": "Legal Metrology (General) Rules, 2011 - Standard Annual Verification",
        "description": f"Standard periodicity for unclassified instruments ({DEFAULT_VALIDITY_MONTHS} months)",
        "reverification_guidelines": f"Annual re-verification required every {DEFAULT_VALIDITY_MONTHS} months."
    }


def calculate_validity(
    instrument_type: str,
    verification_date: date | None = None,
    custom_months: int | None = None
) -> tuple[date, date, int, str]:
    """
    Calculates valid_from, valid_until, validity_months, and legal reference.
    
    Returns:
        (valid_from, valid_until, validity_months, legal_reference)
    """
    start_date = verification_date or date.today()
    
    if custom_months and custom_months > 0:
        validity_months = custom_months
        legal_ref = f"Custom Authorized Period ({custom_months} months)"
    else:
        rule = get_validity_rule_for_instrument(instrument_type)
        validity_months = rule["validity_months"]
        legal_ref = rule["legal_reference"]
        
    valid_until = add_months(start_date, validity_months)
    return start_date, valid_until, validity_months, legal_ref


def assess_instrument_due_status(
    next_due_date: date | None,
    current_status: str,
    target_date: date | None = None
) -> dict[str, Any]:
    """
    Computes real-time statutory compliance, days remaining, urgency, and renewal eligibility.
    """
    check_date = target_date or date.today()
    
    if not next_due_date:
        return {
            "days_until_due": None,
            "is_expired": False,
            "urgency": "Unknown",
            "statutory_compliance": "Unverified / Pending Initial Verification",
            "is_renewal_eligible": True,
            "penalty_risk": "None"
        }
        
    days_diff = (next_due_date - check_date).days
    
    if days_diff < 0:
        overdue_days = abs(days_diff)
        urgency = "Overdue"
        statutory_compliance = f"Non-Compliant (Expired {overdue_days} days ago)"
        penalty_risk = "High" if overdue_days > 30 else "Medium"
        is_expired = True
        is_renewal_eligible = True
    elif days_diff <= 15:
        urgency = "Critical"
        statutory_compliance = f"Expiring Urgently (in {days_diff} days)"
        penalty_risk = "Low (Within Grace Period)"
        is_expired = False
        is_renewal_eligible = True
    elif days_diff <= 45:
        urgency = "Upcoming"
        statutory_compliance = f"Renewal Window Open (in {days_diff} days)"
        penalty_risk = "None"
        is_expired = False
        is_renewal_eligible = True
    else:
        urgency = "Normal"
        statutory_compliance = f"Statutorily Compliant ({days_diff} days remaining)"
        penalty_risk = "None"
        is_expired = False
        is_renewal_eligible = False
        
    return {
        "days_until_due": days_diff,
        "is_expired": is_expired,
        "urgency": urgency,
        "statutory_compliance": statutory_compliance,
        "is_renewal_eligible": is_renewal_eligible,
        "penalty_risk": penalty_risk
    }


def sync_database_expiry_statuses(db: Session) -> dict[str, int]:
    """
    Batch synchronizes expired statuses across instruments and certificates in PostgreSQL.
    Safely transitions active records whose validity has lapsed into 'Expired'.
    """
    from app.models.instrument import Instrument
    from app.models.certificate import Certificate
    
    today = date.today()
    
    # 1. Sync expired instruments
    expired_instruments = db.query(Instrument).filter(
        Instrument.next_due_date < today,
        Instrument.status == "Verified"
    ).all()
    
    for inst in expired_instruments:
        inst.status = "Expired"
        
    # 2. Sync expired certificates
    expired_certs = db.query(Certificate).filter(
        Certificate.valid_until < today,
        Certificate.status == "Active"
    ).all()
    
    for cert in expired_certs:
        cert.status = "Expired"
        
    db.commit()
    
    return {
        "instruments_expired": len(expired_instruments),
        "certificates_expired": len(expired_certs)
    }


def get_all_rules() -> list[dict[str, Any]]:
    """Returns all active Legal Metrology validity rules."""
    return LEGAL_METROLOGY_VALIDITY_RULES
