"""
USAJOBS AI Agent Interface

This module provides a simplified interface for AI agents to interact with the USAJOBS API.
It abstracts away the complexity of the API and provides simple functions for common tasks.
"""

from typing import Dict, List, Optional, Any
from .client import USAJobsClient, create_usajobs_client


class USAJobsAIAgent:
    """
    AI Agent interface for USAJOBS API.
    
    This class provides simplified methods for AI agents to search and retrieve job information.
    """
    
    def __init__(self):
        """Initialize the AI agent with a USAJobsClient."""
        self.client = create_usajobs_client()
    
    def search_jobs_by_keywords(
        self,
        keywords: str,
        location: Optional[str] = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for jobs by keywords.
        
        Args:
            keywords: Keywords to search for (e.g., "software engineer", "project manager")
            location: Optional location filter (e.g., "Washington, DC", "Remote")
            max_results: Maximum number of results to return
            
        Returns:
            List of job dictionaries with key information
        """
        return self.client.search_and_format_jobs(
            keyword=keywords,
            location=location,
            results_per_page=max_results
        )
    
    def search_jobs_by_category(
        self,
        job_category: str,
        location: Optional[str] = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for jobs by job category/series.
        
        Args:
            job_category: Job category code (e.g., "2210" for IT, "0343" for Management)
            location: Optional location filter
            max_results: Maximum number of results to return
            
        Returns:
            List of job dictionaries with key information
        """
        return self.client.search_and_format_jobs(
            job_series=job_category,
            location=location,
            results_per_page=max_results
        )
    
    def search_remote_jobs(
        self,
        keywords: Optional[str] = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for remote jobs.
        
        Args:
            keywords: Optional keywords to filter by
            max_results: Maximum number of results to return
            
        Returns:
            List of remote job dictionaries with key information
        """
        return self.client.search_and_format_jobs(
            keyword=keywords,
            location="Remote",
            results_per_page=max_results
        )
    
    def search_jobs_by_salary(
        self,
        min_salary: Optional[int] = None,
        max_salary: Optional[int] = None,
        keywords: Optional[str] = None,
        location: Optional[str] = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for jobs within a salary range.
        
        Args:
            min_salary: Minimum salary
            max_salary: Maximum salary
            keywords: Optional keywords to filter by
            location: Optional location filter
            max_results: Maximum number of results to return
            
        Returns:
            List of job dictionaries with key information
        """
        # Note: USAJOBS API doesn't directly support salary range filtering
        # We'll search by keywords/location and then filter the results
        jobs = self.client.search_and_format_jobs(
            keyword=keywords,
            location=location,
            results_per_page=max_results * 2  # Get more results to filter from
        )
        
        # Filter by salary range
        filtered_jobs = []
        for job in jobs:
            try:
                salary_min = int(job.get("salary_min", 0).replace("$", "").replace(",", ""))
                if (min_salary is None or salary_min >= min_salary) and \
                   (max_salary is None or salary_min <= max_salary):
                    filtered_jobs.append(job)
                    if len(filtered_jobs) >= max_results:
                        break
            except (ValueError, AttributeError):
                # Skip jobs with invalid salary information
                continue
        
        return filtered_jobs
    
    def get_job_categories(self) -> List[Dict[str, Any]]:
        """
        Get available job categories/series.
        
        Returns:
            List of job category dictionaries
        """
        return self.client.get_code_list("occupationalseries")
    
    def get_locations(self) -> List[Dict[str, Any]]:
        """
        Get available location codes.
        
        Returns:
            List of location dictionaries
        """
        return self.client.get_code_list("countries")
    
    def get_job_details(self, job_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific job.
        
        Args:
            job_id: The job ID to retrieve details for
            
        Returns:
            Dictionary containing detailed job information
        """
        return self.client.get_job_details(job_id)
    
    def summarize_job(self, job_data: Dict[str, Any]) -> str:
        """
        Create a human-readable summary of a job.
        
        Args:
            job_data: Job data dictionary
            
        Returns:
            Human-readable job summary
        """
        title = job_data.get("title", "Unknown Position")
        company = job_data.get("company", "Unknown Organization")
        location = job_data.get("location", "Unknown Location")
        description = job_data.get("description", "No description available")
        salary_min = job_data.get("salary_min", "")
        salary_max = job_data.get("salary_max", "")
        salary_interval = job_data.get("salary_interval", "")
        
        # Format salary information
        salary = ""
        if salary_min and salary_max:
            salary = f"Salary: ${salary_min} - ${salary_max} {salary_interval}"
        elif salary_min:
            salary = f"Salary: ${salary_min}+ {salary_interval}"
        
        # Create summary
        summary = f"**{title}** at {company} in {location}\n\n"
        if salary:
            summary += f"{salary}\n\n"
        
        # Truncate description if too long
        if len(description) > 500:
            description = description[:500] + "..."
        
        summary += f"Description: {description}\n\n"
        
        if job_data.get("url"):
            summary += f"Apply: {job_data.get('url')}"
        
        return summary


# Simple functions for AI agents to use
def search_jobs(keywords: str, location: Optional[str] = None, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Simple function to search for jobs.
    
    Args:
        keywords: Keywords to search for
        location: Optional location filter
        max_results: Maximum number of results to return
        
    Returns:
        List of job dictionaries
    """
    agent = USAJobsAIAgent()
    return agent.search_jobs_by_keywords(keywords, location, max_results)


def find_remote_jobs(keywords: Optional[str] = None, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Simple function to find remote jobs.
    
    Args:
        keywords: Optional keywords to filter by
        max_results: Maximum number of results to return
        
    Returns:
        List of remote job dictionaries
    """
    agent = USAJobsAIAgent()
    return agent.search_remote_jobs(keywords, max_results)


def get_job_summary(job_id: str) -> str:
    """
    Get a human-readable summary of a job.
    
    Args:
        job_id: The job ID to retrieve details for
        
    Returns:
        Human-readable job summary
    """
    agent = USAJobsAIAgent()
    job_details = agent.get_job_details(job_id)
    return agent.summarize_job(job_details)


if __name__ == "__main__":
    # Example usage
    try:
        agent = USAJobsAIAgent()
        
        # Search for IT jobs
        it_jobs = agent.search_jobs_by_keywords("IT", "Washington, DC", 5)
        print(f"Found {len(it_jobs)} IT jobs in Washington, DC")
        
        # Find remote jobs
        remote_jobs = agent.find_remote_jobs("project manager", 5)
        print(f"Found {len(remote_jobs)} remote project manager jobs")
        
        # Get job categories
        categories = agent.get_job_categories()
        print(f"Available job categories: {len(categories)}")
        
        # Get a job summary
        if it_jobs:
            job_id = it_jobs[0].get("job_id")
            if job_id:
                summary = get_job_summary(job_id)
                print(f"Job summary:\n{summary}")
        
    except Exception as e:
        print(f"Error: {e}")
