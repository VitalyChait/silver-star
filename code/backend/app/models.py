from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Text, Boolean, ForeignKey, Float, JSON
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
    craigslist_jobs: Mapped[list["CraigslistJob"]] = relationship("CraigslistJob", back_populates="user")


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


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, index=True)

    full_name: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    location: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    age: Mapped[Optional[str]] = mapped_column(String(32), default=None)
    physical_condition: Mapped[Optional[str]] = mapped_column(Text, default=None)
    interests: Mapped[Optional[str]] = mapped_column(Text, default=None)
    limitations: Mapped[Optional[str]] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship("User")


class CraigslistJob(Base):
    """
    Cached Craigslist job listings from scraper.
    
    This model stores scraped job listings with metadata for matching to user profiles.
    Jobs are cached to avoid repeated scraping and to enable quick searches.
    """
    __tablename__ = "craigslist_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Job details
    title: Mapped[str] = mapped_column(String(500), index=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    location: Mapped[Optional[str]] = mapped_column(String(255), index=True, default=None)
    snippet: Mapped[Optional[str]] = mapped_column(Text, default=None)  # Short description
    apply_url: Mapped[str] = mapped_column(String(1000))  # Craigslist posting URL
    posted_at: Mapped[Optional[str]] = mapped_column(String(100), default=None)  # Date posted
    
    # Source metadata
    source: Mapped[str] = mapped_column(String(50), default="craigslist")  # Always craigslist
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), default=None)  # Search URL used
    
    # Matching/ranking data
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, default=None)
    search_intent: Mapped[Optional[dict]] = mapped_column(JSON, default=None)  # Original intent JSON
    
    # Association with user/session
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), index=True, default=None)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, default=None)  # For anonymous sessions
    
    # Status tracking
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_viewed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)  # Cache expiry
    
    # Relationships
    user: Mapped[Optional[User]] = relationship("User", back_populates="craigslist_jobs")
