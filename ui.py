import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from default_items import CATEGORIES, DEFAULT_ITEMS
# ※ llm.py がOpenAIに変わるまでは既存のGemini関数を呼び出します
from llm import (
    food_weight_from_jelly,
    get_result_summary,
    get_user_profile,
    infer_weights_from_survey,
)
from optimizer import food_related_score

# =====================================================================
# Food Cost Estimation (no-UI helper)
# =====================================================================
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
    # C_min: Minimalist（最低限）までの“充足”コスト（ここでは QOL加算は希望水準のまま反映）
    # C_survey: アンケートの希望水準（home style + dining tone/freq + オプション）
    # C_max: 理論上の最大（home style最大 + 外食最大 + オプション全部ON）
    minimalist_floor = base_component * 0.75 + qol_add
    estimated = (base_component * style_coeff) + qol_add  # C_survey

    max_style_coeff = 1.45
    max_qol_add = 45.0 * 3.2 * (4.0 / 1.5) + 35.0 + 35.0 + 45.0
    max_possible = (base_component * max_style_coeff) + max_qol_add  # C_max

    # Stage1: C_min -> C_survey
    food_stage1_band_max = max(0.0, estimated - minimalist_floor)
    # Stage2: C_survey -> C_max
    food_stage2_band_max = max(0.0, max_possible - estimated)

    return {
        "estimated_monthly_food_cost": round(estimated, 2),
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

# =====================================================================
# 初期化関数（app.pyから呼ばれる）
# =====================================================================
def init_category_dfs():
    """DEFAULT_ITEMSをカテゴリごとのDataFrameに変換して初期化"""
    dfs = {}
    for cat_key in CATEGORIES["en"].keys():
        items = [item for item in DEFAULT_ITEMS if item["category"] == cat_key]
        processed = []
        for it in items:
            processed.append({
                "name_ja": it["name_ja"],
                "name_en": it["name_en"],
                "name": it["name_ja"], # デフォルト表示用
                "initial_cost": it["initial_cost"],
                "monthly_cost": it["monthly_cost"],
                "health": it.get("health", 0),
                "connections": it.get("connections", 0),
                "freedom": it.get("freedom", 0),
                "growth": it.get("growth", 0),
                "priority": it.get("priority", 3),
                "mandatory": False # 初期状態では必須アイテムはなし
            })
        dfs[cat_key] = pd.DataFrame(processed)
    return dfs

# =====================================================================
# 動的アイテム補正ロジック（ライフスタイル Q1〜Q5）
# =====================================================================
def apply_dynamic_overrides(lifestyle_data):
    """回答に基づいてSessionState上のアイテムのコストや優先度を書き換える"""
    dfs = st.session_state.category_dfs
    
    def set_val(cat, name_ja, key_prefix, value):
        if cat in dfs:
            idx_list = dfs[cat].index[dfs[cat]['name_ja'] == name_ja].tolist()
            if idx_list:
                idx = idx_list[0]
                state_key = f"{key_prefix}_{cat}_{idx}"
                # ユーザーが手動で変更した項目は自動上書きしない
                if st.session_state.get(f"manual_{state_key}", False):
                    return
                st.session_state[state_key] = value

    # Q1: 車と移動
    q1a = lifestyle_data.get("car_necessity", "")
    if "A:" in q1a:
        # 【必須】にする
        set_val("transport", "車メイン", "mandatory", True)
        set_val("transport", "車メイン", "priority", 5)
    elif "B:" in q1a:
        # 【任意】にする（ここが抜けていました）
        set_val("transport", "車メイン", "mandatory", False)
        set_val("transport", "車メイン", "priority", 3) 
    elif "C:" in q1a:
        # 【除外】にする
        set_val("transport", "車メイン", "mandatory", False)
        set_val("transport", "車メイン", "priority", 0)
        
    # Q2: 所有状況による初期費用$0化
    if lifestyle_data.get("own_car"):
        set_val("transport", "車メイン", "initial_cost", 0)
    if lifestyle_data.get("own_ebike"):
        set_val("transport", "電動自転車＋Uber", "initial_cost", 0)
    if lifestyle_data.get("own_bike"):
        set_val("transport", "自転車のみ", "initial_cost", 0)
        set_val("transport", "カーシェア＋自転車", "initial_cost", 0)
    if lifestyle_data.get("own_moto"):
        # バイクメインアイテムが追加されている前提
        set_val("transport", "バイクメイン", "initial_cost", 0)

    # Q3: 働き方
    q2 = lifestyle_data.get("work_style", "")
    if "A:" in q2: # リモート
        set_val("living", "エルゴノミクスチェア", "priority", 5)
    elif "C:" in q2: # 出社
        set_val("living", "エルゴノミクスチェア", "priority", 0)

    # Q4: 交際
    q4 = lifestyle_data.get("social", "")
    if "A:" in q4: # 頻繁
        set_val("leisure", "交際費・飲み代", "monthly_cost", 225) # 飲み代1.5倍
    elif "C:" in q4: # 一人が好き
        set_val("leisure", "交際費・飲み代", "priority", 0)
        set_val("learning", "本・電子書籍・Audible", "priority", 5)

    # Q5: 余暇
    q5 = lifestyle_data.get("leisure", "")
    if "A:" in q5: # インドア
        set_val("leisure", "ゲーム", "priority", 5)
        set_val("leisure", "動画・音楽サブスク", "priority", 5)
        set_val("leisure", "アウトドア・スポーツ", "priority", 0)
    elif "B:" in q5: # アウトドア
        set_val("leisure", "アウトドア・スポーツ", "priority", 5)
        set_val("wellbeing", "旅行・リトリート積立", "priority", 5)
    elif "C:" in q5: # お出かけ
        set_val("leisure", "映画・観劇・美術館", "priority", 5)
        set_val("leisure", "推し活・ファンコミュニティ", "priority", 5)


def apply_food_overrides(food_data: dict) -> None:
    """食事スタイルに基づく living カテゴリの自動補正（手動編集は上書きしない）。"""
    dfs = st.session_state.category_dfs

    def set_val(cat, name_ja, key_prefix, value):
        if cat in dfs:
            idx_list = dfs[cat].index[dfs[cat]["name_ja"] == name_ja].tolist()
            if idx_list:
                idx = idx_list[0]
                state_key = f"{key_prefix}_{cat}_{idx}"
                if st.session_state.get(f"manual_{state_key}", False):
                    return
                st.session_state[state_key] = value

    style = (food_data or {}).get("home_meal_style", "standard")
    if style == "minimalist":
        set_val("living", "コーヒー・カフェ代", "monthly_cost", 30)
        set_val("leisure", "外飲み・バー（週1〜2回）", "priority", 0)
    elif style == "time_saving":
        set_val("living", "時短家電（食洗機・ルンバ等）", "priority", 5)
        set_val("leisure", "交際費・飲み代", "monthly_cost", 200)
    elif style == "health_conscious":
        set_val("wellbeing", "サプリメント・健康食品", "priority", 4)
        set_val("leisure", "宅飲み・ワイン/クラフトビール", "priority", 0)


# =====================================================================
# Step 1: お金とリスクの設定
# =====================================================================
def render_financial_setup(T):
    st.header(T.get("step1_title", "1. 💰 予算と目標の設定"))

    with st.container(border=True):
        st.subheader(T.get("section_budget", "💵 Monthly budget"))
        know_budget = st.radio(
            T.get("know_budget_q", ""),
            [T.get("yes_calc", "Yes"), T.get("no_calc", "No")],
        )

        monthly_budget = 0
        if know_budget == T.get("yes_calc", ""):
            monthly_budget = st.number_input(
                T.get("budget_label", "Monthly budget ($)"),
                min_value=0,
                value=1500,
                step=100,
            )
        else:
            with st.expander(T.get("calc_expander", ""), expanded=True):
                income = st.number_input(T.get("income_label", ""), value=4000, step=100)
                st.markdown(f"**{T.get('calc_fixed_subheading', '')}**")
                col_l, col_r = st.columns(2)
                with col_l:
                    rent_util = st.number_input(
                        T.get("lbl_rent_util", ""),
                        min_value=0,
                        value=1700,
                        step=50,
                    )
                    insurance = st.number_input(
                        T.get("lbl_insurance", ""),
                        min_value=0,
                        value=200,
                        step=50,
                    )
                with col_r:
                    telecom = st.number_input(
                        T.get("lbl_telecom", ""),
                        min_value=0,
                        value=120,
                        step=10,
                    )
                    other_fixed = st.number_input(
                        T.get("lbl_other_fixed", ""),
                        min_value=0,
                        value=300,
                        step=50,
                    )
                monthly_budget = income - (rent_util + insurance + telecom + other_fixed)
                st.info(f"**{T.get('calc_result', '')}:** ${monthly_budget}")

        initial_budget = st.number_input(
            T.get("initial_budget_label", ""),
            min_value=0,
            value=5000,
            step=500,
        )

    st.divider()

    with st.container(border=True):
        st.subheader(T.get("section_profile", ""))
        consider_risk = st.toggle(T.get("risk_toggle", ""), value=False)
        st.caption(T.get("risk_household_caption", ""))
        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input(
                T.get("lbl_age", ""),
                min_value=0,
                max_value=120,
                value=30,
                step=1,
            )
            adults = st.number_input(
                T.get("lbl_adults", ""),
                min_value=0,
                value=1,
                step=1,
            )
        with col2:
            children = st.number_input(
                T.get("lbl_children", ""),
                min_value=0,
                value=0,
                step=1,
            )
            infants = st.number_input(
                T.get("lbl_infants", ""),
                min_value=0,
                value=0,
                step=1,
            )

    family = T.get("family_summary_fmt", "").format(
        adults=int(adults),
        children=int(children),
        infants=int(infants),
    )

    st.divider()

    with st.container(border=True):
        st.subheader(T.get("goals_subdir", "🎯 Goals"))
        col3, col4 = st.columns(2)
        with col3:
            target_total_savings = st.number_input(
                T.get("target_total_label", ""),
                min_value=0,
                value=18000,
                step=1000,
            )
        with col4:
            savings_period_years = st.number_input(
                T.get("period_label", ""),
                min_value=1,
                value=5,
            )

    # 内部で毎月の必要貯金額を計算（オプティマイザーに渡すため）
    target_monthly_savings = target_total_savings / (savings_period_years * 12) if savings_period_years > 0 else 0

    return {
        "monthly_budget": max(0, monthly_budget),
        "initial_budget": initial_budget,
        "target_total_savings": target_total_savings,
        "target_monthly_savings": target_monthly_savings,
        "savings_period_years": savings_period_years,
        "user_profile": {
            "age": age,
            "family": family,
            "consider_risk": consider_risk,
            "household_adults": int(adults),
            "household_children": int(children),
            "household_infants": int(infants),
        }
    }

# =====================================================================
# Step 2: 現在の生活ヒアリング（定型質問：ハードファクト）
# =====================================================================
def render_lifestyle_questions(T, lang):
    st.header(T.get("step2_title", "2. 👤 Current lifestyle"))
    st.markdown(T.get("step2_desc", ""))
    st.markdown(
        """
        <style>
        [data-testid="stCheckbox"] {
            margin-bottom: -0.2rem;
        }
        [data-testid="stCheckbox"] label p {
            margin: 0;
            line-height: 1;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    q1a_opts = T.get("lifestyle_q1_options", [])
    q2_opts = T.get("lifestyle_q_work_options", [])
    q4_opts = T.get("lifestyle_q_social_options", [])
    q5_opts = T.get("lifestyle_q_leisure_options", [])

    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        with st.container(border=True):
            q1a = st.radio(
                T.get("q_car_necessity", "Q1. 現在のお住まいや生活において、車は必須ですか？"),
                q1a_opts,
                index=1,
                key="q_step2_car_necessity",
            )
    with row1_col2:
        with st.container(border=True):
            st.write(T.get("q_own_transport", "Q2. 現在所有している移動手段はありますか？（複数選択可）"))
            c1, c2, c3 = st.columns(3)
            with c1:
                own_car = st.checkbox("🚗 " + T.get("own_car", "Car"), key="q_step2_own_car")
                own_moto = st.checkbox("🏍️ " + T.get("own_moto", "Motorcycle"), key="q_step2_own_moto")
            with c2:
                own_ebike = st.checkbox("⚡ " + T.get("own_ebike", "E-bike"), key="q_step2_own_ebike")
                own_none = st.checkbox("🚶 " + T.get("own_none", "None"), key="q_step2_own_none")
            with c3:
                own_bike = st.checkbox("🚲 " + T.get("own_bike", "Bicycle"), key="q_step2_own_bike")

    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        with st.container(border=True):
            q2 = st.radio(
                T.get("q_work_style", "Q3. 現在の働き方はどれに一番近いですか？"),
                q2_opts,
                index=1,
                key="q_step2_work_style",
            )
    with row2_col2:
        with st.container(border=True):
            q4 = st.radio(
                T.get("q_social", "Q4. 人付き合いや、飲み会などの頻度はどのくらいですか？"),
                q4_opts,
                index=1,
                key="q_step2_social",
            )

    with st.container(border=True):
        q5 = st.radio(
            T.get("q_leisure", "Q5. 休日の主な過ごし方（余暇のスタイル）はどれに一番近いですか？"),
            q5_opts,
            index=1,
            key="q_step2_leisure",
        )

    lifestyle_data = {
        "car_necessity": q1a,
        "own_car": own_car, "own_ebike": own_ebike, "own_bike": own_bike, "own_moto": own_moto,
        "work_style": q2, "social": q4, "leisure": q5,
    }

    # 裏側でアイテムの初期費用や優先度を魔法のように書き換える（APIコスト$0ロジック）
    apply_dynamic_overrides(lifestyle_data)

    return lifestyle_data


# =====================================================================
# Step 2b: 食事・外食（推定食費・補正ロジック用）
# =====================================================================
def render_food_questions(T):
    st.header(T.get("step_food_title", "2b. 🍽️ Food"))
    st.caption(T.get("step_food_intro", ""))
    st.markdown(
        """
        <style>
        [data-testid="stCheckbox"] {
            margin-bottom: -0.2rem;
        }
        [data-testid="stCheckbox"] label p { margin: 0; line-height: 1.15; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --- 自宅での食事の質（ベース単価係数は estimate_food_cost 側）---
    home_labels = [
        T.get("food_home_minimalist", ""),
        T.get("food_home_standard", ""),
        T.get("food_home_health", ""),
        T.get("food_home_time", ""),
    ]
    home_keys = ["minimalist", "standard", "health_conscious", "time_saving"]

    freq_labels = [
        T.get("food_freq_01", ""),
        T.get("food_freq_23", ""),
        T.get("food_freq_4p", ""),
    ]
    freq_keys = ["0_1", "2_3", "4_plus"]

    tone_labels = [
        T.get("food_tone_utility", ""),
        T.get("food_tone_casual", ""),
        T.get("food_tone_experience", ""),
    ]
    tone_keys = ["utility", "casual", "experience"]

    # Q1 左カラム / Q2 右カラム
    col_q1, col_q2 = st.columns(2)
    with col_q1:
        with st.container(border=True):
            home_idx = home_labels.index(
                st.radio(
                    T.get("food_q1", ""),
                    home_labels,
                    index=1,
                    key="food_home_meal_style_radio",
                )
            )
            home_meal_style = home_keys[home_idx]
    with col_q2:
        with st.container(border=True):
            fi = freq_labels.index(
                st.radio(
                    T.get("food_q2", ""),
                    freq_labels,
                    index=0,
                    key="food_dining_freq_radio",
                )
            )
            dining_out_frequency = freq_keys[fi]

    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        with st.container(border=True):
            ti = tone_labels.index(
                st.radio(
                    T.get("food_q3", ""),
                    tone_labels,
                    index=1,
                    key="food_dining_tone_radio",
                )
            )
            dining_out_tone = tone_keys[ti]

    # --- 嗜好品・特定支出 ---
    with row2_col2:
        with st.container(border=True):
            st.write(T.get("food_q4", ""))
            opt_alcohol = st.checkbox(
                T.get("food_opt_alcohol", ""),
                key="food_opt_alcohol",
            )
            opt_supp = st.checkbox(
                T.get("food_opt_supp", ""),
                key="food_opt_supp",
            )
            opt_diet = st.checkbox(
                T.get("food_opt_diet", ""),
                key="food_opt_diet",
            )

    food_data = {
        "home_meal_style": home_meal_style,
        "dining_out_frequency": dining_out_frequency,
        "dining_out_tone": dining_out_tone,
        "optional_alcohol": opt_alcohol,
        "optional_supplements": opt_supp,
        "optional_special_diet": opt_diet,
    }
    apply_food_overrides(food_data)
    return food_data


# =====================================================================
# Step 3: 価値観のLLM推論（心理テスト＆自由記述ハイブリッド）
# =====================================================================
def render_llm_profiling(T, lang, lifestyle_data, financial_data, food_data=None):
    st.header(T.get("step3_title", "3. 🧠 Values"))
    st.markdown(T.get("step3_desc", ""))

    st.subheader(T.get("step3_part1_sub", "🧘 Value Discovery — Part 1"))

    q_time_opts = list(T.get("values_q_time_options", []))
    q_risk_opts = list(T.get("values_q_risk_options", []))
    q_live_opts = list(T.get("values_q_live_options", []))
    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        with st.container(border=True):
            q_time = st.radio(
                T.get("q_time_deploy", "Q1. もし来週、予期せぬ3日間の休暇と自由な$500が与えられたら？"),
                q_time_opts,
                index=0,
                key="q_step3_time",
            )
    with row1_col2:
        with st.container(border=True):
            q_risk = st.radio(
                T.get("q_risk_deploy", "Q2. 生活費が1.2倍になりました。『最後まで削りたくない』のは？"),
                q_risk_opts,
                index=2,
                key="q_step3_risk",
            )

    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        with st.container(border=True):
            q_live = st.radio(
                T.get("q_live_deploy", "Q3. あなたが最も『生きてる実感』を覚える瞬間は？"),
                q_live_opts,
                index=0,
                key="q_step3_live",
            )
    with row2_col2:
        st.empty()

    st.subheader(T.get("step3_part2_sub", "🧘 Value Discovery — Part 2"))

    q_jelly_opts = [
        T.get("q_jelly_a", ""),
        T.get("q_jelly_b", ""),
        T.get("q_jelly_c", ""),
        T.get("q_jelly_d", ""),
    ]
    with st.container(border=True):
        q_jelly = st.radio(
            T.get("q_jelly_deploy", ""),
            q_jelly_opts,
            index=1,
            key="q_step3_jelly",
        )
    if st.session_state.get("_prev_q_step3_jelly") != q_jelly:
        fv = food_weight_from_jelly(q_jelly)
        st.session_state.w_food = fv
        st.session_state.val_food = fv
        st.session_state._prev_q_step3_jelly = q_jelly

    with st.container(border=True):
        st.write(T.get("freetext_q5_intro", ""))
        free_text = st.text_area(
            T.get("freetext_label", "自由記述 (譲れないこだわり)"),
            height=170,
            placeholder=T.get("freetext_placeholder", "例：健康のために自炊はしたいが、移動の自由（車）は絶対に譲れない..."),
            key="q_step3_freetext",
        )

    # セッションステートの初期化（スライダー用：未入力時はオール5、食はQ4ゼリー回答で上書き）
    for key in ["w_health", "w_connections", "w_freedom", "w_growth", "w_savings", "w_food"]:
        if key not in st.session_state:
            st.session_state[key] = 5
    _val_keys = ("val_health", "val_conn", "val_free", "val_grow", "val_save", "val_food")
    _w_keys = ("w_health", "w_connections", "w_freedom", "w_growth", "w_savings", "w_food")
    for vk, wk in zip(_val_keys, _w_keys):
        if vk not in st.session_state:
            st.session_state[vk] = st.session_state[wk]

    def _apply_weights_to_sliders(weights: dict) -> None:
        pairs = [
            ("health", "w_health", "val_health"),
            ("connections", "w_connections", "val_conn"),
            ("freedom", "w_freedom", "val_free"),
            ("growth", "w_growth", "val_grow"),
            ("savings", "w_savings", "val_save"),
            ("food", "w_food", "val_food"),
        ]
        for field, wk, vk in pairs:
            v = max(1, min(10, int(weights.get(field, 5))))
            st.session_state[wk] = v
            st.session_state[vk] = v

    st.divider()
    col1, col2 = st.columns([1, 1])
    with col2:
        use_ai_for_values = st.toggle(
            T.get("use_ai_for_values", "🤖 AIを使って価値観を反映"),
            value=True,
            key="use_ai_for_values",
        )
    with col1:
        analyze_btn = st.button(
            T.get("reflect_to_slider_btn", "✨ 価値観をスライダーに反映"),
            type="primary",
            use_container_width=True,
        )

    if analyze_btn:
        with st.spinner(T.get("analyzing", "プロファイリング中...")):
            # 定型回答と自由記述、基本情報をすべてガッチャンコしてLLMに投げる
            combined_data = {
                "lifestyle_fact": lifestyle_data,  # Q1〜Q5（ハードファクト）＋ food
                "food_fact": food_data or lifestyle_data.get("food"),
                "financial_goal": financial_data,  # 予算、目標、リスク設定
                "value_quiz": {
                    "q_time": q_time,
                    "q_risk": q_risk,
                    "q_live": q_live,
                    "q_jelly": q_jelly,
                },
                "passion_free_text": free_text,  # 自由記述（熱量）
            }
            # strに変換してプロンプトへ
            combined_info_str = str(combined_data)
            
            if use_ai_for_values:
                # llm.py を呼び出し（OpenAIへの移行が終わるまではGemini版を使用します）
                user_profile = financial_data["user_profile"]
                profile_result = get_user_profile(user_profile["age"], user_profile["family"], combined_info_str, lang)

                if profile_result:
                    _apply_weights_to_sliders(profile_result)
                    st.success(T.get("analysis_success", "AIがあなたの深層価値観を推論しました！下のスライダーで最終調整してください。"))
                else:
                    fallback = infer_weights_from_survey(
                        lifestyle_data,
                        financial_data,
                        {
                            "q_time": q_time,
                            "q_risk": q_risk,
                            "q_live": q_live,
                            "q_jelly": q_jelly,
                        },
                        free_text=free_text,
                        food_data=food_data,
                    )
                    _apply_weights_to_sliders(fallback)
                    st.warning(T.get("analysis_fallback", ""))
            else:
                fallback = infer_weights_from_survey(
                    lifestyle_data,
                    financial_data,
                    {"q_time": q_time, "q_risk": q_risk, "q_live": q_live},
                    free_text=free_text,
                    food_data=food_data,
                )
                _apply_weights_to_sliders(fallback)
                st.info(T.get("analysis_manual_mode", "AIを使わず、回答内容から推定して反映しました。"))

    st.divider()
    st.subheader(T.get("w_subdir", "⚖️ Value weights"))
    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        w_health = st.slider(T.get("w_health", "健康"), 1, 10, st.session_state.w_health, key="val_health")
    with r1c2:
        w_conn = st.slider(T.get("w_connections", "つながり"), 1, 10, st.session_state.w_connections, key="val_conn")
    with r1c3:
        w_free = st.slider(T.get("w_freedom", "自由"), 1, 10, st.session_state.w_freedom, key="val_free")
    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1:
        w_grow = st.slider(T.get("w_growth", "成長"), 1, 10, st.session_state.w_growth, key="val_grow")
    with r2c2:
        w_save = st.slider(T.get("w_savings", "貯蓄"), 1, 10, st.session_state.w_savings, key="val_save")
    with r2c3:
        w_food = st.slider(T.get("w_food", "食"), 1, 10, st.session_state.w_food, key="val_food")

    return {
        "health": w_health,
        "connections": w_conn,
        "freedom": w_free,
        "growth": w_grow,
        "savings": w_save,
        "food": w_food,
    }

# =====================================================================
# Step 4: アイテム修正（Optional）
# =====================================================================
def render_item_review(T, lang):
    st.header(T.get("step4_title", "4. ⚙️ Items"))

    def _mark_manual(key_name: str) -> None:
        st.session_state[f"manual_{key_name}"] = True

    with st.expander(T.get("item_review_expander", "")):
        st.info(T.get("item_review_info", ""))

        st.subheader(T.get("add_custom_item_title", ""))
        with st.form("add_custom_item_form", clear_on_submit=True):
            f1, f2, f3 = st.columns(3)
            with f1:
                cat_options = list(CATEGORIES[lang].items())
                cat_labels = [name for _, name in cat_options]
                selected_cat_label = st.selectbox(
                    T.get("form_category", "Category"),
                    cat_labels,
                )
            with f2:
                item_name = st.text_input(T.get("form_item_name", ""))
            with f3:
                priority_new = st.slider(T.get("form_priority", "Priority"), 0, 10, 3)

            c1, c2 = st.columns(2)
            with c1:
                initial_cost_new = st.number_input(
                    T.get("form_initial", ""),
                    min_value=0,
                    value=0,
                    step=50,
                )
            with c2:
                monthly_cost_new = st.number_input(
                    T.get("form_monthly", ""),
                    min_value=0,
                    value=0,
                    step=10,
                )

            v1, v2, v3, v4 = st.columns(4)
            with v1:
                health_new = st.slider(T.get("form_health", ""), -10, 10, 0)
            with v2:
                conn_new = st.slider(T.get("form_connections", ""), -10, 10, 0)
            with v3:
                free_new = st.slider(T.get("form_freedom", ""), -10, 10, 0)
            with v4:
                grow_new = st.slider(T.get("form_growth", ""), -10, 10, 0)

            submit_add = st.form_submit_button(
                T.get("form_submit_add", "Add"),
                use_container_width=True,
            )

            if submit_add:
                if not item_name.strip():
                    st.warning(T.get("warn_item_name_required", ""))
                else:
                    cat_key = next((k for k, v in CATEGORIES[lang].items() if v == selected_cat_label), None)
                    if cat_key is None:
                        st.error(T.get("err_category_resolve", ""))
                    else:
                        new_row = {
                            "name_ja": item_name.strip() if lang == "ja" else item_name.strip(),
                            "name_en": item_name.strip() if lang == "en" else item_name.strip(),
                            "name": item_name.strip(),
                            "initial_cost": int(initial_cost_new),
                            "monthly_cost": int(monthly_cost_new),
                            "health": int(health_new),
                            "connections": int(conn_new),
                            "freedom": int(free_new),
                            "growth": int(grow_new),
                            "priority": int(priority_new),
                            "mandatory": False,
                        }
                        st.session_state.category_dfs[cat_key] = pd.concat(
                            [st.session_state.category_dfs[cat_key], pd.DataFrame([new_row])],
                            ignore_index=True,
                        )
                        st.success(T.get("success_item_added", ""))
                        st.rerun()

        st.divider()
        st.subheader(T.get("item_list_subheader", ""))
        cat_items = list(CATEGORIES[lang].items())
        cat_tabs = st.tabs([cat_name for _, cat_name in cat_items])

        for tab, (cat_key, cat_name) in zip(cat_tabs, cat_items):
            with tab:
                df = st.session_state.category_dfs[cat_key]

                for idx, row in df.iterrows():
                    # 動的補正されたSessionState上の値を初期値として表示
                    pri_key = f"priority_{cat_key}_{idx}"
                    mc_key = f"monthly_cost_{cat_key}_{idx}"
                    ic_key = f"initial_cost_{cat_key}_{idx}"
                    mand_key = f"mandatory_{cat_key}_{idx}"

                    # SessionStateに無ければDataFrameの値を入れる（リセット時の対策）
                    if pri_key not in st.session_state:
                        st.session_state[pri_key] = row["priority"]
                    if mc_key not in st.session_state:
                        st.session_state[mc_key] = row["monthly_cost"]
                    if ic_key not in st.session_state:
                        st.session_state[ic_key] = row["initial_cost"]
                    if mand_key not in st.session_state:
                        st.session_state[mand_key] = row["mandatory"]

                    c0, c1, c2, c3 = st.columns([0.7, 2, 1, 1])
                    with c0:
                        is_mandatory = st.checkbox(
                            T.get("mandatory_label", "必須"),
                            key=mand_key,
                            on_change=_mark_manual,
                            args=(mand_key,),
                        )
                        # 必須指定時に除外状態にならないよう最低優先度を担保
                        if is_mandatory and st.session_state.get(pri_key, 0) <= 0:
                            st.session_state[pri_key] = 1
                    with c1:
                        lbl = f"{row['name']} {T.get('item_slider_suffix', '')}"
                        if st.session_state[mand_key]:
                            st.caption("✅ " + T.get("item_slider_caption_mandatory", ""))
                        st.slider(lbl, 0, 10, key=pri_key, on_change=_mark_manual, args=(pri_key,))
                    with c2:
                        st.number_input(T.get("lbl_mc", "月額 $"), min_value=0, key=mc_key, on_change=_mark_manual, args=(mc_key,))
                    with c3:
                        st.number_input(T.get("lbl_ic", "初期 $"), min_value=0, key=ic_key, on_change=_mark_manual, args=(ic_key,))

# =====================================================================
# 結果表示・AIライフコーチ描画
# =====================================================================
def render_risk_and_results(
    result,
    user_profile,
    weights,
    T,
    lang,
    use_ai_for_summary=True,
    financial_data=None,
):
    if not result or result.get("status") != "ok":
        st.error(T.get("opt_fail", ""))
        return

    if result.get("best_effort_mandatory_relaxed"):
        st.success(T.get("best_effort_mandatory_ok", ""))
        st.warning(
            T.get("best_effort_mandatory_warn", "").format(
                relaxed=int(result.get("relaxed_mandatory_count", 0)),
                missed=int(result.get("missed_mandatory_count", 0)),
            )
        )
        missed_items = result.get("missed_mandatory_items", [])
        if missed_items:
            st.markdown(f"**{T.get('missed_mandatory_heading', '')}**")
            for item in missed_items:
                name = item.get("name_ja") if lang == "ja" else item.get("name_en")
                if not name:
                    name = item.get("name", item.get("id", ""))
                st.markdown(f"- {name}")
    else:
        st.success(T.get("opt_success", ""))

    if result.get("best_effort_zero_food_stages"):
        st.info(
            T.get(
                "opt_best_effort_zero_food",
                "ベストエフォート: 食費の可変枠（Stage1/2）を0にして再計算しました。",
            )
        )
    if result.get("best_effort_transport_optional"):
        st.info(
            T.get(
                "opt_best_effort_transport",
                "ベストエフォート: 「移動手段を1つ選ぶ」制約を外して再計算しました（移動ゼロも許容）。",
            )
        )

    # -----------------------------------------------------------------
    # 非AIの実行ダッシュボード（最適化結果の直後に表示）
    # -----------------------------------------------------------------
    st.subheader(T.get("dash_exec_title", ""))

    selected = result.get("selected", [])
    monthly_budget = float((financial_data or {}).get("monthly_budget", 0) or 0)
    initial_budget = float((financial_data or {}).get("initial_budget", 0) or 0)
    food_floor = float((financial_data or {}).get("food_minimalist_floor", 0) or 0)
    food_info = (financial_data or {}).get("estimated_food_cost", {}) or {}
    food_stage1_cap = float((financial_data or {}).get("food_stage1_cap", 0) or 0)
    food_stage2_cap = float((financial_data or {}).get("food_stage2_cap", 0) or 0)
    food_stage1_used = float(result.get("food_stage1_monthly_cost", 0) or 0)
    food_stage2_used = float(result.get("food_stage2_monthly_cost", 0) or 0)
    food_total = food_floor + food_stage1_used + food_stage2_used
    monthly_mix_base = monthly_budget + food_floor
    target_monthly = float(result.get("target_monthly_savings", 0) or 0)
    actual_monthly = float(result.get("actual_monthly_savings", 0) or 0)
    period_years = int((financial_data or {}).get("savings_period_years", 1) or 1)
    monthly_rate_raw = (actual_monthly / target_monthly) if target_monthly > 0 else 1.0
    tot_monthly_spend = float(result.get("total_monthly_cost", 0) or 0)
    # 最適化側: monthly_budget = tot_monthly_spend + actual_monthly（常に配分尽くし）
    alloc_sum = tot_monthly_spend + actual_monthly
    initial_used = float(result.get("total_initial_cost", 0) or 0)
    initial_left = max(initial_budget - initial_used, 0)

    if food_floor > 0:
        st.caption(
            T.get("dash_food_floor_caption", "").format(floor=int(food_floor)),
        )

    st.subheader(T.get("dash_section_overview_title", ""))
    monthly_block = "📅 月予算" if lang == "ja" else "📅 Monthly budget"
    initial_block = "🧾 初期費用" if lang == "ja" else "🧾 Initial cost"
    savings_block = "💰 貯蓄" if lang == "ja" else "💰 Savings"
    food_block = "🍽️ 食費" if lang == "ja" else "🍽️ Food"

    row_a1, row_a2 = st.columns(2)
    with row_a1:
        with st.container(border=True):
            st.markdown(f"**{monthly_block}**")
            m_left, m_right = st.columns(2)
            with m_left:
                st.metric(
                    T.get("dash_metric_monthly_pool", ""),
                    f"${int(monthly_budget):,}",
                )
            with m_right:
                alloc_label = "配分合計" if lang == "ja" else "Allocated total"
                st.metric(
                    alloc_label,
                    f"${int(alloc_sum):,}",
                )
            st.caption(
                T.get("dash_metric_monthly_pool_help", "").format(
                    spend=f"${int(tot_monthly_spend):,}",
                    save=f"${int(actual_monthly):,}",
                    total=f"${int(alloc_sum):,}",
                )
            )
            if abs(alloc_sum - monthly_budget) > 0.51:
                st.caption(T.get("dash_rounding_note", ""))

    with row_a2:
        with st.container(border=True):
            st.markdown(f"**{initial_block}**")
            i_left, i_right = st.columns(2)
            with i_left:
                st.metric(
                    T.get("dash_metric_initial_cap", ""),
                    f"${int(initial_budget):,}",
                )
            with i_right:
                st.metric(
                    T.get("dash_metric_initial_left", ""),
                    f"${int(initial_left):,}",
                )
            st.caption(
                T.get("dash_metric_initial_used", "").format(
                    used=f"${int(initial_used):,}",
                )
            )

    row_b1, row_b2 = st.columns(2)
    with row_b1:
        with st.container(border=True):
            st.markdown(f"**{savings_block}**")
            s_left, s_right = st.columns(2)
            with s_left:
                st.metric(
                    T.get("dash_metric_monthly_savings", ""),
                    f"${int(actual_monthly):,}",
                )
            with s_right:
                st.metric(
                    T.get("dash_metric_savings_rate", ""),
                    f"{monthly_rate_raw:.0%}",
                )
            st.caption(T.get("dash_metric_monthly_savings_help", ""))

    with row_b2:
        with st.container(border=True):
            st.markdown(f"**{food_block}**")
            f_left, f_right = st.columns(2)
            with f_left:
                st.metric(
                    T.get("dash_cat_food", "Food"),
                    f"${int(food_total):,}",
                )
            with f_right:
                upgrade_label = "食のグレードアップ" if lang == "ja" else "Food upgrade"
                st.metric(
                    upgrade_label,
                    f"${int(food_stage2_used):,}",
                )
            if lang == "ja":
                summary = f"食費合計：固定 ${int(food_floor):,} + 通常食費 ${int(food_stage1_used):,} + {upgrade_label} ${int(food_stage2_used):,}"
            else:
                summary = f"Total food: Fixed ${int(food_floor):,} + Standard ${int(food_stage1_used):,} + {upgrade_label} ${int(food_stage2_used):,}"
            st.caption(summary)

    # AIライフコーチダッシュボード（予算配分サマリーとカテゴリ別内訳の間に挿入）
    st.divider()
    if not use_ai_for_summary:
        st.caption(T.get("ai_summary_off", "AI summary is turned off."))
    elif summary := get_result_summary(result, user_profile, weights, lang):
        st.subheader(T.get("ai_dashboard", "💡 AI ライフコーチ ダッシュボード"))
        lbl_theme = T.get("theme", "テーマ")
        lbl_analysis = T.get("analysis", "分析")
        lbl_blind_spot = T.get("blind_spot", "死角・リスク")
        lbl_action = T.get("next_action", "次のアクション")

        st.info(f"**{lbl_theme}:** {summary.get('concept', '')}")
        st.write(f"**{lbl_analysis}:** {summary.get('analysis', '')}")
        st.warning(f"**{lbl_blind_spot}:** {summary.get('blind_spot', '')}")
        st.success(f"**{lbl_action}:** {summary.get('next_action', '')}")
    else:
        st.caption(T.get("ai_error_summary", "AIダッシュボードの生成に失敗しました。"))

    # 2) カテゴリごとの使用額/割合（月/初期）
    if selected:
        ck = T.get("dash_col_category", "Category")
        cm = T.get("dash_col_monthly", "Monthly")
        cmp_ = T.get("dash_col_monthly_pct", "Monthly %")
        ci = T.get("dash_col_initial", "Initial")
        cip = T.get("dash_col_initial_pct", "Initial %")
        rows = []
        for cat_key, cat_label in CATEGORIES[lang].items():
            cat_items_sel = [it for it in selected if it.get("category") == cat_key]
            if not cat_items_sel:
                continue
            cat_mc = sum(float(it.get("monthly_cost", 0) or 0) for it in cat_items_sel)
            cat_ic = sum(float(it.get("initial_cost", 0) or 0) for it in cat_items_sel)
            rows.append(
                {
                    ck: cat_label,
                    cm: int(cat_mc),
                    cmp_: (cat_mc / monthly_mix_base * 100) if monthly_mix_base > 0 else 0,
                    ci: int(cat_ic),
                    cip: (cat_ic / initial_budget * 100) if initial_budget > 0 else 0,
                }
            )
        rows.append(
            {
                ck: T.get("dash_cat_savings", ""),
                cm: int(actual_monthly),
                cmp_: (actual_monthly / monthly_mix_base * 100) if monthly_mix_base > 0 else 0,
                ci: 0,
                cip: 0.0,
            }
        )
        if food_total > 0:
            rows.append(
                {
                    ck: T.get("dash_cat_food", ""),
                    cm: int(food_total),
                    cmp_: (food_total / monthly_mix_base * 100) if monthly_mix_base > 0 else 0,
                    ci: 0,
                    cip: 0.0,
                }
            )
        if rows:
            df_cat = pd.DataFrame(rows)
            st.subheader(T.get("dash_section_2_title", ""))
            st.dataframe(df_cat, use_container_width=True, hide_index=True)
            cat_col = ck
            monthly_pct_col = cmp_
            initial_pct_col = cip

            p1, p2 = st.columns(2)
            with p1:
                st.caption(T.get("dash_chart_monthly_mix", ""))
                _m = df_cat.sort_values(monthly_pct_col, ascending=False)
                fig_m = px.bar(
                    _m,
                    x=cat_col,
                    y=monthly_pct_col,
                    color=monthly_pct_col,
                    color_continuous_scale="Blues",
                    text=monthly_pct_col,
                    labels={cat_col: "", monthly_pct_col: "%"},
                )
                fig_m.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                fig_m.update_layout(margin=dict(l=10, r=10, t=10, b=10), coloraxis_showscale=False)
                st.plotly_chart(fig_m, width="stretch", key="exec_dash_cat_monthly_pct")
            with p2:
                st.caption(T.get("dash_chart_initial_mix", ""))
                _i = df_cat.sort_values(initial_pct_col, ascending=False)
                fig_i = px.bar(
                    _i,
                    x=cat_col,
                    y=initial_pct_col,
                    color=initial_pct_col,
                    color_continuous_scale="Purples",
                    text=initial_pct_col,
                    labels={cat_col: "", initial_pct_col: "%"},
                )
                fig_i.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                fig_i.update_layout(margin=dict(l=10, r=10, t=10, b=10), coloraxis_showscale=False)
                st.plotly_chart(fig_i, width="stretch", key="exec_dash_cat_initial_pct")

    st.subheader(T.get("dash_section_savings_title", ""))
    c1, c2, c3, c4 = st.columns(4)
    target_total = float((financial_data or {}).get("target_total_savings", 0) or 0)
    if target_total <= 0:
        target_total = target_monthly * period_years * 12
    projected_total = actual_monthly * period_years * 12
    total_gap = max(target_total - projected_total, 0)
    total_progress_ratio = min(projected_total / target_total, 1.0) if target_total > 0 else 1.0
    c1.metric(
        T.get("dash_metric_target_total", ""),
        f"${int(target_total):,}",
        f"{period_years}y",
    )
    over_total = max(projected_total - target_total, 0)
    c2.metric(
        T.get("dash_metric_projected_total", ""),
        f"${int(projected_total):,}",
    )
    c3.metric(
        T.get("dash_metric_achievement", ""),
        f"{(projected_total / target_total if target_total > 0 else 1.0):.1%}",
    )
    c4.metric(
        T.get("dash_metric_remaining_goal", ""),
        f"${int(total_gap):,}",
    )
    st.progress(total_progress_ratio)
    st.caption(
        T.get("dash_caption_goal_progress", "").format(
            years=period_years,
            pct=total_progress_ratio,
        )
    )
    if over_total > 0:
        st.caption(
            T.get("dash_caption_surplus", "").format(amt=over_total),
        )
    st.caption(
        T.get("dash_caption_target_source", "").format(years=period_years),
    )

    achieved_amount = min(projected_total, target_total) if target_total > 0 else projected_total
    remaining_amount = max(target_total - achieved_amount, 0)
    over_amount = max(projected_total - target_total, 0) if target_total > 0 else 0

    bar_y = T.get("dash_chart_bar_goal", "")
    fig_s = go.Figure()
    fig_s.add_trace(
        go.Bar(
            y=[bar_y],
            x=[achieved_amount],
            name=T.get("dash_chart_achieved", ""),
            legendrank=2,
            orientation="h",
            marker_color="#3b82f6",
            text=[f"${achieved_amount:,.0f}"],
            textposition="inside",
        )
    )
    fig_s.add_trace(
        go.Bar(
            y=[bar_y],
            x=[remaining_amount],
            name=T.get("dash_chart_remaining", ""),
            legendrank=1,
            orientation="h",
            marker_color="#f59e0b",
            text=[f"${remaining_amount:,.0f}"],
            textposition="inside",
        )
    )
    if over_amount > 0:
        fig_s.add_trace(
            go.Bar(
                y=[bar_y],
                x=[over_amount],
                name=T.get("dash_chart_over", ""),
                legendrank=3,
                orientation="h",
                marker_color="#10b981",
                text=[f"${over_amount:,.0f}"],
                textposition="inside",
            )
        )

    fig_s.update_layout(
        barmode="stack",
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title="$",
        yaxis_title="",
        legend_title="",
        legend=dict(traceorder="normal"),
    )
    st.plotly_chart(fig_s, width="stretch", key="exec_dash_savings_actual_vs_target")
    st.caption(T.get("dash_gap_caption", "").format(gap=total_gap))

    if selected:
        value_axes = ["health", "connections", "freedom", "growth", "food"]
        value_col = T.get("dash_col_value", "")
        score_col = T.get("dash_col_score", "")
        fill_col = T.get("dash_col_fulfillment", "")
        weighted_col = T.get("dash_col_weighted", "")
        axis_labels = {
            "health": T.get("form_health", ""),
            "connections": T.get("form_connections", ""),
            "freedom": T.get("form_freedom", ""),
            "growth": T.get("form_growth", ""),
            "food": T.get("val_axis_food", ""),
        }
        n_sel = max(len(selected), 1)
        value_rows = []
        for axis in value_axes:
            if axis == "food":
                raw_score = sum(float(food_related_score(it)) for it in selected)
                cap = 20.0 * n_sel
            else:
                raw_score = sum(float(it.get(axis, 0) or 0) for it in selected)
                cap = 10.0 * n_sel
            normalized = (raw_score / cap) * 100 if cap > 0 else 0.0
            weighted = raw_score * float(weights.get(axis, 5) or 5)
            value_rows.append(
                {
                    value_col: axis_labels[axis],
                    score_col: round(raw_score, 1),
                    fill_col: round(max(0, normalized), 1),
                    weighted_col: round(weighted, 1),
                }
            )
        df_value = pd.DataFrame(value_rows)
        st.subheader(T.get("dash_section_values_title", ""))

        # 追加指標: 価値観重みと選択アイテムの一致度
        # 計算: 各軸の「重みシェア」と「実現シェア（負値は0扱い）」のL1距離から一致度へ変換
        # match = 1 - 0.5 * Σ|p_i - q_i|  (0〜1)
        weight_vec = {axis: max(float(weights.get(axis, 0) or 0), 0.0) for axis in value_axes}
        achieved_vec = {
            axis: max(sum(float(it.get(axis, 0) or 0) for it in selected), 0.0)
            for axis in value_axes
        }
        sw = sum(weight_vec.values())
        sa = sum(achieved_vec.values())
        if sw > 0 and sa > 0:
            pref_share = {axis: weight_vec[axis] / sw for axis in value_axes}
            ach_share = {axis: achieved_vec[axis] / sa for axis in value_axes}
            match_ratio = max(
                0.0,
                min(1.0, 1.0 - 0.5 * sum(abs(pref_share[a] - ach_share[a]) for a in value_axes)),
            )
        else:
            match_ratio = 0.0

        st.metric(
            T.get("dash_value_match", ""),
            f"{match_ratio:.1%}",
            help=T.get("dash_value_match_help", ""),
        )
        st.caption(T.get("dash_values_chart_caption", ""))
        _v = df_value.sort_values(fill_col, ascending=False)
        fig_v = px.bar(
            _v,
            x=value_col,
            y=fill_col,
            color=fill_col,
            color_continuous_scale="Teal",
            text=fill_col,
            labels={value_col: "", fill_col: "%"},
        )
        fig_v.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_v.update_layout(margin=dict(l=10, r=10, t=10, b=10), coloraxis_showscale=False)
        st.plotly_chart(fig_v, width="stretch", key="exec_dash_value_fulfillment")

    st.divider()
    st.subheader(T.get("sel_items", ""))
    selected = result["selected"]
    if selected:
        cat_items = list(CATEGORIES[lang].items())
        tabs = st.tabs([name for _, name in cat_items])
        for tab, (cat_key, cat_name) in zip(tabs, cat_items):
            with tab:
                by_cat = [it for it in selected if it.get("category") == cat_key]
                if not by_cat:
                    st.caption(T.get("dash_no_items_in_cat", ""))
                    continue

                ic_sum = int(sum(float(it.get("initial_cost", 0) or 0) for it in by_cat))
                mc_sum = int(sum(float(it.get("monthly_cost", 0) or 0) for it in by_cat))
                st.caption(
                    T.get("dash_item_summary", "").format(
                        n=len(by_cat),
                        ic=ic_sum,
                        mc=mc_sum,
                    )
                )
                for item in by_cat:
                    orig = next((i for i in DEFAULT_ITEMS if f"{i['category']}_{i.get('priority',999)}" == item["id"]), None)
                    if lang == "ja":
                        name = item.get("name_ja") or item.get("name") or item.get("name_en", "")
                    else:
                        name = item.get("name_en") or item.get("name") or item.get("name_ja", "")
                    if lang == "ja" and orig and orig.get("note_ja"):
                        name += f" ({orig['note_ja']})"
                    elif lang == "en" and orig and orig.get("note_en"):
                        name += f" ({orig['note_en']})"

                    st.markdown(
                        f"- **{name}**  \n"
                        f"  {T.get('dash_item_initial', '')}: `${int(item.get('initial_cost', 0)):,}` / "
                        f"{T.get('dash_item_monthly', '')}: `${int(item.get('monthly_cost', 0)):,}`"
                    )
    else:
        st.write(T.get("none", "なし"))