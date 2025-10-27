from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator


# Auth
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    sub: Optional[str] = None


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str
    name: Optional[str] = None

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    name: Optional[str] = None

    class Config:
        from_attributes = True


class JobBase(BaseModel):
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    description: str
    job_type: Optional[str] = None
    url: Optional[str] = None
    is_active: bool = True


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    job_type: Optional[str] = None
    url: Optional[str] = None
    is_active: Optional[bool] = None


class JobPublic(JobBase):
    id: int
    created_at: datetime
    owner_id: Optional[int] = None

    class Config:
        from_attributes = True
