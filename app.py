import streamlit as st
import pandas as pd
from lang import LANG
from default_items import DEFAULT_ITEMS, CATEGORIES
import ui as ui_mod

st.set_page_config(page_title="Life-Value Optimizer", layout="wide")

PORTFOLIO_URL = "https://mona2083.github.io/portfolio-2026/index.html"

# ── カスタムCSS ────────────────────────────────────────────────────
st.markdown("""
<style>
div[data-testid="stButton"] > button {
    font-size: 0.7rem !important;
    padding: 2px 10px !important;
    height: auto !important;
    line-height: 1.4 !important;
    white-space: nowrap !important;
}
</style>
""", unsafe_allow_html=True)


def _build_category_df(lang: str, category: str) -> pd.DataFrame:
    name_key = "name_ja" if lang == "ja" else "name_en"
    note_key = "note_ja" if lang == "ja" else "note_en"
    rows = []
    for item in DEFAULT_ITEMS:
        if item["category"] != category:
            continue
        rows.append({
            "name":         item[name_key],
            "initial_cost": item["initial_cost"],
            "monthly_cost": item["monthly_cost"],
            "health":       item["health"],
            "connections":  item["connections"],
            "freedom":      item["freedom"],
            "growth":       item["growth"],
            "priority":     item.get("priority", 0),
            "mandatory":    False,
            "category":     item["category"],
            "note":         item.get(note_key, ""),
        })
    return pd.DataFrame(rows)


def _init_all_category_dfs(lang: str) -> dict:
    return {cat: _build_category_df(lang, cat) for cat in CATEGORIES[lang]}


# ── サイドバーと言語選択 ──────────────────────────────────────────
with st.sidebar:
    lang_choice = st.radio("🌐 Language / 言語", ["日本語", "English"], horizontal=True)
    lang = "ja" if lang_choice == "日本語" else "en"
    T = LANG[lang]
    st.link_button(T["portfolio_btn"], PORTFOLIO_URL)
    st.divider()

# ── セッション初期化 ──────────────────────────────────────────────
if "items_lang" not in st.session_state or st.session_state.items_lang != lang:
    st.session_state.items_lang    = lang
    st.session_state.category_dfs = _init_all_category_dfs(lang)

# ── ヘッダー ──────────────────────────────────────────────────────
head_l, head_r = st.columns([0.78, 0.22], vertical_alignment="center")
with head_l:
    st.title(T["title"])
    st.caption(T["caption"])
with head_r:
    st.link_button(T["portfolio_label"], PORTFOLIO_URL, use_container_width=True)

# ── UIモジュールの呼び出し（ビジネスロジックの分離） ───────────────
(
    age, gender, family, monthly_income, rent, utilities,
    internet, groceries, health_insurance_fixed, other_fixed,
    disposable_income, total_budget,
) = ui_mod.render_step1(T, lang)

(
    savings_period_years, target_monthly_savings,
    w_health, w_connections, w_freedom, w_growth, w_savings,
) = ui_mod.render_step2(T, lang)

lifestyle_adj = ui_mod.render_step2_5(T, lang, disposable_income, savings_period_years)

ui_mod.render_step3(T, lang)

ui_mod.render_risk_and_results(
    T=T,
    lang=lang,
    age=int(age),
    family=family,
    savings_period_years=int(savings_period_years),
    total_budget=int(total_budget),
    target_monthly_savings=int(target_monthly_savings),
    w_health=int(w_health),
    w_connections=int(w_connections),
    w_freedom=int(w_freedom),
    w_growth=int(w_growth),
    w_savings=int(w_savings),
    lifestyle_adj=lifestyle_adj,
)