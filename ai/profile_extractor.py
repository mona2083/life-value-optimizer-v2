"""
Profile extractor - parses LLM responses into structured domain models.
Single responsibility: Convert raw LLM JSON responses to FoodEstimate, UserProfile, etc.
LLM calls are handled separately in llm_client.py.
"""

import json
import re
from typing import Optional, Dict, Any
from core.models import UserProfile, FoodData, LifestyleData, FoodEstimate
import logging

logger = logging.getLogger(__name__)


class ProfileExtractor:
    """
    Parses LLM responses into structured domain models.
    """
    
    @staticmethod
    def extract_from_response(llm_response: str) -> Dict[str, Any]:
        """
        Parse LLM response and extract structured data.
        Returns a dict with: food_estimate, user_profile, lifestyle_data
        """
        try:
            # Try to extract JSON from response
            json_data = ProfileExtractor._parse_json(llm_response)
            
            # Extract food estimate from AI response
            ai_food_data = json_data.get("estimated_food_cost", {})
            
            # Extract value scores
            value_scores = json_data.get("value_scores", {})
            
            # Extract text fields
            lifestyle_notes = json_data.get("lifestyle_notes", "")
            passion_text = json_data.get("passion_text", "")
            
            return {
                "ai_estimated_food": ai_food_data,
                "value_scores": value_scores,
                "lifestyle_notes": lifestyle_notes,
                "passion_text": passion_text,
                "raw_response": llm_response,
            }
        
        except Exception as e:
            logger.error(f"Error extracting from LLM response: {e}")
            return {
                "ai_estimated_food": {},
                "value_scores": {},
                "lifestyle_notes": "",
                "passion_text": "",
                "raw_response": llm_response,
                "error": str(e),
            }
    
    @staticmethod
    def _parse_json(response_text: str) -> Dict[str, Any]:
        """
        Extract JSON from LLM response.
        LLMs sometimes wrap JSON in markdown code blocks.
        """
        # Try direct JSON parsing first
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON in markdown code block
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", response_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON object in curly braces
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        # If all else fails, return empty dict
        logger.warning("Could not parse JSON from LLM response")
        return {}
    
    @staticmethod
    def should_update_food_estimate(ai_data: Dict[str, Any]) -> bool:
        """
        Decide whether to use AI's food estimate or keep the calculated one.
        
        Strategy:
        - AI food data must have ALL fields to be considered complete
        - If AI data is incomplete, use the calculated FoodEstimate instead
        - This prevents the bug where partial AI data overwrites good defaults
        """
        required_fields = ["minimalist_floor_cost", "monthly_food_cost", "max_possible_food_cost"]
        
        # Check if all required fields are present and non-zero
        has_all_fields = all(
            ai_data.get(field) and float(ai_data.get(field, 0)) > 0
            for field in required_fields
        )
        
        return has_all_fields
