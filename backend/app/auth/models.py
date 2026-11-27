"""
SetuHaul Logistics — Authentication Data Models
Provides typed Pydantic models for user profiles, roles, and login/signup contracts.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    DRIVER = "DRIVER"
    SUPERVISOR = "SUPERVISOR"
    OPERATOR = "OPERATOR"


class UserProfile(BaseModel):
    user_id: str
    username: str
    full_name: str
    role: UserRole
    driver_id: Optional[str] = None
    shipment_id: Optional[str] = None
    order_reference: Optional[str] = None
    phone: Optional[str] = None
    carrier_id: Optional[str] = None
    created_at: Optional[str] = None


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username or Driver ID")
    password: str = Field(..., description="Account password (default: 123456)")


class SignupRequest(BaseModel):
    username: str = Field(..., description="Unique username")
    password: str = Field(..., description="Account password")
    full_name: str = Field(..., description="Full user name")
    role: UserRole = Field(UserRole.DRIVER, description="Account role (DRIVER or ADMIN)")
    driver_id: Optional[str] = Field(None, description="Optional Driver ID")
    phone: Optional[str] = Field(None, description="Contact phone")


class AuthResponse(BaseModel):
    status: str = "SUCCESS"
    access_token: str
    token_type: str = "bearer"
    user: UserProfile
    message: Optional[str] = None
