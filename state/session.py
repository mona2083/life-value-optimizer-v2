"""
Centralized state management for the application.
This module provides clean read/write APIs for application state,
preventing silent overwrites and ensuring single source of truth.
"""

import streamlit as st
from typing import Optional, Dict, Any
from core.models import FoodEstimate, UserProfile, LifestyleData, OptimizationResult


class SessionState:
    """
    Centralized state management wrapper.
    Must be the ONLY place where session_state is modified.
    """
    
    # Keys for session_state
    KEY_FOOD_ESTIMATE = "food_estimate"
    KEY_USER_PROFILE = "user_profile"
    KEY_LIFESTYLE_DATA = "lifestyle_data"
    KEY_OPTIMIZATION_RESULT = "optimization_result"
    KEY_AI_INSIGHT = "ai_insight"
    
    @staticmethod
    def get_food_estimate() -> Optional[FoodEstimate]:
        """Get the current food estimate (single source of truth)"""
        data = st.session_state.get(SessionState.KEY_FOOD_ESTIMATE)
        if data and isinstance(data, dict):
            return FoodEstimate.from_dict(data)
        return None
    
    @staticmethod
    def set_food_estimate(estimate: FoodEstimate) -> None:
        """
        Set the food estimate. This is the ONLY place where food_estimate is written.
        No silent overwrites - must be explicit.
        """
        print(f"🔍 SessionState: Writing food_estimate")
        print(f"   minimalist_floor_cost: {estimate.minimalist_floor_cost}")
        print(f"   food_stage1_band_max: {estimate.food_stage1_band_max}")
        print(f"   food_stage2_band_max: {estimate.food_stage2_band_max}")
        st.session_state[SessionState.KEY_FOOD_ESTIMATE] = estimate.to_dict()
    
    @staticmethod
    def get_user_profile() -> Optional[UserProfile]:
        """Get user profile"""
        return st.session_state.get(SessionState.KEY_USER_PROFILE)
    
    @staticmethod
    def set_user_profile(profile: UserProfile) -> None:
        """Set user profile"""
        st.session_state[SessionState.KEY_USER_PROFILE] = profile
    
    @staticmethod
    def get_lifestyle_data() -> Optional[LifestyleData]:
        """Get lifestyle data"""
        return st.session_state.get(SessionState.KEY_LIFESTYLE_DATA)
    
    @staticmethod
    def set_lifestyle_data(lifestyle: LifestyleData) -> None:
        """Set lifestyle data"""
        st.session_state[SessionState.KEY_LIFESTYLE_DATA] = lifestyle
    
    @staticmethod
    def get_optimization_result() -> Optional[OptimizationResult]:
        """Get optimization result"""
        data = st.session_state.get(SessionState.KEY_OPTIMIZATION_RESULT)
        if data and isinstance(data, dict):
            # Parse dict back to OptimizationResult
            result = OptimizationResult()
            for key, value in data.items():
                if hasattr(result, key):
                    setattr(result, key, value)
            return result
        return None
    
    @staticmethod
    def set_optimization_result(result: OptimizationResult) -> None:
        """Set optimization result"""
        st.session_state[SessionState.KEY_OPTIMIZATION_RESULT] = result
    
    @staticmethod
    def get_ai_insight() -> Optional[Dict[str, Any]]:
        """Get AI insight/profile from LLM"""
        return st.session_state.get(SessionState.KEY_AI_INSIGHT)
    
    @staticmethod
    def set_ai_insight(insight: Dict[str, Any]) -> None:
        """Set AI insight from LLM"""
        st.session_state[SessionState.KEY_AI_INSIGHT] = insight
    
    @staticmethod
    def clear_all() -> None:
        """Clear all application state (for testing/reset)"""
        for key in [
            SessionState.KEY_FOOD_ESTIMATE,
            SessionState.KEY_USER_PROFILE,
            SessionState.KEY_LIFESTYLE_DATA,
            SessionState.KEY_OPTIMIZATION_RESULT,
            SessionState.KEY_AI_INSIGHT,
        ]:
            if key in st.session_state:
                del st.session_state[key]
