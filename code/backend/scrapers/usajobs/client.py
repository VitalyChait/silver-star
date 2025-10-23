"""
USAJOBS API Client Module

This module provides a client for interacting with the USAJOBS API to search and retrieve job listings.
It's designed to be accessible by AI agents for job searching functionality.

API Documentation: https://developer.usajobs.gov/
"""

import os
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
import json


class USAJobsClient:
    """
    Client for interacting with the USAJOBS API.
    
    This class provides methods to search for jobs, retrieve job details,
    and access various USAJOBS API endpoints.
    """
    
    BASE_URL = "https://data.usajobs.gov/api"
    
    def __init__(self, api_key: Optional[str] = None, email: Optional[str] = None):
        """
        Initialize the USAJOBS API client.
        
        Args:
            api_key: Your USAJOBS API key. If not provided, will try to get from USAJOBS_API_KEY env variable.
            email: Your email associated with the API key. If not provided, will try to get from USAJOBS_EMAIL env variable.
        """
        self.api_key = api_key or os.environ.get("USAJOBS_API_KEY")
        self.email = email or os.environ.get("USAJOBS_EMAIL")
        
        if not self.api_key:
            raise ValueError("API key is required. Provide it directly or set USAJOBS_API_KEY environment variable.")
        
        if not self.email:
            raise ValueError("Email is required. Provide it directly or set USAJOBS_EMAIL environment variable.")
        
        self.headers = {
            "Authorization-Key": self.api_key,
            "User-Agent": f"SilverStar-JobBoard/1.0 ({self.email})",
            "Host": "data.usajobs.gov"
        }
    
    def search_jobs(
        self,
        keyword: Optional[str] = None,
        location: Optional[str] = None,
        radius: Optional[int] = None,
        hiring_path: Optional[str] = None,
        pay_grade: Optional[str] = None,
        job_series: Optional[str] = None,
        organization: Optional[str] = None,
        position_offering_type: Optional[str] = None,
        travel_percentage: Optional[int] = None,
        security_clearance: Optional[str] = None,
        page: int = 1,
        results_per_page: int = 50
    ) -> Dict[str, Any]:
        """
        Search for jobs using the USAJOBS API.
        
        Args:
            keyword: Keywords to search for in job titles and descriptions
            location: City, state, or ZIP code
            radius: Search radius in miles (if location is provided)
            hiring_path: Hiring path (e.g., "public", "student", "veterans")
            pay_grade: Pay grade (e.g., "GS-9", "GS-11")
            job_series: Job series code (e.g., "2210" for IT)
            organization: Organization code (e.g., "AF" for Air Force)
            position_offering_type: Position offering type (e.g., "FT" for full-time)
            travel_percentage: Required travel percentage
            security_clearance: Security clearance required
            page: Page number for pagination
            results_per_page: Number of results per page (max 500)
            
        Returns:
            Dictionary containing job search results
        """
        endpoint = f"{self.BASE_URL}/Search"
        params = {"Page": page, "ResultsPerPage": min(results_per_page, 500)}
        
        if keyword:
            params["Keyword"] = keyword
        if location:
            params["LocationName"] = location
        if radius:
            params["Radius"] = radius
        if hiring_path:
            params["HiringPath"] = hiring_path
        if pay_grade:
            params["PayGrade"] = pay_grade
        if job_series:
            params["JobCategoryCode"] = job_series
        if organization:
            params["Organization"] = organization
        if position_offering_type:
            params["PositionOfferingTypeCode"] = position_offering_type
        if travel_percentage:
            params["TravelPercentage"] = travel_percentage
        if security_clearance:
            params["SecurityClearanceRequired"] = security_clearance
            
        response = requests.get(endpoint, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_job_details(self, job_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific job.
        
        Args:
            job_id: The job ID to retrieve details for
            
        Returns:
            Dictionary containing detailed job information
        """
        endpoint = f"{self.BASE_URL}/Job/{job_id}"
        response = requests.get(endpoint, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_historic_job_announcement(self, announcement_number: str) -> Dict[str, Any]:
        """
        Get information about a historic job announcement.
        
        Args:
            announcement_number: The announcement number to retrieve
            
        Returns:
            Dictionary containing historic job announcement information
        """
        endpoint = f"{self.BASE_URL}/api/HistoricJoa"
        params = {"AnnouncementNumber": announcement_number}
        response = requests.get(endpoint, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_code_list(self, code_type: str) -> List[Dict[str, Any]]:
        """
        Get a list of codes for a specific type (e.g., countries, job series, etc.).
        
        Args:
            code_type: The type of code list to retrieve
            
        Returns:
            List of dictionaries containing code information
        """
        endpoint = f"{self.BASE_URL}/codelist/{code_type}"
        response = requests.get(endpoint, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def format_job_for_db(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format job data from USAJOBS API for database storage.
        
        Args:
            job_data: Raw job data from USAJOBS API
            
        Returns:
            Formatted job data ready for database insertion
        """
        # Extract the relevant fields from the job data
        job = job_data.get("MatchedObjectDescriptor", {})
        
        # Format the job data for our database
        formatted_job = {
            "title": job.get("PositionTitle", ""),
            "company": job.get("OrganizationName", ""),
            "location": job.get("PositionLocation", [{}])[0].get("LocationName", ""),
            "description": job.get("UserArea", {}).get("Details", {}).get("MajorDuties", ""),
            "job_type": job.get("PositionSchedule", [{}])[0].get("Name", ""),
            "url": job.get("ApplyURI", [None])[0],
            "salary_min": job.get("PositionRemuneration", [{}])[0].get("MinimumRange", ""),
            "salary_max": job.get("PositionRemuneration", [{}])[0].get("MaximumRange", ""),
            "salary_interval": job.get("PositionRemuneration", [{}])[0].get("RateIntervalCode", ""),
            "posted_date": job.get("PublicationStartDate", ""),
            "closing_date": job.get("ApplicationCloseDate", ""),
            "job_id": job.get("PositionID", ""),
            "announcement_number": job.get("PositionURI", "").split("/")[-1] if job.get("PositionURI") else "",
            "department": job.get("DepartmentName", ""),
            "who_may_apply": job.get("UserArea", {}).get("Details", {}).get("WhoMayApply", {}).get("Value", ""),
            "requirements": job.get("QualificationSummary", ""),
            "source": "USAJOBS",
            "created_at": datetime.now().isoformat()
        }
        
        return formatted_job
    
    def search_and_format_jobs(
        self,
        keyword: Optional[str] = None,
        location: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search for jobs and format them for database storage.
        
        Args:
            keyword: Keywords to search for
            location: Location to search in
            **kwargs: Additional search parameters
            
        Returns:
            List of formatted job data ready for database insertion
        """
        search_results = self.search_jobs(keyword=keyword, location=location, **kwargs)
        jobs = search_results.get("SearchResult", {}).get("SearchResultItems", [])
        
        formatted_jobs = []
        for job_item in jobs:
            formatted_job = self.format_job_for_db(job_item)
            formatted_jobs.append(formatted_job)
            
        return formatted_jobs


# AI Agent Helper Functions
def create_usajobs_client() -> USAJobsClient:
    """
    Create a USAJobsClient instance using environment variables.
    
    Returns:
        USAJobsClient instance
    """
    return USAJobsClient()


def search_jobs_for_ai(
    query: str,
    location: Optional[str] = None,
    max_results: int = 10
) -> List[Dict[str, Any]]:
    """
    AI-friendly function to search for jobs.
    
    Args:
        query: Search query for jobs
        location: Optional location filter
        max_results: Maximum number of results to return
        
    Returns:
        List of job dictionaries with key information
    """
    client = create_usajobs_client()
    results = client.search_jobs(keyword=query, location=location, results_per_page=max_results)
    
    jobs = []
    for item in results.get("SearchResult", {}).get("SearchResultItems", []):
        job = item.get("MatchedObjectDescriptor", {})
        
        # Extract only the most relevant information for AI processing
        job_summary = {
            "id": job.get("PositionID", ""),
            "title": job.get("PositionTitle", ""),
            "company": job.get("OrganizationName", ""),
            "location": job.get("PositionLocation", [{}])[0].get("LocationName", ""),
            "description": job.get("QualificationSummary", ""),
            "url": job.get("ApplyURI", [None])[0],
            "salary": f"${job.get('PositionRemuneration', [{}])[0].get('MinimumRange', '')} - ${job.get('PositionRemuneration', [{}])[0].get('MaximumRange', '')}",
            "posted_date": job.get("PublicationStartDate", ""),
            "closing_date": job.get("ApplicationCloseDate", "")
        }
        
        jobs.append(job_summary)
    
    return jobs


if __name__ == "__main__":
    # Example usage
    try:
        client = USAJobsClient()
        
        # Search for IT jobs in Washington, DC
        results = client.search_jobs(keyword="IT", location="Washington, DC")
        print(f"Found {len(results.get('SearchResult', {}).get('SearchResultItems', []))} jobs")
        
        # Format jobs for database
        formatted_jobs = client.search_and_format_jobs(keyword="IT", location="Washington, DC")
        print(f"Formatted {len(formatted_jobs)} jobs for database")
        
        # AI-friendly search
        ai_jobs = search_jobs_for_ai("software engineer", "Remote")
        print(f"AI found {len(ai_jobs)} software engineer jobs")
        
    except Exception as e:
        print(f"Error: {e}")
