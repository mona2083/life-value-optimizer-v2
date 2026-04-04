"""
LLM client for OpenAI API.
Single responsibility: Make LLM calls and return raw responses.
Response parsing is handled separately in profile_extractor.py.
"""

import os
from typing import Optional
from openai import OpenAI


class LLMClient:
    """
    Client for OpenAI API.
    Handles authentication and LLM calls.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize LLM client"""
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
    
    def extract_profile(self, user_input: str) -> str:
        """
        Send user input to LLM for psychological profiling.
        Returns raw JSON string from LLM.
        """
        prompt = self._build_profile_prompt(user_input)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs strict JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return (response.choices[0].message.content or "").strip()
    
    def _build_profile_prompt(self, user_input: str) -> str:
        """Build the prompt for profile extraction"""
        return f"""Analyze the user's input about their lifestyle and values. 
        Extract structured data in JSON format with these fields:

        {{
            "estimated_food_cost": {{
                "minimalist_floor_cost": <number>,
                "monthly_food_cost": <number>,
                "max_possible_food_cost": <number>
            }},
            "value_scores": {{
                "health": <0-100>,
                "independence": <0-100>,
                "relationships": <0-100>,
                "spiritual": <0-100>,
                "career": <0-100>,
                "leisure": <0-100>
            }},
            "lifestyle_notes": "<text>",
            "passion_text": "<text>"
        }}

        User input:
        {user_input}

        Return ONLY valid JSON, no markdown or explanation."""
    
    def refine_response(self, prompt: str) -> str:
        """
        Send a custom prompt to LLM for refinement/additional analysis.
        Used for follow-up questions or clarifications.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        return (response.choices[0].message.content or "").strip()
