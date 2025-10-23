"""
USAJOBS API Module

This module provides a client and AI agent interface for interacting with the USAJOBS API.
It allows searching for federal job listings and retrieving job details.

Usage:
    from scrapers.usajobs import USAJobsClient, USAJobsAIAgent, search_jobs
    
    # Use the client directly
    client = USAJobsClient(api_key="your_key", email="your_email")
    results = client.search_jobs(keyword="IT", location="Washington, DC")
    
    # Use the AI agent interface
    agent = USAJobsAIAgent()
    jobs = agent.search_jobs_by_keywords("software engineer", "Remote")
    
    # Use simple functions
    jobs = search_jobs("project manager", "New York")
"""

from .client import USAJobsClient, create_usajobs_client, search_jobs_for_ai
from .ai_interface import USAJobsAIAgent, search_jobs, find_remote_jobs, get_job_summary

__all__ = [
    "USAJobsClient",
    "create_usajobs_client",
    "search_jobs_for_ai",
    "USAJobsAIAgent",
    "search_jobs",
    "find_remote_jobs",
    "get_job_summary"
]
