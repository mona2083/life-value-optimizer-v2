"""
Summary/Overview page for results dashboard.
Displays key metrics and execution summary.
"""

import streamlit as st
from ui.logic import dict_get_or_zero


def render_overview_metrics(financial_data, result, lang, T):
    """
    Render the overview section with key financial metrics.
    
    Args:
        financial_data: Dict with budget and financial info
        result: Optimizer result dict
        lang: Language code ('en' or 'ja')
        T: Translation dictionary
    """
    # Extract financial values
    monthly_budget = float((financial_data or {}).get("monthly_budget", 0) or 0)
    initial_budget = float((financial_data or {}).get("initial_budget", 0) or 0)
    food_floor = float((financial_data or {}).get("food_minimalist_floor", 0) or 0)
    food_info = (financial_data or {}).get("estimated_food_cost", {}) or {}
    food_stage1_cap = float((financial_data or {}).get("food_stage1_cap", 0) or 0)
    food_stage2_cap = float((financial_data or {}).get("food_stage2_cap", 0) or 0)
    
    # Extract result values
    food_stage1_used = float(result.get("food_stage1_monthly_cost", 0) or 0)
    food_stage2_used = float(result.get("food_stage2_monthly_cost", 0) or 0)
    food_total = food_floor + food_stage1_used + food_stage2_used
    target_monthly = float(result.get("target_monthly_savings", 0) or 0)
    actual_monthly = float(result.get("actual_monthly_savings", 0) or 0)
    period_years = int((financial_data or {}).get("savings_period_years", 1) or 1)
    debt_repayment = float((financial_data or {}).get("user_profile", {}).get("debt_repayment", 0) or 0)
    monthly_rate_raw = (actual_monthly / target_monthly) if target_monthly > 0 else 1.0
    tot_monthly_spend = float(result.get("total_monthly_cost", 0) or 0)
    initial_used = float(result.get("total_initial_cost", 0) or 0)
    initial_left = max(initial_budget - initial_used, 0)
    
    # Display monthly budget section
    st.subheader(T.get("dash_section_overview_title", ""))
    monthly_block = "📅 月次予算" if lang == "ja" else "📅 Monthly budget"
    initial_block = "🧾 初期費用" if lang == "ja" else "🧾 Initial cost"
    savings_block = "💰 貯蓄" if lang == "ja" else "💰 Savings"
    food_block = "🍽️ 食費" if lang == "ja" else "🍽️ Food"
    
    row_a1, row_a2 = st.columns(2)
    
    with row_a1:
        with st.container(border=True):
            st.markdown(f"**{monthly_block}**")
            
            gross_budget = float((financial_data or {}).get("original_monthly_budget", 0) or 0) + debt_repayment
            risk_cost = float((financial_data or {}).get("risk_monthly_total", 0) or 0)
            fixed_sum = debt_repayment + dict_get_or_zero(financial_data, "food_minimalist_floor") + risk_cost
            
            m_left, m_right = st.columns(2)
            with m_left:
                st.metric(
                    T.get("total", "Total"),
                    f"${int(gross_budget):,}",
                )
            with m_right:
                st.metric(
                    T.get("allocatable", "Allocatable"),
                    f"${int(monthly_budget):,}",
                )
            
            m_c1, m_c2 = st.columns(2)
            with m_c1:
                st.metric(
                    T.get("fixed_costs", "Fixed costs"),
                    f"${int(fixed_sum):,}",
                )
            with m_c2:
                st.metric(
                    T.get("allocated_items", "Allocated items"),
                    f"${int(tot_monthly_spend):,}",
                )
    
    with row_a2:
        with st.container(border=True):
            st.markdown(f"**{savings_block}**")
            
            target_text = f"target: ${int(target_monthly)}" if lang == "en" else f"目標: ${int(target_monthly)}"
            st.metric(
                T.get("monthly_savings", "Monthly savings"),
                f"${int(actual_monthly):,}",
                f"{int(monthly_rate_raw * 100)}% {target_text}",
            )
            
            years_text = f"years" if lang == "en" else "年"
            total_savings = actual_monthly * 12 * period_years
            st.metric(
                f"{period_years} {years_text} {T.get('total', 'Total').lower()}",
                f"${int(total_savings):,}",
            )
    
    row_b1, row_b2 = st.columns(2)
    
    with row_b1:
        with st.container(border=True):
            st.markdown(f"**{food_block}**")
            
            f_c1, f_c2 = st.columns(2)
            with f_c1:
                st.metric(
                    T.get("minimalist_floor", "Minimalist floor"),
                    f"${int(food_floor):,}",
                )
            with f_c2:
                st.metric(
                    "Stage1+2",
                    f"${int(food_stage1_used + food_stage2_used):,}",
                )
            
            st.metric(
                T.get("total", "Total"),
                f"${int(food_total):,}",
            )
    
    with row_b2:
        with st.container(border=True):
            st.markdown(f"**{initial_block}**")
            
            i_c1, i_c2 = st.columns(2)
            with i_c1:
                st.metric(
                    T.get("used", "Used"),
                    f"${int(initial_used):,}",
                )
            with i_c2:
                st.metric(
                    T.get("remaining", "Remaining"),
                    f"${int(initial_left):,}",
                )
