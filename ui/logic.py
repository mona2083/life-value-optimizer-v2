import streamlit as st
import pandas as pd
from default_items import CATEGORIES, DEFAULT_ITEMS

def dict_get_or_zero(d, key):
    """Safely get a float value from a dictionary, defaulting to 0.0 if not found or None."""
    res = (d or {}).get(key, 0)
    return float(res) if res is not None else 0.0

def estimate_food_cost(user_profile: dict, lifestyle_data: dict) -> dict:
    """
    推定食費を返す（UI表示はしない）。
    式:
      (世帯人数係数 × 基本単価) × スタイル補正係数 + 外食/QOL加算
    """
    base_unit = 400.0
    child_coeff = 0.7
    infant_coeff = 0.5 

    adults = int(user_profile.get("household_adults", 1) or 0)
    children = int(user_profile.get("household_children", 0) or 0)
    infants = int(user_profile.get("household_infants", 0) or 0)

    # 成人等価人数
    adult_equivalent = adults + children * child_coeff + infants * infant_coeff
    total_headcount = adults + children + infants

    # 世帯規模調整
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

    # 外食・デリバリー QOL 加算（頻度 × トーン）
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

    # ===== 2段階食費モデル =====
    # C_min: Minimalist（最低限）までの"充足"コスト（生存ラインのみ、外食加算なし）
    # C_survey: アンケートの希望水準（home style + dining tone/freq + オプション）
    # C_max: 理論上の最大（home style最大 + 外食最大 + オプション全部ON）
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
