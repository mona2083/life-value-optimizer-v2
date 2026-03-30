import streamlit as st
import pandas as pd
from default_items import CATEGORIES, DEFAULT_ITEMS

def dict_get_or_zero(d, key):
    """Safely get a float value from a dictionary, defaulting to 0.0 if not found or None."""
    res = (d or {}).get(key, 0)
    return float(res) if res is not None else 0.0

def estimate_food_cost(user_profile: dict, lifestyle_data: dict) -> dict:
    """
    Returns estimated food cost (not displayed in UI directly).
    Formula:
      (Household scale factor * base unit) * style adjustment factor + dining/QOL addition
    Returns a dictionary with standard food cost and minimalist floor.
    """
    adults = user_profile.get("household_adults", 1)
    children = user_profile.get("household_children", 0)
    infants = user_profile.get("household_infants", 0)
    
    adult_equivalent = adults + (children * 0.5) + (infants * 0.3)
    
    # Base unit: single person minimalist cost (e.g. $250)
    base_unit = 250.0
    
    # Scale adjustment for bulk cooking efficiency
    # 1 person = 1.0, 2 people = ~0.85 per equivalent adult, ...
    if adult_equivalent <= 1.0:
        scale_adjust = 1.0
    elif adult_equivalent <= 2.0:
        scale_adjust = 0.85
    elif adult_equivalent <= 3.0:
        scale_adjust = 0.75
    else:
        scale_adjust = 0.70

    q_home = lifestyle_data.get("food_style", "")
    if "C:" in q_home:
        style_multiplier = 0.8  # Minimalist
    elif "A:" in q_home:
        style_multiplier = 1.3  # Organic/Premium
    else:
        style_multiplier = 1.0  # Balance/Standard

    q_dining = lifestyle_data.get("dining_out", "")
    dining_add = 0.0
    if "A:" in q_dining:
        dining_add = 300.0 * adult_equivalent  # Frequent dining out
    elif "B:" in q_dining:
        dining_add = 100.0 * adult_equivalent  # Weekend dining out
    else:
        dining_add = 0.0                       # Self-cooking mostly

    base_component = adult_equivalent * base_unit * scale_adjust

    # ===== 2-Stage Food Cost Model =====
    # C_min: "Sufficiency" cost up to Minimalist (includes QOL addition as requested)
    # C_survey: Full requested level from survey (home style + dining freq + options)

    # 1. Calculate floor/minimalist level (style_multiplier=0.8, no dining_add)
    # The absolute lowest realistic food cost
    cost_min = (adult_equivalent * base_unit * scale_adjust) * 0.8 

    # 2. Add options/QOL adjustments that are currently selected (e.g. supplements)
    # This reflects items the user *explicitly* requested via UI
    qol_add = 0.0
    dfs = st.session_state.get("category_dfs", {})
    if "food" in dfs:
        df = dfs["food"]
        # E.g. Check for items like supplements/coffee beans
        for idx, row in df.iterrows():
            item_name = row.get("name_ja", "")
            # If standardly defined added items:
            if item_name in ["プロテイン・サプリ", "コーヒー豆・お茶類"]:
                key = f"priority_food_{idx}"
                if int(st.session_state.get(key, row.get("priority", 0))) > 0:
                    q_val = float(st.session_state.get(f"monthly_cost_food_{idx}", row.get("monthly_cost", 0)))
                    qol_add += q_val

    cost_min += qol_add

    # 3. Calculate full requested survey cost
    cost_survey = (base_component * style_multiplier) + dining_add + qol_add

    return {
        "monthly_food_cost": cost_survey,
        "minimalist_floor": cost_min,
        "qol_addition": qol_add
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
                "health", "connections", "freedom", "growth"
            ])
        else:
            if "priority" not in df.columns:
                df["priority"] = 3
            if "mandatory" not in df.columns:
                df["mandatory"] = False
        
        # Add default `name` column to prevent KeyErrors in UI
        if "name" not in df.columns:
            df["name"] = df["name_ja"] if "name_ja" in df.columns else ""
            
        # Ensure primitive types for seamless frontend/backend integration
        df["initial_cost"] = df["initial_cost"].fillna(0).astype("float64")
        df["monthly_cost"] = df["monthly_cost"].fillna(0).astype("float64")
        df["priority"] = df["priority"].fillna(3).astype("int64")
        df["mandatory"] = df["mandatory"].fillna(False).astype("bool")
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
        set_val("transport", "車メイン", "mandatory", True)
        set_val("transport", "車メイン", "priority", 5)
    elif "B:" in q1a:
        # Optional requirement
        set_val("transport", "車メイン", "mandatory", False)
        set_val("transport", "車メイン", "priority", 3) 
    elif "C:" in q1a:
        # Excluded
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
