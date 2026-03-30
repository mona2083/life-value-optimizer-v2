import streamlit as st
import pandas as pd
from default_items import CATEGORIES

def render_item_review(T, lang):
    st.header(T.get("step4_title", "4. ⚙️ Items"))

    def _mark_manual(key_name: str) -> None:
        """Flags that the user manually edited an item, preventing automatic overrides."""
        st.session_state[f"manual_{key_name}"] = True

    with st.expander(T.get("item_review_expander", "Review & Edit Categorized Items")):
        st.info(T.get("item_review_info", "Review and manually adjust the estimated items derived from your lifestyle answers if needed."))

        st.subheader(T.get("add_custom_item_title", "Add Custom Item"))
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
                item_name = st.text_input(T.get("form_item_name", "Item Name"))
            with f3:
                priority_new = st.slider(T.get("form_priority", "Priority"), 0, 10, 3)

            c1, c2 = st.columns(2)
            with c1:
                initial_cost_new = st.number_input(
                    T.get("form_initial", "Initial Cost ($)"),
                    min_value=0,
                    value=0,
                    step=50,
                )
            with c2:
                monthly_cost_new = st.number_input(
                    T.get("form_monthly", "Monthly Cost ($)"),
                    min_value=0,
                    value=0,
                    step=10,
                )

            v1, v2, v3, v4 = st.columns(4)
            with v1:
                health_new = st.slider(T.get("form_health", "Health Impact"), -10, 10, 0)
            with v2:
                conn_new = st.slider(T.get("form_connections", "Connections Impact"), -10, 10, 0)
            with v3:
                free_new = st.slider(T.get("form_freedom", "Freedom Impact"), -10, 10, 0)
            with v4:
                grow_new = st.slider(T.get("form_growth", "Growth Impact"), -10, 10, 0)

            submit_add = st.form_submit_button(
                T.get("form_submit_add", "Add Item"),
                use_container_width=True,
            )

            if submit_add:
                if not item_name.strip():
                    st.warning(T.get("warn_item_name_required", "Item name is required."))
                else:
                    cat_key = next((k for k, v in CATEGORIES[lang].items() if v == selected_cat_label), None)
                    if cat_key is None:
                        st.error(T.get("err_category_resolve", "Could not resolve selected category."))
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
                        st.success(T.get("success_item_added", "Item added successfully!"))
                        st.rerun()

        st.divider()
        st.subheader(T.get("item_list_subheader", "Item List"))
        cat_items = list(CATEGORIES[lang].items())
        cat_tabs = st.tabs([cat_name for _, cat_name in cat_items])

        for tab, (cat_key, cat_name) in zip(cat_tabs, cat_items):
            with tab:
                df = st.session_state.category_dfs[cat_key]

                for idx, row in df.iterrows():
                    # Display values potentially overridden by lifestyle questionnaire dynamically
                    pri_key = f"priority_{cat_key}_{idx}"
                    mc_key = f"monthly_cost_{cat_key}_{idx}"
                    ic_key = f"initial_cost_{cat_key}_{idx}"
                    mand_key = f"mandatory_{cat_key}_{idx}"

                    # Fallback to dataframe default if missing from session state (e.g., app reset)
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
                            T.get("mandatory_label", "Mandatory"),
                            key=mand_key,
                            on_change=_mark_manual,
                            args=(mand_key,),
                        )
                        # Ensure priority is at least 1 if an item is marked mandatory
                        if is_mandatory and st.session_state.get(pri_key, 0) <= 0:
                            st.session_state[pri_key] = 1
                    with c1:
                        lbl = f"{row['name']} {T.get('item_slider_suffix', '')}"
                        if st.session_state[mand_key]:
                            st.caption("✅ " + T.get("item_slider_caption_mandatory", "Must have (Cannot be excluded)"))
                        st.slider(lbl, 0, 10, key=pri_key, on_change=_mark_manual, args=(pri_key,))
                    with c2:
                        st.number_input(T.get("lbl_mc", "Monthly $"), min_value=0, key=mc_key, on_change=_mark_manual, args=(mc_key,))
                    with c3:
                        st.number_input(T.get("lbl_ic", "Initial $"), min_value=0, key=ic_key, on_change=_mark_manual, args=(ic_key,))