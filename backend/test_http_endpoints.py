import sys
import os
import time
import json
import threading
import urllib.request
import urllib.error

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from app.main import app

def run_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="warning")
    server = uvicorn.Server(config)
    server.run()

def test_endpoints():
    print("=== Testing FastAPI HTTP Endpoints on port 8001 ===")
    
    # Start server in daemon thread
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    
    # Wait for server to be ready
    base_url = "http://127.0.0.1:8001"
    ready = False
    for _ in range(20):
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(0.5)
            
    if not ready:
        print("[FAIL] Server failed to start on port 8001")
        sys.exit(1)
        
    print("[OK] FastAPI server is up and healthy.")
    
    # Test 1: GET /health and /
    with urllib.request.urlopen(f"{base_url}/") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        print(f"[OK] Root endpoint response: {data}")

    # Test 2: GET /certificates/rules
    with urllib.request.urlopen(f"{base_url}/certificates/rules") as resp:
        assert resp.status == 200
        rules = json.loads(resp.read().decode())
        assert len(rules) > 0
        print(f"[OK] GET /certificates/rules returned {len(rules)} Legal Metrology rule categories.")

    # Test 3: GET /certificates/
    with urllib.request.urlopen(f"{base_url}/certificates/") as resp:
        assert resp.status == 200
        certs = json.loads(resp.read().decode())
        print(f"[OK] GET /certificates/ returned {len(certs)} certificate(s).")
        if certs:
            first_cert = certs[0]
            cert_num = first_cert["certificate_number"]
            qr_token = first_cert["qr_token"]
            
            # Test 4: GET /certificates/number/{cert_num}
            with urllib.request.urlopen(f"{base_url}/certificates/number/{cert_num}") as r_num:
                assert r_num.status == 200
                res_data = json.loads(r_num.read().decode())
                assert res_data["certificate_number"] == cert_num
                print(f"[OK] GET /certificates/number/{cert_num} succeeded.")

            # Test 5: GET /certificates/token/{qr_token}
            with urllib.request.urlopen(f"{base_url}/certificates/token/{qr_token}") as r_tok:
                assert r_tok.status == 200
                res_tok = json.loads(r_tok.read().decode())
                assert res_tok["qr_token"] == qr_token
                print(f"[OK] GET /certificates/token/{qr_token} succeeded.")

    # Test 6: Invalid token lookup returns 404
    try:
        urllib.request.urlopen(f"{base_url}/certificates/token/invalid_token_xyz_123")
        assert False, "Should have received 404 for invalid QR token!"
    except urllib.error.HTTPError as e:
        assert e.code == 404
        print(f"[OK] GET /certificates/token/invalid correctly returned HTTP 404.")

    print("\n=== ALL HTTP ENDPOINT TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    test_endpoints()
