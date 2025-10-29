"""Job fetching tool with CrewAI BaseTool compatibility.

Falls back to a minimal shim if crewai isn't available or BaseTool moved.
"""
try:
    from crewai.tools import BaseTool  # older CrewAI
except Exception:  # pragma: no cover
    try:
        from crewai_tools import BaseTool  # some distributions expose this
    except Exception:
        class BaseTool:  # minimal shim for our usage
            name: str = "BaseTool"
            description: str = ""
            args_schema = None
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
            def run(self, **kwargs):
                return self._run(**kwargs)
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import re
from tools.craigslist_scraper import fetch_craigslist

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
        Fetch jobs from multiple sources based on intent criteria.
        Uses Craigslist (jobs + gigs + services fallbacks) via ScrapingBee.
        """
        try:
            raw_intent = json.loads(intent_json)

            # --- Craigslist via ScrapingBee (multi-category fallbacks) ---
            # NEW signature: returns (jobs, attempted_urls, hit_urls, errors)
            from tools.craigslist_scraper import fetch_craigslist
            cl_jobs, cl_attempted, cl_hits, cl_errors = fetch_craigslist(raw_intent)

            all_jobs = []
            fetch_results = {
                "successful_sources": [],
                "failed_sources": [],
                "total_jobs_found": 0,
                "craigslist_attempted": cl_attempted,  # all URLs we tried
                "craigslist_hits": cl_hits,            # URLs that yielded results
                "craigslist_errors": cl_errors,        # [{"url","error"}, ...]
            }

            # Map Craigslist results to your raw format for standardization
            if cl_jobs:
                fetch_results["successful_sources"].append("Craigslist")
                for j in cl_jobs:
                    all_jobs.append({
                        "title": j.get("title") or "N/A",
                        "company": j.get("company") or "N/A",
                        "location": j.get("location") or "N/A",
                        "description": j.get("snippet") or "",
                        "salary": "N/A",
                        "url": j.get("apply_url") or "",
                        "date_posted": j.get("posted_at") or "N/A",
                        "source": "Craigslist",
                        "source_url": j.get("source_url") or "",
                        "job_type": "N/A",
                    })
            else:
                fetch_results["failed_sources"].append("Craigslist")

            # ---- Standardize -> Filter -> Rank ----
            standardized_jobs = self._standardize_job_data(all_jobs)

            keywords = raw_intent.get("keywords", [])
            loc_obj = raw_intent.get("location", "")
            location = loc_obj.get("city") if isinstance(loc_obj, dict) else (loc_obj or "")
            salary_min = raw_intent.get("salary_min", 0)
            salary_max = raw_intent.get("salary_max", 999999)
            experience_level = raw_intent.get("experience_level", "")
            work_type = raw_intent.get("work_type") or []
            job_type = (work_type[0] if isinstance(work_type, list) and work_type else work_type) or ""
            remote_ok = (
                isinstance(loc_obj, dict) and (loc_obj.get("type", "").lower() == "remote")
            ) or (isinstance(loc_obj, str) and loc_obj.strip().lower() == "remote")

            filtered_jobs = self._filter_jobs(
                standardized_jobs, keywords, location, salary_min, salary_max,
                experience_level, job_type, remote_ok
            )
            ranked_jobs = self._rank_jobs(filtered_jobs, raw_intent)
            fetch_results["total_jobs_found"] = len(ranked_jobs)

            response = {
                "status": "success",
                "fetch_summary": fetch_results,
                "jobs_found": len(ranked_jobs),
                "jobs": ranked_jobs[:50],
                "search_criteria": {
                    "keywords": keywords,
                    "location": location,
                    "salary_range": f"${salary_min} - ${salary_max}",
                    "experience_level": experience_level,
                    "job_type": job_type,
                    "remote_ok": remote_ok,
                },
                "craigslist": {
                    "attempted": cl_attempted,
                    "hits": cl_hits,
                    "errors": cl_errors,
                },
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
    
    
    
    def _filter_jobs(self, jobs, keywords, location, salary_min, salary_max, experience_level, job_type, remote_ok):
        filtered = []
        for job in jobs:
            if keywords:
                title_desc = (job['title'] + ' ' + job['description']).lower()
                if not any(k.lower() in title_desc for k in keywords):
                    continue

            if location and location.lower() not in job['location'].lower() and not job['remote_ok']:
                continue

            job_salary = job['salary']
            if (
                job_salary['min'] > 0 and job_salary['max'] > 0 and
                not (salary_min <= job_salary['max'] and salary_max >= job_salary['min'])
            ):
                continue

            if experience_level and experience_level != job['experience_level'] and job['experience_level'] != 'unknown':
                continue

            if job_type and job_type.replace('_','-').lower() not in job['job_type'].lower():
                continue

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
