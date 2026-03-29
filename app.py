import streamlit as st
import pandas as pd

# ローカルモジュールのインポート
import ui
from optimizer import run_optimizer
from lang import LANG
from default_items import CATEGORIES, CATEGORY_CONSTRAINTS
from risk_cost import calculate_risk_costs

# =====================================================================
# 初期設定・状態管理
# =====================================================================
st.set_page_config(page_title="Life-Value Optimizer", page_icon="⚖️", layout="wide")

if "lang" not in st.session_state:
    st.session_state.lang = "ja"

# 翻訳辞書の取得
lang = st.session_state.lang
T = LANG[lang]

# カテゴリごとのDataFrame初期化（セッションステートで保持）
if "category_dfs" not in st.session_state:
    st.session_state.category_dfs = ui.init_category_dfs()

# =====================================================================
# サイドバー（言語設定・リセット）
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
        for key in list(st.session_state.keys()):
            if key != "lang":
                del st.session_state[key]
        st.rerun()

st.title(T["title"])
st.caption(T.get("caption", ""))
st.markdown(T["desc"])

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

# 食費推定（UI表示はしない。後続のロジック連携用に保持）
food_estimation = ui.estimate_food_cost(financial_data["user_profile"], lifestyle_data)
financial_data["estimated_food_cost"] = food_estimation
st.session_state["estimated_food_cost"] = food_estimation

st.divider()

# 6. 価値観のLLM推論（ハイブリッド・プロファイリング）
# Step 5の定型データと、ユーザーの自由記述を合わせてLLMに投げ、スライダーを自動設定します
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
        food_info = financial_data.get("estimated_food_cost", {}) or {}
        minimalist_floor = float(food_info.get("minimalist_floor_cost", 0) or 0)
        food_stage1_max = int(float(food_info.get("food_stage1_band_max", 0) or 0))
        food_stage2_max = int(float(food_info.get("food_stage2_band_max", 0) or 0))
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
                        "initial_cost": ic,
                        "monthly_cost": mc,
                        "health": row["health"],
                        "connections": row["connections"],
                        "freedom": row["freedom"],
                        "growth": row["growth"]
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