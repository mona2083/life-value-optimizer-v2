import streamlit as st
import pandas as pd

# Local module imports
import ui
from optimizer import run_optimizer
from lang import LANG
from default_items import CATEGORIES, CATEGORY_CONSTRAINTS
from risk_cost import calculate_risk_costs

# New architecture imports
from core.food_calculator import calculate_food_estimate
from core.models import UserProfile, FoodData, FoodEstimate
from state.session import SessionState
from ai.profile_extractor import ProfileExtractor

# =====================================================================
# Initialization and State Management
# =====================================================================
st.set_page_config(page_title="Life-Value Optimizer", page_icon="⚖️", layout="wide")

if "lang" not in st.session_state:
    st.session_state.lang = "en"

# Get translation dictionary
lang = st.session_state.lang
T = LANG[lang]

# Initialize DataFrame for each category (stored in session state)
if "category_dfs" not in st.session_state:
    st.session_state.category_dfs = ui.init_category_dfs()

# =====================================================================
# Sidebar (Language settings and reset)
# =====================================================================
with st.sidebar:
    st.header(f"⚙️ {T.get('sidebar_title', 'Settings')}")
    new_lang = st.radio(
        T.get("sidebar_language", "Language"),
        ["ja", "en"],
        index=0 if lang == "ja" else 1,
        format_func=lambda c: "日本語" if c == "ja" else "English",
    )
    if new_lang != lang:
        st.session_state.lang = new_lang
        st.rerun()

    if st.button(T["reset_btn"]):
        # Clear new state management
        SessionState.clear_all()
        # Clear old state management
        for key in list(st.session_state.keys()):
            if key != "lang":
                del st.session_state[key]
        st.rerun()

st.title(T["title"])
st.caption(T.get("caption", ""))
st.markdown(T["desc"])

# =====================================================================
# Step 0.5: Passion Text Input
# =====================================================================
passion_text = ui.render_passion_text_input(T)

st.divider()

# =====================================================================
# メインフロー（新UI：9つのステップ）
# =====================================================================

# 1. 使える金額の確定 & 2. リスクコスト & 3. 収入見込み & 4. 貯金目標
# （これらは「基本の財務設定」として1つのUI関数にまとめます）
financial_data = ui.render_financial_setup(T)

st.divider()

# 5. 現在のライフスタイル（Q1〜Q5）＋ 5b. 食事・外食（推定食費用）
# 回答は dict として受け取り、後続のアイテム補正・食費推定・LLM推論に使います
lifestyle_data = ui.render_lifestyle_questions(T, lang)
food_data = ui.render_food_questions(T)
lifestyle_data["food"] = food_data

# 食費推定（NEW: Location-aware calculation from new architecture）
# Using the new core/food_calculator which includes location detection
user_profile = financial_data.get("user_profile", {})
passion_text = st.session_state.get("passion_text", "")

# Create FoodData object for the calculator
food_obj = FoodData(
    home_meal_style=food_data.get("home_meal_style", "standard"),
    dining_out_tone=food_data.get("dining_out_tone", "utility"),
    dining_out_frequency=food_data.get("dining_out_frequency", "0_1"),
    optional_alcohol=food_data.get("optional_alcohol", False),
    optional_supplements=food_data.get("optional_supplements", False),
    optional_special_diet=food_data.get("optional_special_diet", False),
)

# Calculate food estimate (includes location adjustment)
# Determine family status from household composition
adults = int(user_profile.get("household_adults", 1) or 1)
children = int(user_profile.get("household_children", 0) or 0)
infants = int(user_profile.get("household_infants", 0) or 0)
total_kids = children + infants

if total_kids > 0:
    family_status = "family_with_kids"
elif adults > 1:
    family_status = "couple"
else:
    family_status = "single"

user_profile_obj = UserProfile(
    age=int(user_profile.get("age", 30) or 30),
    family_status=family_status,
    household_adults=adults,
    household_children=children,
    household_infants=infants,
    debt_repayment=float(user_profile.get("debt_repayment", 0) or 0),
    passion_text=passion_text,
)

food_estimate = calculate_food_estimate(user_profile_obj, food_obj, passion_text)
food_estimation = food_estimate.to_dict()

# Store in both old and new state management for compatibility
SessionState.set_food_estimate(food_estimate)
financial_data["estimated_food_cost"] = food_estimation
st.session_state["estimated_food_cost"] = food_estimation

print(f"🍽️ Food Estimate Calculated:")
print(f"   minimalist_floor_cost: ${food_estimate.minimalist_floor_cost:,.2f}")
print(f"   food_stage1_band_max: ${food_estimate.food_stage1_band_max:,.2f}")
print(f"   food_stage2_band_max: ${food_estimate.food_stage2_band_max:,.2f}")
print(f"   location_adjustment: {food_estimate.location_adjustment}x")

st.divider()

# 6. 価値観のLLM推論（ハイブリッド・プロファイリング）
# Step 5の定型データと、ユーザーの自由記述を合わせてLLMに投げ、スライダーを自動設定します
# Note: ui/lifestyle.py の render_llm_profiling 内で既に estimated_food_cost の処理が行われています
weights_data = ui.render_llm_profiling(T, lang, lifestyle_data, financial_data, food_data=food_data)

st.divider()

# 7. アイテム修正（Optional）
# 裏側で補正されたアイテム一覧を表示し、微調整したいユーザーだけが触る画面
ui.render_item_review(T, lang)

st.divider()

# サマリー表示 & 最適化の実行
st.header(T.get("step89_title", "5. 📊 Summary & optimization"))
st.info(T.get("step89_intro", ""))
use_ai_for_optimize = st.toggle(
    T.get("use_ai_for_optimize", "🤖 AIを使って最適化結果サマリーを作成"),
    value=True,
    key="use_ai_for_optimize",
)

if st.button(T["run_opt_btn"], type="primary", use_container_width=True):
    with st.spinner(T.get("opt_spinner", "Running optimization…")):
        food_info = st.session_state.get("estimated_food_cost") or financial_data.get("estimated_food_cost", {}) or {}
        
        minimalist_floor = float(food_info.get("minimalist_floor_cost", 0) or 0)
        food_stage1_max = int(float(food_info.get("food_stage1_band_max", 0) or 0))
        food_stage2_max = int(float(food_info.get("food_stage2_band_max", 0) or 0))
        
        # If food_stage bands are not in AI estimate, calculate them from minimalist_floor and monthly_food_cost
        if food_stage1_max == 0 or food_stage2_max == 0:
            monthly_food_cost = float(food_info.get("monthly_food_cost", minimalist_floor) or minimalist_floor)
            mid_level_cost = (minimalist_floor + monthly_food_cost) / 2
            food_stage1_max = int(max(0, mid_level_cost - minimalist_floor))
            food_stage2_max = int(max(0, monthly_food_cost - mid_level_cost))
        
        base_monthly_after_food = max(
            0,
            int(financial_data["monthly_budget"]) - int(round(minimalist_floor)),
        )
        optimizer_monthly_budget = base_monthly_after_food
        risk_breakdown = []
        risk_monthly_total = 0

        profile = (financial_data or {}).get("user_profile", {}) or {}
        if profile.get("consider_risk"):
            adults = int(profile.get("household_adults", 1) or 0)
            children = int(profile.get("household_children", 0) or 0)
            infants = int(profile.get("household_infants", 0) or 0)
            num_kids = max(children + infants, 0)

            if num_kids <= 0:
                family_label = "Single" if adults <= 1 else "Couple"
            else:
                family_label = f"Couple + {min(num_kids, 4)} Kid"
                if num_kids >= 2:
                    family_label += "s"

            risk_breakdown = calculate_risk_costs(
                age=int(profile.get("age", 30) or 30),
                family=family_label,
                savings_period_years=int(financial_data.get("savings_period_years", 1) or 1),
                monthly_budget=int(financial_data.get("monthly_budget", 0) or 0),
                car_selected=bool(lifestyle_data.get("own_car")),
            )
            risk_monthly_total = int(
                sum(float(r.get("monthly_cost", 0) or 0) for r in risk_breakdown)
            )
            optimizer_monthly_budget = max(0, base_monthly_after_food - risk_monthly_total)

            st.info(
                f"{T.get('risk_effective', 'Effective monthly budget after risk costs')}: "
                f"${optimizer_monthly_budget:,} "
                f"(base ${base_monthly_after_food:,} - risk ${risk_monthly_total:,})"
            )

        # 最適化エンジンに渡す全候補アイテムのリストを構築
        candidates = []
        for cat, df in st.session_state.category_dfs.items():
            for idx, row in df.iterrows():
                # UI側のセッションステート（スライダー等の値）から最新の状態を取得
                pri = st.session_state.get(f"priority_{cat}_{idx}", row["priority"])
                mand = st.session_state.get(f"mandatory_{cat}_{idx}", row["mandatory"])
                ic = st.session_state.get(f"initial_cost_{cat}_{idx}", row["initial_cost"])
                mc = st.session_state.get(f"monthly_cost_{cat}_{idx}", row["monthly_cost"])
                
                # 優先度0は除外。ただし必須指定は候補に残す
                if pri > 0 or mand:
                    candidates.append({
                        "id": f"{cat}_{idx}",
                        "name": row["name"],
                        "name_ja": row.get("name_ja", row["name"]),
                        "name_en": row.get("name_en", row["name"]),
                        "category": cat,
                        "priority": pri,
                        "mandatory": mand,
                        "initial_cost": int(ic),  # Ensure integer
                        "monthly_cost": int(mc),  # Ensure integer
                        "health": row["health"],
                        "connections": row["connections"],
                        "freedom": row["freedom"],
                        "growth": row["growth"],
                        "source": row.get("source", "default")  # Preserve source field
                    })

        result = None
        if not candidates:
            st.warning(
                T.get(
                    "opt_no_candidates",
                    "候補アイテムがありません。Step 4 で少なくとも1件、優先度を1以上にするか必須にしてください。",
                )
            )
        else:
            weights_core = {
                "health": int(weights_data["health"]),
                "connections": int(weights_data["connections"]),
                "freedom": int(weights_data["freedom"]),
                "growth": int(weights_data["growth"]),
                "savings": int(weights_data["savings"]),
                "food": int(weights_data.get("food", 5)),
            }
            tb = int(financial_data["initial_budget"])
            tms = int(financial_data["target_monthly_savings"])

            def _run_opt(items, fs1, fs2, require_transport: bool):
                return run_optimizer(
                    items=items,
                    total_budget=tb,
                    monthly_budget=optimizer_monthly_budget,
                    target_monthly_savings=tms,
                    weights=weights_core,
                    food_stage1_max=fs1,
                    food_stage2_max=fs2,
                    require_transport=require_transport,
                )

            mandatory_ids = [c["id"] for c in candidates if c.get("mandatory")]
            working = candidates
            mandatory_relaxed_applied = False

            result = _run_opt(working, food_stage1_max, food_stage2_max, True)

            if result.get("status") != "ok" and mandatory_ids:
                working = []
                for c in candidates:
                    cc = dict(c)
                    if cc.get("id") in mandatory_ids:
                        cc["mandatory"] = False
                        cc["priority"] = max(int(cc.get("priority", 0)), 10)
                    working.append(cc)
                mandatory_relaxed_applied = True
                result = _run_opt(working, food_stage1_max, food_stage2_max, True)

            if result.get("status") != "ok":
                result = _run_opt(working, 0, 0, True)
                if result.get("status") == "ok":
                    result["best_effort_zero_food_stages"] = True

            if result.get("status") != "ok":
                result = _run_opt(working, 0, 0, False)
                if result.get("status") == "ok":
                    result["best_effort_transport_optional"] = True

            if (
                result.get("status") == "ok"
                and mandatory_relaxed_applied
                and mandatory_ids
            ):
                selected_ids = {it.get("id") for it in result.get("selected", [])}
                missed_ids = [mid for mid in mandatory_ids if mid not in selected_ids]
                id_to_item = {c["id"]: c for c in candidates}
                missed_items = [id_to_item[mid] for mid in missed_ids if mid in id_to_item]
                result["best_effort_mandatory_relaxed"] = True
                result["relaxed_mandatory_count"] = len(mandatory_ids)
                result["missed_mandatory_count"] = len(missed_ids)
                result["missed_mandatory_items"] = missed_items

        # 結果の描画（AIライフコーチダッシュボード含む）
        if result is not None:
            ui.render_risk_and_results(
                result,
                financial_data["user_profile"],
                weights_data,
                T,
                lang,
                use_ai_for_summary=use_ai_for_optimize,
                financial_data={
                    **financial_data,
                    "lifestyle_data": lifestyle_data,
                    "food_data": food_data,
                    "candidates": candidates,
                    "monthly_budget": optimizer_monthly_budget,
                    "original_monthly_budget": financial_data.get("monthly_budget", 0),
                    "monthly_budget_before_risk": base_monthly_after_food,
                    "risk_monthly_total": risk_monthly_total,
                    "risk_monthly_breakdown": risk_breakdown,
                    "food_minimalist_floor": minimalist_floor,
                    "food_stage1_cap": food_stage1_max,
                    "food_stage2_cap": food_stage2_max,
                },
            )