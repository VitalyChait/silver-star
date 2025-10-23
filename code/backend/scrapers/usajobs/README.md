# USAJOBS API Module

This module provides a client and AI agent interface for interacting with the USAJOBS API. It allows searching for federal job listings and retrieving job details.

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your environment variables:
```bash
export USAJOBS_API_KEY="your_api_key_here"
export USAJOBS_EMAIL="your_email@example.com"
```

To get an API key, visit [https://developer.usajobs.gov/](https://developer.usajobs.gov/) and register for an API key.

## Usage

### Basic Usage

```python
from scrapers.usajobs import search_jobs, find_remote_jobs

# Search for jobs by keywords
jobs = search_jobs("software engineer", "Washington, DC")
for job in jobs:
    print(f"{job['title']} at {job['company']} in {job['location']}")

# Find remote jobs
remote_jobs = find_remote_jobs("project manager")
for job in remote_jobs:
    print(f"{job['title']} - {job['url']}")
```

### Advanced Usage

```python
from scrapers.usajobs import USAJobsAIAgent

# Create an AI agent
agent = USAJobsAIAgent()

# Search for jobs by keywords
jobs = agent.search_jobs_by_keywords("IT", "Remote", max_results=20)

# Search for jobs by category
jobs = agent.search_jobs_by_category("2210", "New York")  # 2210 is IT series

# Search for jobs by salary range
jobs = agent.search_jobs_by_salary(min_salary=80000, keywords="manager")

# Get job categories
categories = agent.get_job_categories()

# Get a job summary
if jobs:
    job_id = jobs[0].get("job_id")
    summary = agent.summarize_job(jobs[0])
    print(summary)
```

### Direct API Usage

```python
from scrapers.usajobs import USAJobsClient

# Create a client
client = USAJobsClient(api_key="your_key", email="your_email")

# Search for jobs with advanced parameters
results = client.search_jobs(
    keyword="IT",
    location="Washington, DC",
    radius=25,
    pay_grade="GS-11,GS-12,GS-13",
    results_per_page=100
)

# Get job details
job_id = results["SearchResult"]["SearchResultItems"][0]["MatchedObjectDescriptor"]["PositionID"]
details = client.get_job_details(job_id)

# Format jobs for database storage
formatted_jobs = client.search_and_format_jobs(keyword="IT", location="Remote")
```

## API Reference

### USAJobsClient

The main client class for interacting with the USAJOBS API.

#### Methods

- `search_jobs(**kwargs)`: Search for jobs with various filters
- `get_job_details(job_id)`: Get detailed information about a specific job
- `get_historic_job_announcement(announcement_number)`: Get historic job announcement
- `get_code_list(code_type)`: Get a list of codes for a specific type
- `format_job_for_db(job_data)`: Format job data for database storage
- `search_and_format_jobs(**kwargs)`: Search for jobs and format them for database

### USAJobsAIAgent

A simplified interface for AI agents to interact with the USAJOBS API.

#### Methods

- `search_jobs_by_keywords(keywords, location=None, max_results=10)`: Search by keywords
- `search_jobs_by_category(job_category, location=None, max_results=10)`: Search by category
- `search_remote_jobs(keywords=None, max_results=10)`: Search for remote jobs
- `search_jobs_by_salary(min_salary=None, max_salary=None, **kwargs)`: Search by salary range
- `get_job_categories()`: Get available job categories
- `get_locations()`: Get available locations
- `get_job_details(job_id)`: Get job details
- `summarize_job(job_data)`: Create a human-readable job summary

### Simple Functions

- `search_jobs(keywords, location=None, max_results=10)`: Simple job search
- `find_remote_jobs(keywords=None, max_results=10)`: Find remote jobs
- `get_job_summary(job_id)`: Get a job summary

## Data Format

Jobs returned by the module have the following format:

```python
{
    "title": "Job Title",
    "company": "Organization Name",
    "location": "Location Name",
    "description": "Job Description",
    "job_type": "Full-Time",
    "url": "Application URL",
    "salary_min": "Minimum Salary",
    "salary_max": "Maximum Salary",
    "salary_interval": "Per Year",
    "posted_date": "2023-01-01",
    "closing_date": "2023-02-01",
    "job_id": "1234567",
    "announcement_number": "ABC-123-DEPT",
    "department": "Department Name",
    "who_may_apply": "Who May Apply",
    "requirements": "Requirements",
    "source": "USAJOBS",
    "created_at": "2023-01-01T12:00:00"
}
```

## Rate Limiting

The USAJOBS API has rate limits. Be mindful of how many requests you make in a short period. The module handles pagination automatically, but you should implement additional rate limiting if making many requests.

## Error Handling

The module will raise exceptions for:

- Missing API key or email
- API request failures
- Invalid job IDs

Make sure to wrap your code in try-except blocks to handle these errors gracefully.

## License

This module is part of the Silver Star project.
