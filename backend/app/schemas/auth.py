from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


UserRole = Literal["applicant", "inspector", "approving_officer", "administrator"]


class UserRegistrationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=150)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class BootstrapAdminRequest(UserRegistrationRequest):
    bootstrap_token: str = Field(min_length=1)


class AdminUserCreate(UserRegistrationRequest):
    role: UserRole


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    # The current password is required so that a stolen access token on its own
    # is not enough to take over the account. It is never logged or echoed back.
    current_password: str = Field(min_length=1, max_length=128)
    # Same length policy as UserRegistrationRequest, so an account cannot be
    # "upgraded" into a weaker password by going through the reset path.
    new_password: str = Field(min_length=8, max_length=128)


class AdminPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class PasswordChangeResponse(BaseModel):
    detail: str
