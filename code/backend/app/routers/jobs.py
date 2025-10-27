from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import schemas, crud, models
from ..db import get_db
from ..deps import get_current_user


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/", response_model=list[schemas.JobPublic])
def list_jobs(
    q: Optional[str] = Query(None, description="Keyword search"),
    limit: int = 50,
    skip: int = 0,
    db: Session = Depends(get_db),
):
    return crud.list_jobs(db, q=q, limit=limit, skip=skip)


@router.post("/", response_model=schemas.JobPublic, status_code=status.HTTP_201_CREATED)
def create_job(
    job_in: schemas.JobCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return crud.create_job(db, owner_id=user.id, job_in=job_in)


@router.get("/{job_id}", response_model=schemas.JobPublic)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.patch("/{job_id}", response_model=schemas.JobPublic)
def update_job(
    job_id: int,
    job_in: schemas.JobUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    job = crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.owner_id and job.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return crud.update_job(db, job, job_in)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    job = crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.owner_id and job.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    crud.delete_job(db, job)
    return None
