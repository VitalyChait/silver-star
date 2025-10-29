import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..db import get_db
from ..deps import get_current_user

# Import scrapers
import sys
import os
from pathlib import Path

# Add scrapers directory to path
scrapers_path = Path(__file__).parent.parent.parent.parent / "scrapers"
sys.path.insert(0, str(scrapers_path))

try:
    from scrapers.usajobs.client import USAJobsClient
    USAJOBS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"USAJOBS scraper not available: {e}")
    USAJOBS_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/job-scraper", tags=["job-scraper"])


@router.post("/scrape-usajobs", status_code=status.HTTP_202_ACCEPTED)
async def scrape_usajobs(
    background_tasks: BackgroundTasks,
    keyword: Optional[str] = None,
    location: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Scrape jobs from USAJOBS and add them to the database.
    
    Args:
        keyword: Optional keyword to search for
        location: Optional location to search in
        limit: Maximum number of jobs to scrape
        db: Database session
        current_user: Current authenticated user (must be admin)
        
    Returns:
        Accepted response if scraping task is started
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can scrape jobs"
        )
    
    if not USAJOBS_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="USAJOBS scraper is not available"
        )
    
    # Add scraping task to background
    background_tasks.add_task(
        scrape_usajobs_background,
        keyword=keyword,
        location=location,
        limit=limit,
        db_url=str(db.bind.url)
    )
    
    return {"message": "Job scraping task started"}


async def scrape_usajobs_background(
    keyword: Optional[str],
    location: Optional[str],
    limit: int,
    db_url: str
):
    """
    Background task to scrape jobs from USAJOBS.
    
    Args:
        keyword: Optional keyword to search for
        location: Optional location to search in
        limit: Maximum number of jobs to scrape
        db_url: Database URL to connect to
    """
    try:
        # Create a new database session for this background task
        from ..db import engine, SessionLocal
        db = SessionLocal()
        
        # Initialize USAJOBS client
        client = USAJobsClient()
        
        # Search for jobs
        results = client.search_jobs(
            keyword=keyword,
            location=location,
            results_per_page=limit
        )
        
        jobs = results.get("SearchResult", {}).get("SearchResultItems", [])
        
        # Process each job
        added_count = 0
        for job_item in jobs:
            try:
                # Format job for database
                formatted_job = client.format_job_for_db(job_item)
                
                # Check if job already exists
                existing_job = db.query(models.Job).filter(
                    models.Job.title == formatted_job["title"],
                    models.Job.company == formatted_job["company"],
                    models.Job.location == formatted_job["location"]
                ).first()
                
                if not existing_job:
                    # Create new job
                    job_create = schemas.JobCreate(
                        title=formatted_job["title"],
                        company=formatted_job["company"],
                        location=formatted_job["location"],
                        description=formatted_job["description"],
                        job_type=formatted_job["job_type"],
                        url=formatted_job["url"]
                    )
                    
                    crud.create_job(db, owner_id=None, job_in=job_create)
                    added_count += 1
                    logger.info(f"[job_scraper.py] Added job: {formatted_job['title']} at {formatted_job['company']}")
            except Exception as e:
                logger.error(f"[job_scraper.py] Error processing job: {str(e)}")
                continue
        
        db.close()
        logger.info(f"[job_scraper.py] Scraping completed. Added {added_count} new jobs out of {len(jobs)} found.")
        
    except Exception as e:
        logger.error(f"[job_scraper.py] Error in background scraping task: {str(e)}")


@router.get("/scraping-status", response_model=Dict[str, Any])
def get_scraping_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Get the status of job scraping.
    
    Args:
        db: Database session
        current_user: Current authenticated user (must be admin)
        
    Returns:
        Dictionary with scraping status information
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view scraping status"
        )
    
    # Get job count
    job_count = db.query(models.Job).count()
    
    # Get recent jobs
    recent_jobs = db.query(models.Job).order_by(
        models.Job.created_at.desc()
    ).limit(5).all()
    
    recent_jobs_data = []
    for job in recent_jobs:
        recent_jobs_data.append({
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "created_at": job.created_at.isoformat() if job.created_at else None
        })
    
    return {
        "total_jobs": job_count,
        "recent_jobs": recent_jobs_data,
        "scrapers_available": {
            "usajobs": USAJOBS_AVAILABLE
        }
    }
