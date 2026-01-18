"""
Gemini AI service for intelligent grant matching
"""
import json
import google.generativeai as genai
from django.conf import settings
from typing import Dict, List, Tuple, Optional


class GeminiMatchingService:
    """Service for using Gemini AI to match projects with grants"""
    
    def __init__(self):
        """Initialize Gemini API client"""
        api_key = getattr(settings, 'GEMINI_API_KEY', '')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured in settings")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
    
    def match_project_to_grant(self, project_data: Dict, grant_data: Dict) -> Tuple[int, List[str]]:
        """
        Use Gemini AI to match a project with a grant
        
        Args:
            project_data: Dictionary containing project information
            grant_data: Dictionary containing grant information
            
        Returns:
            Tuple of (match_score: int, match_reasons: List[str])
            match_score is 0-100, match_reasons is list of explanation strings
        """
        try:
            # Prepare project information
            project_info = self._format_project_info(project_data)
            grant_info = self._format_grant_info(grant_data)
            
            # Create prompt for Gemini
            prompt = self._create_matching_prompt(project_info, grant_info)
            
            # Call Gemini API
            response = self.model.generate_content(prompt)
            
            # Parse response
            match_score, match_reasons = self._parse_gemini_response(response.text)
            
            return match_score, match_reasons
            
        except Exception as e:
            print(f"Error in Gemini matching: {e}")
            # Return fallback score
            return self._fallback_matching(project_data, grant_data)
    
    def _format_project_info(self, project: Dict) -> str:
        """Format project data into a readable string"""
        info_parts = []
        
        info_parts.append(f"Title: {project.get('title', 'N/A')}")
        info_parts.append(f"Description: {project.get('description', 'N/A')}")
        
        if project.get('focus_area'):
            info_parts.append(f"Focus Area: {project.get('focus_area')}")
        
        if project.get('budget_required_min') or project.get('budget_required_max'):
            min_budget = project.get('budget_required_min', 0)
            max_budget = project.get('budget_required_max', 0)
            info_parts.append(f"Budget Required: ${min_budget:,.0f} - ${max_budget:,.0f}")
        
        if project.get('duration_years'):
            info_parts.append(f"Duration: {project.get('duration_years')}")
        
        if project.get('beneficiary_types'):
            info_parts.append(f"Beneficiary Types: {', '.join(project.get('beneficiary_types', []))}")
        
        if project.get('interested_in'):
            info_parts.append(f"Interested In: {', '.join(project.get('interested_in', []))}")
        
        if project.get('need_support_for'):
            info_parts.append(f"Need Support For: {', '.join(project.get('need_support_for', []))}")
        
        if project.get('kpis'):
            info_parts.append(f"KPIs: {project.get('kpis')}")
        
        if project.get('service_outcomes'):
            info_parts.append(f"Service Outcomes: {project.get('service_outcomes')}")
        
        return "\n".join(info_parts)
    
    def _format_grant_info(self, grant: Dict) -> str:
        """Format grant data into a readable string"""
        info_parts = []
        
        info_parts.append(f"Grant Title: {grant.get('title', 'N/A')}")
        info_parts.append(f"Agency: {grant.get('agency_name', 'N/A')} ({grant.get('agency_acronym', 'N/A')})")
        info_parts.append(f"Description: {grant.get('description', 'N/A')}")
        
        if grant.get('funding_min') or grant.get('funding_max'):
            min_funding = grant.get('funding_min', 0)
            max_funding = grant.get('funding_max', 0)
            info_parts.append(f"Funding Range: ${min_funding:,.0f} - ${max_funding:,.0f}")
        
        if grant.get('duration_years'):
            info_parts.append(f"Duration: {grant.get('duration_years')}")
        
        if grant.get('eligibility_criteria'):
            info_parts.append(f"Eligibility Criteria: {grant.get('eligibility_criteria')}")
        
        if grant.get('closing_date'):
            info_parts.append(f"Closing Date: {grant.get('closing_date')}")
        
        return "\n".join(info_parts)
    
    def _create_matching_prompt(self, project_info: str, grant_info: str) -> str:
        """Create the prompt for Gemini AI"""
        prompt = f"""You are an expert grant matching assistant. Your task is to analyze a project and a grant opportunity, then determine how well they match.

PROJECT INFORMATION:
{project_info}

GRANT OPPORTUNITY:
{grant_info}

Please analyze the compatibility between this project and grant opportunity. Consider:
1. Alignment of project goals with grant objectives
2. Budget compatibility (project needs vs grant funding range)
3. Beneficiary alignment
4. Focus area compatibility
5. Timeline/duration compatibility
6. Eligibility criteria match
7. Service outcomes alignment

Provide your response in the following JSON format:
{{
    "match_score": <integer between 0-100>,
    "match_reasons": [
        "<reason 1>",
        "<reason 2>",
        "<reason 3>"
    ]
}}

The match_score should reflect:
- 90-100: Excellent match, highly recommended
- 80-89: Strong match, very suitable
- 70-79: Good match, suitable with some considerations
- 60-69: Moderate match, may require adjustments
- Below 60: Weak match, not recommended

Provide exactly 3 match reasons that are specific, clear, and actionable. Focus on the most important alignment factors.

Respond ONLY with valid JSON, no additional text."""
        
        return prompt
    
    def _parse_gemini_response(self, response_text: str) -> Tuple[int, List[str]]:
        """Parse Gemini's JSON response"""
        try:
            # Clean the response text (remove markdown code blocks if present)
            cleaned_text = response_text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.startswith('```'):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # Parse JSON
            response_data = json.loads(cleaned_text)
            
            match_score = int(response_data.get('match_score', 0))
            match_reasons = response_data.get('match_reasons', [])
            
            # Validate score range
            match_score = max(0, min(100, match_score))
            
            # Ensure we have reasons
            if not match_reasons or len(match_reasons) == 0:
                match_reasons = ["AI analysis completed"]
            
            return match_score, match_reasons[:3]  # Return top 3 reasons
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error parsing Gemini response: {e}")
            print(f"Response text: {response_text}")
            # Return default values
            return 50, ["AI analysis encountered an error"]
    
    def _fallback_matching(self, project_data: Dict, grant_data: Dict) -> Tuple[int, List[str]]:
        """Fallback matching logic when Gemini API fails"""
        score = 0
        reasons = []
        
        # Simple keyword matching
        project_desc = project_data.get('description', '').lower()
        grant_desc = grant_data.get('description', '').lower()
        
        if project_data.get('focus_area'):
            focus = project_data.get('focus_area', '').lower()
            if focus in grant_desc:
                score += 30
                reasons.append(f"Focus area '{project_data.get('focus_area')}' aligns with grant objectives")
        
        # Budget matching
        if project_data.get('budget_required_min') and grant_data.get('funding_min'):
            proj_min = float(project_data.get('budget_required_min', 0))
            proj_max = float(project_data.get('budget_required_max', proj_min))
            grant_min = float(grant_data.get('funding_min', 0))
            grant_max = float(grant_data.get('funding_max', grant_min))
            
            if grant_min <= proj_max and grant_max >= proj_min:
                score += 25
                reasons.append("Budget range matches grant funding")
        
        # Duration matching
        if project_data.get('duration_years') and grant_data.get('duration_years'):
            score += 15
            reasons.append("Project duration aligns with grant timeline")
        
        # Base score
        score += 10
        
        if score < 70:
            return 0, []  # Don't create matches below 70
        
        return min(score, 100), reasons[:3]
