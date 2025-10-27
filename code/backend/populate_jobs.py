#!/usr/bin/env python3
"""
Script to populate the database with sample jobs for testing.
"""

import sys
import os
from pathlib import Path

# Add the app directory to the Python path
app_dir = Path(__file__).parent
sys.path.insert(0, str(app_dir))

from app.db import engine, SessionLocal
from app import crud, models, schemas

# Sample job data
SAMPLE_JOBS = [
    {
        "title": "Part-Time Accountant",
        "company": "Fintech Solutions Inc.",
        "location": "Remote",
        "description": "Manage ledgers and assist with quarterly reports. Flexible 15-20 hrs/week. Experience with QuickBooks required.",
        "job_type": "Part-time",
        "url": "https://example.com/job1"
    },
    {
        "title": "Community Liaison",
        "company": "Wellesley Public Library",
        "location": "Wellesley, MA",
        "description": "Organize and promote adult learning programs. Strong communication skills valued. Experience in community outreach preferred.",
        "job_type": "Part-time",
        "url": "https://example.com/job2"
    },
    {
        "title": "Senior Admin Assistant",
        "company": "Local Health Clinic",
        "location": "Boston, MA",
        "description": "Support clinic operations, scheduling, and patient intake. 3 days a week. Medical office experience helpful.",
        "job_type": "Part-time",
        "url": "https://example.com/job3"
    },
    {
        "title": "Software Developer",
        "company": "Tech Innovations LLC",
        "location": "Remote",
        "description": "Develop web applications using React and Node.js. 5+ years of experience required. Competitive salary and benefits.",
        "job_type": "Full-time",
        "url": "https://example.com/job4"
    },
    {
        "title": "Marketing Coordinator",
        "company": "Creative Agency",
        "location": "New York, NY",
        "description": "Coordinate marketing campaigns and manage social media presence. Experience with digital marketing tools required.",
        "job_type": "Full-time",
        "url": "https://example.com/job5"
    }
]

def main():
    """Populate the database with sample jobs."""
    print("Populating database with sample jobs...")
    
    # Create a database session
    db = SessionLocal()
    
    try:
        # Create tables if they don't exist
        from app.db import engine, Base
        Base.metadata.create_all(bind=engine)
        print("Database tables created")
        
        # Check if jobs already exist
        existing_count = db.query(models.Job).count()
        if existing_count > 0:
            print(f"Database already contains {existing_count} jobs. Skipping population.")
            return
        
        # Add sample jobs
        for job_data in SAMPLE_JOBS:
            job_create = schemas.JobCreate(**job_data)
            job = crud.create_job(db, owner_id=None, job_in=job_create)
            print(f"Added job: {job.title} at {job.company}")
        
        print(f"Successfully added {len(SAMPLE_JOBS)} sample jobs to the database.")
    except Exception as e:
        print(f"Error populating database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
