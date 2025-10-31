from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from . import models, schemas
from .security import get_password_hash


# Users
def get_user_by_email(db: Session, email: str) -> models.User | None:
    stmt = select(models.User).where(models.User.email == email)
    return db.execute(stmt).scalars().first()


def create_user(db: Session, user_in: schemas.UserCreate) -> models.User:
    user = models.User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# Jobs
def create_job(db: Session, owner_id: int | None, job_in: schemas.JobCreate) -> models.Job:
    job = models.Job(owner_id=owner_id, **job_in.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: int) -> models.Job | None:
    return db.get(models.Job, job_id)


def list_jobs(db: Session, q: str | None = None, limit: int = 50, skip: int = 0) -> list[models.Job]:
    stmt = select(models.Job).where(models.Job.is_active == True)  # noqa: E712
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (models.Job.title.ilike(like))
            | (models.Job.company.ilike(like))
            | (models.Job.location.ilike(like))
            | (models.Job.description.ilike(like))
        )
    stmt = stmt.order_by(models.Job.created_at.desc()).limit(limit).offset(skip)
    return list(db.execute(stmt).scalars().all())


def update_job(db: Session, job: models.Job, job_in: schemas.JobUpdate) -> models.Job:
    data = job_in.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(job, key, value)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def delete_job(db: Session, job: models.Job) -> None:
    db.delete(job)
    db.commit()


# Candidate Profiles
def get_candidate_profile(db: Session, user_id: int) -> models.CandidateProfile | None:
    stmt = select(models.CandidateProfile).where(models.CandidateProfile.user_id == user_id)
    return db.execute(stmt).scalars().first()


def upsert_candidate_profile(db: Session, user_id: int, data: schemas.CandidateProfileUpdate) -> models.CandidateProfile:
    profile = get_candidate_profile(db, user_id)
    payload = data.model_dump(exclude_unset=True)
    if profile is None:
        profile = models.CandidateProfile(user_id=user_id)
        db.add(profile)
    for key, value in payload.items():
        setattr(profile, key, value.strip() if isinstance(value, str) else value)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


# Craigslist Jobs
def create_craigslist_job(
    db: Session,
    job_data: Dict[str, Any],
    user_id: Optional[int] = None,
    conversation_id: Optional[str] = None,
    search_intent: Optional[Dict[str, Any]] = None,
    relevance_score: Optional[float] = None,
    cache_hours: int = 24
) -> models.CraigslistJob:
    """
    Create a new cached Craigslist job listing.
    
    Args:
        db: Database session
        job_data: Job data from scraper (title, company, location, etc.)
        user_id: Optional user ID for authenticated users
        conversation_id: Optional conversation ID for anonymous sessions
        search_intent: Optional search intent JSON that led to this result
        relevance_score: Optional relevance score for ranking
        cache_hours: Number of hours to cache this job (default: 24)
    
    Returns:
        Created CraigslistJob model instance
    """
    expires_at = datetime.utcnow() + timedelta(hours=cache_hours)
    
    job = models.CraigslistJob(
        title=job_data.get("title", "Untitled"),
        company=job_data.get("company"),
        location=job_data.get("location"),
        snippet=job_data.get("snippet"),
        apply_url=job_data.get("apply_url", ""),
        posted_at=job_data.get("posted_at"),
        source=job_data.get("source", "craigslist"),
        source_url=job_data.get("source_url"),
        relevance_score=relevance_score,
        search_intent=search_intent,
        user_id=user_id,
        conversation_id=conversation_id,
        expires_at=expires_at,
    )
    
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def bulk_create_craigslist_jobs(
    db: Session,
    jobs_data: List[Dict[str, Any]],
    user_id: Optional[int] = None,
    conversation_id: Optional[str] = None,
    search_intent: Optional[Dict[str, Any]] = None,
    cache_hours: int = 24
) -> List[models.CraigslistJob]:
    """
    Bulk create Craigslist job listings for efficient batch inserts.
    
    Args:
        db: Database session
        jobs_data: List of job data dicts from scraper
        user_id: Optional user ID for authenticated users
        conversation_id: Optional conversation ID for anonymous sessions
        search_intent: Optional search intent JSON
        cache_hours: Number of hours to cache jobs (default: 24)
    
    Returns:
        List of created CraigslistJob instances
    """
    expires_at = datetime.utcnow() + timedelta(hours=cache_hours)
    
    jobs = []
    for job_data in jobs_data:
        job = models.CraigslistJob(
            title=job_data.get("title", "Untitled"),
            company=job_data.get("company"),
            location=job_data.get("location"),
            snippet=job_data.get("snippet"),
            apply_url=job_data.get("apply_url", ""),
            posted_at=job_data.get("posted_at"),
            source=job_data.get("source", "craigslist"),
            source_url=job_data.get("source_url"),
            relevance_score=job_data.get("relevance_score"),
            search_intent=search_intent,
            user_id=user_id,
            conversation_id=conversation_id,
            expires_at=expires_at,
        )
        jobs.append(job)
    
    db.add_all(jobs)
    db.commit()
    for job in jobs:
        db.refresh(job)
    
    return jobs


def get_craigslist_jobs(
    db: Session,
    user_id: Optional[int] = None,
    conversation_id: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    include_expired: bool = False,
    order_by_relevance: bool = True
) -> List[models.CraigslistJob]:
    """
    Retrieve cached Craigslist jobs for a user or conversation.
    
    Args:
        db: Database session
        user_id: Optional user ID filter
        conversation_id: Optional conversation ID filter
        limit: Maximum number of results
        skip: Number of results to skip (pagination)
        include_expired: Whether to include expired cache entries
        order_by_relevance: Sort by relevance_score (descending) vs created_at (descending)
    
    Returns:
        List of CraigslistJob instances
    """
    stmt = select(models.CraigslistJob).where(models.CraigslistJob.is_active == True)  # noqa: E712
    
    # Filter by user_id or conversation_id
    if user_id is not None:
        stmt = stmt.where(models.CraigslistJob.user_id == user_id)
    elif conversation_id is not None:
        stmt = stmt.where(models.CraigslistJob.conversation_id == conversation_id)
    
    # Filter out expired cache entries unless requested
    if not include_expired:
        stmt = stmt.where(
            or_(
                models.CraigslistJob.expires_at == None,  # noqa: E711
                models.CraigslistJob.expires_at > datetime.utcnow()
            )
        )
    
    # Order by relevance or recency
    if order_by_relevance:
        stmt = stmt.order_by(
            models.CraigslistJob.relevance_score.desc().nullslast(),
            models.CraigslistJob.created_at.desc()
        )
    else:
        stmt = stmt.order_by(models.CraigslistJob.created_at.desc())
    
    stmt = stmt.limit(limit).offset(skip)
    
    return list(db.execute(stmt).scalars().all())


def search_craigslist_jobs(
    db: Session,
    query: str,
    user_id: Optional[int] = None,
    conversation_id: Optional[str] = None,
    limit: int = 50
) -> List[models.CraigslistJob]:
    """
    Search cached Craigslist jobs by text query.
    
    Args:
        db: Database session
        query: Search query string
        user_id: Optional user ID filter
        conversation_id: Optional conversation ID filter
        limit: Maximum number of results
    
    Returns:
        List of matching CraigslistJob instances
    """
    like = f"%{query}%"
    
    stmt = select(models.CraigslistJob).where(
        and_(
            models.CraigslistJob.is_active == True,  # noqa: E712
            or_(
                models.CraigslistJob.expires_at == None,  # noqa: E711
                models.CraigslistJob.expires_at > datetime.utcnow()
            ),
            or_(
                models.CraigslistJob.title.ilike(like),
                models.CraigslistJob.company.ilike(like),
                models.CraigslistJob.location.ilike(like),
                models.CraigslistJob.snippet.ilike(like)
            )
        )
    )
    
    if user_id is not None:
        stmt = stmt.where(models.CraigslistJob.user_id == user_id)
    elif conversation_id is not None:
        stmt = stmt.where(models.CraigslistJob.conversation_id == conversation_id)
    
    stmt = stmt.order_by(
        models.CraigslistJob.relevance_score.desc().nullslast(),
        models.CraigslistJob.created_at.desc()
    ).limit(limit)
    
    return list(db.execute(stmt).scalars().all())


def update_craigslist_job_status(
    db: Session,
    job_id: int,
    is_viewed: Optional[bool] = None,
    is_applied: Optional[bool] = None,
    is_active: Optional[bool] = None
) -> Optional[models.CraigslistJob]:
    """
    Update the status flags of a Craigslist job.
    
    Args:
        db: Database session
        job_id: Job ID
        is_viewed: Optional viewed status
        is_applied: Optional applied status
        is_active: Optional active status
    
    Returns:
        Updated CraigslistJob instance or None if not found
    """
    job = db.get(models.CraigslistJob, job_id)
    if not job:
        return None
    
    if is_viewed is not None:
        job.is_viewed = is_viewed
    if is_applied is not None:
        job.is_applied = is_applied
    if is_active is not None:
        job.is_active = is_active
    
    job.updated_at = datetime.utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)
    
    return job


def delete_expired_craigslist_jobs(db: Session) -> int:
    """
    Delete expired Craigslist job cache entries.
    
    Args:
        db: Database session
    
    Returns:
        Number of jobs deleted
    """
    stmt = select(models.CraigslistJob).where(
        and_(
            models.CraigslistJob.expires_at != None,  # noqa: E711
            models.CraigslistJob.expires_at <= datetime.utcnow()
        )
    )
    
    expired_jobs = db.execute(stmt).scalars().all()
    count = len(expired_jobs)
    
    for job in expired_jobs:
        db.delete(job)
    
    db.commit()
    return count


def clear_craigslist_jobs_for_conversation(
    db: Session,
    conversation_id: str
) -> int:
    """
    Clear all Craigslist jobs for a specific conversation.
    
    Args:
        db: Database session
        conversation_id: Conversation ID
    
    Returns:
        Number of jobs deleted
    """
    stmt = select(models.CraigslistJob).where(
        models.CraigslistJob.conversation_id == conversation_id
    )
    
    jobs = db.execute(stmt).scalars().all()
    count = len(jobs)
    
    for job in jobs:
        db.delete(job)
    
    db.commit()
    return count
