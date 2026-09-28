import hmac

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, get_current_user, hash_password, require_roles, verify_password
from app.models.user import User
from app.schemas.auth import (
    AdminPasswordResetRequest,
    AdminUserCreate,
    BootstrapAdminRequest,
    ChangePasswordRequest,
    LoginRequest,
    PasswordChangeResponse,
    TokenResponse,
    UserRegistrationRequest,
    UserResponse,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_user(db: Session, email: str, password: str, full_name: str | None, role: str) -> User:
    normalized_email = normalize_email(email)
    if db.query(User).filter(User.email == normalized_email).first():
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    user = User(
        email=normalized_email,
        full_name=full_name.strip() if full_name else None,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_applicant(request: UserRegistrationRequest, db: Session = Depends(get_db)):
    """Public registration is deliberately limited to the applicant role."""
    return create_user(db, request.email, request.password, request.full_name, "applicant")


@router.post("/bootstrap-admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_administrator(request: BootstrapAdminRequest, db: Session = Depends(get_db)):
    """One-time administrator bootstrap guarded by an environment-only secret."""
    if not settings.ADMIN_BOOTSTRAP_TOKEN:
        raise HTTPException(status_code=503, detail="Administrator bootstrap is not configured")
    if not hmac.compare_digest(request.bootstrap_token, settings.ADMIN_BOOTSTRAP_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid administrator bootstrap token")
    if db.query(User).filter(User.role == "administrator").first():
        raise HTTPException(status_code=409, detail="An administrator already exists")
    return create_user(db, request.email, request.password, request.full_name, "administrator")


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_privileged_user(
    request: AdminUserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("administrator")),
):
    return create_user(db, request.email, request.password, request.full_name, request.role)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == normalize_email(request.email)).first()
    if not user or not user.is_active or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return TokenResponse(access_token=create_access_token(user), user=user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password", response_model=PasswordChangeResponse)
def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Self-service password change for a signed-in user.

    The current password is mandatory. Without it, anyone holding a leaked or
    stolen access token could silently lock the real owner out. Hashing is
    unchanged: both the check and the write go through the scrypt helpers in
    app.core.security.
    """
    if not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if verify_password(request.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=400,
            detail="New password must be different from the current password",
        )

    current_user.password_hash = hash_password(request.new_password)
    db.commit()
    return PasswordChangeResponse(detail="Password updated successfully")


@router.post("/admin/users/{user_id}/reset-password", response_model=PasswordChangeResponse)
def admin_reset_password(
    user_id: int,
    request: AdminPasswordResetRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("administrator")),
):
    """Administrator-assisted recovery for an account that cannot sign in.

    There is no email delivery in this deployment, so a self-service reset link
    cannot be sent. This is the deliberate substitute: it is gated by the same
    require_roles helper every other privileged route uses, so RBAC behaviour is
    not weakened or duplicated. It only ever re-hashes a new password; it never
    reads, returns or logs the stored hash.
    """
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if not target.is_active:
        raise HTTPException(
            status_code=409,
            detail="Cannot reset the password of an inactive account",
        )

    target.password_hash = hash_password(request.new_password)
    db.commit()
    return PasswordChangeResponse(detail="Password reset successfully")
