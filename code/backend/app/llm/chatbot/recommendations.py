import json
import logging
import sys
from typing import Dict, List, Any, Optional

from sqlalchemy.orm import Session

# Import the main app modules directly
try:
    from app import crud, models
except ImportError as e:
    print(f"Error importing server modules: {e}", file=sys.stderr)
    sys.exit(1)

from ..core.service import llm_service

logger = logging.getLogger(__name__)


class JobRecommendationService:
    """Service for generating job recommendations based on candidate information."""
    
    def __init__(self):
        """Initialize the job recommendation service."""
        pass
    
    async def get_recommendations(
        self, 
        candidate_info: Dict[str, Any], 
        db: Session,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get job recommendations for a candidate based on their information.
        
        Args:
            candidate_info: Dictionary containing candidate information
            db: Database session
            limit: Maximum number of recommendations to return
            
        Returns:
            List of job recommendations with match scores
        """
        try:
            # Get all active jobs from the database
            jobs = crud.list_jobs(db, limit=100)  # Get more jobs to have a good selection
            
            if not jobs:
                return []
            
            # Convert jobs to dictionaries for LLM processing
            job_dicts = []
            for job in jobs:
                job_dicts.append({
                    "id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "description": job.description,
                    "job_type": job.job_type,
                    "url": job.url
                })
            
            # Generate recommendations using LLM
            recommendations = await self._generate_recommendations_with_llm(
                candidate_info, job_dicts, limit
            )
            
            return recommendations
        except Exception as e:
            logger.error(f"Error generating job recommendations: {str(e)}")
            return []
    
    async def _generate_recommendations_with_llm(
        self, 
        candidate_info: Dict[str, Any], 
        jobs: List[Dict[str, Any]], 
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Generate job recommendations using the LLM.
        
        Args:
            candidate_info: Dictionary containing candidate information
            jobs: List of job dictionaries
            limit: Maximum number of recommendations to return
            
        Returns:
            List of job recommendations with match scores
        """
        # Create a prompt for the LLM
        candidate_summary = json.dumps(candidate_info, indent=2)
        jobs_summary = json.dumps(jobs, indent=2)
        
        prompt = f"""
        You are an expert job recruiter. Based on the following candidate information, 
        recommend the most suitable jobs from the list provided.
        
        Candidate Information:
        {candidate_summary}
        
        Available Jobs:
        {jobs_summary}
        
        Please analyze the candidate's skills, location, what they're looking for, and availability
        to determine which jobs would be the best match.
        
        Return your response as a JSON array of job recommendations. Each recommendation should include:
        1. job_id: The ID of the job
        2. match_score: A score from 0-100 indicating how well the job matches the candidate
        3. match_reason: A brief explanation of why this job is a good match
        
        Only recommend jobs that are genuinely relevant to the candidate. 
        Return at most {limit} recommendations.
        
        Response format:
        [
            {{
                "job_id": 1,
                "match_score": 85,
                "match_reason": "This job matches the candidate's skills in X and is located in Y"
            }},
            ...
        ]
        """
        
        try:
            response = await llm_service.generate_response(
                prompt, 
                temperature=0.3,  # Lower temperature for more consistent recommendations
                max_output_tokens=2048
            )
            
            # Parse the JSON response
            recommendations = json.loads(response)
            
            # Ensure we have a list
            if not isinstance(recommendations, list):
                logger.error("LLM response is not a list")
                return []
            
            # Limit the number of recommendations
            return recommendations[:limit]
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
            logger.error(f"LLM response: {response}")
            return []
        except Exception as e:
            logger.error(f"Error generating recommendations with LLM: {str(e)}")
            return []
    
    async def get_job_details_for_recommendation(
        self, 
        job_id: int, 
        db: Session
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific job for recommendation purposes.
        
        Args:
            job_id: ID of the job
            db: Database session
            
        Returns:
            Dictionary with job details or None if not found
        """
        try:
            job = crud.get_job(db, job_id)
            if not job:
                return None
            
            return {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "description": job.description,
                "job_type": job.job_type,
                "url": job.url,
                "created_at": job.created_at.isoformat() if job.created_at else None
            }
        except Exception as e:
            logger.error(f"Error getting job details: {str(e)}")
            return None


# Create a singleton instance
job_recommendation_service = JobRecommendationService()
