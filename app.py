import streamlit as st
import pandas as pd

# ローカルモジュールのインポート
import ui
from optimizer import run_optimizer
from lang import LANG
from default_items import CATEGORIES, CATEGORY_CONSTRAINTS

# =====================================================================
# 初期設定・状態管理
# =====================================================================
st.set_page_config(page_title="Life-Value Optimizer", page_icon="⚖️", layout="wide")

if "lang" not in st.session_state:
    st.session_state.lang = "ja"

# 翻訳辞書の取得
lang = st.session_state.lang
T = LANG[lang]

# カテゴリごとのDataFrame初期化（セッションステートで保持）
if "category_dfs" not in st.session_state:
    st.session_state.category_dfs = ui.init_category_dfs()

# =====================================================================
# サイドバー（言語設定・リセット）
# =====================================================================
with st.sidebar:
    st.title("⚙️ Settings")
    new_lang = st.radio("Language / 言語", ["ja", "en"], index=0 if lang == "ja" else 1)
    if new_lang != lang:
        st.session_state.lang = new_lang
        st.rerun()

    if st.button(T["reset_btn"]):
        for key in list(st.session_state.keys()):
            if key != "lang":
                del st.session_state[key]
        st.rerun()

st.title(T["title"])
st.markdown(T["desc"])

# =====================================================================
# メインフロー（新UI：9つのステップ）
# =====================================================================

# 1. 使える金額の確定 & 2. リスクコスト & 3. 収入見込み & 4. 貯金目標
# （これらは「基本の財務設定」として1つのUI関数にまとめます）
financial_data = ui.render_financial_setup(T, lang)

st.divider()

# 5. 現在の生活ヒアリング（定型質問：Q1〜Q5）
# ここで回答された内容は dict として受け取り、後続のアイテム補正やLLM推論に使います
lifestyle_data = ui.render_lifestyle_questions(T, lang)

st.divider()

# 6. 価値観のLLM推論（ハイブリッド・プロファイリング）
# Step 5の定型データと、ユーザーの自由記述を合わせてLLMに投げ、スライダーを自動設定します
weights_data = ui.render_llm_profiling(T, lang, lifestyle_data, financial_data)

st.divider()

# 7. アイテム修正（Optional）
# 裏側で補正されたアイテム一覧を表示し、微調整したいユーザーだけが触る画面
ui.render_item_review(T, lang)

st.divider()

# 8. サマリー表示 & 9. 最適化の実行
st.header("🚀 Step 8 & 9: Summary & Optimize")
st.info("設定が完了しました。現在の予算と価値観に基づき、最高のライフスタイルを計算します。")
use_ai_for_optimize = st.toggle(
    T.get("use_ai_for_optimize", "🤖 AIを使って最適化結果サマリーを作成"),
    value=True,
    key="use_ai_for_optimize",
)

if st.button(T["run_opt_btn"], type="primary", use_container_width=True):
    with st.spinner("数理最適化エンジンを実行中..."):
        # 最適化エンジンに渡す全候補アイテムのリストを構築
        candidates = []
        for cat, df in st.session_state.category_dfs.items():
            for idx, row in df.iterrows():
                # UI側のセッションステート（スライダー等の値）から最新の状態を取得
                pri = st.session_state.get(f"priority_{cat}_{idx}", row["priority"])
                mand = st.session_state.get(f"mandatory_{cat}_{idx}", row["mandatory"])
                ic = st.session_state.get(f"initial_cost_{cat}_{idx}", row["initial_cost"])
                mc = st.session_state.get(f"monthly_cost_{cat}_{idx}", row["monthly_cost"])
                
                # 優先度が0（除外）のものはオミット
                if pri > 0:
                    candidates.append({
                        "id": f"{cat}_{idx}",
                        "name": row["name"],
                        "name_ja": row.get("name_ja", row["name"]),
                        "name_en": row.get("name_en", row["name"]),
                        "category": cat,
                        "priority": pri,
                        "mandatory": mand,
                        "initial_cost": ic,
                        "monthly_cost": mc,
                        "health": row["health"],
                        "connections": row["connections"],
                        "freedom": row["freedom"],
                        "growth": row["growth"]
                    })

        # financial_data と weights_data を展開してオプティマイザーに渡す
        result = run_optimizer(
            items=candidates,
            total_budget=int(financial_data["initial_budget"]),
            monthly_budget=int(financial_data["monthly_budget"]),
            target_monthly_savings=int(financial_data["target_monthly_savings"]),
            weights={
                "health": int(weights_data["health"]),
                "connections": int(weights_data["connections"]),
                "freedom": int(weights_data["freedom"]),
                "growth": int(weights_data["growth"]),
                "savings": int(weights_data["savings"]),
            },
        )

        # 結果の描画（AIライフコーチダッシュボード含む）
        ui.render_risk_and_results(
            result,
            financial_data["user_profile"],
            weights_data,
            T,
            lang,
            use_ai_for_summary=use_ai_for_optimize,
        )