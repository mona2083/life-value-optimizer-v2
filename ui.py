import streamlit as st
import pandas as pd

from optimizer import run_optimizer
from sensitivity import run_sensitivity, make_line_chart
from llm import get_item_defaults, get_result_summary, get_user_profile_from_chat
from lang import PRESETS
from default_items import DEFAULT_ITEMS, CATEGORIES, CATEGORY_CONSTRAINTS
from lifestyle import calculate_lifestyle_adjustments, INCOME_REASON_OPTIONS
from risk_cost import calculate_risk_costs


def _collect_all_items(lang: str) -> list[dict]:
    items = []
    for category, df in st.session_state.category_dfs.items():
        for i, row in df.iterrows():
            items.append(
                {
                    "name": row["name"],
                    "initial_cost": int(
                        st.session_state.get(
                            f"initial_cost_{category}_{i}", int(row["initial_cost"])
                        )
                    ),
                    "monthly_cost": int(
                        st.session_state.get(
                            f"monthly_cost_{category}_{i}", int(row["monthly_cost"])
                        )
                    ),
                    "health": int(row["health"]),
                    "connections": int(row["connections"]),
                    "freedom": int(row["freedom"]),
                    "growth": int(row["growth"]),
                    "priority": int(row["priority"]),
                    "mandatory": bool(row["mandatory"]),
                    "category": row["category"],
                }
            )
    return items


def _render_cost_summary(
    items: list[dict],
    total_budget: int,
    effective_monthly_budget: int,
    lang: str,
) -> bool:
    from lang import LANG

    T = LANG[lang]
    mandatory = [item for item in items if item["mandatory"]]
    candidates = [item for item in items if item["priority"] > 0 or item["mandatory"]]
    m_initial = sum(item["initial_cost"] for item in mandatory)
    m_monthly = sum(item["monthly_cost"] for item in mandatory)
    c_initial = sum(item["initial_cost"] for item in candidates)
    c_monthly = sum(item["monthly_cost"] for item in candidates)

    st.subheader(T["mandatory_summary_title"])
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        T["must_initial"],
        f"${m_initial:,}",
        delta=f"上限${total_budget:,}" if lang == "ja" else f"Limit${total_budget:,}",
        delta_color="inverse" if m_initial > total_budget else "off",
    )
    col2.metric(
        T["must_monthly"],
        f"${m_monthly:,}",
        delta=f"予算${effective_monthly_budget:,}" if lang == "ja" else f"Budget${effective_monthly_budget:,}",
        delta_color="inverse" if m_monthly > effective_monthly_budget else "off",
    )
    col3.metric(T["cand_initial"], f"${c_initial:,}")
    col4.metric(T["cand_monthly"], f"${c_monthly:,}")

    if m_initial > total_budget:
        st.error(T["validation_initial_over"].format(m_initial, total_budget))
    if m_monthly > effective_monthly_budget:
        st.error(
            T["validation_monthly_over"].format(m_monthly, effective_monthly_budget)
        )

    return m_initial > total_budget or m_monthly > effective_monthly_budget


def _render_recommendations(
    all_items: list[dict],
    result: dict,
    effective_monthly_budget: int,
    total_budget: int,
    lang: str,
) -> None:
    from lang import LANG

    T = LANG[lang]
    selected_names = {item["name"] for item in result["selected"]}
    car_chosen = any(
        "車メイン" in n or "Car (Primary)" in n for n in selected_names
    )
    pet_chosen = any(n in ("ペット", "Pet") for n in selected_names)

    unselected = [
        item
        for item in all_items
        if item["name"] not in selected_names
        and item.get("priority", 0) > 0
        and not item.get("mandatory", False)
        and item.get("category") != "_savings"
        and not (item["name"] in ("車保険", "Car Insurance") and not car_chosen)
        and not (item["name"] in ("ペット保険", "Pet Insurance") and not pet_chosen)
    ]
    unselected.sort(key=lambda x: x.get("priority", 99))

    if not unselected:
        return

    st.subheader(T["rec_title"])
    remaining_monthly = effective_monthly_budget - result["total_monthly_cost"]
    remaining_initial = total_budget - result["total_initial_cost"]

    for item in unselected[:5]:
        shortfall_m = max(item["monthly_cost"] - remaining_monthly, 0)
        shortfall_i = max(item["initial_cost"] - remaining_initial, 0)
        label = (
            f"優先度{item['priority']}: **{item['name']}**　初期${item['initial_cost']:,} / 月次${item['monthly_cost']:,}"
            if lang == "ja"
            else f"Priority {item['priority']}: **{item['name']}**　Initial${item['initial_cost']:,} / Monthly${item['monthly_cost']:,}"
        )
        if shortfall_m == 0 and shortfall_i == 0:
            st.success(f"{label}　→ {T['rec_within_budget']}")
        else:
            parts = []
            if shortfall_m > 0:
                parts.append(
                    f"月次あと${shortfall_m:,}" if lang == "ja" else f"${shortfall_m:,}/month more"
                )
            if shortfall_i > 0:
                parts.append(
                    f"初期費用あと${shortfall_i:,}" if lang == "ja" else f"${shortfall_i:,} more initial"
                )
            suffix = "必要" if lang == "ja" else "needed"
            st.info(f"{label}　→ {' / '.join(parts)}{suffix}")


def render_step1(T: dict, lang: str):
    """Render Step 1 and return inputs used by later steps."""
    st.header(T["step1"])

    col1, col2, col3 = st.columns(3)
    with col1:
        age = st.number_input(T["age"], min_value=18, max_value=100, value=42)
    with col2:
        gender = st.selectbox(T["gender"], T["gender_options"])
    with col3:
        family = st.selectbox(T["family"], T["family_options"])

    monthly_income = st.number_input(T["monthly_income"], min_value=0, value=4000, step=100)

    st.subheader(T["fixed_costs_title"])
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        rent = st.number_input(T["rent"], min_value=0, value=1500, step=50)
        utilities = st.number_input(T["utilities"], min_value=0, value=150, step=10)
    with col_f2:
        internet = st.number_input(T["internet"], min_value=0, value=130, step=10)
        groceries = st.number_input(T["groceries"], min_value=0, value=400, step=50)
    with col_f3:
        health_insurance_fixed = st.number_input(T["health_insurance_fixed"], min_value=0, value=150, step=10)
        other_fixed = st.number_input(T["other_fixed"], min_value=0, value=0, step=50)

    total_fixed = rent + utilities + internet + groceries + health_insurance_fixed + other_fixed
    disposable_income = max(monthly_income - total_fixed, 0)

    st.metric(
        T["disposable_income"],
        f"${disposable_income:,}",
        delta=(f"収入${monthly_income:,} − 固定費${total_fixed:,}" if lang == "ja" else f"Income${monthly_income:,} − Fixed${total_fixed:,}"),
        delta_color="off",
        help=T["disposable_income_help"],
    )

    total_budget = st.number_input(
        T["total_budget"],
        min_value=0,
        value=5000,
        step=500,
        help=T["total_budget_help"],
    )

    st.divider()

    return (
        age,
        gender,
        family,
        monthly_income,
        rent,
        utilities,
        internet,
        groceries,
        health_insurance_fixed,
        other_fixed,
        disposable_income,
        total_budget,
    )


def render_step2(T: dict, lang: str):
    """Render Step 2 and return weights/targets used by later steps."""
    st.header(T["step2"])

    col6, col7 = st.columns(2)
    with col6:
        savings_goal = st.number_input(T["savings_goal"], min_value=0, value=1200, step=100)
    with col7:
        savings_period_years = st.selectbox(T["savings_period"], [1, 5, 10, 20, 50], index=0)

    target_monthly_savings = int(savings_goal / (savings_period_years * 12))
    st.caption(T["monthly_savings_cap"].format(target_monthly_savings))

    st.divider()

    # =====================================================================
    # 【追加】AIライフスタイル・プロファイラー (Chat UI)
    # =====================================================================
    st.subheader("🤖 AI プロファイリング (Optional)")
    st.caption("休日の理想的な過ごし方や、最近買って満足したものを教えてください。AIがあなたの価値観を推測し、設定を自動補完します。")
    
    chat_input_label = "例: 週末はカフェで読書したり、友人と美味しいご飯を食べるのが好きです。" if lang == "ja" else "e.g., I love reading at cafes and dining out with friends on weekends."
    user_text = st.chat_input(chat_input_label)
    
    if user_text:
        with st.chat_message("user"):
            st.write(user_text)
        with st.spinner("行動経済学の観点からあなたの価値観を分析中..."):
            profile = get_user_profile_from_chat(user_text, lang)
            
            if profile and "weights" in profile:
                # 1. スライダー用のセッションステートをAIの推論値で上書き
                w = profile["weights"]
                st.session_state["slider_health"] = w.get("health", 5)
                st.session_state["slider_connections"] = w.get("connections", 5)
                st.session_state["slider_freedom"] = w.get("freedom", 5)
                st.session_state["slider_growth"] = w.get("growth", 5)
                st.session_state["slider_savings"] = w.get("savings", 5)
                
                # 2. カスタムアイテムの自動追加（hobbyカテゴリに挿入）
                c_item = profile.get("custom_item")
                if c_item and "hobby" in st.session_state.category_dfs:
                    cat_name = "hobby"
                    new_idx = len(st.session_state.category_dfs[cat_name])
                    new_row = pd.DataFrame([{
                        "name": f"✨ {c_item.get('name', 'AI Custom Item')}",
                        "initial_cost": c_item.get("initial_cost", 0),
                        "monthly_cost": c_item.get("monthly_cost", 0),
                        "health": c_item.get("health", 0),
                        "connections": c_item.get("connections", 0),
                        "freedom": c_item.get("freedom", 0),
                        "growth": c_item.get("growth", 0),
                        "priority": 1,
                        "mandatory": False,
                        "category": cat_name,
                        "note": "AIがあなたの回答から推測・生成しました"
                    }])
                    # DataFrameの更新
                    st.session_state.category_dfs[cat_name] = pd.concat(
                        [st.session_state.category_dfs[cat_name], new_row], ignore_index=True
                    )
                    # UI状態の同期
                    st.session_state[f"priority_{cat_name}_{new_idx}"] = 1
                    st.session_state[f"mandatory_{cat_name}_{new_idx}"] = False
                    st.session_state[f"initial_cost_{cat_name}_{new_idx}"] = c_item.get("initial_cost", 0)
                    st.session_state[f"monthly_cost_{cat_name}_{new_idx}"] = c_item.get("monthly_cost", 0)
                
                st.success("✨ 分析完了！スライダーとあなた専用のアイテムが自動設定されました。（Step 3の「趣味・嗜好」タブを確認してください）")
            else:
                st.error("分析に失敗しました。もう少し長めの文章でもう一度お試しください。")

    st.divider()

    # =====================================================================
    # 価値観の重み（スライダー）
    # =====================================================================
    st.subheader(T["priority"])
    goal_preset = st.radio(T["goal_type"], T["goal_options"], horizontal=True)
    preset = PRESETS[lang][goal_preset]

    # セッションステートに値がない場合はプリセットの初期値を入れる
    for key, p_key in [("slider_health", "health"), ("slider_connections", "connections"), 
                       ("slider_freedom", "freedom"), ("slider_growth", "growth"), 
                       ("slider_savings", "savings")]:
        if key not in st.session_state:
            st.session_state[key] = preset[p_key]

    col8, col9, col10, col11, col12 = st.columns(5)
    with col8:
        w_health = st.slider(T["w_health"], 1, 10, key="slider_health")
    with col9:
        w_connections = st.slider(T["w_connections"], 1, 10, key="slider_connections")
    with col10:
        w_freedom = st.slider(T["w_freedom"], 1, 10, key="slider_freedom")
    with col11:
        w_growth = st.slider(T["w_growth"], 1, 10, key="slider_growth")
    with col12:
        w_savings = st.slider(T["w_savings"], 1, 10, key="slider_savings")

    st.divider()

    return (
        savings_period_years,
        target_monthly_savings,
        w_health,
        w_connections,
        w_freedom,
        w_growth,
        w_savings,
    )


def render_step2_5(T: dict, lang: str, disposable_income: int, savings_period_years: int) -> dict:
    """Render Step 2.5 (lifestyle projection) and return lifestyle adjustment dict."""
    st.header(T["step_lifestyle"])

    col_inc1, col_inc2, col_inc3 = st.columns(3)
    with col_inc1:
        income_increase = st.number_input(T["income_increase"], min_value=0, value=0, step=50)
    with col_inc2:
        income_years = st.selectbox(T["income_years"], [1, 2, 3, 5, 10, 15, 20], index=2)
    with col_inc3:
        income_reason = st.selectbox(T["income_reason"], INCOME_REASON_OPTIONS[lang])

    lifestyle_adj = calculate_lifestyle_adjustments(
        {
            "income_increase": income_increase,
            "income_years": income_years,
            "income_reason": income_reason,
            "monthly_budget": disposable_income,
            "savings_years": savings_period_years,
        },
        lang,
    )

    if lifestyle_adj.get("future_note"):
        st.info(lifestyle_adj["future_note"])

    st.divider()
    return lifestyle_adj


def render_step3(T: dict, lang: str) -> None:
    """Render Step 3 (item editor + AI add) using Streamlit session state."""
    st.header(T["step3"])
    st.caption(T["step3_caption"])

    tabs = st.tabs(list(CATEGORIES[lang].values()))
    for tab, category in zip(tabs, CATEGORIES[lang].keys()):
        with tab:
            constraint_label = (
                CATEGORY_CONSTRAINTS[category]["label_ja"]
                if lang == "ja"
                else CATEGORY_CONSTRAINTS[category]["label_en"]
            )
            df = st.session_state.category_dfs[category]
            st.caption(constraint_label)

            col_da, col_aa, _ = st.columns([1, 1, 5])
            with col_da:
                st.markdown('<div class="small-btn">', unsafe_allow_html=True)
                if st.button(T["deactivate_all"], key=f"deact_{category}"):
                    for i in range(len(df)):
                        st.session_state.category_dfs[category].at[i, "priority"] = 0
                        st.session_state[f"priority_{category}_{i}"] = 0
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with col_aa:
                st.markdown('<div class="small-btn">', unsafe_allow_html=True)
                if st.button(T["activate_all"], key=f"act_{category}"):
                    name_key = "name_ja" if lang == "ja" else "name_en"
                    default_map = {
                        item[name_key]: item.get("priority", 1)
                        for item in DEFAULT_ITEMS
                        if item["category"] == category
                    }
                    for i, row in df.iterrows():
                        p = default_map.get(row["name"], 1)
                        st.session_state.category_dfs[category].at[i, "priority"] = p
                        st.session_state[f"priority_{category}_{i}"] = p
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            h = st.columns([1, 1, 3, 2, 2, 1, 1, 1, 1, 2])
            for col, label in zip(
                h,
                [
                    T["col_priority"],
                    T["col_mandatory"],
                    T["col_name"],
                    T["col_initial"],
                    T["col_monthly"],
                    T["col_health"],
                    T["col_connections"],
                    T["col_freedom"],
                    T["col_growth"],
                    T["col_note"],
                ],
            ):
                col.caption(label)
            st.divider()

            for i, row in df.iterrows():
                _p_key = f"priority_{category}_{i}"
                _m_key = f"mandatory_{category}_{i}"
                _ic_key = f"initial_cost_{category}_{i}"
                _mc_key = f"monthly_cost_{category}_{i}"

                for key, default in [
                    (_p_key, int(row["priority"])),
                    (_m_key, bool(row["mandatory"])),
                    (_ic_key, int(row["initial_cost"])),
                    (_mc_key, int(row["monthly_cost"])),
                ]:
                    if key not in st.session_state:
                        st.session_state[key] = default

                r = st.columns([1, 1, 3, 2, 2, 1, 1, 1, 1, 2])
                priority = r[0].number_input(
                    "",
                    min_value=0,
                    max_value=99,
                    key=_p_key,
                    label_visibility="collapsed",
                    step=1,
                )
                mandatory = r[1].checkbox("", key=_m_key, label_visibility="collapsed")
                r[2].write(row["name"])
                initial_cost = r[3].number_input("", min_value=0, key=_ic_key, label_visibility="collapsed", step=50)
                monthly_cost = r[4].number_input("", min_value=0, key=_mc_key, label_visibility="collapsed", step=10)
                r[5].write(str(int(row["health"])))
                r[6].write(str(int(row["connections"])))
                r[7].write(str(int(row["freedom"])))
                r[8].write(str(int(row["growth"])))
                r[9].caption(str(row.get("note", "")))

                st.session_state.category_dfs[category].at[i, "priority"] = priority
                st.session_state.category_dfs[category].at[i, "mandatory"] = mandatory
                st.session_state.category_dfs[category].at[i, "initial_cost"] = initial_cost
                st.session_state.category_dfs[category].at[i, "monthly_cost"] = monthly_cost

            st.divider()

            col_ai1, col_ai2 = st.columns([3, 1])
            with col_ai1:
                ai_name = st.text_input(
                    T["ai_item_placeholder"],
                    key=f"ai_input_{category}",
                    label_visibility="collapsed",
                    placeholder=T["ai_item_placeholder"],
                )
            with col_ai2:
                if st.button(T["ai_complete_button"], key=f"ai_btn_{category}") and ai_name:
                    with st.spinner("AI..."):
                        defaults = get_item_defaults(ai_name, lang)
                    if defaults:
                        new_idx = len(st.session_state.category_dfs[category])
                        new_row = pd.DataFrame(
                            [
                                {
                                    "name": ai_name,
                                    "initial_cost": defaults.get("initial_cost", 0),
                                    "monthly_cost": defaults.get("monthly_cost", 0),
                                    "health": defaults.get("health", 5),
                                    "connections": defaults.get("connections", 5),
                                    "freedom": defaults.get("freedom", 5),
                                    "growth": defaults.get("growth", 5),
                                    "priority": 1,
                                    "mandatory": False,
                                    "category": category,
                                    "note": "",
                                }
                            ]
                        )
                        st.session_state.category_dfs[category] = pd.concat(
                            [st.session_state.category_dfs[category], new_row], ignore_index=True
                        )
                        for key, val in [
                            (f"priority_{category}_{new_idx}", 1),
                            (f"mandatory_{category}_{new_idx}", False),
                            (f"initial_cost_{category}_{new_idx}", defaults.get("initial_cost", 0)),
                            (f"monthly_cost_{category}_{new_idx}", defaults.get("monthly_cost", 0)),
                        ]:
                            st.session_state[key] = val
                        st.rerun()
                    else:
                        st.warning(T["ai_error_complete"])

    st.divider()


def render_risk_and_results(
    T: dict,
    lang: str,
    age: int,
    family: str,
    savings_period_years: int,
    total_budget: int,
    target_monthly_savings: int,
    w_health: int,
    w_connections: int,
    w_freedom: int,
    w_growth: int,
    w_savings: int,
    lifestyle_adj: dict,
) -> None:
    # ── リスクコスト ──────────────────────────────────────
    use_risk = st.toggle(T["risk_toggle"], value=False)
    effective_monthly_budget = int(lifestyle_adj["future_monthly_budget"])

    if use_risk:
        st.subheader(T["risk_title"])
        st.caption(T["risk_caption"])

        transport_df = st.session_state.category_dfs.get("transport", pd.DataFrame())
        car_selected = any(
            ("車メイン" in str(row.get("name", "")) or "Car (Primary)" in str(row.get("name", "")))
            and (row.get("priority", 0) > 0 or row.get("mandatory", False))
            for _, row in transport_df.iterrows()
        ) if not transport_df.empty else False

        raw_costs = calculate_risk_costs(
            age=int(age),
            family=family,
            savings_period_years=int(savings_period_years),
            monthly_budget=effective_monthly_budget,
            car_selected=car_selected,
        )

        risk_df = pd.DataFrame(
            [
                {
                    T["risk_col_category"]: T["risk_categories"][c["category"]],
                    T["risk_col_cost"]: c["monthly_cost"],
                }
                for c in raw_costs
            ]
        )

        edited_risk_df = st.data_editor(
            risk_df, num_rows="fixed", use_container_width=True, key="risk_editor"
        )
        total_risk = int(edited_risk_df[T["risk_col_cost"]].sum())
        effective_monthly_budget = max(
            int(lifestyle_adj["future_monthly_budget"]) - total_risk, 0
        )

        st.metric(
            T["risk_effective"],
            f"${effective_monthly_budget:,}",
            delta=f"-${total_risk:,}",
            delta_color="inverse",
        )

    st.divider()

    # ── 費用サマリー ──────────────────────────────────────
    preview_items = _collect_all_items(lang)
    _render_cost_summary(preview_items, int(total_budget), effective_monthly_budget, lang)

    # ── 最適化実行 ────────────────────────────────────────
    if st.button(T["run_button"], type="primary"):
        all_items = _collect_all_items(lang)
        weights = {
            "health": w_health,
            "connections": w_connections,
            "freedom": w_freedom,
            "growth": w_growth,
            "savings": w_savings,
        }

        mandatory_items = [item for item in all_items if item["mandatory"]]
        transport_cands = [
            item
            for item in all_items
            if item["category"] == "transport" and (item["priority"] > 0 or item["mandatory"])
        ]

        errors = []
        if sum(item["initial_cost"] for item in mandatory_items) > int(total_budget):
            errors.append(
                T["validation_initial_over"].format(
                    sum(item["initial_cost"] for item in mandatory_items), int(total_budget)
                )
            )
        if sum(item["monthly_cost"] for item in mandatory_items) > effective_monthly_budget:
            errors.append(
                T["validation_monthly_over"].format(
                    sum(item["monthly_cost"] for item in mandatory_items),
                    effective_monthly_budget,
                )
            )
        if not transport_cands:
            st.warning(T["validation_no_transport"])

        for e in errors:
            st.error(e)

        if not errors:
            with st.spinner("Optimizing..."):
                result = run_optimizer(
                    items=all_items,
                    total_budget=int(total_budget),
                    monthly_budget=effective_monthly_budget,
                    target_monthly_savings=target_monthly_savings,
                    weights=weights,
                )
                sens = run_sensitivity(
                    items=all_items,
                    monthly_budget=effective_monthly_budget,
                    total_budget=int(total_budget),
                    target_monthly_savings=target_monthly_savings,
                    weights=weights,
                )

            if result["status"] == "ok":
                st.success(T["result_ok"])

                with st.spinner("AI..."):
                    summary = get_result_summary(
                        result=result,
                        user_profile={"age": age, "family": family},
                        weights=weights,
                        lang=lang,
                    )
                # =====================================================================
                # Render AI Life Coach Dashboard
                # =====================================================================
                if summary and isinstance(summary, dict):
                    st.subheader("💡 AI Life Coach Dashboard")
                    
                    # 1. Concept (Theme)
                    st.info(f"**Theme:** {summary.get('concept', '')}")
                    
                    # 2. Analysis
                    st.write(f"**Analysis:** {summary.get('analysis', '')}")
                    
                    # 3. Blind Spot (Warning)
                    st.warning(f"**Blind Spot:** {summary.get('blind_spot', '')}")
                    
                    # 4. Next Action (Success/Recommendation)
                    st.success(f"**Next Action:** {summary.get('next_action', '')}")
                else:
                    st.caption(T["ai_error_summary"])

                if lifestyle_adj.get("future_note"):
                    st.caption(lifestyle_adj["future_note"])

                col_r1, col_r2, col_r3, col_r4 = st.columns(4)
                col_r1.metric(T["total_initial"], f"${result['total_initial_cost']:,}")
                col_r2.metric(T["total_monthly"], f"${result['total_monthly_cost']:,}")
                col_r3.metric(T["actual_savings"], f"${result['actual_monthly_savings']:,}")
                col_r4.metric(T["savings_rate"], f"{result['savings_rate']:.0%}")

                if result["savings_shortfall"] > 0:
                    st.warning(T["shortfall_warn"].format(result["savings_shortfall"]))

                st.subheader(T["selected_items"])
                if result["selected"]:
                    selected_by_cat: dict[str, list] = {}
                    for item in result["selected"]:
                        selected_by_cat.setdefault(item.get("category", "other"), []).append(item)

                    for cat, cat_items in selected_by_cat.items():
                        st.markdown(f"**{CATEGORIES[lang].get(cat, cat)}**")
                        cat_df = pd.DataFrame(cat_items)[
                            ["name", "initial_cost", "monthly_cost", "health", "connections", "freedom", "growth"]
                        ].rename(
                            columns={
                                "name": T["col_name"],
                                "initial_cost": T["col_initial"],
                                "monthly_cost": T["col_monthly"],
                                "health": T["col_health"],
                                "connections": T["col_connections"],
                                "freedom": T["col_freedom"],
                                "growth": T["col_growth"],
                            }
                        )
                        st.dataframe(cat_df, use_container_width=True, hide_index=True)

                _render_recommendations(all_items, result, effective_monthly_budget, int(total_budget), lang)

                st.header(T["sensitivity_title"])
                tab_m, tab_i = st.tabs([T["tab_monthly"], T["tab_initial"]])

                with tab_m:
                    st.plotly_chart(
                        make_line_chart(
                            sens["monthly_range"],
                            sens["monthly_values"],
                            effective_monthly_budget,
                            T["chart_monthly_x"],
                            T["chart_value"],
                            T["chart_line_title_m"],
                        ),
                        use_container_width=True,
                    )

                with tab_i:
                    st.plotly_chart(
                        make_line_chart(
                            sens["initial_range"],
                            sens["initial_values"],
                            int(total_budget),
                            T["chart_initial_x"],
                            T["chart_value"],
                            T["chart_line_title_i"],
                        ),
                        use_container_width=True,
                    )
            else:
                st.error(T["result_ng"])

