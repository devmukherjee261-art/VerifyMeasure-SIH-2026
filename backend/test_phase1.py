import sys
import os
from datetime import date
from sqlalchemy import inspect

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import Base, engine, SessionLocal
from app.models.instrument import Instrument
from app.models.application import Application
from app.models.inspection import Inspection
from app.models.certificate import Certificate
from app.services.validity_service import calculate_validity, get_all_rules
from app.routers.certificate import issue_certificate, generate_certificate_number
from app.schemas.certificate import CertificateIssueRequest
from fastapi import HTTPException


def run_tests():
    print("=== SIH26036 Phase 1 Test Suite ===")
    
    # 1. Test Database Connection & Table Creation
    print("\n1. Testing Database Connection & Schema Migration...")
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Tables in database: {tables}")
    assert "certificates" in tables, "Table 'certificates' not found in database!"
    
    cert_cols = [c["name"] for c in inspector.get_columns("certificates")]
    print(f"Columns in 'certificates': {cert_cols}")
    required_cols = [
        "id", "certificate_number", "qr_token", "application_id",
        "instrument_id", "inspection_id", "valid_from", "valid_until",
        "validity_months", "result", "issuing_authority"
    ]
    for col in required_cols:
        assert col in cert_cols, f"Required column '{col}' missing from 'certificates'!"
    print("[OK] Schema migration verified successfully.")

    # 2. Test Rule-based Validity Service
    print("\n2. Testing Legal Metrology Validity Rules...")
    test_cases = [
        ("Electronic Weighing Scale", 24),
        ("Weighbridge 50T", 12),
        ("Cast Iron Standard Weight", 24),
        ("Linear Tape Measure", 24),
        ("Bulk Storage Tank Calibration", 60),
        ("Industrial Water Meter", 60),
        ("Fuel Dispenser Petrol Pump", 12),
        ("Taxi Fare Meter", 12),
    ]
    for inst_type, expected_months in test_cases:
        v_from, v_until, months, ref = calculate_validity(inst_type, date(2026, 1, 1))
        assert months == expected_months, f"Expected {expected_months} months for {inst_type}, got {months}"
        print(f"  - '{inst_type}': {months} months | Valid until {v_until} | Ref: {ref}")
    print("[OK] Legal Metrology validity rules verified successfully.")

    # 3. Test Certificate Issuance Workflow
    print("\n3. Testing Certificate Issuance Workflow & Constraints...")
    db = SessionLocal()
    try:
        # Clean up any existing test data (in correct FK order)
        db.query(Certificate).filter(Certificate.certificate_number.like("CERT-TEST%")).delete()
        db.query(Certificate).filter(Certificate.certificate_number.like("CERT-2026-0000%")).delete()
        db.query(Inspection).filter(Inspection.application_id.in_(
            db.query(Application.id).filter(Application.application_number.like("APP-TEST%"))
        )).delete(synchronize_session=False)
        db.query(Inspection).filter(Inspection.application_id.in_(
            db.query(Application.id).filter(Application.instrument_id.in_(
                db.query(Instrument.id).filter(Instrument.instrument_id == "TEST-PHASE1-INS-001")
            ))
        )).delete(synchronize_session=False)
        db.query(Application).filter(Application.application_number.like("APP-TEST%")).delete()
        db.query(Application).filter(Application.instrument_id.in_(
            db.query(Instrument.id).filter(Instrument.instrument_id == "TEST-PHASE1-INS-001")
        )).delete(synchronize_session=False)
        db.query(Certificate).filter(Certificate.instrument_id.in_(
            db.query(Instrument.id).filter(Instrument.instrument_id == "TEST-PHASE1-INS-001")
        )).delete(synchronize_session=False)
        db.query(Instrument).filter(Instrument.instrument_id == "TEST-PHASE1-INS-001").delete()
        db.commit()

        # Create or fetch test instrument
        test_inst_id = "TEST-PHASE1-INS-001"
        inst = db.query(Instrument).filter(Instrument.instrument_id == test_inst_id).first()
        if not inst:
            inst = Instrument(
                instrument_id=test_inst_id,
                instrument_type="Electronic Weighing Scale",
                manufacturer="Avery Weigh-Tronix",
                model_number="E1010",
                serial_number="SN-TEST-998877",
                capacity="50 kg",
                location="Delhi Mandi Yard",
                owner_name="Ramesh Trading Corp",
                status="Pending"
            )
            db.add(inst)
            db.commit()
            db.refresh(inst)
        print(f"  Test Instrument ID: {inst.id} ({inst.instrument_id})")

        # Create verification application
        app_num = f"APP-TEST-{inst.id}-{date.today().strftime('%Y%m%d%H%M%S')}"
        app = Application(
            application_number=app_num,
            instrument_id=inst.id,
            application_type="Verification",
            application_date=date.today(),
            status="Submitted",
            remarks="Initial verification test"
        )
        db.add(app)
        db.commit()
        db.refresh(app)
        print(f"  Test Application ID: {app.id} ({app.application_number})")

        # Constraint Test A: Issuing without inspection must fail
        print("  Testing constraint: Issuing certificate without inspection...")
        try:
            issue_certificate(CertificateIssueRequest(application_id=app.id), db=db)
            assert False, "Should have failed to issue certificate without inspection!"
        except HTTPException as e:
            print(f"  [OK] Expected failure: HTTP {e.status_code} - {e.detail}")

        # Create Failed inspection
        fail_insp = Inspection(
            application_id=app.id,
            standard_value=10.0,
            measured_value=10.5, # Error 0.5 exceeds tolerance
            error=0.5,
            result="Fail",
            inspection_date=date.today(),
            inspector_remarks="Exceeded maximum permissible error"
        )
        db.add(fail_insp)
        app.status = "Rejected"
        db.commit()
        db.refresh(fail_insp)
        print(f"  Test Failed Inspection ID: {fail_insp.id}")

        # Constraint Test B: Issuing for Failed inspection must fail
        print("  Testing constraint: Issuing certificate for Failed inspection...")
        try:
            issue_certificate(CertificateIssueRequest(inspection_id=fail_insp.id), db=db)
            assert False, "Should have failed to issue certificate for Failed inspection!"
        except HTTPException as e:
            print(f"  [OK] Expected failure: HTTP {e.status_code} - {e.detail}")

        # Create Passed inspection
        pass_insp = Inspection(
            application_id=app.id,
            standard_value=10.0,
            measured_value=10.01,
            error=0.01,
            result="Pass",
            inspection_date=date.today(),
            inspector_remarks="Within legal tolerance limits"
        )
        db.add(pass_insp)
        app.status = "approved"
        db.commit()
        db.refresh(pass_insp)
        print(f"  Test Passed Inspection ID: {pass_insp.id}")

        # Issuance Test: Issue certificate for Passed inspection
        print("  Testing issuance: Issue certificate for Passed inspection...")
        cert = issue_certificate(
            CertificateIssueRequest(
                inspection_id=pass_insp.id,
                issuing_authority="Legal Metrology Standards Laboratory, Delhi",
                remarks="Annual statutory verification"
            ),
            db=db
        )
        print(f"  [OK] Certificate issued successfully!")
        print(f"    - Certificate Number: {cert.certificate_number}")
        print(f"    - QR Token: {cert.qr_token}")
        print(f"    - Valid From: {cert.valid_from} to {cert.valid_until} ({cert.validity_months} months)")
        print(f"    - Inspection ID FK: {cert.inspection_id}")
        print(f"    - Issuing Authority: {cert.issuing_authority}")

        # Check instrument synchronization
        db.refresh(inst)
        assert inst.status == "Verified", f"Instrument status not updated! Current: {inst.status}"
        assert inst.verification_date == cert.valid_from, "Instrument verification_date mismatch!"
        assert inst.next_due_date == cert.valid_until, "Instrument next_due_date mismatch!"
        print(f"  [OK] Instrument synchronized: Status={inst.status}, Due Date={inst.next_due_date}")

        # Constraint Test C: Duplicate issuance must fail
        print("  Testing constraint: Duplicate certificate issuance...")
        try:
            issue_certificate(CertificateIssueRequest(inspection_id=pass_insp.id), db=db)
            assert False, "Should have failed to issue duplicate certificate!"
        except HTTPException as e:
            print(f"  [OK] Expected failure: HTTP {e.status_code} - {e.detail}")

        # Retrieval Tests
        print("\n4. Testing Certificate Retrieval Endpoints...")
        by_num = db.query(Certificate).filter(Certificate.certificate_number == cert.certificate_number).first()
        assert by_num is not None, "Certificate lookup by number failed"
        assert by_num.qr_token == cert.qr_token, "QR token mismatch"
        print(f"  [OK] Lookup by certificate number '{cert.certificate_number}' succeeded.")

        by_token = db.query(Certificate).filter(Certificate.qr_token == cert.qr_token).first()
        assert by_token is not None, "Certificate lookup by QR token failed"
        print(f"  [OK] Lookup by QR token '{cert.qr_token}' succeeded.")

        by_app = db.query(Certificate).filter(Certificate.application_id == app.id).first()
        assert by_app is not None, "Certificate lookup by application ID failed"
        print(f"  [OK] Lookup by application ID '{app.id}' succeeded.")

        print("\n=== ALL PHASE 1 TESTS PASSED SUCCESSFULLY! ===")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
