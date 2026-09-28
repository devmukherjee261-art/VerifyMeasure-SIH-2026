import sys
import os
import json
import time
import threading
import urllib.request
import urllib.error

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from app.main import app
from app.core.database import SessionLocal
from app.core.security import hash_password, verify_password
from app.models.user import User

PORT = 8021
BASE_URL = f"http://127.0.0.1:{PORT}"

APPLICANT_EMAIL = "pwtest.applicant@example.com"
ADMIN_EMAIL = "pwtest.admin@example.com"
APPLICANT_PASSWORD = "OriginalPass123"
RESET_PASSWORD = "AdminSetPass456"

CHANGED_PASSWORD = "ChangedPass789"

PASSED = 0
FAILED = 0


def check(label, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"[OK] {label}")
    else:
        FAILED += 1
        print(f"[FAIL] {label} {detail}")


def call(method, path, body=None, token=None, expect=200):
    """Return (status_code, decoded_body_or_None)."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"{BASE_URL}{path}", data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = response.read().decode()
            return response.status, (json.loads(payload) if payload else None)
    except urllib.error.HTTPError as error:
        payload = error.read().decode()
        try:
            return error.code, (json.loads(payload) if payload else None)
        except json.JSONDecodeError:
            return error.code, {"detail": payload}


def run_server():
    config = uvicorn.Config(
        app, host="127.0.0.1", port=PORT, log_level="warning"
    )
    uvicorn.Server(config).run()


def clean_up():
    db = SessionLocal()
    try:
        db.query(User).filter(
            User.email.in_([APPLICANT_EMAIL, ADMIN_EMAIL])
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def create_test_administrator():
    """An administrator already exists in the local database, so /bootstrap-admin
    correctly refuses to run. The test provisions its own throwaway administrator
    through the same hashing path the API uses, and removes it afterwards."""
    db = SessionLocal()
    try:
        admin = User(
            email=ADMIN_EMAIL,
            full_name="Password Test Admin",
            password_hash=hash_password(RESET_PASSWORD),
            role="administrator",
        )
        db.add(admin)
        db.commit()
    finally:
        db.close()


def main():
    clean_up()
    create_test_administrator()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    ready = False
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=1) as response:
                if response.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(0.5)

    if not ready:
        print("[FAIL] Server failed to start")
        clean_up()
        sys.exit(1)

    print("=== Testing password change and reset flow ===\n")

    try:
        # --- Hashing invariants, checked before any HTTP call ---------------
        db = SessionLocal()
        try:
            first = hash_password("identical-password")
            second = hash_password("identical-password")
            applicant_row = (
                db.query(User).filter(User.email == APPLICANT_EMAIL).first()
            ) or None
        finally:
            db.close()

        check(
            "Hash format is still scrypt$salt$hash",
            first.startswith("scrypt$") and first.count("$") == 5,
        )
        check(
            "Plaintext never appears in the hash",
            "identical-password" not in first,
        )
        check(
            "Same password hashes differently (random salt)",
            first != second,
        )
        check(
            "verify_password accepts the correct password",
            verify_password("identical-password", first),
        )
        check(
            "verify_password rejects a wrong password",
            not verify_password("wrong-password", first),
        )

        # --- Existing behaviour is preserved --------------------------------
        status, body = call(
            "POST", "/auth/register",
            {
                "email": APPLICANT_EMAIL,
                "password": APPLICANT_PASSWORD,
                "full_name": "Password Test Applicant",
            },
            expect=201,
        )
        check("Public registration still works", status == 201, f"got {status}")

        status, body = call(
            "POST", "/auth/login",
            {"email": APPLICANT_EMAIL, "password": APPLICANT_PASSWORD},
        )
        check("Login still works", status == 200, f"got {status}")
        applicant_token = body["access_token"] if status == 200 else None

        status, _ = call("GET", "/auth/me", token=applicant_token)
        check("GET /auth/me still works", status == 200, f"got {status}")

        # --- Authentication is required --------------------------------------
        status, _ = call(
            "POST", "/auth/change-password",
            {"current_password": APPLICANT_PASSWORD, "new_password": CHANGED_PASSWORD},
        )
        check("Change without a token is rejected", status == 401, f"got {status}")

        status, _ = call(
            "POST", "/auth/change-password",
            {"current_password": APPLICANT_PASSWORD, "new_password": CHANGED_PASSWORD},
            token="not-a-real-token",
        )
        check("Change with a bogus token is rejected", status == 401, f"got {status}")

        # --- The current password is genuinely enforced ----------------------
        status, body = call(
            "POST", "/auth/change-password",
            {"current_password": "wrong-current", "new_password": CHANGED_PASSWORD},
            token=applicant_token,
        )
        check("Wrong current password is rejected", status == 400, f"got {status}")
        check(
            "Rejection message does not leak the hash",
            "scrypt" not in json.dumps(body or {}).lower(),
        )

        status, _ = call(
            "POST", "/auth/change-password",
            {"current_password": APPLICANT_PASSWORD, "new_password": "short"},
            token=applicant_token,
        )
        check("Too-short new password is rejected by validation", status == 422, f"got {status}")

        status, _ = call(
            "POST", "/auth/change-password",
            {
                "current_password": APPLICANT_PASSWORD,
                "new_password": APPLICANT_PASSWORD,
            },
            token=applicant_token,
        )
        check("Reusing the current password is rejected", status == 400, f"got {status}")

        # --- The successful change -------------------------------------------
        status, body = call(
            "POST", "/auth/change-password",
            {"current_password": APPLICANT_PASSWORD, "new_password": CHANGED_PASSWORD},
            token=applicant_token,
        )
        check("Change with the correct current password succeeds", status == 200, f"got {status}")
        check(
            "Response carries no password material",
            "password" not in json.dumps(body or {}).lower().replace("password updated successfully", ""),
        )

        status, _ = call(
            "POST", "/auth/login",
            {"email": APPLICANT_EMAIL, "password": APPLICANT_PASSWORD},
        )
        check("Old password no longer works", status == 401, f"got {status}")

        status, _ = call(
            "POST", "/auth/login",
            {"email": APPLICANT_EMAIL, "password": CHANGED_PASSWORD},
        )
        check("New password works", status == 200, f"got {status}")

        # --- RBAC on the admin reset path -------------------------------------
        status, _ = call(
            "POST", "/auth/admin/users/1/reset-password",
            {"new_password": "AttackerChosen99"},
            token=applicant_token,
        )
        check("Applicant cannot use the admin reset route", status == 403, f"got {status}")

        status, _ = call(
            "POST", "/auth/admin/users/1/reset-password",
            {"new_password": "AttackerChosen99"},
        )
        check("Admin reset without a token is rejected", status == 401, f"got {status}")

        # --- Administrator-driven recovery (the locked-out account case) ------
        status, _ = call(
            "POST", "/auth/login",
            {"email": ADMIN_EMAIL, "password": RESET_PASSWORD},
        )
        check("Test administrator can sign in", status == 200, f"got {status}")
        admin_token = call(
            "POST", "/auth/login",
            {"email": ADMIN_EMAIL, "password": RESET_PASSWORD},
        )[1]["access_token"]

        status, _ = call(
            "POST", "/auth/admin/users/999999/reset-password",
            {"new_password": "Whatever12345"},
            token=admin_token,
        )
        check("Resetting an unknown user returns 404", status == 404, f"got {status}")

        db = SessionLocal()
        try:
            target = db.query(User).filter(User.email == APPLICANT_EMAIL).first()
            target_id = target.id
        finally:
            db.close()

        status, _ = call(
            "POST", f"/auth/admin/users/{target_id}/reset-password",
            {"new_password": RESET_PASSWORD},
            token=admin_token,
        )
        check("Administrator can reset a locked-out user", status == 200, f"got {status}")

        status, _ = call(
            "POST", "/auth/login",
            {"email": APPLICANT_EMAIL, "password": CHANGED_PASSWORD},
        )
        check("Previous password stops working after admin reset", status == 401, f"got {status}")

        status, _ = call(
            "POST", "/auth/login",
            {"email": APPLICANT_EMAIL, "password": RESET_PASSWORD},
        )
        check("Administrator-set password works", status == 200, f"got {status}")

        # --- The stored value is still a hash --------------------------------
        db = SessionLocal()
        try:
            row = db.query(User).filter(User.email == APPLICANT_EMAIL).first()
            stored = row.password_hash
        finally:
            db.close()

        check("Stored value is still a scrypt hash", stored.startswith("scrypt$"))
        check("Stored value is not the plaintext", stored != RESET_PASSWORD)
        check("Hash verifies against the new password", verify_password(RESET_PASSWORD, stored))

    finally:
        clean_up()

    print(f"\n=== {PASSED} passed, {FAILED} failed ===")
    if FAILED:
        sys.exit(1)
    print("=== ALL PASSWORD TESTS PASSED ===")


if __name__ == "__main__":
    main()
