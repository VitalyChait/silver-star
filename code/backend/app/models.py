from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="owner")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    location: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    description: Mapped[str] = mapped_column(Text)
    job_type: Mapped[Optional[str]] = mapped_column(String(50), default=None)  # e.g., part-time, remote
    url: Mapped[Optional[str]] = mapped_column(String(500), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    owner: Mapped[Optional[User]] = relationship("User", back_populates="jobs")
