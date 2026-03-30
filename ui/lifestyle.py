import streamlit as st
from ui.logic import apply_dynamic_overrides, apply_food_overrides
from llm import (
    food_weight_from_jelly,
    get_user_profile,
    infer_weights_from_survey,
)

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
                T.get("q_car_necessity", "Q1. Is a car necessary for your life/residence?"),
                q1a_opts,
                index=1,
                key="q_step2_car_necessity",
            )
    with row1_col2:
        with st.container(border=True):
            st.write(T.get("q_own_transport", "Q2. Do you currently own any vehicles? (Multiple choice)"))
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
                T.get("q_work_style", "Q3. What is your current work style?"),
                q2_opts,
                index=1,
                key="q_step2_work_style",
            )
    with row2_col2:
        with st.container(border=True):
            q4 = st.radio(
                T.get("q_social", "Q4. How frequently do you socialize or dine out with others?"),
                q4_opts,
                index=1,
                key="q_step2_social",
            )

    with st.container(border=True):
        q5 = st.radio(
            T.get("q_leisure", "Q5. How do you predominantly spend your days off (leisure style)?"),
            q5_opts,
            index=1,
            key="q_step2_leisure",
        )

    lifestyle_data = {
        "car_necessity": q1a,
        "own_car": own_car, "own_ebike": own_ebike, "own_bike": own_bike, "own_moto": own_moto,
        "work_style": q2, "social": q4, "leisure": q5,
    }

    # Automatically rewrite item initial costs and priorities in the background (zero API cost logic)
    apply_dynamic_overrides(lifestyle_data)

    return lifestyle_data

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

    # --- Home dining quality (base unit multiplier mapped in estimate_food_cost) ---
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

    # --- Specific habits / Discretionary spending ---
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
                T.get("q_time_deploy", "Q1. If given 3 unexpected days off and a free $500 next week, what would you do?"),
                q_time_opts,
                index=0,
                key="q_step3_time",
            )
    with row1_col2:
        with st.container(border=True):
            q_risk = st.radio(
                T.get("q_risk_deploy", "Q2. If your living costs multiplied by 1.2x, what is the absolute last thing you would cut?"),
                q_risk_opts,
                index=2,
                key="q_step3_risk",
            )

    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        with st.container(border=True):
            q_live = st.radio(
                T.get("q_live_deploy", "Q3. When do you feel most 'alive'?"),
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
            T.get("freetext_label", "Free description (non-negotiables)"),
            height=170,
            placeholder=T.get("freetext_placeholder", "e.g., I want to cook for health, but freedom of mobility (car) is non-negotiable..."),
            key="q_step3_freetext",
        )

    # Initialize session state for sliders (defaults to all 5, food overridden by jelly question)
    for key in ["w_health", "w_connections", "w_freedom", "w_growth", "w_savings", "w_food"]:
        if key not in st.session_state:
            st.session_state[key] = 5
            
    _val_keys = ("val_health", "val_conn", "val_free", "val_grow", "val_save", "val_food")
    _w_keys = ("w_health", "w_connections", "w_freedom", "w_growth", "w_savings", "w_food")
    for vk, wk in zip(_val_keys, _w_keys):
        if vk not in st.session_state:
            st.session_state[vk] = st.session_state[wk]

    def _apply_weights_to_sliders(result: dict) -> None:
        weights = result.get("weights", result)
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
            T.get("use_ai_for_values", "🤖 Reflect values using AI"),
            value=True,
            key="use_ai_for_values",
        )
    with col1:
        analyze_btn = st.button(
            T.get("reflect_to_slider_btn", "✨ Reflect values onto sliders"),
            type="primary",
            use_container_width=True,
        )

    if analyze_btn:
        with st.spinner(T.get("analyzing", "Profiling in progress...")):
            # Combine standard answers, free text, and basic info to send to LLM
            combined_data = {
                "lifestyle_fact": lifestyle_data,
                "food_fact": food_data or lifestyle_data.get("food"),
                "financial_goal": financial_data,
                "value_quiz": {
                    "q_time": q_time,
                    "q_risk": q_risk,
                    "q_live": q_live,
                    "q_jelly": q_jelly,
                },
                "passion_free_text": free_text,
            }
            # Convert to string for prompt
            combined_info_str = str(combined_data)
            
            if use_ai_for_values:
                # Calls llm.py (Uses Gemini version until OpenAI migration is complete)
                user_profile = financial_data["user_profile"]
                profile_result = get_user_profile(user_profile["age"], user_profile["family"], combined_info_str, lang)

                if profile_result:
                    _apply_weights_to_sliders(profile_result)
                    
                    st.session_state["ai_insight"] = profile_result
                        
                    for item in profile_result.get("custom_items", []):
                        cat_key = item.get("category", "leisure")
                        if cat_key in st.session_state.category_dfs:
                            import pandas as pd
                            new_row = {
                                "id": f"custom_{hash(item.get('name_en'))}",
                                "name_ja": item.get("name_ja", ""),
                                "name_en": item.get("name_en", ""),
                                "name": item.get("name_ja", ""),  # Fallback for UI
                                "category": cat_key,
                                "initial_cost": item.get("initial_cost", 0),
                                "monthly_cost": item.get("monthly_cost", 0),
                                "health": item.get("health", 5),
                                "connections": item.get("connections", 5),
                                "freedom": item.get("freedom", 5),
                                "growth": item.get("growth", 5),
                                "priority": 10,
                                "mandatory": False,
                                "ai_message": item.get("ai_message", "")
                            }
                            st.session_state.category_dfs[cat_key] = pd.concat(
                                [st.session_state.category_dfs[cat_key], pd.DataFrame([new_row])],
                                ignore_index=True
                            )
                    
                    # 確実に画面を再描画させて、下部のセッションステート表示処理を走らせる
                    st.rerun()

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
                st.info(T.get("analysis_manual_mode", "Reflected values based on answers without using AI."))

    if st.session_state.get("ai_insight"):
        st.divider()
        st.success(T.get("analysis_success", "AIがあなたの深層価値観を推論しました！下のスライダーで最終調整してください。"))
        
        res = st.session_state["ai_insight"]
        st.markdown(f"### 🤖 AI Insight")
        custom_items_from_res = res.get("custom_items") or []
        
        # JSONキーが日本語に翻訳された場合もフォールバックとして対応
        is_ja = st.session_state.get("lang") == "ja"
        p_title = "ペルソナ (Persona):" if is_ja else "Persona:"
        t_title = "心の綱引き (Tug-of-War):" if is_ja else "Tug-of-War:"
        d_title = "悪魔の囁き (The Devil's Whisper):" if is_ja else "The Devil's Whisper:"
        d_added = "追加アイテム" if is_ja else "Added Items"

        persona = res.get("persona_title") or res.get("ペルソナ") or res.get("ペルソナ名") or res.get("アーキタイプ") or res.get("persona") or None
        conflict = res.get("psychological_conflict") or res.get("心の綱引き") or res.get("心理的葛藤") or None
        
        if persona:
            st.info(f"🎭 **{p_title}** {persona}")

        # == Added items declared by the AI profiling response (fallback to session data if needed) ==
        added_items = []
        seen_items = set()

        def _add_item(name, ai_msg, initial_cost, monthly_cost):
            key = (name, float(initial_cost or 0), float(monthly_cost or 0))
            if key in seen_items:
                return
            seen_items.add(key)
            added_items.append({
                "name": name,
                "ai_message": (ai_msg or "").strip(),
                "initial_cost": float(initial_cost or 0),
                "monthly_cost": float(monthly_cost or 0),
            })

        for item in custom_items_from_res:
            if not isinstance(item, dict):
                continue
            name_fields = (
                item.get("name_ja"),
                item.get("name_en"),
                item.get("name"),
            )
            name_disp = next((n for n in name_fields if isinstance(n, str) and n.strip()), "Custom Item")
            _add_item(
                name_disp,
                item.get("ai_message", ""),
                item.get("initial_cost", 0),
                item.get("monthly_cost", 0),
            )

        for cat_key, df in st.session_state.get("category_dfs", {}).items():
            if df.empty:
                continue
            for _, row in df.iterrows():
                ai_message_raw = row.get("ai_message")
                if not isinstance(ai_message_raw, str):
                    ai_message_raw = ""
                is_custom_id = isinstance(row.get("id"), str) and row["id"].startswith("custom_")
                if not ai_message_raw.strip() and not is_custom_id:
                    continue
                name_ja = row.get("name_ja")
                name_en = row.get("name_en")
                name_fallback = row.get("name")
                name_ja_str = name_ja if isinstance(name_ja, str) else ""
                name_en_str = name_en if isinstance(name_en, str) else ""
                name_fb_str = name_fallback if isinstance(name_fallback, str) else "Mystery Item"
                name_disp = name_ja_str if is_ja and name_ja_str else (name_en_str if name_en_str else name_fb_str)
                _add_item(
                    name_disp,
                    ai_message_raw,
                    row.get("initial_cost", 0),
                    row.get("monthly_cost", 0),
                )
        if added_items:
            st.markdown(f"**📝 {d_added}**")
            for item in added_items:
                cost_line = f"Initial: ${item['initial_cost']:.0f} / Monthly: ${item['monthly_cost']:.0f}"
                with st.container():
                    st.markdown(f"**🌟 {item['name']}**  ·  {cost_line}")
                    if item["ai_message"]:
                        st.caption(f"🗣️ {d_title} — {item['ai_message']}")
        elif custom_items_from_res:
            st.caption("AIからのカスタムアイテムはありましたが、追加中にフィルタされています。セッションデータを確認してください。")
                    
        if conflict:
            st.warning(f"⚖️ **{t_title}**\n\n{conflict}")

        if not persona and not conflict and not added_items:
            st.info("💡 （※AIモデルから回答を受信しましたが、ペルソナなどの追加インサイトが含まれていませんでした。プロンプトを更新したので、もう一度上部の「✨ 反映する」ボタンを押してみてください）")

    st.divider()
    st.subheader(T.get("w_subdir", "⚖️ Value weights"))
    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        w_health = st.slider(T.get("w_health", "Health"), 1, 10, st.session_state.w_health, key="val_health")
    with r1c2:
        w_conn = st.slider(T.get("w_connections", "Connections"), 1, 10, st.session_state.w_connections, key="val_conn")
    with r1c3:
        w_free = st.slider(T.get("w_freedom", "Freedom"), 1, 10, st.session_state.w_freedom, key="val_free")
    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1:
        w_grow = st.slider(T.get("w_growth", "Growth"), 1, 10, st.session_state.w_growth, key="val_grow")
    with r2c2:
        w_save = st.slider(T.get("w_savings", "Savings"), 1, 10, st.session_state.w_savings, key="val_save")
    with r2c3:
        w_food = st.slider(T.get("w_food", "Food"), 1, 10, st.session_state.w_food, key="val_food")

    return {
        "health": w_health,
        "connections": w_conn,
        "freedom": w_free,
        "growth": w_grow,
        "savings": w_save,
        "food": w_food,
    }
