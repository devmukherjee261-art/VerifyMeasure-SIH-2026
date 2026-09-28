import sys
import os
import json
import time
import threading
import urllib.request
import urllib.error
from datetime import date, timedelta

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.certificate import Certificate
from app.services.qr_service import mask_stakeholder_name, generate_qr_code_png
import uvicorn
from app.main import app


def run_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8003, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def run_tests():
    print("=== SIH26036 Phase 3: QR Generation & Public Verification Test Suite ===")

    # 1. Test Stakeholder PII Masking Unit Function
    print("\n1. Testing Stakeholder PII Masking...")
    name_tests = [
        ("Ramesh Trading Corp", "R***h T***g C**p"),
        ("Anil Kumar", "A**l K***r"),
        ("Om", "O*"),
        ("Dev", "D*v"),
    ]
    for raw, expected in name_tests:
        masked = mask_stakeholder_name(raw)
        assert "*" in masked, f"Masked name '{masked}' must contain masking asterisks!"
        assert raw != masked, f"Raw name '{raw}' must not equal masked name '{masked}'"
        print(f"  [OK] Masked '{raw}' -> '{masked}'")

    # 2. Test QR PNG Binary Generation
    print("\n2. Testing QR PNG Binary Generation...")
    sample_png = generate_qr_code_png("https://legalmetrology.gov.in/verify?token=sample")
    assert isinstance(sample_png, bytes)
    assert sample_png.startswith(b"\x89PNG\r\n\x1a\n"), "Invalid PNG magic bytes header!"
    print(f"  [OK] QR PNG generated with valid magic bytes. Size: {len(sample_png)} bytes.")

    # 3. HTTP Server Endpoints Test
    print("\n3. Testing Public Verification & QR Endpoints on port 8003...")
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    base_url = "http://127.0.0.1:8003"
    ready = False
    for _ in range(20):
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(0.5)

    assert ready, "Server failed to start on port 8003"
    print("  [OK] Server is ready on port 8003.")

    db = SessionLocal()
    try:
        cert = db.query(Certificate).first()
        assert cert is not None, "No test certificate found in database!"

        # Test 3A: Valid QR Verification endpoint
        verify_url = f"{base_url}/certificates/verify/{cert.qr_token}"
        with urllib.request.urlopen(verify_url) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            print(f"  [OK] GET /certificates/verify/{cert.qr_token} returned 200.")
            print(f"    - is_authentic: {data.get('is_authentic')}")
            print(f"    - certificate_number: {data.get('certificate_number')}")
            print(f"    - instrument: {data.get('instrument_identifier')} ({data.get('instrument_type')})")
            print(f"    - owner_masked: {data.get('owner_masked')}")
            print(f"    - days_remaining: {data.get('days_remaining')}")
            print(f"    - is_valid_currently: {data.get('is_valid_currently')}")

            # SECURITY VALIDATION: Ensure NO internal IDs or DB credentials are leaked!
            forbidden_keys = ["id", "application_id", "instrument_id", "inspection_id", "DATABASE_URL", "password"]
            for key in forbidden_keys:
                assert key not in data, f"SECURITY VIOLATION: Sensitive or internal key '{key}' found in public verification payload!"
            
            # Ensure owner name is masked
            assert "*" in data["owner_masked"], "Stakeholder name was not masked in public response!"
            print("  [OK] Security check passed: Zero internal IDs or raw stakeholder PII exposed.")

        # Test 3B: Invalid QR Verification (Tampered/Fake Token)
        invalid_tokens = ["invalid_fake_token_123", "00000000000000000000000000000000", "tampered_qr_code"]
        for fake_token in invalid_tokens:
            try:
                urllib.request.urlopen(f"{base_url}/certificates/verify/{fake_token}")
                assert False, f"Should have failed for counterfeit token: {fake_token}"
            except urllib.error.HTTPError as e:
                assert e.code == 404
                err_data = json.loads(e.read().decode())
                print(f"  [OK] Fake token '{fake_token}' correctly rejected with HTTP 404: {err_data.get('detail')}")

        # Test 3C: QR Image Stream by Token
        qr_token_url = f"{base_url}/certificates/token/{cert.qr_token}/qr"
        with urllib.request.urlopen(qr_token_url) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type") == "image/png"
            png_bytes = resp.read()
            assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
            print(f"  [OK] GET /certificates/token/{cert.qr_token}/qr returned valid PNG ({len(png_bytes)} bytes).")

        # Test 3D: QR Image Stream by Certificate Number
        qr_num_url = f"{base_url}/certificates/number/{cert.certificate_number}/qr"
        with urllib.request.urlopen(qr_num_url) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type") == "image/png"
            png_bytes2 = resp.read()
            assert png_bytes2.startswith(b"\x89PNG\r\n\x1a\n")
            print(f"  [OK] GET /certificates/number/{cert.certificate_number}/qr returned valid PNG ({len(png_bytes2)} bytes).")

        # Test 3E: QR Image Stream for Invalid Token
        try:
            urllib.request.urlopen(f"{base_url}/certificates/token/fake_qr_token/qr")
            assert False, "Should have returned 404 for invalid QR token image request"
        except urllib.error.HTTPError as e:
            assert e.code == 404
            print("  [OK] Fake QR image request correctly rejected with HTTP 404.")

        # Test 3F: Test Expired Certificate Status Logic
        print("\n4. Testing Validity / Expiry Status Calculation...")
        from app.models.inspection import Inspection
        today = date.today()

        test_insp = Inspection(
            application_id=cert.application_id,
            standard_value=50.0,
            measured_value=50.01,
            error=0.01,
            result="Pass",
            inspection_date=today - timedelta(days=400),
            inspector_remarks="Historical inspection for expiry test"
        )
        db.add(test_insp)
        db.commit()
        db.refresh(test_insp)

        past_cert = Certificate(
            certificate_number="CERT-TEST-EXPIRED-001",
            qr_token="expired_token_test_abc123",
            application_id=cert.application_id,
            instrument_id=cert.instrument_id,
            inspection_id=test_insp.id,
            instrument_identifier="EXP-INS-001",
            instrument_type="Platform Scale",
            manufacturer="Metler",
            model_number="M100",
            serial_number="EXP-SN-001",
            capacity="100 kg",
            location="Warehouse 4",
            owner_name="Gupta Industries",
            standard_value=50.0,
            measured_value=50.01,
            error=0.01,
            result="Pass",
            verification_date=today - timedelta(days=400),
            valid_from=today - timedelta(days=400),
            valid_until=today - timedelta(days=35), # Expired 35 days ago
            validity_months=12,
            issuing_authority="Legal Metrology Lab",
            status="Active"
        )
        db.add(past_cert)
        db.commit()
        db.refresh(past_cert)

        with urllib.request.urlopen(f"{base_url}/certificates/verify/{past_cert.qr_token}") as exp_resp:
            assert exp_resp.status == 200
            exp_data = json.loads(exp_resp.read().decode())
            assert exp_data["is_valid_currently"] is False, "Expired certificate must have is_valid_currently == False!"
            assert exp_data["status"] == "Expired", f"Status should be 'Expired', got '{exp_data['status']}'"
            assert exp_data["days_remaining"] < 0, "Days remaining for expired certificate must be negative!"
            print(f"  [OK] Expired certificate correctly detected:")
            print(f"    - status: {exp_data['status']}")
            print(f"    - is_valid_currently: {exp_data['is_valid_currently']}")
            print(f"    - days_remaining: {exp_data['days_remaining']}")

        # Clean up temporary test certificate and inspection
        db.delete(past_cert)
        db.delete(test_insp)
        db.commit()

        print("\n=== ALL PHASE 3 TESTS PASSED SUCCESSFULLY! ===")

    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
