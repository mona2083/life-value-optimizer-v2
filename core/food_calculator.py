"""
Food cost calculation module - SINGLE SOURCE OF TRUTH for all food estimates.
All food cost calculations must go through this module.
No overwrites, no silent changes - just pure calculation.
"""

from core.models import FoodEstimate, FoodData, UserProfile


def calculate_food_estimate(
    user_profile: UserProfile,
    food_data: FoodData,
    passion_text: str = ""
) -> FoodEstimate:
    """
    Calculate food costs based on household composition and preferences.
    
    This is THE ONLY place where food estimates are created.
    Once created, they should NOT be modified elsewhere.
    
    Args:
        user_profile: User household information
        food_data: Food preferences
        passion_text: User's freeform text (for location detection)
    
    Returns:
        FoodEstimate: Complete food cost model with all required fields
    """
    
    # Constants
    BASE_UNIT = 400.0
    CHILD_COEFF = 0.7
    INFANT_COEFF = 0.5
    
    # Extract location adjustment from passion_text
    location_adjustment = _extract_location_adjustment(passion_text)
    
    # Calculate adult equivalent
    adult_equivalent = (
        user_profile.household_adults
        + user_profile.household_children * CHILD_COEFF
        + user_profile.household_infants * INFANT_COEFF
    )
    total_headcount = (
        user_profile.household_adults
        + user_profile.household_children
        + user_profile.household_infants
    )
    
    # Scale adjustment based on household size
    scale_adjust = _get_scale_adjustment(total_headcount)
    
    # Meal style coefficient
    style_name, style_coeff = _get_style_coefficient(food_data.home_meal_style)
    
    # Quality of life additions (dining out, alcohol, etc.)
    qol_add = _calculate_qol_addition(food_data)
    
    # Base component calculation
    base_component = adult_equivalent * BASE_UNIT * scale_adjust
    
    # ===== 2-STAGE FOOD COST MODEL =====
    # C_min: Minimalist floor (survival-level costs, no dining out)
    # C_survey: Estimated level (per survey preferences)
    # C_max: Theoretical maximum (all premium options)
    
    minimalist_floor = base_component * 0.75 * location_adjustment
    estimated = (base_component * style_coeff * location_adjustment) + qol_add
    
    max_style_coeff = 1.45
    max_qol_add = 45.0 * 3.2 * (4.0 / 1.5) + 35.0 + 35.0 + 45.0
    max_possible = (base_component * max_style_coeff * location_adjustment) + max_qol_add
    
    # Flexible spending bands
    food_stage1_band_max = max(0.0, estimated - minimalist_floor)
    food_stage2_band_max = max(0.0, max_possible - estimated)
    
    # Debug output
    print(f"🔍 calculate_food_estimate() DEBUG:")
    print(f"   base_component={base_component:.2f}, adult_equiv={adult_equivalent:.2f}")
    print(f"   scale={scale_adjust}, location_adj={location_adjustment}")
    print(f"   minimalist_floor={minimalist_floor:.2f}, estimated={estimated:.2f}")
    print(f"   stage1_band_max={food_stage1_band_max:.2f}, stage2_band_max={food_stage2_band_max:.2f}")
    
    # Create and return the estimate
    return FoodEstimate(
        monthly_food_cost=round(estimated, 2),
        minimalist_floor_cost=round(minimalist_floor, 2),
        max_possible_food_cost=round(max_possible, 2),
        food_stage1_band_max=round(food_stage1_band_max, 2),
        food_stage2_band_max=round(food_stage2_band_max, 2),
        location_adjustment=location_adjustment,
        scale_adjustment=scale_adjust,
        style_name=style_name,
        style_coeff=style_coeff,
        qol_add=round(qol_add, 2),
        adult_equivalent=round(adult_equivalent, 3),
        headcount_total=total_headcount,
    )


def _extract_location_adjustment(passion_text: str) -> float:
    """
    Extract location from passion_text and return appropriate multiplier.
    Supports both English and Japanese.
    """
    if not passion_text:
        return 1.0
    
    location_adjustment = 1.0
    passion_lower = passion_text.lower()
    
    # English keywords
    if any(word in passion_lower for word in ["hawaii", "honolulu"]):
        location_adjustment = 1.25
        print(f"   ✓ Detected Hawaii/Honolulu (English) -> 1.25x")
    elif any(word in passion_lower for word in ["alaska", "anchorage"]):
        location_adjustment = 1.25
        print(f"   ✓ Detected Alaska/Anchorage (English) -> 1.25x")
    elif any(word in passion_lower for word in ["new york", "nyc", "manhattan"]):
        location_adjustment = 1.2
        print(f"   ✓ Detected NYC (English) -> 1.2x")
    elif any(word in passion_lower for word in ["california", "san francisco", "los angeles", "la"]):
        location_adjustment = 1.15
        print(f"   ✓ Detected California (English) -> 1.15x")
    elif any(word in passion_lower for word in ["rural", "countryside"]):
        location_adjustment = 0.9
        print(f"   ✓ Detected Rural (English) -> 0.9x")
    # Japanese keywords
    elif "ハワイ" in passion_text:
        location_adjustment = 1.25
        print(f"   ✓ Detected ハワイ (Hawaii in Japanese) -> 1.25x")
    elif "アラスカ" in passion_text:
        location_adjustment = 1.25
        print(f"   ✓ Detected アラスカ (Alaska in Japanese) -> 1.25x")
    elif "ニューヨーク" in passion_text or "NYC" in passion_text:
        location_adjustment = 1.2
        print(f"   ✓ Detected ニューヨーク (NYC in Japanese) -> 1.2x")
    elif "カリフォルニア" in passion_text:
        location_adjustment = 1.15
        print(f"   ✓ Detected カリフォルニア (California in Japanese) -> 1.15x")
    elif "田舎" in passion_text or "農村" in passion_text:
        location_adjustment = 0.9
        print(f"   ✓ Detected 田舎/農村 (Rural in Japanese) -> 0.9x")
    
    return location_adjustment


def _get_scale_adjustment(headcount: int) -> float:
    """Get household size adjustment factor"""
    if headcount <= 1:
        return 1.2
    elif headcount == 2:
        return 1.1
    elif headcount == 3:
        return 1.05
    elif headcount == 4:
        return 1.0
    else:
        return 0.95


def _get_style_coefficient(style_key: str) -> tuple:
    """Get meal style name and cost multiplier"""
    style_map = {
        "minimalist": ("Minimalist", 0.75),
        "standard": ("Standard", 1.00),
        "health_conscious": ("Health-Conscious", 1.25),
        "time_saving": ("Time-Saving", 1.45),
    }
    return style_map.get(style_key, ("Standard", 1.00))


def _calculate_qol_addition(food_data: FoodData) -> float:
    """Calculate quality-of-life additions (dining out, alcohol, supplements)"""
    tone_coeffs = {"utility": 1.5, "casual": 2.5, "experience": 4.0}
    freq_mult = {"0_1": 1.0, "2_3": 2.0, "4_plus": 3.2}
    
    tc = tone_coeffs.get(food_data.dining_out_tone, 1.5)
    fm = freq_mult.get(food_data.dining_out_frequency, 1.0)
    
    qol_add = 45.0 * fm * (tc / 1.5)
    
    if food_data.optional_alcohol:
        qol_add += 35.0
    if food_data.optional_supplements:
        qol_add += 35.0
    if food_data.optional_special_diet:
        qol_add += 45.0
    
    return qol_add
