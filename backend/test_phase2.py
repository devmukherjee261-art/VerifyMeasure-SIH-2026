import sys
import os
import io
import time
import json
import threading
import urllib.request
import urllib.error

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.certificate import Certificate
from app.services.pdf_service import generate_certificate_pdf
import uvicorn
from app.main import app


def run_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8002, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def run_tests():
    print("=== SIH26036 Phase 2: PDF Certificate Generation Test Suite ===")

    # 1. Direct PDF Generation Test
    print("\n1. Testing in-memory PDF generation with ReportLab & QRCode...")
    db = SessionLocal()
    try:
        cert = db.query(Certificate).first()
        assert cert is not None, "No existing certificate found in database! Run Phase 1 first."
        print(f"  Testing with Certificate: {cert.certificate_number} (ID: {cert.id})")
        print(f"  - Instrument: {cert.instrument_identifier} ({cert.instrument_type})")
        print(f"  - Validity: {cert.valid_from} to {cert.valid_until} ({cert.validity_months} months)")
        print(f"  - QR Token: {cert.qr_token}")

        pdf_bytes = generate_certificate_pdf(cert)
        assert isinstance(pdf_bytes, bytes), "PDF generation must return bytes"
        assert pdf_bytes.startswith(b"%PDF-"), "Generated content does not have a valid %PDF- magic header!"
        print(f"  [OK] PDF bytes successfully generated. Total size: {len(pdf_bytes)} bytes.")

        # Save sample PDF for inspection
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_pdfs")
        os.makedirs(output_dir, exist_ok=True)
        sample_path = os.path.join(output_dir, f"{cert.certificate_number}.pdf")
        with open(sample_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"  [OK] Sample PDF saved to disk: {sample_path}")

    finally:
        db.close()

    # 2. HTTP PDF Streaming Endpoints Test
    print("\n2. Testing HTTP PDF Streaming Endpoints on port 8002...")
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    base_url = "http://127.0.0.1:8002"
    ready = False
    for _ in range(20):
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(0.5)

    assert ready, "Server failed to start on port 8002"
    print("  [OK] Server is ready on port 8002.")

    # Test endpoint A: GET /certificates/{id}/pdf
    url_by_id = f"{base_url}/certificates/{cert.id}/pdf"
    with urllib.request.urlopen(url_by_id) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        assert resp.headers.get("Content-Type") == "application/pdf", "Expected application/pdf"
        data = resp.read()
        assert data.startswith(b"%PDF-"), "Invalid PDF header from /certificates/{id}/pdf"
        print(f"  [OK] GET /certificates/{cert.id}/pdf returned 200 with {len(data)} PDF bytes.")

    # Test endpoint B: GET /certificates/number/{cert_num}/pdf
    url_by_num = f"{base_url}/certificates/number/{cert.certificate_number}/pdf"
    with urllib.request.urlopen(url_by_num) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        assert resp.headers.get("Content-Type") == "application/pdf", "Expected application/pdf"
        data = resp.read()
        assert data.startswith(b"%PDF-"), "Invalid PDF header from /certificates/number/{num}/pdf"
        print(f"  [OK] GET /certificates/number/{cert.certificate_number}/pdf returned 200 with {len(data)} PDF bytes.")

    # Test endpoint C: GET /certificates/token/{qr_token}/pdf
    url_by_tok = f"{base_url}/certificates/token/{cert.qr_token}/pdf"
    with urllib.request.urlopen(url_by_tok) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        assert resp.headers.get("Content-Type") == "application/pdf", "Expected application/pdf"
        data = resp.read()
        assert data.startswith(b"%PDF-"), "Invalid PDF header from /certificates/token/{token}/pdf"
        print(f"  [OK] GET /certificates/token/{cert.qr_token}/pdf returned 200 with {len(data)} PDF bytes.")

    # Test endpoint D: 404 for non-existent certificate
    try:
        urllib.request.urlopen(f"{base_url}/certificates/999999/pdf")
        assert False, "Should have returned 404 for non-existent certificate"
    except urllib.error.HTTPError as e:
        assert e.code == 404, f"Expected 404, got {e.code}"
        print(f"  [OK] Non-existent certificate correctly returned HTTP 404.")

    print("\n=== ALL PHASE 2 TESTS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    run_tests()
