import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from llm import get_result_summary
from ui.logic import dict_get_or_zero
from optimizer import food_related_score
from default_items import CATEGORIES, DEFAULT_ITEMS


def _count_non_default_rows(df) -> int:
    if df is None:
        return 0
    return len([idx for idx, row in df.iterrows() if row.get("source") != "default"])


def _build_item_group_stats(selected, category_keys, lang: str) -> dict:
    category_dfs = getattr(st.session_state, "category_dfs", {}) if hasattr(st.session_state, "category_dfs") else {}
    category_key_set = set(category_keys)

    selected_in_group = [it for it in selected if it.get("category") in category_key_set]
    default_available = len([it for it in DEFAULT_ITEMS if it.get("category") in category_key_set])
    ai_available = sum(_count_non_default_rows(category_dfs.get(cat_key)) for cat_key in category_keys)
    total_available = default_available + ai_available

    selected_count = len(selected_in_group)
    default_selected_count = len([it for it in selected_in_group if it.get("source") == "default"])
    ai_selected_count = len([it for it in selected_in_group if it.get("source") != "default"])
    selection_rate = (selected_count / total_available * 100) if total_available > 0 else 0

    breakdown_lines = []
    for cat_key in category_keys:
        cat_default = len([it for it in DEFAULT_ITEMS if it.get("category") == cat_key])
        cat_ai = _count_non_default_rows(category_dfs.get(cat_key)) if cat_key in category_dfs else 0
        cat_selected = len([it for it in selected if it.get("category") == cat_key])
        cat_total = cat_default + cat_ai
        if cat_default > 0 or cat_ai > 0 or cat_selected > 0:
            cat_label = CATEGORIES[lang].get(cat_key, cat_key)
            breakdown_lines.append(f"• {cat_label}: {cat_selected}/{cat_total}")

    return {
        "selected_count": selected_count,
        "default_selected_count": default_selected_count,
        "ai_selected_count": ai_selected_count,
        "default_available": default_available,
        "ai_available": ai_available,
        "total_available": total_available,
        "selection_rate": selection_rate,
        "breakdown_lines": breakdown_lines,
    }


def _render_item_group_breakdown(selected, lang: str) -> None:
    group_labels = {
        "transport": "🚗 移動・交通" if lang == "ja" else "🚗 Transport",
        "others": "📚 それ以外のカテゴリ" if lang == "ja" else "📚 Other categories",
    }
    metric_labels = {
        "selected": "選択数" if lang == "ja" else "Selected",
        "default": "デフォルト" if lang == "ja" else "Default",
        "ai": "AI提案" if lang == "ja" else "AI Proposed",
        "rate": "選択率" if lang == "ja" else "Rate",
        "no_items": "対象アイテムはありません" if lang == "ja" else "No items in this group",
        "not_selected": "未選択" if lang == "ja" else "Not selected",
        "selected_method": "選択手段" if lang == "ja" else "Selected method",
    }

    others_stats = _build_item_group_stats(selected, ["living", "wellbeing", "leisure", "learning"], lang)
    transport_selected = [it for it in selected if it.get("category") == "transport"]
    transport_names = []
    for item in transport_selected:
        name = item.get("name_ja") if lang == "ja" else item.get("name_en")
        transport_names.append(name or item.get("name") or "")

    col_left, col_right = st.columns([4, 6])

    with col_left:
        with st.container(border=True):
            st.markdown(f"**{group_labels['transport']}**")
            if transport_names:
                st.markdown(f"**{metric_labels['selected_method']}**")
                st.markdown("\n".join([f"- {name}" for name in transport_names]))
            else:
                st.caption(metric_labels["not_selected"])

    with col_right:
        with st.container(border=True):
            st.markdown(f"**{group_labels['others']}**")
            rate_text = f"{others_stats['selection_rate']:.1f}%" if others_stats["total_available"] > 0 else "-"
            metric1, metric2, metric3, metric4 = st.columns(4)
            with metric1:
                st.metric(metric_labels["selected"], f"{others_stats['selected_count']}/{others_stats['total_available']}")
            with metric2:
                st.metric(metric_labels["default"], f"{others_stats['default_selected_count']}/{others_stats['default_available']}")
            with metric3:
                st.metric(metric_labels["ai"], f"{others_stats['ai_selected_count']}/{others_stats['ai_available']}")
            with metric4:
                st.metric(metric_labels["rate"], rate_text)

            st.divider()
            if others_stats["breakdown_lines"]:
                st.markdown("\n".join(others_stats["breakdown_lines"]))
            else:
                st.caption(metric_labels["no_items"])

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
    # Non-AI Execution Dashboard (displayed right after optimization results)
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
    debt_repayment = float((financial_data or {}).get("user_profile", {}).get("debt_repayment", 0) or 0)
    monthly_rate_raw = (actual_monthly / target_monthly) if target_monthly > 0 else 1.0
    tot_monthly_spend = float(result.get("total_monthly_cost", 0) or 0)
    # Optimization side: monthly_budget = tot_monthly_spend + actual_monthly (always fully allocated)
    alloc_sum = tot_monthly_spend + actual_monthly
    initial_used = float(result.get("total_initial_cost", 0) or 0)
    initial_left = max(initial_budget - initial_used, 0)

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
                    T.get("dash_metric_monthly_pool", ""),
                    f"${int(monthly_budget):,}",
                )
            with m_right:
                fixed_label = "月固定費" if lang == "ja" else "Monthly fixed costs"
                st.metric(
                    fixed_label,
                    f"${int(fixed_sum):,}",
                )
            
            deducts = []
            if debt_repayment > 0:
                deducts.append(f"ローン(\\${int(debt_repayment):,})" if lang == "ja" else f"Loan (\\${int(debt_repayment):,})")
            if dict_get_or_zero(financial_data, "food_minimalist_floor") > 0:
                deducts.append(f"基本食費(\\${int(dict_get_or_zero(financial_data, 'food_minimalist_floor')):,})" if lang == "ja" else f"Base food (\\${int(dict_get_or_zero(financial_data, 'food_minimalist_floor')):,})")
            if risk_cost > 0:
                deducts.append(f"リスク(\\${int(risk_cost):,})" if lang == "ja" else f"Risk (\\${int(risk_cost):,})")
            
            if deducts:
                calc_text = f"月固定費内訳：{' + '.join(deducts)}" if lang == "ja" else f"Fixed breakdown: {' + '.join(deducts)}"
                st.caption(f"💡 {calc_text}")

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
            if lang == "ja":
                st.caption(f"💡 初期費内訳：予算(\\${int(initial_budget):,}) = Used(\\${int(initial_used):,}) + Remaining(\\${int(initial_left):,})")
            else:
                st.caption(f"💡 Initial breakdown: Budget(\\${int(initial_budget):,}) = Used(\\${int(initial_used):,}) + Left(\\${int(initial_left):,})")

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
            if lang == "ja":
                st.caption(f"💡 貯蓄内訳：目標額(\\${int(target_monthly):,}) achievement rate")
            else:
                st.caption(f"💡 Savings breakdown: Achievement vs Target(\\${int(target_monthly):,})")

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
                st.caption(f"💡 食費内訳：固定(\\${int(food_floor):,}) + 通常(\\${int(food_stage1_used):,}) + グレードアップ(\\${int(food_stage2_used):,}) = 合計(\\${int(food_total):,})")
            else:
                st.caption(f"💡 Food breakdown: Base(\\${int(food_floor):,}) + Std(\\${int(food_stage1_used):,}) + Upgrade(\\${int(food_stage2_used):,}) = Total(\\${int(food_total):,})")


    # アイテム選択カウント表示
    if selected:
        with st.container(border=True):
            st.markdown(f"**📦 {'アイテム選択数' if lang == 'ja' else 'Selected Items'} / 📊 {'カテゴリ別内訳' if lang == 'ja' else 'Category Breakdown'}**")
            _render_item_group_breakdown(selected, lang)


    # AI Life Coach Dashboard (inserted between budget summary and category breakdown)
    st.divider()
    if not use_ai_for_summary:
        st.caption(T.get("ai_summary_off", "AI summary is turned off."))
    elif summary := get_result_summary(
        result,
        user_profile,
        weights,
        lang,
        context={
            "financial_data": financial_data or {},
            "lifestyle_data": (financial_data or {}).get("lifestyle_data", {}) or {},
            "food_data": (financial_data or {}).get("food_data", {}) or {},
            "candidates": (financial_data or {}).get("candidates", []) or [],
        },
    ):
        st.subheader(T.get("ai_dashboard", "💡 AI ライフコーチ ダッシュボード"))
        lbl_theme = T.get("theme", "テーマ")
        lbl_analysis = "Overall Analysis" if lang == "ja" else "Overall Analysis"
        lbl_food_advice = T.get("food_advice", "食費の分析")
        lbl_savings_advice = T.get("savings_advice", "貯蓄の分析")
        lbl_blind_spot = T.get("blind_spot", "死角・リスク")
        lbl_action = T.get("next_action", "次のアクション")

        concept_text = str(summary.get("concept", "") or "").strip()
        analysis_text = str(summary.get("analysis", "") or "").strip()
        food_advice_text = str(summary.get("food_advice", "") or "").strip()
        savings_advice_text = str(summary.get("savings_advice", "") or "").strip()
        blind_spot_text = str(summary.get("blind_spot", "") or "").strip()
        action_text = str(summary.get("next_action", "") or "").strip()

        st.info(f"**{lbl_theme}： {concept_text or ('Could not be generated' if lang == 'ja' else 'Not generated')}**")

        col_sum_left, col_sum_right = st.columns(2)
        
        with col_sum_left:
            with st.container(border=True):
                st.markdown(f"**{lbl_analysis}**")
                st.write(analysis_text or ("分析をCould not be generated。" if lang == "ja" else "Analysis could not be generated."))
            with st.container(border=True):
                st.markdown(f"**{lbl_food_advice}**")
                st.write(food_advice_text or ("分析をCould not be generated。" if lang == "ja" else "Analysis could not be generated."))
            
        with col_sum_right:
            with st.container(border=True):
                st.markdown(f"**{lbl_savings_advice}**")
                st.write(savings_advice_text or ("分析をCould not be generated。" if lang == "ja" else "Analysis could not be generated."))
            with st.container(border=True):
                st.markdown(f"**{lbl_blind_spot}**")
                st.write(blind_spot_text or ("No clear blind spots were found at this time." if lang == "ja" else "No clear blind spot was identified."))

        st.success(f"**{lbl_action}**\n\n{action_text or ('Start by deciding on one small action you can take today.' if lang == 'ja' else 'Start with one small action you can do today.')}")
    else:
        st.caption(T.get("ai_error_summary", "AIダッシュボードの生成に失敗しました。"))
    st.divider()

    # 2) Usage amount/ratio by category (monthly/initial)
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

        # Additional metric: Alignment between value weights and selected items
        # Calculation: Converted to match degree from L1 distance between 'weight share' and 'realized share (negatives treated as 0)' of each axis
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
    # Non-AI Execution Dashboard (displayed right after optimization results)
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
    debt_repayment = float((financial_data or {}).get("user_profile", {}).get("debt_repayment", 0) or 0)
    monthly_rate_raw = (actual_monthly / target_monthly) if target_monthly > 0 else 1.0
    tot_monthly_spend = float(result.get("total_monthly_cost", 0) or 0)
    # Optimization side: monthly_budget = tot_monthly_spend + actual_monthly (always fully allocated)
    alloc_sum = tot_monthly_spend + actual_monthly
    initial_used = float(result.get("total_initial_cost", 0) or 0)
    initial_left = max(initial_budget - initial_used, 0)

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
                    T.get("dash_metric_monthly_pool", ""),
                    f"${int(monthly_budget):,}",
                )
            with m_right:
                fixed_label = "月固定費" if lang == "ja" else "Monthly fixed costs"
                st.metric(
                    fixed_label,
                    f"${int(fixed_sum):,}",
                )
            
            deducts = []
            if debt_repayment > 0:
                deducts.append(f"ローン(\\${int(debt_repayment):,})" if lang == "ja" else f"Loan (\\${int(debt_repayment):,})")
            if dict_get_or_zero(financial_data, "food_minimalist_floor") > 0:
                deducts.append(f"基本食費(\\${int(dict_get_or_zero(financial_data, 'food_minimalist_floor')):,})" if lang == "ja" else f"Base food (\\${int(dict_get_or_zero(financial_data, 'food_minimalist_floor')):,})")
            if risk_cost > 0:
                deducts.append(f"リスク(\\${int(risk_cost):,})" if lang == "ja" else f"Risk (\\${int(risk_cost):,})")
            
            if deducts:
                calc_text = f"月固定費内訳：{' + '.join(deducts)}" if lang == "ja" else f"Fixed breakdown: {' + '.join(deducts)}"
                st.caption(f"💡 {calc_text}")

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
            if lang == "ja":
                st.caption(f"💡 初期費内訳：予算(\\${int(initial_budget):,}) = Used(\\${int(initial_used):,}) + Remaining(\\${int(initial_left):,})")
            else:
                st.caption(f"💡 Initial breakdown: Budget(\\${int(initial_budget):,}) = Used(\\${int(initial_used):,}) + Left(\\${int(initial_left):,})")

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
            if lang == "ja":
                st.caption(f"💡 貯蓄内訳：目標額(\\${int(target_monthly):,}) achievement rate")
            else:
                st.caption(f"💡 Savings breakdown: Achievement vs Target(\\${int(target_monthly):,})")

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
                st.caption(f"💡 食費内訳：固定(\\${int(food_floor):,}) + 通常(\\${int(food_stage1_used):,}) + グレードアップ(\\${int(food_stage2_used):,}) = 合計(\\${int(food_total):,})")
            else:
                st.caption(f"💡 Food breakdown: Base(\\${int(food_floor):,}) + Std(\\${int(food_stage1_used):,}) + Upgrade(\\${int(food_stage2_used):,}) = Total(\\${int(food_total):,})")

    # アイテム選択カウント表示
    if selected:
        with st.container(border=True):
            st.markdown(f"**📦 {'アイテム選択数' if lang == 'ja' else 'Selected Items'} / 📊 {'カテゴリ別内訳' if lang == 'ja' else 'Category Breakdown'}**")
            _render_item_group_breakdown(selected, lang)

    # AI Life Coach Dashboard (inserted between budget summary and category breakdown)
    st.divider()
    if not use_ai_for_summary:
        st.caption(T.get("ai_summary_off", "AI summary is turned off."))
    elif summary := get_result_summary(
        result,
        user_profile,
        weights,
        lang,
        context={
            "financial_data": financial_data or {},
            "lifestyle_data": (financial_data or {}).get("lifestyle_data", {}) or {},
            "food_data": (financial_data or {}).get("food_data", {}) or {},
            "candidates": (financial_data or {}).get("candidates", []) or [],
        },
    ):
        st.subheader(T.get("ai_dashboard", "💡 AI ライフコーチ ダッシュボード"))
        lbl_theme = T.get("theme", "テーマ")
        lbl_analysis = "Overall Analysis" if lang == "ja" else "Overall Analysis"
        lbl_food_advice = T.get("food_advice", "食費の分析")
        lbl_savings_advice = T.get("savings_advice", "貯蓄の分析")
        lbl_blind_spot = T.get("blind_spot", "死角・リスク")
        lbl_action = T.get("next_action", "次のアクション")

        concept_text = str(summary.get("concept", "") or "").strip()
        analysis_text = str(summary.get("analysis", "") or "").strip()
        food_advice_text = str(summary.get("food_advice", "") or "").strip()
        savings_advice_text = str(summary.get("savings_advice", "") or "").strip()
        blind_spot_text = str(summary.get("blind_spot", "") or "").strip()
        action_text = str(summary.get("next_action", "") or "").strip()

        st.info(f"**{lbl_theme}： {concept_text or ('Could not be generated' if lang == 'ja' else 'Not generated')}**")

        col_sum_left, col_sum_right = st.columns(2)
        
        with col_sum_left:
            with st.container(border=True):
                st.markdown(f"**{lbl_analysis}**")
                st.write(analysis_text or ("分析をCould not be generated。" if lang == "ja" else "Analysis could not be generated."))
            with st.container(border=True):
                st.markdown(f"**{lbl_food_advice}**")
                st.write(food_advice_text or ("分析をCould not be generated。" if lang == "ja" else "Analysis could not be generated."))
            
        with col_sum_right:
            with st.container(border=True):
                st.markdown(f"**{lbl_savings_advice}**")
                st.write(savings_advice_text or ("分析をCould not be generated。" if lang == "ja" else "Analysis could not be generated."))
            with st.container(border=True):
                st.markdown(f"**{lbl_blind_spot}**")
                st.write(blind_spot_text or ("No clear blind spots were found at this time." if lang == "ja" else "No clear blind spot was identified."))

        st.success(f"**{lbl_action}**\n\n{action_text or ('Start by deciding on one small action you can take today.' if lang == 'ja' else 'Start with one small action you can do today.')}")
    else:
        st.caption(T.get("ai_error_summary", "AIダッシュボードの生成に失敗しました。"))
    st.divider()

    # 2) Usage amount/ratio by category (monthly/initial)
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

        # Additional metric: Alignment between value weights and selected items
        # Calculation: Converted to match degree from L1 distance between 'weight share' and 'realized share (negatives treated as 0)' of each axis
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