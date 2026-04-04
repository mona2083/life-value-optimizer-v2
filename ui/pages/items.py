"""
Items page - displays selected items from optimization.
"""

import streamlit as st
import pandas as pd


def render_selected_items(result, lang, T):
    """
    Render the selected items section.
    
    Args:
        result: Optimizer result dict
        lang: Language code
        T: Translation dictionary
    """
    st.subheader(T.get("sel_items", ""))
    
    selected = result.get("selected", [])
    if not selected:
        st.info(T.get("sel_items_empty", "No items selected"))
        return
    
    # Prepare DataFrame
    rows = []
    for item in selected:
        name = item.get("name_ja") if lang == "ja" else item.get("name_en", item.get("name", ""))
        rows.append({
            "Name": name,
            "Category": item.get("category", ""),
            "Priority": item.get("priority", 0),
            "Initial Cost": f"${item.get('initial_cost', 0):,}",
            "Monthly Cost": f"${item.get('monthly_cost', 0):,}",
        })
    
    if rows:
        df_display = pd.DataFrame(rows)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.write(T.get("none", "None"))
