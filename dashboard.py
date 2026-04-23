import streamlit as st

# =====================================================================
# Global Configuration (Must be the first Streamlit command)
# =====================================================================
st.set_page_config(
    page_title="Life & Financial Dashboard",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =====================================================================
# Global State Initialization
# =====================================================================
if "lang" not in st.session_state:
    st.session_state.lang = "ja"

# =====================================================================
# Global Sidebar (Shared across all pages)
# =====================================================================
with st.sidebar:
    st.title("Navigation")
    new_lang = st.radio(
        "Language / 言語",
        ["ja", "en"],
        index=0 if st.session_state.lang == "ja" else 1,
        format_func=lambda c: "日本語" if c == "ja" else "English",
    )
    if new_lang != st.session_state.lang:
        st.session_state.lang = new_lang
        st.rerun()

# =====================================================================
# Navigation Setup (Streamlit 1.36+)
# =====================================================================
pg = st.navigation([
    st.Page("app.py", title="Life-Value Optimizer", icon="⚖️"),
    st.Page("spending_app.py", title="Spending Analyzer", icon="📊")
])
pg.run()