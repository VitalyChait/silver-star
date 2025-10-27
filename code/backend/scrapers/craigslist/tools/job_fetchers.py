from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import re

class JobSearchIntentInput(BaseModel):
    """Input schema for JobFetchers Tool."""
    intent_json: str = Field(
        ..., 
        description="JSON string containing job search intent with criteria like keywords, location, salary, experience level, etc."
    )

class JobFetchersTool(BaseTool):
    """Tool for fetching job listings from multiple sources including RSS feeds and job board APIs."""

    name: str = "JobFetchers"
    description: str = (
        "Fetches job listings from multiple sources (RSS feeds, job board APIs), "
        "standardizes the data format, filters and ranks results based on user intent criteria. "
        "Returns a comprehensive list of job opportunities with source metadata."
    )
    args_schema: Type[BaseModel] = JobSearchIntentInput

    def _run(self, intent_json: str) -> str:
        """
        Fetches jobs from multiple sources based on intent criteria.
        
        Note: For security reasons, this implementation focuses on:
        - RSS feed parsing using safe XML parsing
        - REST API calls to public job board APIs
        - Basic web requests (no complex scraping)
        
        Email processing and advanced web scraping are excluded for security.
        """
        try:
            # Parse the intent JSON
            intent_data = json.loads(intent_json)
            
            # Extract search criteria
            keywords = intent_data.get('keywords', [])
            location = intent_data.get('location', '')
            salary_min = intent_data.get('salary_min', 0)
            salary_max = intent_data.get('salary_max', 999999)
            experience_level = intent_data.get('experience_level', '')
            job_type = intent_data.get('job_type', '')  # full-time, part-time, contract
            remote_ok = intent_data.get('remote_ok', False)
            
            all_jobs = []
            fetch_results = {
                'successful_sources': [],
                'failed_sources': [],
                'total_jobs_found': 0
            }
            
            # 1. Fetch from RSS feeds
            rss_jobs, rss_success = self._fetch_from_rss_feeds(keywords, location)
            all_jobs.extend(rss_jobs)
            if rss_success:
                fetch_results['successful_sources'].append('RSS feeds')
            else:
                fetch_results['failed_sources'].append('RSS feeds')
            
            # 2. Fetch from job board APIs (simulated/demo endpoints)
            api_jobs, api_success = self._fetch_from_job_apis(keywords, location)
            all_jobs.extend(api_jobs)
            if api_success:
                fetch_results['successful_sources'].append('Job board APIs')
            else:
                fetch_results['failed_sources'].append('Job board APIs')
            
            # 3. Standardize job data format
            standardized_jobs = self._standardize_job_data(all_jobs)
            
            # 4. Filter and rank based on intent criteria
            filtered_jobs = self._filter_jobs(
                standardized_jobs, keywords, location, salary_min, 
                salary_max, experience_level, job_type, remote_ok
            )
            
            # 5. Rank results
            ranked_jobs = self._rank_jobs(filtered_jobs, intent_data)
            
            fetch_results['total_jobs_found'] = len(ranked_jobs)
            
            # Prepare final response
            response = {
                'status': 'success',
                'fetch_summary': fetch_results,
                'jobs_found': len(ranked_jobs),
                'jobs': ranked_jobs[:50],  # Limit to top 50 results
                'search_criteria': {
                    'keywords': keywords,
                    'location': location,
                    'salary_range': f"${salary_min} - ${salary_max}",
                    'experience_level': experience_level,
                    'job_type': job_type,
                    'remote_ok': remote_ok
                }
            }
            
            return json.dumps(response, indent=2)
            
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON format in intent_json: {str(e)}"
        except Exception as e:
            return f"Error fetching jobs: {str(e)}"
    
    def _fetch_from_rss_feeds(self, keywords: List[str], location: str) -> tuple:
        """Fetch jobs from RSS feeds (safe XML parsing only)."""
        try:
            jobs = []
            
            # Common job site RSS feeds (these are examples - real URLs would be used)
            rss_urls = [
                "https://example-jobs.com/rss/feed.xml",
                "https://sample-careers.com/jobs.rss"
            ]
            
            for url in rss_urls:
                try:
                    headers = {'User-Agent': 'JobFetchers/1.0'}
                    response = requests.get(url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        # Parse RSS XML safely
                        root = ET.fromstring(response.content)
                        
                        # Extract job items (RSS format)
                        for item in root.findall('.//item'):
                            title = item.find('title')
                            description = item.find('description')
                            link = item.find('link')
                            pub_date = item.find('pubDate')
                            
                            job = {
                                'title': title.text if title is not None else 'N/A',
                                'description': description.text if description is not None else 'N/A',
                                'url': link.text if link is not None else 'N/A',
                                'date_posted': pub_date.text if pub_date is not None else 'N/A',
                                'source': 'RSS Feed',
                                'source_url': url
                            }
                            
                            jobs.append(job)
                            
                except requests.RequestException:
                    # Skip failed RSS feeds, continue with others
                    continue
                except ET.ParseError:
                    # Skip feeds with invalid XML
                    continue
            
            return jobs, True
            
        except Exception:
            # Return empty list if RSS fetching fails entirely
            return [], False
    
    def _fetch_from_job_apis(self, keywords: List[str], location: str) -> tuple:
        """Fetch jobs from job board APIs (safe REST API calls only)."""
        try:
            jobs = []
            
            # Example API endpoints (these would be real job board APIs)
            # Note: Real implementation would require proper API keys and endpoints
            api_endpoints = [
                {
                    'name': 'Generic Jobs API',
                    'url': 'https://api.example-jobs.com/search',
                    'params': {
                        'q': ' '.join(keywords),
                        'location': location,
                        'limit': 25
                    }
                }
            ]
            
            for endpoint in api_endpoints:
                try:
                    headers = {
                        'User-Agent': 'JobFetchers/1.0',
                        'Content-Type': 'application/json'
                    }
                    
                    response = requests.get(
                        endpoint['url'], 
                        params=endpoint['params'],
                        headers=headers,
                        timeout=15
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Extract job data (format depends on API)
                        job_listings = data.get('jobs', data.get('results', []))
                        
                        for job_data in job_listings:
                            job = {
                                'title': job_data.get('title', 'N/A'),
                                'company': job_data.get('company', 'N/A'),
                                'location': job_data.get('location', 'N/A'),
                                'description': job_data.get('description', 'N/A'),
                                'salary': job_data.get('salary', 'N/A'),
                                'url': job_data.get('url', 'N/A'),
                                'date_posted': job_data.get('date_posted', 'N/A'),
                                'source': endpoint['name'],
                                'job_type': job_data.get('type', 'N/A')
                            }
                            
                            jobs.append(job)
                            
                except requests.RequestException:
                    # Skip failed API calls
                    continue
                except json.JSONDecodeError:
                    # Skip APIs returning invalid JSON
                    continue
            
            return jobs, True
            
        except Exception:
            return [], False
    
    def _standardize_job_data(self, jobs: List[Dict]) -> List[Dict]:
        """Standardize job data into consistent format."""
        standardized = []
        
        for job in jobs:
            # Create standardized job object
            standard_job = {
                'id': f"job_{len(standardized)}_{int(datetime.now().timestamp())}",
                'title': str(job.get('title', 'N/A')).strip(),
                'company': str(job.get('company', 'N/A')).strip(),
                'location': str(job.get('location', 'N/A')).strip(),
                'description': str(job.get('description', 'N/A')).strip(),
                'salary': self._standardize_salary(job.get('salary', 'N/A')),
                'job_type': str(job.get('job_type', 'N/A')).strip(),
                'experience_level': self._extract_experience_level(job.get('description', '')),
                'remote_ok': self._check_remote_friendly(job.get('description', '') + ' ' + job.get('title', '')),
                'url': str(job.get('url', 'N/A')).strip(),
                'date_posted': str(job.get('date_posted', 'N/A')).strip(),
                'source': str(job.get('source', 'Unknown')).strip(),
                'source_url': str(job.get('source_url', 'N/A')).strip()
            }
            
            standardized.append(standard_job)
        
        return standardized
    
    def _standardize_salary(self, salary_text: str) -> Dict:
        """Extract and standardize salary information."""
        salary_info = {
            'raw': str(salary_text),
            'min': 0,
            'max': 0,
            'currency': 'USD',
            'period': 'yearly'
        }
        
        if salary_text and salary_text != 'N/A':
            # Simple salary extraction (basic regex)
            numbers = re.findall(r'\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', str(salary_text))
            
            if numbers:
                try:
                    # Convert to integers, removing commas
                    nums = [int(num.replace(',', '').split('.')[0]) for num in numbers]
                    if len(nums) == 1:
                        salary_info['min'] = nums[0]
                        salary_info['max'] = nums[0]
                    elif len(nums) >= 2:
                        salary_info['min'] = min(nums)
                        salary_info['max'] = max(nums)
                except ValueError:
                    pass
        
        return salary_info
    
    def _extract_experience_level(self, description: str) -> str:
        """Extract experience level from job description."""
        desc_lower = description.lower()
        
        if any(word in desc_lower for word in ['entry', 'junior', 'graduate', 'new grad']):
            return 'entry'
        elif any(word in desc_lower for word in ['senior', 'lead', 'principal', 'architect']):
            return 'senior'
        elif any(word in desc_lower for word in ['mid', 'intermediate', '3-5 years', '2-4 years']):
            return 'mid'
        else:
            return 'unknown'
    
    def _check_remote_friendly(self, text: str) -> bool:
        """Check if job mentions remote work."""
        text_lower = text.lower()
        remote_keywords = ['remote', 'work from home', 'telecommute', 'distributed', 'wfh']
        return any(keyword in text_lower for keyword in remote_keywords)
    
    def _filter_jobs(self, jobs: List[Dict], keywords: List[str], location: str, 
                     salary_min: int, salary_max: int, experience_level: str, 
                     job_type: str, remote_ok: bool) -> List[Dict]:
        """Filter jobs based on user criteria."""
        filtered = []
        
        for job in jobs:
            # Keyword matching
            if keywords:
                title_desc = (job['title'] + ' ' + job['description']).lower()
                if not any(keyword.lower() in title_desc for keyword in keywords):
                    continue
            
            # Location filtering
            if location and location.lower() not in job['location'].lower() and not job['remote_ok']:
                continue
            
            # Salary filtering
            job_salary = job['salary']
            if (job_salary['min'] > 0 and job_salary['max'] > 0 and 
                not (salary_min <= job_salary['max'] and salary_max >= job_salary['min'])):
                continue
            
            # Experience level filtering
            if experience_level and experience_level != job['experience_level'] and job['experience_level'] != 'unknown':
                continue
            
            # Job type filtering
            if job_type and job_type.lower() not in job['job_type'].lower():
                continue
            
            # Remote work filtering
            if remote_ok and not job['remote_ok']:
                continue
            
            filtered.append(job)
        
        return filtered
    
    def _rank_jobs(self, jobs: List[Dict], intent_data: Dict) -> List[Dict]:
        """Rank jobs based on relevance to user intent."""
        keywords = intent_data.get('keywords', [])
        
        def calculate_score(job):
            score = 0
            
            # Keyword relevance in title (higher weight)
            title_lower = job['title'].lower()
            for keyword in keywords:
                if keyword.lower() in title_lower:
                    score += 10
            
            # Keyword relevance in description
            desc_lower = job['description'].lower()
            for keyword in keywords:
                if keyword.lower() in desc_lower:
                    score += 3
            
            # Boost for complete salary information
            if job['salary']['min'] > 0:
                score += 2
            
            # Boost for remote-friendly if requested
            if intent_data.get('remote_ok', False) and job['remote_ok']:
                score += 5
            
            # Experience level match
            if intent_data.get('experience_level') == job['experience_level']:
                score += 8
            
            return score
        
        # Sort by score (descending)
        ranked_jobs = sorted(jobs, key=calculate_score, reverse=True)
        
        # Add ranking score to each job
        for i, job in enumerate(ranked_jobs):
            job['relevance_score'] = calculate_score(job)
            job['rank'] = i + 1
        
        return ranked_jobs