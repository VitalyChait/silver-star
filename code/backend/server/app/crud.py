from sqlalchemy.orm import Session
from sqlalchemy import select

from . import models, schemas
from .security import get_password_hash


# Users
def get_user_by_email(db: Session, email: str) -> models.User | None:
    stmt = select(models.User).where(models.User.email == email)
    return db.execute(stmt).scalars().first()


def create_user(db: Session, user_in: schemas.UserCreate) -> models.User:
    user = models.User(
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
