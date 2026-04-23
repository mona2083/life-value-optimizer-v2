import streamlit as st
import pandas as pd
import json
import re
import unicodedata
import plotly.express as px
import os

# =====================================================================
# Multi-language dictionary for Spending Analyzer
# =====================================================================
LANG = {
    "en": {
        "title": "📊 Spending Analyzer",
        "desc": "Upload your credit card statements (CSV) to analyze your spending habits.",
        "upload_label": "Upload CSV File",
        "rule_error": "Mapping rules config not found.",
        "summary": "Spending Summary",
        "col_error": "Could not identify required columns (Date, Description, Amount). Please check your CSV format.",
        "pie_title": "Spending by Category",
        "bar_title": "Daily Spending Trend",
        "raw_data": "Processed Data",
        "metrics_total": "Total Spent",
        "metrics_transactions": "Transactions",
        "cat_breakdown": "Category Breakdown",
        "filter_label": "Filter details by category",
        "all_cats": "All Categories",
        "filter_year": "Filter by Year",
        "filter_month": "Filter by Month",
        "all_years": "All Years",
        "all_months": "All Months",
        "trend_agg_label": "Time Aggregation",
        "agg_monthly": "Monthly",
        "agg_yearly": "Yearly",
        "trend_title": "Spending Trend",
        "trend_filter_cat": "Filter Categories",
        "unclass_title": "❓ Resolve Unclassified (other)",
        "unclass_desc": "Assign categories to these top unclassified merchants to train the system.",
        "unclass_all_done": "✅ All items are successfully classified!",
        "rules_mgmt_title": "📚 Rule Management",
        "rules_mgmt_desc": "Edit, add, or delete rules. Grouped by category and sorted alphabetically.",
        "save_rules_btn": "💾 Save '{cat}' Rules",
        "save_success": "Rules saved successfully!",
        "manual_override_btn": "Add Rule",
        "budget_title": "Monthly Budget Target",
        "budget_label": "Budget ($)",
        "metrics_income": "Total Income",
        "metrics_cashflow": "Net Cash Flow",
        "subs_title": "Recurring Expenses (Subscriptions)",
        "subs_ignore_btn": "Ignore Selected",
        "budget_usage": "Budget Usage",
        "tab_dashboard": "Dashboard",
        "tab_settings": "Settings & Adjustments",
        "cat_income": "Income / Deposit",
        "download_csv_btn": "📥 Download Cleaned Data (CSV)",
        "current_rules_title": "Current Mapping Rules",
        "rule_merchant": "Merchant / Keyword",
        "rule_category": "Category",
        "merchant_trend_title": "Merchant Spending Trend",
        "merchant_filter_label": "Select Merchants (Recurring Only)",
    },
    "ja": {
        "title": "📊 支出アナライザー",
        "desc": "クレジットカードの明細（CSV）をアップロードして、支出の傾向を分析します。",
        "upload_label": "CSVファイルをアップロード",
        "rule_error": "マッピングルールの設定ファイルが見つかりません。",
        "summary": "支出サマリー",
        "col_error": "必須カラム（日付、摘要、金額）を自動判別できませんでした。CSVのフォーマットを確認してください。",
        "pie_title": "カテゴリ別支出割合",
        "bar_title": "日別支出トレンド",
        "raw_data": "処理済みデータ",
        "metrics_total": "合計支出",
        "metrics_transactions": "トランザクション数",
        "cat_breakdown": "カテゴリ別内訳",
        "filter_label": "カテゴリで明細を絞り込み",
        "all_cats": "すべてのカテゴリ",
        "filter_year": "年で絞り込み",
        "filter_month": "月で絞り込み",
        "all_years": "すべての年",
        "all_months": "すべての月",
        "trend_agg_label": "集計単位",
        "agg_monthly": "月別",
        "agg_yearly": "年別",
        "trend_title": "支出推移トレンド",
        "trend_filter_cat": "カテゴリで絞り込み",
        "unclass_title": "❓ 未分類データの解決（other）",
        "unclass_desc": "以下の店舗にカテゴリを割り当てると、ルールとして学習・保存されます。（金額が大きい順トップ10）",
        "unclass_all_done": "✅ すべての店舗が分類されています！",
        "rules_mgmt_title": "📚 カテゴリルールの管理・編集",
        "rules_mgmt_desc": "カテゴリごとにタブで分かれています。アルファベット順に表示された店舗名を直接編集・追加・削除できます。",
        "save_rules_btn": "💾 「{cat}」のルールを保存",
        "save_success": "ルールを保存しました！",
        "manual_override_btn": "ルール追加",
        "budget_title": "月間予算設定",
        "budget_label": "予算額 ($)",
        "metrics_income": "総収入",
        "metrics_cashflow": "純キャッシュフロー",
        "subs_title": "定期的な支払い（サブスク・固定費）",
        "subs_ignore_btn": "選択項目を除外",
        "budget_usage": "予算消化率",
        "tab_dashboard": "ダッシュボード",
        "tab_settings": "設定と調整",
        "cat_income": "収入・入金",
        "download_csv_btn": "📥 クリーニング済みデータをダウンロード (CSV)",
        "current_rules_title": "現在のカテゴリルール一覧",
        "rule_merchant": "店舗・キーワード",
        "rule_category": "カテゴリ",
        "merchant_trend_title": "店舗別支出推移トレンド",
        "merchant_filter_label": "店舗を選択（複数回利用のみ）",
    }
}

lang = st.session_state.get("lang", "en")
T = LANG.get(lang, LANG["en"])

st.title(T["title"])
st.markdown(T["desc"])

# =====================================================================
# State Management
# =====================================================================
if "ignored_subs" not in st.session_state:
    st.session_state.ignored_subs = []
if "monthly_budget" not in st.session_state:
    st.session_state.monthly_budget = 2000

# =====================================================================
# Load Spending Rules (Config)
# =====================================================================
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "spending_rules.json")

@st.cache_data
def load_spending_rules(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

rules = load_spending_rules(CONFIG_PATH)
if not rules:
    st.warning(T["rule_error"])

def save_spending_rules(path: str, rules_data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rules_data, f, ensure_ascii=False, indent=2)
    load_spending_rules.clear() # Invalidate Streamlit cache

# =====================================================================
# Data Normalization & Categorization Logic
# =====================================================================
def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize varied bank CSV columns into standard 'date', 'desc', 'amount'."""
    col_mapping = {
        'date': ['date', 'transaction date', 'post date', '日付', 'ご利用日', '利用日', 'お取扱日', 'ご利用年月日', '利用年月日', '取引日'],
        'desc': ['description', 'payee', 'merchant', 'name', '詳細', 'ご利用店名', '摘要', '利用店名', '利用先', 'ご利用店名・商品名', '店舗名'],
        'amount': ['amount', 'cost', 'price', 'debit', '金額', '支払額', '利用金額', 'ご利用金額', 'お支払金額', '出金額', '引出金額', '引出額'],
        'income': ['income', 'deposit', 'credit', '入金額', '預入額', '入金']
    }
    
    # Clean dataframe columns for matching (lowercase, strip whitespace)
    df_cols_cleaned = {str(c).strip().lower(): str(c) for c in df.columns}
    norm_df = pd.DataFrame()
    
    for std_col, candidates in col_mapping.items():
        # 1. Try exact match on cleaned column names
        for c in candidates:
            if c in df_cols_cleaned:
                norm_df[std_col] = df[df_cols_cleaned[c]]
                break
                
        # 2. If not found, try partial match (substring) fallback
        if std_col not in norm_df.columns:
            for col_clean, col_orig in df_cols_cleaned.items():
                if any(c in col_clean for c in candidates):
                    norm_df[std_col] = df[col_orig]
                    break
                
    return norm_df

def assign_category_and_name(desc: str, mapping_rules: dict, aliases: dict):
    desc_lower = str(desc).lower()
    
    # 1. 表記揺れ（エイリアス）の吸収
    sorted_aliases = sorted(aliases.keys(), key=len, reverse=True)
    for alias in sorted_aliases:
        if alias in desc_lower:
            desc_lower = aliases[alias]
            break
            
    # 2. ルールマッチと店舗名の名寄せ（統一）
    sorted_keywords = sorted(mapping_rules.keys(), key=len, reverse=True)
    for keyword in sorted_keywords:
        if keyword.lower() in desc_lower:
            canon_name = " ".join(w.capitalize() for w in keyword.split())
            return canon_name, mapping_rules[keyword]
            
    return desc, "other"

def is_excluded_transaction(desc: str) -> bool:
    """Identify internal transfers and credit card payments to exclude."""
    exclude_keywords = [
        '新規開設', 'へ振替', 'より振替', 'payment - thank you', 'online payment', 'autopay'
    ]
    # NFKC正規化で全角半角の揺れをなくしてから判定
    desc_norm = unicodedata.normalize('NFKC', str(desc)).lower()
    return any(keyword in desc_norm for keyword in exclude_keywords)

def clean_description(desc: str) -> str:
    """Extract pure company name by removing bank/location noise."""
    if pd.isna(desc): return ""
    
    # NFKC正規化: Ｖｉｓａ -> Visa, ﾃﾞﾋﾞｯﾄ -> デビット, 全角スペース -> 半角スペース
    # 日本の銀行CSV特有の全角/半角表記揺れを統一（これが無いと正規表現が全てすり抜けます）
    d = unicodedata.normalize('NFKC', str(desc)).strip()
    orig = d
    
    # 1. 明示的なトランザクション・伝票番号プレフィックスの削除 (Transaction, Ref, ID, POS など)
    d = re.sub(r'(?i)^(?:transaction|trans|txn|ref|reference|id|auth|pos|card|no\.?|#)\s*[:\-]?\s*[a-z0-9\-\*]+\s+', '', d)

    # 2. 決済・送金プレフィックスとそれに続く承認番号の削除
    d = re.sub(r'(?i)^(?:[a-z0-9]*デビット|id払い|quicpay|applepay|paypay|suica|pasmo|被仕向外貨送金|外貨送金|送金振込|送金|振込|決済)\s*(?:\d+\s+)?', '', d)

    # 3. PayPal, Square等の決済代行・アグリゲーターのプレフィックス削除 (全角アスタリスク・各種ダッシュ記号対応)
    d = re.sub(r'(?i)^[a-z0-9]{2,15}\s*[\*＊]\s*(?:[a-z0-9]+\s*[\-\:\_ー—–]+)?\s*', '', d)

    # 4. 先頭に残った純粋な数字（3桁以上）や日付の削除（各種ダッシュ記号対応）
    d = re.sub(r'^\d{3,}[\s\-\_\:\.ー—–]+', '', d)
    d = re.sub(r'^\d{2,4}[/:\-]\d{2}(?:[/:\-]\d{2,4})?[\s\-\_\:\.ー—–]+', '', d)

    # 5. 先頭の英数字混在ID（5文字以上、英字と数字の両方を含む）の削除
    d = re.sub(r'^(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{5,}[\s\-\_\:\.ー—–]+', '', d)

    # 6. サブスクリプションなどの固定文字列以降を削除 (例: CLAUDE.AI SUBSCRIPTISAN FRANCISCO -> CLAUDE.AI)
    d = re.sub(r'(?i)\s*(?:subscripti|recurring|autopay|payment).*$', '', d)

    # 7. Webドメイン(.com等)以降のランダム文字列を削除 (例: TOTALAVPRO.COM XADDD -> TOTALAVPRO.COM)
    d = re.sub(r'(?i)(\.com|\.net|\.org|\.io)[\*\s]+.*$', r'\1', d)

    # 8. AmazonやMarketplaceの固有ノイズを削除 (例: AMAZON MKTPL*ddd -> AMAZON)
    d = re.sub(r'(?i)\s*(?:MKTPL?|MARKETPLACE|MKTP)[\*\s]*.*$', '', d)

    # 9. ハイフン等による支店名・補足情報の分離を削除 (例: DAISO - PIIKOI -> DAISO)
    d = re.sub(r'\s+-\s+.*$', '', d)

    # 10. ショッピングモール名の削除 (例: ALA MOANA FOODLAND -> FOODLAND)
    d = re.sub(r'(?i)\b(?:ALA MOANA|PEARLRIDGE)\b', '', d)

    # 7. 米国系: 連続する数字（店番号）以降を削除 (例: SAM'S CLUB 4755 4755HONOLULU)
    d = re.sub(r'(?<=[a-zA-Z\'"&])\s+\d{3,}.*$', '', d)

    # 8. 店舗番号・ブランチ記号の削除 (例: #2944, No.123)
    d = re.sub(r'(?i)(?:#|no\.?)\s*\d+', '', d)

    # 9. ハワイ・特定都市の地名ノイズ削除 (例: DON QUIJOTE KAHEKA -> DON QUIJOTE)
    d = re.sub(r'(?i)\s+(?:HONOLULU|KAHEKA|HAWAII|HAWA|QUE|WAIKIKI|KAPOLEI|KAILUA)\b.*$', '', d)

    # 10. ストリート名と前の単語を削除 (例: DAISO PIIKOI ST -> DAISO)
    d = re.sub(r'(?i)\s+[a-z]+\s+(?:st|ave|blvd|rd|dr|ln|way|ct|pl|sq|street|avenue|road|drive)\b.*$', '', d)

    # 11. 電話番号の削除
    d = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '', d)

    # 12. 米国の州コードの削除 (例: CA, HI)
    d = re.sub(r'(?i)\s+[a-z]{2}$', '', d)

    # 13. 連続する空白の処理: 2つ以上連続する空白がある場合、それ以降は場所名などのノイズとみなして削除
    if '  ' in d:
        d = d.split('  ')[0]
        
    d = re.sub(r'\s+', ' ', d).strip()
    
    return d if d else orig

# =====================================================================
# File Upload & Analysis
# =====================================================================
uploaded_file = st.file_uploader(T["upload_label"], type=["csv"])

if uploaded_file is not None:
    try:
        # Robust loading: attempt multiple encodings for varied bank CSVs (e.g., Shift-JIS in Japan)
        encodings_to_try = ['utf-8', 'shift_jis', 'cp932', 'latin1']
        raw_df = None
        
        for enc in encodings_to_try:
            try:
                uploaded_file.seek(0) # Reset file pointer before each read attempt
                raw_df = pd.read_csv(uploaded_file, encoding=enc)
                break # Success
            except UnicodeDecodeError:
                continue
                
        if raw_df is None:
            raise ValueError("Could not decode the CSV file. Please ensure it is saved in UTF-8 or Shift-JIS format.")
            
        df = normalize_dataframe(raw_df)
        
        if not {'date', 'desc', 'amount'}.issubset(df.columns):
            missing = {'date', 'desc', 'amount'} - set(df.columns)
            found_cols = list(raw_df.columns)
            st.error(f"{T['col_error']}\n\n**Missing mapped columns:** {missing}\n\n**Found CSV columns:** {found_cols}")
            st.stop()
            
        # Filter exclusions and clean descriptions
        df = df[~df['desc'].apply(is_excluded_transaction)].copy()
        df['desc'] = df['desc'].apply(clean_description)
            
        # Clean and type conversion for Amount & Income
        df['amount'] = pd.to_numeric(df['amount'].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce')
        if 'income' in df.columns:
            df['income'] = pd.to_numeric(df['income'].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce')
        else:
            df['income'] = 0.0
            # Assume negative amount is income (refund/deposit)
            df.loc[df['amount'] < 0, 'income'] = df['amount'].abs()
            df.loc[df['amount'] < 0, 'amount'] = 0.0
        
        # Clean and type conversion for Date (handles standard and Japanese YYYY年MM月DD日 formats)
        date_str = df['date'].astype(str).str.replace(r'[年月]', '/', regex=True).str.replace(r'日', '', regex=True)
        df['date'] = pd.to_datetime(date_str, errors='coerce')
        
        # Drop invalid rows
        df = df.dropna(subset=['date'])
        df['amount'] = df['amount'].fillna(0).abs()
        df['income'] = df['income'].fillna(0).abs()
        
        # Extract Year and Month for filtering
        df['year'] = df['date'].dt.year.astype(str)
        df['month'] = df['date'].dt.month.astype(str).str.zfill(2)
        df['year_month'] = df['date'].dt.strftime('%Y-%m')
        
        # Apply categorization and unify merchant names based on rules
        canon_info = df['desc'].apply(lambda x: assign_category_and_name(x, rules.get("mapping_rules", {}), rules.get("aliases", {})))
        df['desc'] = [x[0] for x in canon_info]
        df['category'] = [x[1] for x in canon_info]
        
        # Override category for Income/Deposit transactions
        df.loc[df['income'] > 0, 'category'] = T.get("cat_income", "Income / Deposit")
        
        raw_processed_df = df.copy()
        
        st.divider()
        
        csv_data_export = raw_processed_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label=T.get("download_csv_btn", "📥 Download Cleaned Data (CSV)"),
            data=csv_data_export,
            file_name="cleaned_spending_data.csv",
            mime="text/csv",
            use_container_width=True,
            type="primary"
        )

        tab_dash, tab_set = st.tabs([T.get("tab_dashboard", "Dashboard"), T.get("tab_settings", "Settings & Adjustments")])
        
        with tab_dash:
            # Time Filters (Year and Month)
            col_y, col_m = st.columns(2)
            
            years = [T["all_years"]] + sorted(df['year'].unique().tolist())
            selected_year = col_y.selectbox(T["filter_year"], years)
            if selected_year != T["all_years"]:
                df = df[df['year'] == selected_year]
                
            months = [T["all_months"]] + sorted(df['month'].unique().tolist())
            selected_month = col_m.selectbox(T["filter_month"], months)
            if selected_month != T["all_months"]:
                df = df[df['month'] == selected_month]
                
            if df.empty:
                st.warning("No data available for the selected period." if lang == "en" else "選択された期間のデータがありません。")
                st.stop()
                
            # Metrics
            total_spent = df['amount'].sum()
            total_income = df['income'].sum()
            net_cashflow = total_income - total_spent
            
            # Calculate Month-over-Month (MoM) delta if a specific month is selected
            delta_spent = None
            if selected_month != T["all_months"] and selected_year != T["all_years"]:
                try:
                    curr_period = pd.Period(f"{selected_year}-{selected_month}", freq='M')
                    prev_period = curr_period - 1
                    prev_ym = prev_period.strftime('%Y-%m')
                    prev_df = raw_processed_df[raw_processed_df['year_month'] == prev_ym]
                    prev_spent = prev_df['amount'].sum()
                    delta_spent = total_spent - prev_spent
                except Exception:
                    pass
                    
            col1, col2, col3, col4 = st.columns(4)
            col1.metric(T["metrics_total"], f"${total_spent:,.2f}", delta=f"{delta_spent:,.2f}" if delta_spent is not None else None, delta_color="inverse")
            col2.metric(T.get("metrics_income", "Total Income"), f"${total_income:,.2f}")
            col3.metric(T.get("metrics_cashflow", "Net Cash Flow"), f"${net_cashflow:,.2f}")
            col4.metric(T["metrics_transactions"], len(df[df['amount'] > 0]))
            
            # Budget vs Actuals Tracking
            if selected_month != T["all_months"] and st.session_state.monthly_budget > 0:
                budget_pct = min(total_spent / st.session_state.monthly_budget, 1.0)
                st.progress(budget_pct, text=f"{T.get('budget_usage', 'Budget Usage')}: ${total_spent:,.2f} / ${st.session_state.monthly_budget:,.2f} ({budget_pct*100:.1f}%)")
            
            st.divider()
            
            # Macro Trend Chart (Toggleable Year/Month)
            st.subheader(T.get("trend_title", "Spending Trend"))
            col_agg, col_tcat = st.columns(2)
            with col_agg:
                agg_choice = st.radio(
                    T.get("trend_agg_label", "Time Aggregation"), 
                    [T.get("agg_monthly", "Monthly"), T.get("agg_yearly", "Yearly")], 
                    horizontal=True
                )
            with col_tcat:
                all_cats_list = sorted(df['category'].unique().tolist())
                selected_trend_cats = st.multiselect(
                    T.get("trend_filter_cat", "Filter Categories"),
                    options=all_cats_list,
                    default=all_cats_list
                )
            
            time_col = 'year_month' if agg_choice == T.get("agg_monthly", "Monthly") else 'year'
            trend_df = df[df['category'].isin(selected_trend_cats)]
            trend_df = trend_df.groupby([time_col, 'category'], as_index=False)['amount'].sum()
            
            fig_trend = px.bar(trend_df, x=time_col, y='amount', color='category', title=f"{agg_choice} Trend")
            fig_trend.update_layout(xaxis_type='category') # 期間の間延びを防ぐ
            st.plotly_chart(fig_trend, use_container_width=True)
            
            st.divider()
            
            # Micro Breakdown (Pie Chart & Table)
            c1, c2 = st.columns(2)
            with c1:
                fig_pie = px.pie(df, values='amount', names='category', title=T["pie_title"], hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)
                
            with c2:
                st.subheader(T["cat_breakdown"])
                cat_summary = df.groupby('category').agg(
                    Total_Amount=('amount', 'sum'),
                    Transactions=('amount', 'count')
                ).reset_index()
                cat_summary = cat_summary.sort_values(by='Total_Amount', ascending=False)
                
                display_cat = cat_summary.copy()
                display_cat['Total_Amount'] = display_cat['Total_Amount'].apply(lambda x: f"${x:,.2f}")
                st.dataframe(display_cat, use_container_width=True, hide_index=True)
            
            st.divider()
            
            # Merchant Trend Chart
            st.subheader(T.get("merchant_trend_title", "Merchant Spending Trend"))
            merchant_counts = df.groupby('desc').size()
            recurring_merchants = merchant_counts[merchant_counts >= 2].index.tolist()
            
            if recurring_merchants:
                top_merchants = df[df['desc'].isin(recurring_merchants)].groupby('desc')['amount'].sum().nlargest(5).index.tolist()
                
                selected_merchants = st.multiselect(
                    T.get("merchant_filter_label", "Select Merchants (Recurring Only)"),
                    options=sorted(recurring_merchants),
                    default=top_merchants
                )
                
                if selected_merchants:
                    merch_df = df[df['desc'].isin(selected_merchants)]
                    merch_trend_df = merch_df.groupby([time_col, 'desc'], as_index=False)['amount'].sum()
                    
                    fig_merch_trend = px.bar(merch_trend_df, x=time_col, y='amount', color='desc', title=f"{agg_choice} Trend by Merchant")
                    fig_merch_trend.update_layout(xaxis_type='category')
                    st.plotly_chart(fig_merch_trend, use_container_width=True)
                else:
                    st.info("Please select at least one merchant." if lang == "en" else "店舗を1つ以上選択してください。")
            else:
                st.info("No recurring merchants found in this period." if lang == "en" else "この期間に複数回利用した店舗はありません。")

            with st.expander(T["raw_data"]):
                cats = [T["all_cats"]] + list(df['category'].unique())
                selected_cat = st.selectbox(T["filter_label"], cats)
                
                if selected_cat != T["all_cats"]:
                    filtered_df = df[df['category'] == selected_cat]
                else:
                    filtered_df = df
                    
                st.dataframe(filtered_df, use_container_width=True, hide_index=True)


        with tab_set:
            st.header(T.get("tab_settings", "⚙️ Settings & Adjustments"))
            
            # 1. Unclassified Items (other)
            st.subheader(T.get("unclass_title", "❓ Resolve Unclassified (other)"))
            st.markdown(T.get("unclass_desc", "Assign categories to these top unclassified merchants to train the system."))
            other_df = raw_processed_df[raw_processed_df['category'] == 'other']
            categories_list = rules.get("categories", [])
            
            if not other_df.empty:
                other_summary = other_df.groupby('desc').agg(Total=('amount', 'sum'), Count=('amount', 'count')).reset_index().sort_values('Total', ascending=False)
                for _, row in other_summary.head(10).iterrows():
                    merchant = row['desc']
                    c1, c2, c3 = st.columns([4, 3, 2])
                    c1.write(f"**{merchant}**  \n${row['Total']:.2f} ({row['Count']} tx)")
                    new_cat = c2.selectbox("Category", options=categories_list, key=f"unclass_cat_{merchant}", label_visibility="collapsed")
                    if c3.button(T.get("manual_override_btn", "Add Rule"), key=f"unclass_btn_{merchant}"):
                        rules.setdefault("mapping_rules", {})[merchant.lower()] = new_cat
                        save_spending_rules(CONFIG_PATH, rules)
                        st.rerun()
            else:
                st.success(T.get("unclass_all_done", "✅ All items are successfully classified!"))
                
            st.divider()
            
            # 2. Existing Rules by Tab
            st.subheader(T.get("rules_mgmt_title", "📚 Rule Management"))
            st.markdown(T.get("rules_mgmt_desc", "Edit, add, or delete rules. Grouped by category and sorted alphabetically."))
            
            if categories_list:
                rule_tabs = st.tabs(categories_list)
                for i, cat in enumerate(categories_list):
                    with rule_tabs[i]:
                        cat_rules = {k: v for k, v in rules.get("mapping_rules", {}).items() if v == cat}
                        sorted_keys = sorted(cat_rules.keys())
                        df_rules = pd.DataFrame([{"Keyword": k, "Category": v} for k in sorted_keys for v in [cat_rules[k]]])
                        
                        if df_rules.empty:
                            df_rules = pd.DataFrame(columns=["Keyword", "Category"])
                            
                        edited_df = st.data_editor(
                            df_rules,
                            column_config={
                                "Keyword": st.column_config.TextColumn(T.get("rule_merchant", "Merchant / Keyword")),
                                "Category": st.column_config.SelectboxColumn(T.get("rule_category", "Category"), options=categories_list)
                            },
                            hide_index=True,
                            num_rows="dynamic",
                            key=f"editor_{cat}",
                            use_container_width=True
                        )
                        
                        save_btn_label = T.get("save_rules_btn", "💾 Save '{cat}' Rules").replace("{cat}", cat)
                        if st.button(save_btn_label, key=f"save_{cat}"):
                            for k in sorted_keys:
                                if k in rules["mapping_rules"]:
                                    del rules["mapping_rules"][k]
                            for _, row in edited_df.iterrows():
                                kw = str(row["Keyword"]).strip().lower()
                                if kw and kw != "nan":
                                    rules["mapping_rules"][kw] = row["Category"]
                                    
                            save_spending_rules(CONFIG_PATH, rules)
                            st.success(T.get("save_success", "Rules saved successfully!"))
                            st.rerun()

            st.divider()
            
            # 3. Budget Settings
            st.subheader(T.get("budget_title", "Monthly Budget Target"))
            st.session_state.monthly_budget = st.number_input(
                T.get("budget_label", "Budget ($)"), 
                min_value=0, 
                value=st.session_state.monthly_budget, 
                step=100
            )
            
            st.divider()
            
            # 4. Recurring Expenses / Subscriptions
            st.subheader(T.get("subs_title", "Recurring Expenses (Subscriptions)"))
            recurring_candidates = raw_processed_df[raw_processed_df['amount'] > 0].groupby('desc')['year_month'].nunique()
            recurring_descs = recurring_candidates[recurring_candidates >= 2].index.tolist()
            
            subs_df = raw_processed_df[raw_processed_df['desc'].isin(recurring_descs) & ~raw_processed_df['desc'].isin(st.session_state.ignored_subs)]
            
            if not subs_df.empty:
                subs_summary = subs_df.groupby('desc').agg(
                    Average_Monthly=('amount', 'mean'),
                    Category=('category', 'first')
                ).reset_index().sort_values('Average_Monthly', ascending=False)
                
                display_subs = subs_summary.copy()
                display_subs['Average_Monthly'] = display_subs['Average_Monthly'].apply(lambda x: f"${x:,.2f}")
                
                c_sub1, c_sub2 = st.columns([3, 1])
                with c_sub1:
                    st.dataframe(display_subs, use_container_width=True, hide_index=True)
                with c_sub2:
                    to_ignore = st.selectbox("Exclude?", options=subs_summary['desc'].tolist())
                    if st.button(T.get("subs_ignore_btn", "Ignore Selected")):
                        st.session_state.ignored_subs.append(to_ignore)
                        st.rerun()
            else:
                st.info("No recurring expenses found." if lang == "en" else "定期的な支払いは見つかりませんでした。")
        
    except Exception as e:
        st.error(f"Error reading file: {e}")