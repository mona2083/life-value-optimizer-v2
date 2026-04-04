import streamlit as st
from ui.logic import apply_dynamic_overrides, apply_food_overrides, normalize_all_item_costs
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
                
                # Create hash of current input data to detect changes
                import json
                import hashlib
                
                input_data_for_hash = {
                    "age": user_profile.get("age"),
                    "family": user_profile.get("family"),
                    "combined_info": combined_info_str,
                    "lang": lang,
                }
                current_input_hash = hashlib.md5(
                    json.dumps(input_data_for_hash, sort_keys=True, default=str).encode()
                ).hexdigest()
                
                # Check if input has changed since last AI analysis
                last_input_hash = st.session_state.get("last_ai_input_hash", "")
                input_changed = (current_input_hash != last_input_hash)
                
                # Only call LLM if:
                # 1. We don't have cached ai_insight, OR
                # 2. The input data has changed
                if "ai_insight" not in st.session_state or input_changed:
                    profile_result = get_user_profile(user_profile["age"], user_profile["family"], combined_info_str, lang)
                    
                    # Only proceed if we got a valid result
                    if profile_result:
                        # Update cache
                        st.session_state["ai_insight"] = profile_result
                        st.session_state["last_ai_input_hash"] = current_input_hash
                        # Clear the AI items added flag when new analysis is done
                        st.session_state["ai_items_added_from_insight"] = False
                else:
                    profile_result = st.session_state.get("ai_insight")

                if profile_result:
                    _apply_weights_to_sliders(profile_result)
                    
                    # Prioritize AI-estimated food cost: if AI returns estimated_food_cost, use it over defaults
                    ai_estimated_food = profile_result.get("estimated_food_cost")
                    if ai_estimated_food and isinstance(ai_estimated_food, dict) and "minimalist_floor_cost" in ai_estimated_food:
                        # Ensure location_adjustment is applied to minimalist_floor_cost
                        loc_adjustment = float(ai_estimated_food.get("location_adjustment", 1.0) or 1.0)
                        original_floor = float(ai_estimated_food.get("minimalist_floor_cost", 0) or 0)
                        adjusted_floor = original_floor * loc_adjustment
                        
                        ai_estimated_food["minimalist_floor_cost"] = adjusted_floor
                        
                        financial_data["estimated_food_cost"] = ai_estimated_food
                        st.session_state["estimated_food_cost"] = ai_estimated_food
                    
                    # Add AI recommended items ONLY if:
                    # 1. They haven't been added from this specific insight yet, AND
                    # 2. They don't already exist in category_dfs
                    import pandas as pd
                    
                    # Check if AI items already exist by looking for custom_ai_ ids
                    ai_items_exist_in_dfs = False
                    for cat in st.session_state.category_dfs:
                        df = st.session_state.category_dfs[cat]
                        if "id" in df.columns and (df["id"].astype(str).str.startswith("custom_ai_")).any():
                            ai_items_exist_in_dfs = True
                            break
                    
                    # If input changed, remove old AI items before adding new ones
                    if input_changed and ai_items_exist_in_dfs:
                        for cat in st.session_state.category_dfs:
                            df = st.session_state.category_dfs[cat]
                            if "id" in df.columns:
                                mask = df["id"].astype(str).str.startswith("custom_ai_")
                                st.session_state.category_dfs[cat] = df[~mask].reset_index(drop=True)
                        ai_items_exist_in_dfs = False
                    
                    # Add new AI items only if they don't exist
                    if not ai_items_exist_in_dfs:
                        for item in profile_result.get("recommended_actions", []):
                            cat_key = item.get("category", "leisure")
                            if cat_key in st.session_state.category_dfs:
                                new_row = {
                                    "id": f"custom_ai_{item.get('name_en', '').replace(' ', '_')}",
                                    "name_ja": item.get("name_ja", ""),
                                    "name_en": item.get("name_en", ""),
                                    "name": item.get("name_ja", ""),  # Fallback for UI
                                    "category": cat_key,
                                    "initial_cost": item.get("initial_cost", 0),
                                    "monthly_cost": item.get("monthly_cost", 0),
                                    "base_initial_cost": item.get("initial_cost", 0),
                                    "base_monthly_cost": item.get("monthly_cost", 0),
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
                        
                        st.session_state["ai_items_added_from_insight"] = True
                    
                    # Apply adjusted default item costs
                    for adj_item in profile_result.get("adjusted_default_items", []):
                        cat_key = adj_item.get("category", "leisure")
                        item_name_ja = adj_item.get("name_ja", "")
                        item_name_en = adj_item.get("name_en", "")
                        adj_initial = adj_item.get("adjusted_initial_cost")
                        adj_monthly = adj_item.get("adjusted_monthly_cost")
                        
                        if cat_key in st.session_state.category_dfs and adj_initial is not None and adj_monthly is not None:
                            df = st.session_state.category_dfs[cat_key]
                            # Find matching item by name
                            mask = (df["name_ja"] == item_name_ja) | (df["name_en"] == item_name_en)
                            if mask.any():
                                df.loc[mask, "initial_cost"] = adj_initial
                                df.loc[mask, "monthly_cost"] = adj_monthly
                                df.loc[mask, "base_initial_cost"] = adj_initial
                                df.loc[mask, "base_monthly_cost"] = adj_monthly
                                st.session_state.category_dfs[cat_key] = df

                    normalize_all_item_costs(financial_data)
                    
                    # Only rerun if we just added AI items for the first time
                    if not st.session_state.get("ai_items_added_from_insight", False):
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
                    normalize_all_item_costs(financial_data)
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
                normalize_all_item_costs(financial_data)
                st.info(T.get("analysis_manual_mode", "Reflected values based on answers without using AI."))

    if st.session_state.get("ai_insight"):
        st.divider()
        st.success(T.get("analysis_success", "AIがあなたの深層価値観を推論しました！下のスライダーで最終調整してください。"))
        
        res = st.session_state["ai_insight"]
        st.markdown(f"### 🤖 AI Insight")
        
        # Fallback handling for cases where JSON keys are translated into Japanese
        is_ja = st.session_state.get("lang") == "ja"
        p_title = "ペルソナ (Persona):" if is_ja else "Persona:"
        s_title = "サマリー (Summary)" if is_ja else "Summary"
        c_title = "心の綱引き (Psychological Conflict)" if is_ja else "Psychological Conflict"

        # profile is a nested object inside the JSON payload
        profile = res.get("profile", {})
        persona = profile.get("persona_title") or profile.get("ペルソナ") or profile.get("ペルソナ名") or profile.get("アーキタイプ") or profile.get("persona") or None
        summary = profile.get("summary") or profile.get("サマリー") or None
        conflict = profile.get("psychological_conflict") or profile.get("心の綱引き") or profile.get("心理的葛藤") or None
        
        if persona:
            st.info(f"🎭 **{p_title}** {persona}")
        
        # Display summary and psychological conflict in a two-column layout
        if summary or conflict:
            col_left, col_right = st.columns(2)
            
            with col_left:
                if summary:
                    with st.container(border=True):
                        st.markdown(f"**📋 {s_title}**")
                        st.write(summary)
            
            with col_right:
                if conflict:
                    with st.container(border=True):
                        st.markdown(f"**⚖️ {c_title}**")
                        st.write(conflict)

        if not persona and not summary and not conflict:
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
