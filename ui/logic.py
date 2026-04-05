import streamlit as st
import pandas as pd
from default_items import CATEGORIES, DEFAULT_ITEMS


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _build_item_cost_context(financial_data: dict) -> dict:
    profile = (financial_data or {}).get("user_profile", {}) or {}

    monthly_budget = max(0.0, _safe_float((financial_data or {}).get("monthly_budget", 0), 0.0))
    initial_budget = max(0.0, _safe_float((financial_data or {}).get("initial_budget", 0), 0.0))
    adults = max(0, int(_safe_float(profile.get("household_adults", 1), 1)))
    children = max(0, int(_safe_float(profile.get("household_children", 0), 0)))
    infants = max(0, int(_safe_float(profile.get("household_infants", 0), 0)))

    adult_equivalent = adults + (0.6 * children) + (0.4 * infants)
    budget_factor_monthly = _clip((monthly_budget / 1500.0) ** 0.5 if monthly_budget > 0 else 0.75, 0.75, 1.40)
    budget_factor_initial = _clip((initial_budget / 5000.0) ** 0.5 if initial_budget > 0 else 0.70, 0.70, 1.60)
    household_factor = _clip(1.0 + (0.18 * (adult_equivalent - 1.0)), 0.85, 1.70)

    category_monthly_factor = {
        "transport": 1.10,
        "living": 1.00,
        "wellbeing": 1.00,
        "leisure": 0.95,
        "learning": 0.90,
    }
    category_initial_factor = {
        "transport": 1.20,
        "living": 1.00,
        "wellbeing": 1.00,
        "leisure": 0.90,
        "learning": 1.05,
    }

    return {
        "monthly_budget": monthly_budget,
        "initial_budget": initial_budget,
        "budget_factor_monthly": budget_factor_monthly,
        "budget_factor_initial": budget_factor_initial,
        "household_factor": household_factor,
        "category_monthly_factor": category_monthly_factor,
        "category_initial_factor": category_initial_factor,
    }


def _normalize_item_costs(initial_cost, monthly_cost, category: str, source: str, ctx: dict) -> tuple[int, int]:
    base_initial = max(0.0, _safe_float(initial_cost, 0.0))
    base_monthly = max(0.0, _safe_float(monthly_cost, 0.0))

    cat_init = ctx["category_initial_factor"].get(category, 1.0)
    cat_month = ctx["category_monthly_factor"].get(category, 1.0)
    multiplier_initial = ctx["budget_factor_initial"] * ctx["household_factor"] * cat_init
    multiplier_monthly = ctx["budget_factor_monthly"] * ctx["household_factor"] * cat_month

    normalized_initial = base_initial * multiplier_initial
    normalized_monthly = base_monthly * multiplier_monthly

    blend_weight = 0.45 if source == "default" else 0.75
    final_initial = (base_initial * (1.0 - blend_weight)) + (normalized_initial * blend_weight)
    final_monthly = (base_monthly * (1.0 - blend_weight)) + (normalized_monthly * blend_weight)

    monthly_cap = max(100.0, ctx["monthly_budget"] * 0.90)
    initial_cap = max(200.0, ctx["initial_budget"] * 0.90)

    final_initial = _clip(final_initial, 0.0, initial_cap)
    final_monthly = _clip(final_monthly, 0.0, monthly_cap)
    return int(round(final_initial)), int(round(final_monthly))


def normalize_all_item_costs(financial_data: dict, debug: bool = False) -> None:
    if not hasattr(st.session_state, "category_dfs"):
        return

    ctx = _build_item_cost_context(financial_data)
    for cat, df in st.session_state.category_dfs.items():
        if df is None or df.empty:
            continue

        if "base_initial_cost" not in df.columns:
            df["base_initial_cost"] = df["initial_cost"].fillna(0).astype("float64")
        if "base_monthly_cost" not in df.columns:
            df["base_monthly_cost"] = df["monthly_cost"].fillna(0).astype("float64")

        for idx, row in df.iterrows():
            source = row.get("source", "default")
            base_ic = row.get("base_initial_cost", row.get("initial_cost", 0))
            base_mc = row.get("base_monthly_cost", row.get("monthly_cost", 0))
            norm_ic, norm_mc = _normalize_item_costs(base_ic, base_mc, cat, source, ctx)

            df.at[idx, "initial_cost"] = norm_ic
            df.at[idx, "monthly_cost"] = norm_mc

            initial_state_key = f"initial_cost_{cat}_{idx}"
            monthly_state_key = f"monthly_cost_{cat}_{idx}"
            if not st.session_state.get(f"manual_{initial_state_key}", False):
                st.session_state[initial_state_key] = norm_ic
            if not st.session_state.get(f"manual_{monthly_state_key}", False):
                st.session_state[monthly_state_key] = norm_mc

        st.session_state.category_dfs[cat] = df

def dict_get_or_zero(d, key):
    """Safely get a float value from a dictionary, defaulting to 0.0 if not found or None."""
    res = (d or {}).get(key, 0)
    return float(res) if res is not None else 0.0

def estimate_food_cost(user_profile: dict, lifestyle_data: dict) -> dict:
    """
        Return estimated food cost (without rendering UI output).
        Formula:
            (household-size coefficient x base unit cost) x style coefficient + dining/QOL additions
    """
    base_unit = 400.0
    child_coeff = 0.7
    infant_coeff = 0.5 

    adults = int(user_profile.get("household_adults", 1) or 0)
    children = int(user_profile.get("household_children", 0) or 0)
    infants = int(user_profile.get("household_infants", 0) or 0)

    # Adult-equivalent household size
    adult_equivalent = adults + children * child_coeff + infants * infant_coeff
    total_headcount = adults + children + infants

    # Household scale adjustment
    if total_headcount <= 1:
        scale_adjust = 1.2
    elif total_headcount == 2:
        scale_adjust = 1.1
    elif total_headcount == 3:
        scale_adjust = 1.05
    elif total_headcount == 4:
        scale_adjust = 1.0
    else:
        scale_adjust = 0.95

    food = (lifestyle_data or {}).get("food") or {}
    style_key = food.get("home_meal_style", "standard")
    style_map = {
        "minimalist": ("Minimalist", 0.75),
        "standard": ("Standard", 1.00),
        "health_conscious": ("Health-Conscious", 1.25),
        "time_saving": ("Time-Saving", 1.45),
    }
    style_name, style_coeff = style_map.get(style_key, ("Standard", 1.00))

    # Dining out and delivery QOL additions (frequency x tone)
    tone_coeffs = {"utility": 1.5, "casual": 2.5, "experience": 4.0}
    freq_mult = {"0_1": 1.0, "2_3": 2.0, "4_plus": 3.2}
    tone = food.get("dining_out_tone", "utility")
    freq = food.get("dining_out_frequency", "0_1")
    tc = tone_coeffs.get(tone, 1.5)
    fm = freq_mult.get(freq, 1.0)
    qol_add = 45.0 * fm * (tc / 1.5)
    if food.get("optional_alcohol"):
        qol_add += 35.0
    if food.get("optional_supplements"):
        qol_add += 35.0
    if food.get("optional_special_diet"):
        qol_add += 45.0

    base_component = adult_equivalent * base_unit * scale_adjust

    # ===== Two-stage food cost model =====
    # C_min: Fulfillment cost up to Minimalist baseline (survival line only, no dining additions)
    # C_survey: Target level from survey responses (home style + dining tone/frequency + options)
    # C_max: Theoretical maximum (max home style + max dining + all options on)
    minimalist_floor = base_component * 0.75
    estimated = (base_component * style_coeff) + qol_add  # C_survey

    max_style_coeff = 1.45
    max_qol_add = 45.0 * 3.2 * (4.0 / 1.5) + 35.0 + 35.0 + 45.0
    max_possible = (base_component * max_style_coeff) + max_qol_add  # C_max

    # Stage1: C_min -> C_survey
    food_stage1_band_max = max(0.0, estimated - minimalist_floor)
    # Stage2: C_survey -> C_max
    food_stage2_band_max = max(0.0, max_possible - estimated)

    return {
        "monthly_food_cost": round(estimated, 2),
        "minimalist_floor_cost": round(minimalist_floor, 2),
        "max_possible_food_cost": round(max_possible, 2),
        "food_stage1_band_max": round(food_stage1_band_max, 2),
        "food_stage2_band_max": round(food_stage2_band_max, 2),
        "base_unit": base_unit,
        "adult_equivalent": round(adult_equivalent, 3),
        "scale_adjustment": scale_adjust,
        "style_name": style_name,
        "style_coeff": style_coeff,
        "qol_add": round(qol_add, 2),
        "headcount_total": total_headcount,
    }

def init_category_dfs():
    """
    Convert DEFAULT_ITEMS into pandas DataFrames.
    Added standard keys required by the AI optimizer, with explicit types.
    """
    dfs = {}
    for cat in CATEGORIES["en"].keys():
        data = [item for item in DEFAULT_ITEMS if item.get("category") == cat]
        df = pd.DataFrame(data)
        if df.empty:
            df = pd.DataFrame(columns=[
                "name_ja", "name_en", "initial_cost", "monthly_cost",
                "priority", "mandatory", "memo_ja", "memo_en",
                "health", "connections", "freedom", "growth", "source"
            ])
        else:
            if "priority" not in df.columns:
                df["priority"] = 3
            if "mandatory" not in df.columns:
                df["mandatory"] = False
            if "source" not in df.columns:
                df["source"] = "default"
        
        # Add default `name` column to prevent KeyErrors in UI
        if "name" not in df.columns:
            df["name"] = df["name_ja"] if "name_ja" in df.columns else ""
            
        # Ensure primitive types for seamless frontend/backend integration
        df["initial_cost"] = df["initial_cost"].fillna(0).astype("float64")
        df["monthly_cost"] = df["monthly_cost"].fillna(0).astype("float64")
        df["base_initial_cost"] = df["initial_cost"]
        df["base_monthly_cost"] = df["monthly_cost"]
        df["priority"] = df["priority"].fillna(3).astype("int64")
        df["mandatory"] = df["mandatory"].fillna(False).astype("bool")
        if "source" not in df.columns:
            df["source"] = "default"
        dfs[cat] = df
    return dfs

def apply_dynamic_overrides(lifestyle_data):
    """Overwrite item costs and priorities in SessionState based on lifestyle answers."""
    dfs = st.session_state.category_dfs
    
    def set_val(cat, name_ja, key_prefix, value):
        if cat in dfs:
            idx_list = dfs[cat].index[dfs[cat]['name_ja'] == name_ja].tolist()
            if idx_list:
                idx = idx_list[0]
                state_key = f"{key_prefix}_{cat}_{idx}"
                # Do not auto-overwrite if the user manually modified this field
                if st.session_state.get(f"manual_{state_key}", False):
                    return
                st.session_state[state_key] = value

    # Q1: Car & Transportation
    q1a = lifestyle_data.get("car_necessity", "")
    if "A:" in q1a:
        # Mandatory requirement
        st.session_state["prefer_car_soft_bonus"] = False
        st.session_state["prefer_car_soft_bonus_value"] = 0
        set_val("transport", "車メイン", "mandatory", True)
        set_val("transport", "車メイン", "priority", 5)
    elif "B:" in q1a:
        # Optional but preferred
        st.session_state["prefer_car_soft_bonus"] = True
        # Objective utilities are scaled to ~10^4 order per item, so this needs to be large enough.
        st.session_state["prefer_car_soft_bonus_value"] = 30000
        set_val("transport", "車メイン", "mandatory", False)
        set_val("transport", "車メイン", "priority", 6)
    elif "C:" in q1a:
        # Excluded
        st.session_state["prefer_car_soft_bonus"] = False
        st.session_state["prefer_car_soft_bonus_value"] = 0
        set_val("transport", "車メイン", "mandatory", False)
        set_val("transport", "車メイン", "priority", 0)
        
    # Q2: Vehicle ownership logic - resets initial cost to 0 if already owned
    if lifestyle_data.get("own_car"):
        set_val("transport", "車メイン", "initial_cost", 0)
    if lifestyle_data.get("own_ebike"):
        set_val("transport", "電動自転車＋Uber", "initial_cost", 0)
    if lifestyle_data.get("own_bike"):
        set_val("transport", "自転車のみ", "initial_cost", 0)
        set_val("transport", "カーシェア＋自転車", "initial_cost", 0)
    if lifestyle_data.get("own_moto"):
        set_val("transport", "バイクメイン", "initial_cost", 0)
        set_val("transport", "バイクメイン", "priority", 4)
    else:
        set_val("transport", "バイクメイン", "priority", 0)

    # Q3: Work style
    q2 = lifestyle_data.get("work_style", "")
    if "A:" in q2: # Remote
        set_val("living", "エルゴノミクスチェア", "priority", 5)
    elif "B:" in q2: # Hybrid
        set_val("living", "エルゴノミクスチェア", "priority", 3)
    elif "C:" in q2: # Office
        set_val("living", "エルゴノミクスチェア", "priority", 0)

    # Q4: Social life
    q4 = lifestyle_data.get("social", "")
    if "A:" in q4: # Frequent
        set_val("leisure", "交際費・飲み代", "monthly_cost", 225) # 1.5x alcohol cost
    elif "C:" in q4: # Prefers alone time
        set_val("leisure", "交際費・飲み代", "priority", 0)
        set_val("learning", "本・電子書籍・Audible", "priority", 5)

    # Q5: Leisure
    q5 = lifestyle_data.get("leisure", "")
    if "A:" in q5: # Indoor
        set_val("leisure", "ゲーム", "priority", 5)
        set_val("leisure", "動画・音楽サブスク", "priority", 5)
        set_val("leisure", "アウトドア・スポーツ", "priority", 0)
    elif "B:" in q5: # Outdoor
        set_val("leisure", "アウトドア・スポーツ", "priority", 5)
        set_val("wellbeing", "旅行・リトリート積立", "priority", 5)
    elif "C:" in q5: # Going out
        set_val("leisure", "映画・観劇・美術館", "priority", 5)
        set_val("leisure", "推し活・ファンコミュニティ", "priority", 5)

def apply_food_overrides(food_data: dict) -> None:
    """Overwrites specific food preferences in SessionState depending on jelly slider responses."""
    dfs = st.session_state.category_dfs
    if "food" not in dfs:
        return
        
    def set_food_val(name_ja, value, key="priority"):
        idx_list = dfs["food"].index[dfs["food"]['name_ja'] == name_ja].tolist()
        if idx_list:
            idx = idx_list[0]
            state_key = f"{key}_food_{idx}"
            # Skip if user manually adjusted
            if st.session_state.get(f"manual_{state_key}", False):
                return
            st.session_state[state_key] = value

    # Check specialty food priorities
    coffee_pref = food_data.get("coffee_pref", 50)
    if coffee_pref >= 70:
        set_food_val("コーヒー豆・お茶類", 5)
    elif coffee_pref <= 30:
        set_food_val("コーヒー豆・お茶類", 1)

    fitness_pref = food_data.get("fitness_pref", 50)
    if fitness_pref >= 70:
        set_food_val("プロテイン・サプリ", 5)
    elif fitness_pref <= 30:
        set_food_val("プロテイン・サプリ", 1)
