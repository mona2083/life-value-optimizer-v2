import streamlit as st

def render_financial_setup(T):
    st.header(T.get("step1_title", "1. 💰 予算と目標の設定"))

    with st.container(border=True):
        st.subheader(T.get("section_budget", "💵 Monthly budget"))
        know_budget = st.radio(
            T.get("know_budget_q", ""),
            [T.get("yes_calc", "Yes"), T.get("no_calc", "No")],
        )

        monthly_budget = 0
        debt_repayment = 0
        if know_budget == T.get("yes_calc", ""):
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                monthly_budget_raw = st.number_input(
                    T.get("budget_label", "Monthly budget ($)"),
                    min_value=0,
                    value=1500,
                    step=100,
                )
            with col_b2:
                debt_repayment = st.number_input(
                    T.get("lbl_debt_repayment", "Loan / Debt repayment ($)"),
                    min_value=0,
                    value=0,
                    step=50,
                )
            monthly_budget = monthly_budget_raw - debt_repayment
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
                    debt_repayment = st.number_input(
                        T.get("lbl_debt_repayment", "Loan / Debt repayment ($)"),
                        min_value=0,
                        value=0,
                        step=50,
                    )
                    other_fixed = st.number_input(
                        T.get("lbl_other_fixed", ""),
                        min_value=0,
                        value=300,
                        step=50,
                    )
                monthly_budget = income - (rent_util + insurance + telecom + debt_repayment + other_fixed)
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

    # Calculate necessary monthly savings internally for the optimizer
    target_monthly_savings = target_total_savings / (savings_period_years * 12) if savings_period_years > 0 else 0

    # Show alerts to visualize the gap between target savings and disposable income
    if monthly_budget > 0:
        savings_ratio = (target_monthly_savings / monthly_budget) * 100
        if savings_ratio > 100:
            st.error(
                T.get("alert_savings_impossible", "").format(
                    int_target=int(target_monthly_savings),
                    int_budget=int(monthly_budget)
                ) or f"⚠️ **Unrealistic goal**: The calculated monthly savings (${int(target_monthly_savings):,}) exceeds your available budget (${int(monthly_budget):,})."
            )
        elif savings_ratio >= 50:
            st.warning(
                T.get("alert_savings_high", "").format(
                    int_target=int(target_monthly_savings),
                    int_budget=int(monthly_budget),
                    ratio=savings_ratio
                ) or f"⚠️ **Strict goal**: The calculated monthly savings (${int(target_monthly_savings):,}) takes up {savings_ratio:.0f}% of your available budget (${int(monthly_budget):,})."
            )
        elif target_monthly_savings > 0:
            st.info(
                T.get("alert_savings_healthy", "").format(
                    int_target=int(target_monthly_savings),
                    int_budget=int(monthly_budget),
                    ratio=savings_ratio
                ) or f"💡 **Realistic goal**: You will save {savings_ratio:.0f}% of your monthly budget (${int(monthly_budget):,})."
            )

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
            "debt_repayment": debt_repayment,
        }
    }

def render_passion_text_input(T: dict) -> str:
    """
    ユーザーの自由記述テキスト入力UI
    「あなたのことを教えてください」という1つの大きなテキストボックス
    """
    st.header(T.get("passion_title", "✨ Tell us about yourself"))
    st.markdown(T.get("passion_intro", ""))
    
    passion_text = st.text_area(
        T.get("passion_label", "Please describe your life, interests, location, work, and anything else important to you."),
        height=150,
        placeholder=T.get("passion_placeholder", "e.g., I'm a student living in Hawaii, I have a car, I love surfing and meeting new people..."),
        key="passion_text"
    )
    
    return passion_text