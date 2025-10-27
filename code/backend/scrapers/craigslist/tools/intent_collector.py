from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import json

class IntentCollectorInput(BaseModel):
    """Input schema for Intent Collector Tool."""
    user_responses: str = Field(
        ..., 
        description="User responses to job search preference questions, separated by semicolons or as a conversation flow"
    )

class IntentCollectorTool(BaseTool):
    """Tool for collecting job search preferences and building structured intent JSON."""

    name: str = "Intent Collector"
    description: str = (
        "Guides users through collecting job search preferences including location, "
        "job categories, experience level, work arrangement, salary expectations, and "
        "other requirements. Returns a comprehensive structured JSON object."
    )
    args_schema: Type[BaseModel] = IntentCollectorInput

    def _run(self, user_responses: str) -> str:
        """
        Collect and structure job search preferences from user responses.
        
        Args:
            user_responses: User's answers to job search questions
            
        Returns:
            JSON string with structured job search intent
        """
        try:
            # Initialize the intent structure
            intent = {
                "job_search_preferences": {
                    "location": {
                        "preferred_locations": [],
                        "location_flexibility": "",
                        "willing_to_relocate": None
                    },
                    "job_criteria": {
                        "job_categories": [],
                        "job_titles": [],
                        "industry_preferences": [],
                        "company_size_preference": ""
                    },
                    "experience_and_level": {
                        "experience_level": "",
                        "years_of_experience": "",
                        "seniority_level": "",
                        "leadership_experience": None
                    },
                    "work_arrangement": {
                        "preferred_arrangement": "",
                        "remote_flexibility": "",
                        "travel_willingness": ""
                    },
                    "compensation": {
                        "salary_range_min": "",
                        "salary_range_max": "",
                        "currency": "USD",
                        "negotiable": None,
                        "benefits_priorities": []
                    },
                    "senior_specific_needs": {
                        "management_responsibilities": None,
                        "team_size_preference": "",
                        "strategic_vs_tactical_preference": "",
                        "mentorship_opportunities": None,
                        "growth_opportunities": []
                    },
                    "additional_preferences": {
                        "company_culture_priorities": [],
                        "work_life_balance_importance": "",
                        "learning_development_priorities": [],
                        "deal_breakers": [],
                        "must_haves": []
                    }
                },
                "collection_metadata": {
                    "completion_status": "incomplete",
                    "missing_fields": [],
                    "confidence_level": "medium"
                }
            }

            # Process user responses
            responses = self._parse_responses(user_responses)
            
            # Extract information from responses
            self._extract_location_info(responses, intent)
            self._extract_job_criteria(responses, intent)
            self._extract_experience_info(responses, intent)
            self._extract_work_arrangement(responses, intent)
            self._extract_compensation(responses, intent)
            self._extract_senior_needs(responses, intent)
            self._extract_additional_preferences(responses, intent)
            
            # Validate and update completion status
            self._validate_completeness(intent)
            
            return json.dumps(intent, indent=2)
            
        except Exception as e:
            return f"Error processing job search preferences: {str(e)}"

    def _parse_responses(self, user_responses: str) -> Dict[str, str]:
        """Parse user responses into a structured format."""
        responses = {}
        
        # Split by common delimiters
        parts = user_responses.replace(';', '\n').replace('|', '\n').split('\n')
        
        # Common question keywords and their mappings
        question_mapping = {
            'location': ['location', 'where', 'city', 'state', 'country', 'area'],
            'job_category': ['category', 'type', 'role', 'position', 'job'],
            'experience': ['experience', 'years', 'level', 'seniority'],
            'arrangement': ['remote', 'hybrid', 'office', 'onsite', 'work arrangement'],
            'salary': ['salary', 'compensation', 'pay', 'money', 'budget'],
            'management': ['manage', 'lead', 'team', 'supervise', 'direct'],
            'company': ['company', 'organization', 'culture', 'size'],
            'benefits': ['benefits', 'perks', 'insurance', 'vacation'],
            'industry': ['industry', 'sector', 'field', 'domain']
        }
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            # Try to categorize the response
            for category, keywords in question_mapping.items():
                if any(keyword in part.lower() for keyword in keywords):
                    if category not in responses:
                        responses[category] = []
                    responses[category].append(part)
        
        # Also store raw responses
        responses['raw'] = user_responses
        
        return responses

    def _extract_location_info(self, responses: Dict, intent: Dict):
        """Extract location preferences from responses."""
        if 'location' in responses:
            for response in responses['location']:
                # Extract cities, states, countries
                location_text = response.lower()
                if 'remote' in location_text or 'anywhere' in location_text:
                    intent['job_search_preferences']['location']['location_flexibility'] = 'fully_flexible'
                elif 'hybrid' in location_text:
                    intent['job_search_preferences']['location']['location_flexibility'] = 'hybrid_flexible'
                else:
                    # Extract specific locations
                    locations = self._extract_locations_from_text(response)
                    intent['job_search_preferences']['location']['preferred_locations'].extend(locations)

    def _extract_job_criteria(self, responses: Dict, intent: Dict):
        """Extract job criteria from responses."""
        if 'job_category' in responses:
            for response in responses['job_category']:
                categories = self._extract_job_categories(response)
                intent['job_search_preferences']['job_criteria']['job_categories'].extend(categories)
                
        if 'industry' in responses:
            for response in responses['industry']:
                industries = self._extract_industries(response)
                intent['job_search_preferences']['job_criteria']['industry_preferences'].extend(industries)

    def _extract_experience_info(self, responses: Dict, intent: Dict):
        """Extract experience information from responses."""
        if 'experience' in responses:
            for response in responses['experience']:
                exp_info = self._parse_experience(response)
                intent['job_search_preferences']['experience_and_level'].update(exp_info)

    def _extract_work_arrangement(self, responses: Dict, intent: Dict):
        """Extract work arrangement preferences."""
        if 'arrangement' in responses:
            for response in responses['arrangement']:
                arrangement = self._parse_work_arrangement(response)
                intent['job_search_preferences']['work_arrangement'].update(arrangement)

    def _extract_compensation(self, responses: Dict, intent: Dict):
        """Extract compensation information."""
        if 'salary' in responses:
            for response in responses['salary']:
                comp_info = self._parse_compensation(response)
                intent['job_search_preferences']['compensation'].update(comp_info)

    def _extract_senior_needs(self, responses: Dict, intent: Dict):
        """Extract senior-specific needs."""
        if 'management' in responses:
            for response in responses['management']:
                mgmt_info = self._parse_management_preferences(response)
                intent['job_search_preferences']['senior_specific_needs'].update(mgmt_info)

    def _extract_additional_preferences(self, responses: Dict, intent: Dict):
        """Extract additional preferences."""
        if 'company' in responses:
            for response in responses['company']:
                company_prefs = self._parse_company_preferences(response)
                intent['job_search_preferences']['additional_preferences'].update(company_prefs)

    def _extract_locations_from_text(self, text: str) -> List[str]:
        """Extract location names from text."""
        # Simple extraction - in practice, you might use more sophisticated NLP
        locations = []
        text_lower = text.lower()
        
        # Common location patterns
        if 'san francisco' in text_lower or 'sf' in text_lower:
            locations.append('San Francisco, CA')
        if 'new york' in text_lower or 'nyc' in text_lower:
            locations.append('New York, NY')
        if 'seattle' in text_lower:
            locations.append('Seattle, WA')
        if 'austin' in text_lower:
            locations.append('Austin, TX')
        if 'denver' in text_lower:
            locations.append('Denver, CO')
        if 'chicago' in text_lower:
            locations.append('Chicago, IL')
        if 'boston' in text_lower:
            locations.append('Boston, MA')
        if 'los angeles' in text_lower or 'la' in text_lower:
            locations.append('Los Angeles, CA')
            
        return locations

    def _extract_job_categories(self, text: str) -> List[str]:
        """Extract job categories from text."""
        categories = []
        text_lower = text.lower()
        
        category_keywords = {
            'Software Engineering': ['software', 'developer', 'programming', 'coding', 'backend', 'frontend', 'fullstack'],
            'Data Science': ['data scientist', 'data analysis', 'machine learning', 'ai', 'analytics'],
            'Product Management': ['product manager', 'product', 'pm', 'product management'],
            'Engineering Management': ['engineering manager', 'tech lead', 'team lead', 'engineering leadership'],
            'DevOps': ['devops', 'infrastructure', 'sre', 'platform', 'cloud'],
            'Design': ['designer', 'ux', 'ui', 'user experience', 'user interface'],
            'Marketing': ['marketing', 'growth', 'digital marketing', 'content'],
            'Sales': ['sales', 'business development', 'account management'],
            'Consulting': ['consultant', 'consulting', 'advisory'],
            'Teaching': ['teacher', 'professor', 'tutor','educator'],
            'Coaching': ['coach', 'sports coach', 'trainer','life coach']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                categories.append(category)
        print(f"categores {categories}")
        return categories

    def _extract_industries(self, text: str) -> List[str]:
        """Extract industries from text."""
        industries = []
        text_lower = text.lower()
        
        industry_keywords = {
            'Technology': ['tech', 'technology', 'software', 'saas', 'startup'],
            'Finance': ['finance', 'fintech', 'banking', 'investment'],
            'Healthcare': ['healthcare', 'medical', 'biotech', 'pharma'],
            'E-commerce': ['ecommerce', 'retail', 'marketplace'],
            'Education': ['education', 'edtech', 'learning','teaching','lecturing','tutoring'],
            'Media': ['media', 'entertainment', 'publishing','writing'],
            'Consulting': ['consulting', 'professional services']
        }
        
        for industry, keywords in industry_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                industries.append(industry)
                
        return industries

    def _parse_experience(self, text: str) -> Dict[str, Any]:
        """Parse experience information from text."""
        exp_info = {}
        text_lower = text.lower()
        
        # Extract years of experience
        import re
        years_match = re.search(r'(\d+)\s*(?:years?|yrs?)', text_lower)
        if years_match:
            exp_info['years_of_experience'] = years_match.group(1)
        
        # Experience levels
        if any(word in text_lower for word in ['senior', 'sr', 'lead', 'principal']):
            exp_info['experience_level'] = 'senior'
            exp_info['seniority_level'] = 'senior'
        elif any(word in text_lower for word in ['mid', 'intermediate']):
            exp_info['experience_level'] = 'mid'
            exp_info['seniority_level'] = 'mid-level'
        elif any(word in text_lower for word in ['junior', 'entry', 'jr']):
            exp_info['experience_level'] = 'junior'
            exp_info['seniority_level'] = 'entry-level'
        
        return exp_info

    def _parse_work_arrangement(self, text: str) -> Dict[str, Any]:
        """Parse work arrangement preferences."""
        arrangement = {}
        text_lower = text.lower()
        
        if 'remote' in text_lower:
            if 'full' in text_lower or 'completely' in text_lower:
                arrangement['preferred_arrangement'] = 'fully_remote'
            else:
                arrangement['preferred_arrangement'] = 'remote'
        elif 'hybrid' in text_lower:
            arrangement['preferred_arrangement'] = 'hybrid'
        elif 'office' in text_lower or 'onsite' in text_lower:
            arrangement['preferred_arrangement'] = 'onsite'
        else:
            arrangement['preferred_arrangement'] = 'flexible'
        
        if 'travel' in text_lower:
            if 'no travel' in text_lower or 'minimal' in text_lower:
                arrangement['travel_willingness'] = 'minimal'
            elif 'some travel' in text_lower:
                arrangement['travel_willingness'] = 'moderate'
            elif 'frequent' in text_lower or 'extensive' in text_lower:
                arrangement['travel_willingness'] = 'high'
        
        return arrangement

    def _parse_compensation(self, text: str) -> Dict[str, Any]:
        """Parse compensation information."""
        comp_info = {}
        text_lower = text.lower()
        
        # Extract salary ranges
        import re
        salary_pattern = r'\$?(\d+)(?:k|,000)?\s*(?:-|to)\s*\$?(\d+)(?:k|,000)?'
        salary_match = re.search(salary_pattern, text_lower)
        
        if salary_match:
            min_sal = salary_match.group(1)
            max_sal = salary_match.group(2)
            
            # Convert k notation
            if 'k' in text_lower:
                min_sal = str(int(min_sal) * 1000)
                max_sal = str(int(max_sal) * 1000)
            
            comp_info['salary_range_min'] = min_sal
            comp_info['salary_range_max'] = max_sal
        
        # Single salary value
        single_salary = re.search(r'\$?(\d+)k?', text_lower)
        if single_salary and not salary_match:
            salary = single_salary.group(1)
            if 'k' in text_lower:
                salary = str(int(salary) * 1000)
            comp_info['salary_range_min'] = salary
        
        return comp_info

    def _parse_management_preferences(self, text: str) -> Dict[str, Any]:
        """Parse management and leadership preferences."""
        mgmt_info = {}
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['manage', 'lead', 'supervise', 'direct']):
            mgmt_info['management_responsibilities'] = True
        
        # Team size preferences
        if 'small team' in text_lower:
            mgmt_info['team_size_preference'] = 'small (2-5 people)'
        elif 'large team' in text_lower:
            mgmt_info['team_size_preference'] = 'large (10+ people)'
        elif 'medium team' in text_lower:
            mgmt_info['team_size_preference'] = 'medium (5-10 people)'
        
        return mgmt_info

    def _parse_company_preferences(self, text: str) -> Dict[str, Any]:
        """Parse company and culture preferences."""
        company_prefs = {}
        text_lower = text.lower()
        
        culture_priorities = []
        if 'collaborative' in text_lower:
            culture_priorities.append('collaborative')
        if 'innovative' in text_lower:
            culture_priorities.append('innovative')
        if 'work-life balance' in text_lower:
            culture_priorities.append('work-life balance')
        if 'fast-paced' in text_lower:
            culture_priorities.append('fast-paced')
        if 'learning' in text_lower:
            culture_priorities.append('learning-oriented')
        
        if culture_priorities:
            company_prefs['company_culture_priorities'] = culture_priorities
        
        return company_prefs

    def _validate_completeness(self, intent: Dict):
        """Validate completeness of collected information."""
        missing_fields = []
        prefs = intent['job_search_preferences']
        
        # Check required fields
        if not prefs['location']['preferred_locations'] and not prefs['location']['location_flexibility']:
            missing_fields.append('location_preferences')
        
        if not prefs['job_criteria']['job_categories']:
            missing_fields.append('job_categories')
        
        if not prefs['experience_and_level']['experience_level']:
            missing_fields.append('experience_level')
        
        if not prefs['work_arrangement']['preferred_arrangement']:
            missing_fields.append('work_arrangement')
        
        # Update metadata
        intent['collection_metadata']['missing_fields'] = missing_fields
        intent['collection_metadata']['completion_status'] = 'complete' if not missing_fields else 'incomplete'
        intent['collection_metadata']['confidence_level'] = 'high' if len(missing_fields) <= 1 else 'medium' if len(missing_fields) <= 3 else 'low'
