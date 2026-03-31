"""
LLM client for Google Gemini API.
Single responsibility: Make LLM calls and return raw responses.
Response parsing is handled separately in profile_extractor.py.
"""

import os
import json
from typing import Optional, Dict, Any
from google.generativeai import types
import google.generativeai as genai


class LLMClient:
    """
    Client for Google Gemini API.
    Handles authentication and LLM calls.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize LLM client"""
        if api_key is None:
            api_key = os.getenv("GOOGLE_API_KEY")
        
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")
    
    def extract_profile(self, user_input: str) -> str:
        """
        Send user input to LLM for psychological profiling.
        Returns raw JSON string from LLM.
        """
        prompt = self._build_profile_prompt(user_input)
        response = self.model.generate_content(prompt)
        return response.text
    
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
        response = self.model.generate_content(prompt)
        return response.text
