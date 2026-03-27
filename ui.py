import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from default_items import CATEGORIES, DEFAULT_ITEMS
# ※ llm.py がOpenAIに変わるまでは既存のGemini関数を呼び出します
from llm import get_user_profile, get_result_summary, infer_weights_from_survey

# =====================================================================
# 初期化関数（app.pyから呼ばれる）
# =====================================================================
def init_category_dfs():
    """DEFAULT_ITEMSをカテゴリごとのDataFrameに変換して初期化"""
    dfs = {}
    for cat_key in CATEGORIES["en"].keys():
        items = [item for item in DEFAULT_ITEMS if item["category"] == cat_key]
        processed = []
        for it in items:
            processed.append({
                "name_ja": it["name_ja"],
                "name_en": it["name_en"],
                "name": it["name_ja"], # デフォルト表示用
                "initial_cost": it["initial_cost"],
                "monthly_cost": it["monthly_cost"],
                "health": it.get("health", 0),
                "connections": it.get("connections", 0),
                "freedom": it.get("freedom", 0),
                "growth": it.get("growth", 0),
                "priority": it.get("priority", 3),
                "mandatory": False # 初期状態では必須アイテムはなし
            })
        dfs[cat_key] = pd.DataFrame(processed)
    return dfs

# =====================================================================
# 動的アイテム補正ロジック（Q1〜Q6の定型回答に基づく）
# =====================================================================
def apply_dynamic_overrides(lifestyle_data):
    """回答に基づいてSessionState上のアイテムのコストや優先度を書き換える"""
    dfs = st.session_state.category_dfs
    
    def set_val(cat, name_ja, key_prefix, value):
        if cat in dfs:
            idx_list = dfs[cat].index[dfs[cat]['name_ja'] == name_ja].tolist()
            if idx_list:
                idx = idx_list[0]
                state_key = f"{key_prefix}_{cat}_{idx}"
                # ユーザーが手動で変更した項目は自動上書きしない
                if st.session_state.get(f"manual_{state_key}", False):
                    return
                st.session_state[state_key] = value

    # Q1: 車と移動
    q1a = lifestyle_data.get("car_necessity", "")
    if "A:" in q1a:
        # 【必須】にする
        set_val("transport", "車メイン", "mandatory", True)
        set_val("transport", "車メイン", "priority", 5)
    elif "B:" in q1a:
        # 【任意】にする（ここが抜けていました）
        set_val("transport", "車メイン", "mandatory", False)
        set_val("transport", "車メイン", "priority", 3) 
    elif "C:" in q1a:
        # 【除外】にする
        set_val("transport", "車メイン", "mandatory", False)
        set_val("transport", "車メイン", "priority", 0)
        
    # Q2: 所有状況による初期費用$0化
    if lifestyle_data.get("own_car"):
        set_val("transport", "車メイン", "initial_cost", 0)
    if lifestyle_data.get("own_ebike"):
        set_val("transport", "電動自転車＋Uber", "initial_cost", 0)
    if lifestyle_data.get("own_bike"):
        set_val("transport", "自転車のみ", "initial_cost", 0)
        set_val("transport", "カーシェア＋自転車", "initial_cost", 0)
    if lifestyle_data.get("own_moto"):
        # バイクメインアイテムが追加されている前提
        set_val("transport", "バイクメイン", "initial_cost", 0)

    # Q3: 働き方
    q2 = lifestyle_data.get("work_style", "")
    if "A:" in q2: # リモート
        set_val("living", "エルゴノミクスチェア", "priority", 5)
    elif "C:" in q2: # 出社
        set_val("living", "エルゴノミクスチェア", "priority", 0)

    # Q4: 食生活
    q3 = lifestyle_data.get("diet", "")
    if "A:" in q3: # 自炊派
        set_val("living", "外食メイン（ディナー等）", "monthly_cost", 100) # 外食費を半額に
        set_val("living", "食材宅配サービス", "priority", 0)
    elif "C:" in q3: # 外食派
        set_val("living", "外食メイン（ディナー等）", "priority", 5)
        set_val("living", "時短家電（食洗機・ルンバ等）", "priority", 5)

    # Q5: 交際
    q4 = lifestyle_data.get("social", "")
    if "A:" in q4: # 頻繁
        set_val("leisure", "交際費・飲み代", "monthly_cost", 225) # 飲み代1.5倍
    elif "C:" in q4: # 一人が好き
        set_val("leisure", "交際費・飲み代", "priority", 0)
        set_val("learning", "本・電子書籍・Audible", "priority", 5)

    # Q6: 余暇
    q5 = lifestyle_data.get("leisure", "")
    if "A:" in q5: # インドア
        set_val("leisure", "ゲーム", "priority", 5)
        set_val("leisure", "動画・音楽サブスク", "priority", 5)
        set_val("leisure", "アウトドア・スポーツ", "priority", 0)
    elif "B:" in q5: # アウトドア
        set_val("leisure", "アウトドア・スポーツ", "priority", 5)
        set_val("wellbeing", "旅行・リトリート積立", "priority", 5)
    elif "C:" in q5: # お出かけ
        set_val("leisure", "映画・観劇・美術館", "priority", 5)
        set_val("leisure", "推し活・ファンコミュニティ", "priority", 5)


# =====================================================================
# Step 1: お金とリスクの設定
# =====================================================================
def render_financial_setup(T, lang):
    st.header(T.get("step1_title", "1. 💰 予算と目標の設定"))
    
    # 1. 使える金額の確定
    know_budget = st.radio(
        T.get("know_budget_q", "毎月自由に使える予算（可処分所得）は決まっていますか？"), 
        [T.get("yes_calc", "はい"), T.get("no_calc", "いいえ、計算する")]
    )
    
    monthly_budget = 0
    if T.get("yes_calc", "はい") in know_budget:
        monthly_budget = st.number_input(T.get("budget_label", "毎月の予算 ($)"), min_value=0, value=1500, step=100)
    else:
        with st.expander(T.get("calc_expander", "予算の計算"), expanded=True):
            income = st.number_input(T.get("income_label", "手取り月収 ($)"), value=4000, step=100)
            rent = st.number_input(T.get("rent_label", "家賃 ($)"), value=1500, step=100)
            fixed = st.number_input(T.get("fixed_label", "その他固定費 ($)"), value=500, step=100)
            monthly_budget = income - rent - fixed
            st.info(f"**{T.get('calc_result', '算出された予算')}:** ${monthly_budget}")

    initial_budget = st.number_input(T.get("initial_budget_label", "初期投資に使える貯金 ($)"), min_value=0, value=5000, step=500)

    # 2. リスクコストの考慮
    st.write("---")
    consider_risk = st.toggle(T.get("risk_toggle", "⚠️ 現実的なリスクを考慮する"), value=False)
    age = 30
    family = "Single" if lang == "en" else "単身"
    
    if consider_risk:
        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input(T.get("age", "年齢"), min_value=18, max_value=100, value=30)
        with col2:
            fam_opts = ["単身", "夫婦/パートナー", "子育て世帯"] if lang == "ja" else ["Single", "Couple", "Family with kids"]
            family = st.selectbox(T.get("family", "家族構成"), fam_opts)

    # 3 & 4. 貯金目標（総額と期間を聞き、裏で月割りにする）
    st.write("---")
    st.subheader(T.get("goals_subdir", "🎯 目標設定"))
    col3, col4 = st.columns(2)
    with col3:
        target_total_savings = st.number_input(T.get("target_total_label", "目標貯金金額 ($)"), min_value=0, value=18000, step=1000)
    with col4:
        savings_period_years = st.number_input(T.get("period_label", "目標達成までの期間 (年)"), min_value=1, value=5)

    # 内部で毎月の必要貯金額を計算（オプティマイザーに渡すため）
    target_monthly_savings = target_total_savings / (savings_period_years * 12) if savings_period_years > 0 else 0

    return {
        "monthly_budget": max(0, monthly_budget),
        "initial_budget": initial_budget,
        "target_total_savings": target_total_savings,
        "target_monthly_savings": target_monthly_savings,
        "savings_period_years": savings_period_years,
        "user_profile": {
            "age": age,
            "family": family,
            "consider_risk": consider_risk
        }
    }

# =====================================================================
# Step 2: 現在の生活ヒアリング（定型質問：ハードファクト）
# =====================================================================
def render_lifestyle_questions(T, lang):
    st.header(T.get("step2_title", "2. 👤 現在のライフスタイル"))
    st.write(T.get("step2_desc", "あなたに最適な選択肢を絞り込むため、いくつか質問にお答えください。"))

    q1a_opts = ["A: 車がないと生活できない（必須）", "B: できれば車が欲しいが、なくてもなんとかなる", "C: 公共交通機関や自転車で十分（不要）"] if lang == "ja" else ["A: Car is essential", "B: Nice to have, but not strict", "C: Unnecessary (Transit/Bike is fine)"]
    q2_opts = ["A: フルリモート（ほぼ在宅）", "B: ハイブリッド（週の半分くらい出社）", "C: フル出社・現場仕事"] if lang == "ja" else ["A: Full Remote", "B: Hybrid", "C: Full Office/On-site"]
    q3_opts = ["A: ほぼ自炊（節約・健康志向）", "B: 自炊と外食が半々", "C: ほぼ外食・デリバリー"] if lang == "ja" else ["A: Mostly Home-cooked", "B: Half Cook / Half Eat Out", "C: Mostly Eat Out / Delivery"]
    q4_opts = ["A: 頻繁に行く（お酒も場も好き）", "B: たまに行く程度", "C: 一人の時間を優先したい"] if lang == "ja" else ["A: Frequent", "B: Sometimes", "C: Prefer solo time"]
    q5_opts = ["A: インドア・リラックス派", "B: アクティブ・アウトドア派", "C: お出かけ・イベント派"] if lang == "ja" else ["A: Indoor / Relax", "B: Active / Outdoor", "C: Outings / Events"]

    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        with st.container(border=True):
            q1a = st.radio(
                T.get("q_car_necessity", "Q1. 現在のお住まいや生活において、車は必須ですか？"),
                q1a_opts,
                index=1,
                key="q_step2_car_necessity",
            )
    with row1_col2:
        with st.container(border=True):
            st.write(T.get("q_own_transport", "Q2. 現在、すでに所有している移動手段はありますか？（複数選択可）"))
            c1, c2, c3 = st.columns(3)
            with c1:
                own_car = st.checkbox("🚗 " + (T.get("own_car", "車")), key="q_step2_own_car")
                own_moto = st.checkbox("🏍️ " + (T.get("own_moto", "バイク")), key="q_step2_own_moto")
            with c2:
                own_ebike = st.checkbox("⚡ " + (T.get("own_ebike", "電動自転車")), key="q_step2_own_ebike")
                own_none = st.checkbox("🚶 " + (T.get("own_none", "なし")), key="q_step2_own_none")
            with c3:
                own_bike = st.checkbox("🚲 " + (T.get("own_bike", "自転車")), key="q_step2_own_bike")

    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        with st.container(border=True):
            q2 = st.radio(T.get("q_work_style", "Q3. 現在の働き方はどれに一番近いですか？"), q2_opts, index=1, key="q_step2_work_style")
    with row2_col2:
        with st.container(border=True):
            q3 = st.radio(T.get("q_diet", "Q4. 平日の食事はどのように済ませることが多いですか？"), q3_opts, index=1, key="q_step2_diet")

    row3_col1, row3_col2 = st.columns(2)
    with row3_col1:
        with st.container(border=True):
            q4 = st.radio(T.get("q_social", "Q5. 人付き合いや、飲み会などの頻度はどのくらいですか？"), q4_opts, index=1, key="q_step2_social")
    with row3_col2:
        with st.container(border=True):
            q5 = st.radio(T.get("q_leisure", "Q6. 休日の主な過ごし方（余暇のスタイル）はどれに一番近いですか？"), q5_opts, index=1, key="q_step2_leisure")

    lifestyle_data = {
        "car_necessity": q1a,
        "own_car": own_car, "own_ebike": own_ebike, "own_bike": own_bike, "own_moto": own_moto,
        "work_style": q2, "diet": q3, "social": q4, "leisure": q5
    }

    # 裏側でアイテムの初期費用や優先度を魔法のように書き換える（APIコスト$0ロジック）
    apply_dynamic_overrides(lifestyle_data)

    return lifestyle_data

# =====================================================================
# Step 3: 価値観のLLM推論（心理テスト＆自由記述ハイブリッド）
# =====================================================================
def render_llm_profiling(T, lang, lifestyle_data, financial_data):
    st.header(T.get("step3_title", "3. 🧠 価値観と熱量の分析"))
    st.write(T.get("step3_desc", "熟練のライフプランナー兼心理学者として、あなたの深層価値観を抽出するための質問を用意しました。"))

    # 1. 心理テスト的定型質問（学術的背景に基づくトレードオフ）
    st.subheader("🧘 Value Discovery (1-3)")

    q_time_opts = [
        "A: 未経験のアクティビティや学習に没頭する" if lang == "ja" else "A: Immerse in new activity/learning",
        "B: 親しい友人や家族と豪華な時間を過ごす" if lang == "ja" else "B: Spend quality time with loved ones",
        "C: 身体を休め、健康ルーティンを整える" if lang == "ja" else "C: Rest and establish health routine",
        "D: 将来のために全額を貯金し、家で過ごす" if lang == "ja" else "D: Save all and stay home"
    ]
    q_risk_opts = [
        "A: スキルアップのための書籍や講座代" if lang == "ja" else "A: Books/Courses for skill-up",
        "B: 趣味や移動にかかる費用" if lang == "ja" else "B: Hobbies and transportation",
        "C: 健康維持のためのジムや食材代" if lang == "ja" else "C: Gym and healthy food",
        "D: 将来の備えとしての積立" if lang == "ja" else "D: Savings for the future"
    ]
    q_live_opts = [
        "A: 誰にも縛られず、自分のペースで動けている時" if lang == "ja" else "A: Moving at own pace, unbound",
        "B: 新しいことを学び、能力が向上していると感じる時" if lang == "ja" else "B: Learning new things, improving",
        "C: 誰かの役に立ち、感謝や交流がある時" if lang == "ja" else "C: Helping others, interacting",
        "D: 身体が軽く、メンタルが安定している時" if lang == "ja" else "D: Body is light, mental is stable"
    ]
    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        with st.container(border=True):
            q_time = st.radio(
                T.get("q_time_deploy", "Q1. もし来週、予期せぬ3日間の休暇と自由な$500が与えられたら？"),
                q_time_opts,
                index=0,
                key="q_step3_time",
            )
    with row1_col2:
        with st.container(border=True):
            q_risk = st.radio(
                T.get("q_risk_deploy", "Q2. 生活費が1.2倍になりました。『最後まで削りたくない』のは？"),
                q_risk_opts,
                index=2,
                key="q_step3_risk",
            )

    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        with st.container(border=True):
            q_live = st.radio(
                T.get("q_live_deploy", "Q3. あなたが最も『生きてる実感』を覚える瞬間は？"),
                q_live_opts,
                index=0,
                key="q_step3_live",
            )
    with row2_col2:
        st.empty()

    with st.container(border=True):
        q4_label = (
            "Q4. 人生で譲れないこだわり、理想の生活、または『推し活』などの特定の情熱について自由に教えてください。"
            if lang == "ja"
            else "Q4. Tell us your non-negotiables, ideal lifestyle, or specific passions such as fandom activities."
        )
        st.write(q4_label)
        free_text = st.text_area(
            T.get("freetext_label", "自由記述 (譲れないこだわり)"),
            height=170,
            placeholder=T.get("freetext_placeholder", "例：健康のために自炊はしたいが、移動の自由（車）は絶対に譲れない..."),
            key="q_step3_freetext",
        )

    # セッションステートの初期化（スライダー用：未入力時はオール5）
    for key in ["w_health", "w_connections", "w_freedom", "w_growth", "w_savings"]:
        if key not in st.session_state:
            st.session_state[key] = 5
    _val_keys = ("val_health", "val_conn", "val_free", "val_grow", "val_save")
    _w_keys = ("w_health", "w_connections", "w_freedom", "w_growth", "w_savings")
    for vk, wk in zip(_val_keys, _w_keys):
        if vk not in st.session_state:
            st.session_state[vk] = st.session_state[wk]

    def _apply_weights_to_sliders(weights: dict) -> None:
        pairs = [
            ("health", "w_health", "val_health"),
            ("connections", "w_connections", "val_conn"),
            ("freedom", "w_freedom", "val_free"),
            ("growth", "w_growth", "val_grow"),
            ("savings", "w_savings", "val_save"),
        ]
        for field, wk, vk in pairs:
            v = max(1, min(10, int(weights.get(field, 5))))
            st.session_state[wk] = v
            st.session_state[vk] = v

    # 🚀 価値観を分析して反映ボタン（心臓部）
    st.write("---")
    col1, col2 = st.columns([1, 1])
    with col2:
        use_ai_for_values = st.toggle(
            T.get("use_ai_for_values", "🤖 AIを使って価値観を反映"),
            value=True,
            key="use_ai_for_values",
        )
    with col1:
        analyze_btn = st.button(
            T.get("reflect_to_slider_btn", "✨ 価値観をスライダーに反映"),
            type="primary",
            use_container_width=True,
        )

    if analyze_btn:
        with st.spinner(T.get("analyzing", "プロファイリング中...")):
            # 定型回答と自由記述、基本情報をすべてガッチャンコしてLLMに投げる
            combined_data = {
                "lifestyle_fact": lifestyle_data, # Q1〜Q6（ハードファクト）
                "financial_goal": financial_data,  # 予算、目標、リスク設定
                "value_quiz": { "q_time": q_time, "q_risk": q_risk, "q_live": q_live }, # Q1〜Q3（心理テスト）
                "passion_free_text": free_text    # 自由記述（熱量）
            }
            # strに変換してプロンプトへ
            combined_info_str = str(combined_data)
            
            if use_ai_for_values:
                # llm.py を呼び出し（OpenAIへの移行が終わるまではGemini版を使用します）
                user_profile = financial_data["user_profile"]
                profile_result = get_user_profile(user_profile["age"], user_profile["family"], combined_info_str, lang)

                if profile_result:
                    _apply_weights_to_sliders(profile_result)
                    st.success(T.get("analysis_success", "AIがあなたの深層価値観を推論しました！下のスライダーで最終調整してください。"))
                else:
                    fallback = infer_weights_from_survey(
                        lifestyle_data,
                        financial_data,
                        {"q_time": q_time, "q_risk": q_risk, "q_live": q_live},
                        free_text=free_text,
                    )
                    _apply_weights_to_sliders(fallback)
                    st.warning(T.get("analysis_fallback", ""))
            else:
                fallback = infer_weights_from_survey(
                    lifestyle_data,
                    financial_data,
                    {"q_time": q_time, "q_risk": q_risk, "q_live": q_live},
                    free_text=free_text,
                )
                _apply_weights_to_sliders(fallback)
                st.info(T.get("analysis_manual_mode", "AIを使わず、回答内容から推定して反映しました。"))

    # 3. 価値観の重みスライダーUI（AIの結果が反映されている）
    st.write("---")
    st.markdown(f"#### {T.get('w_subdir', '⚖️ 価値観の重み (1〜10)')}")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: w_health = st.slider(T.get("w_health", "健康"), 1, 10, st.session_state.w_health, key="val_health")
    with c2: w_conn = st.slider(T.get("w_connections", "つながり"), 1, 10, st.session_state.w_connections, key="val_conn")
    with c3: w_free = st.slider(T.get("w_freedom", "自由"), 1, 10, st.session_state.w_freedom, key="val_free")
    with c4: w_grow = st.slider(T.get("w_growth", "成長"), 1, 10, st.session_state.w_growth, key="val_grow")
    with c5: w_save = st.slider(T.get("w_savings", "貯蓄"), 1, 10, st.session_state.w_savings, key="val_save")

    return {
        "health": w_health, "connections": w_conn, "freedom": w_free,
        "growth": w_grow, "savings": w_save
    }

# =====================================================================
# Step 4: アイテム修正（Optional）
# =====================================================================
def render_item_review(T, lang):
    st.header(T.get("step4_title", "4. ⚙️ アイテムの微調整 (Optional)"))

    def _mark_manual(key_name: str) -> None:
        st.session_state[f"manual_{key_name}"] = True

    with st.expander(T.get("item_review_expander", "AIが補正した選択肢のリストを確認・微調整する")):
        st.info(T.get("item_review_info", "Step 2の定型質問に基づき、不要なものは優先度0に、所有済みの場合は初期費用が0に自動補正されています。"))

        # ユーザーが任意アイテムを追加できるフォーム
        st.markdown("#### " + ("➕ アイテムを追加" if lang == "ja" else "➕ Add Custom Item"))
        with st.form("add_custom_item_form", clear_on_submit=True):
            f1, f2, f3 = st.columns(3)
            with f1:
                cat_options = list(CATEGORIES[lang].items())
                cat_labels = [name for _, name in cat_options]
                selected_cat_label = st.selectbox(
                    "カテゴリ" if lang == "ja" else "Category",
                    cat_labels,
                )
            with f2:
                item_name = st.text_input("アイテム名" if lang == "ja" else "Item Name")
            with f3:
                priority_new = st.slider("優先度" if lang == "ja" else "Priority", 0, 10, 3)

            c1, c2 = st.columns(2)
            with c1:
                initial_cost_new = st.number_input("初期費用 $" if lang == "ja" else "Initial Cost $", min_value=0, value=0, step=50)
            with c2:
                monthly_cost_new = st.number_input("月額費用 $" if lang == "ja" else "Monthly Cost $", min_value=0, value=0, step=10)

            v1, v2, v3, v4 = st.columns(4)
            with v1:
                health_new = st.slider("健康" if lang == "ja" else "Health", -10, 10, 0)
            with v2:
                conn_new = st.slider("つながり" if lang == "ja" else "Connections", -10, 10, 0)
            with v3:
                free_new = st.slider("自由" if lang == "ja" else "Freedom", -10, 10, 0)
            with v4:
                grow_new = st.slider("成長" if lang == "ja" else "Growth", -10, 10, 0)

            submit_add = st.form_submit_button("追加する" if lang == "ja" else "Add Item", use_container_width=True)

            if submit_add:
                if not item_name.strip():
                    st.warning("アイテム名を入力してください。" if lang == "ja" else "Please enter an item name.")
                else:
                    cat_key = next((k for k, v in CATEGORIES[lang].items() if v == selected_cat_label), None)
                    if cat_key is None:
                        st.error("カテゴリの解決に失敗しました。" if lang == "ja" else "Failed to resolve category.")
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
                        st.success("アイテムを追加しました。" if lang == "ja" else "Item added.")
                        st.rerun()

        cat_items = list(CATEGORIES[lang].items())
        cat_tabs = st.tabs([cat_name for _, cat_name in cat_items])

        for tab, (cat_key, cat_name) in zip(cat_tabs, cat_items):
            with tab:
                df = st.session_state.category_dfs[cat_key]

                for idx, row in df.iterrows():
                    # 動的補正されたSessionState上の値を初期値として表示
                    pri_key = f"priority_{cat_key}_{idx}"
                    mc_key = f"monthly_cost_{cat_key}_{idx}"
                    ic_key = f"initial_cost_{cat_key}_{idx}"
                    mand_key = f"mandatory_{cat_key}_{idx}"

                    # SessionStateに無ければDataFrameの値を入れる（リセット時の対策）
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
                            T.get("mandatory_label", "必須"),
                            key=mand_key,
                            on_change=_mark_manual,
                            args=(mand_key,),
                        )
                        # 必須指定時に除外状態にならないよう最低優先度を担保
                        if is_mandatory and st.session_state.get(pri_key, 0) <= 0:
                            st.session_state[pri_key] = 1
                    with c1:
                        lbl = f"{row['name']} (0=Exclude)" if lang == "en" else f"{row['name']} (優先度0=除外)"
                        if st.session_state[mand_key]:
                            st.caption("✅ " + T.get("mandatory_label", "必須"))
                        st.slider(lbl, 0, 10, key=pri_key, on_change=_mark_manual, args=(pri_key,))
                    with c2:
                        st.number_input(T.get("lbl_mc", "月額 $"), min_value=0, key=mc_key, on_change=_mark_manual, args=(mc_key,))
                    with c3:
                        st.number_input(T.get("lbl_ic", "初期 $"), min_value=0, key=ic_key, on_change=_mark_manual, args=(ic_key,))

# =====================================================================
# 結果表示・AIライフコーチ描画
# =====================================================================
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
        st.error(T.get("opt_fail", "最適化に失敗しました。予算が少なすぎるか、必須アイテムのコストが高すぎる可能性があります。"))
        return

    if result.get("best_effort_mandatory_relaxed"):
        st.success(
            "制約の中で、あなたに寄り添う最善プランを作成しました。"
            if lang == "ja"
            else "Built the best possible plan within your constraints."
        )
        st.warning(
            (
                f"必須指定が予算制約で満たせなかったため、ベストエフォートで再計算しました（必須 {result.get('relaxed_mandatory_count', 0)} 件中、未反映 {result.get('missed_mandatory_count', 0)} 件）。"
                if lang == "ja"
                else f"Hard-mandatory items were infeasible under budget, so best-effort relaxation was applied (missed {result.get('missed_mandatory_count', 0)} of {result.get('relaxed_mandatory_count', 0)} mandatory items)."
            )
        )
        missed_items = result.get("missed_mandatory_items", [])
        if missed_items:
            st.markdown("**守れなかった必須アイテム**" if lang == "ja" else "**Mandatory items not satisfied**")
            for item in missed_items:
                name = item.get("name_ja") if lang == "ja" else item.get("name_en")
                if not name:
                    name = item.get("name", item.get("id", ""))
                st.markdown(f"- {name}")
    else:
        st.success(T.get("opt_success", "最適化が完了しました！"))

    # -----------------------------------------------------------------
    # 非AIの実行ダッシュボード（最適化結果の直後に表示）
    # -----------------------------------------------------------------
    st.subheader("📌 実行ダッシュボード" if lang == "ja" else "📌 Execution Dashboard")

    selected = result.get("selected", [])
    monthly_budget = float((financial_data or {}).get("monthly_budget", 0) or 0)
    initial_budget = float((financial_data or {}).get("initial_budget", 0) or 0)
    target_monthly = float(result.get("target_monthly_savings", 0) or 0)
    actual_monthly = float(result.get("actual_monthly_savings", 0) or 0)
    period_years = int((financial_data or {}).get("savings_period_years", 1) or 1)
    monthly_rate_raw = (actual_monthly / target_monthly) if target_monthly > 0 else 1.0

    # 1) 使用可能金額と使用状況（月/初期）+ 貯金目標達成率
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric(
        "月予算" if lang == "ja" else "Monthly Budget",
        f"${int(monthly_budget):,}",
        (f"使用 ${int(result.get('total_monthly_cost', 0)):,}" if lang == "ja" else f"Used ${int(result.get('total_monthly_cost', 0)):,}"),
    )
    m2.metric(
        "初期予算" if lang == "ja" else "Initial Budget",
        f"${int(initial_budget):,}",
        (f"使用 ${int(result.get('total_initial_cost', 0)):,}" if lang == "ja" else f"Used ${int(result.get('total_initial_cost', 0)):,}"),
    )
    m3.metric(
        "月予算残" if lang == "ja" else "Monthly Remaining",
        f"${int(max(monthly_budget - float(result.get('total_monthly_cost', 0)), 0)):,}",
    )
    m4.metric(
        "初期予算残" if lang == "ja" else "Initial Remaining",
        f"${int(max(initial_budget - float(result.get('total_initial_cost', 0)), 0)):,}",
    )
    m5.metric("貯金目標達成率" if lang == "ja" else "Savings Goal Rate", f"{monthly_rate_raw:.0%}")

    # 2) カテゴリごとの使用額/割合（月/初期）
    if selected:
        rows = []
        for cat_key, cat_label in CATEGORIES[lang].items():
            cat_items = [it for it in selected if it.get("category") == cat_key]
            if not cat_items:
                continue
            cat_mc = sum(float(it.get("monthly_cost", 0) or 0) for it in cat_items)
            cat_ic = sum(float(it.get("initial_cost", 0) or 0) for it in cat_items)
            rows.append(
                {
                    "Category" if lang == "en" else "カテゴリ": cat_label,
                    "Monthly $" if lang == "en" else "月額 $": int(cat_mc),
                    "Monthly %" if lang == "en" else "月額 %": (cat_mc / monthly_budget * 100) if monthly_budget > 0 else 0,
                    "Initial $" if lang == "en" else "初期 $": int(cat_ic),
                    "Initial %" if lang == "en" else "初期 %": (cat_ic / initial_budget * 100) if initial_budget > 0 else 0,
                }
            )
        # 貯金をカテゴリとして追加（月額のみ）
        rows.append(
            {
                "Category" if lang == "en" else "カテゴリ": ("Savings" if lang == "en" else "貯金"),
                "Monthly $" if lang == "en" else "月額 $": int(actual_monthly),
                "Monthly %" if lang == "en" else "月額 %": (actual_monthly / monthly_budget * 100) if monthly_budget > 0 else 0,
                "Initial $" if lang == "en" else "初期 $": 0,
                "Initial %" if lang == "en" else "初期 %": 0.0,
            }
        )
        if rows:
            df_cat = pd.DataFrame(rows)
            st.markdown("#### 2) " + ("Category Spend Mix" if lang == "en" else "カテゴリ別の使用額/割合"))
            st.dataframe(df_cat, use_container_width=True, hide_index=True)
            cat_col = "Category" if lang == "en" else "カテゴリ"
            monthly_pct_col = "Monthly %" if lang == "en" else "月額 %"
            initial_pct_col = "Initial %" if lang == "en" else "初期 %"

            p1, p2 = st.columns(2)
            with p1:
                st.caption("Monthly mix (%)" if lang == "en" else "月額のカテゴリ構成比(%)")
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
                st.caption("Initial mix (%)" if lang == "en" else "初期費用のカテゴリ構成比(%)")
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

    # 3) 貯蓄（期間合計）・貯蓄割合
    # 4) 目標貯蓄額までどれくらいか（期間合計）
    c1, c2, c3, c4 = st.columns(4)
    target_total = float((financial_data or {}).get("target_total_savings", 0) or 0)
    if target_total <= 0:
        target_total = target_monthly * period_years * 12
    projected_total = actual_monthly * period_years * 12
    total_gap = max(target_total - projected_total, 0)
    total_progress_ratio = min(projected_total / target_total, 1.0) if target_total > 0 else 1.0
    c1.metric(
        "目標貯金総額 / Target Savings Total",
        f"${int(target_total):,}",
        f"{period_years}y",
    )
    over_total = max(projected_total - target_total, 0)
    c2.metric(
        "見込み貯金総額 / Projected Savings Total",
        f"${int(projected_total):,}",
    )
    c3.metric(
        "達成率 / Achievement Rate",
        f"{(projected_total / target_total if target_total > 0 else 1.0):.1%}",
    )
    c4.metric("目標まで残り / Remaining to Goal", f"${int(total_gap):,}")
    st.progress(total_progress_ratio)
    st.caption(
        (f"Goal progress over {period_years} years: {total_progress_ratio:.0%}" if lang == "en" else f"{period_years}年での目標進捗: {total_progress_ratio:.0%}")
    )
    if over_total > 0:
        st.caption(
            (
                f"Projected surplus over goal: ${over_total:,.0f}"
                if lang == "en"
                else f"目標超過見込み: ${over_total:,.0f}"
            )
        )
    st.caption(
        (
            f"Target total is taken directly from your input. ({period_years} years)"
            if lang == "en"
            else f"目標総額は入力値をそのまま使用しています。（{period_years}年）"
        )
    )

    achieved_amount = min(projected_total, target_total) if target_total > 0 else projected_total
    remaining_amount = max(target_total - achieved_amount, 0)
    over_amount = max(projected_total - target_total, 0) if target_total > 0 else 0

    fig_s = go.Figure()
    fig_s.add_trace(
        go.Bar(
            y=["Savings Goal" if lang == "en" else "貯蓄目標"],
            x=[achieved_amount],
            name="Achieved" if lang == "en" else "達成分",
            legendrank=2,
            orientation="h",
            marker_color="#3b82f6",
            text=[f"${achieved_amount:,.0f}"],
            textposition="inside",
        )
    )
    fig_s.add_trace(
        go.Bar(
            y=["Savings Goal" if lang == "en" else "貯蓄目標"],
            x=[remaining_amount],
            name="Remaining" if lang == "en" else "残り",
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
                y=["Savings Goal" if lang == "en" else "貯蓄目標"],
                x=[over_amount],
                name="Over" if lang == "en" else "超過分",
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
    st.caption(
        f"{'目標まで' if lang == 'ja' else 'Gap to goal'}: ${total_gap:,.0f}"
    )

    # 5) 今回アイテムで満たされる価値観
    if selected:
        value_axes = ["health", "connections", "freedom", "growth"]
        axis_labels = {
            "health": "健康" if lang == "ja" else "Health",
            "connections": "つながり" if lang == "ja" else "Connections",
            "freedom": "自由" if lang == "ja" else "Freedom",
            "growth": "成長" if lang == "ja" else "Growth",
        }
        n_sel = max(len(selected), 1)
        value_rows = []
        for axis in value_axes:
            raw_score = sum(float(it.get(axis, 0) or 0) for it in selected)
            normalized = (raw_score / (n_sel * 10)) * 100
            weighted = raw_score * float(weights.get(axis, 5) or 5)
            value_rows.append(
                {
                    "Value" if lang == "en" else "価値観": axis_labels[axis],
                    "Score" if lang == "en" else "スコア": round(raw_score, 1),
                    "Fulfillment %" if lang == "en" else "充足率 %": round(max(0, normalized), 1),
                    "Weighted" if lang == "en" else "重み反映値": round(weighted, 1),
                }
            )
        df_value = pd.DataFrame(value_rows)
        st.markdown("#### 5) " + ("Values Fulfilled by Selected Items" if lang == "en" else "今回アイテムで満たされる価値観"))
        value_col = "Value" if lang == "en" else "価値観"
        fill_col = "Fulfillment %" if lang == "en" else "充足率 %"

        # 追加指標: 価値観重みと選択アイテムの一致度
        # 計算: 各軸の「重みシェア」と「実現シェア（負値は0扱い）」のL1距離から一致度へ変換
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
            "価値観マッチ度" if lang == "ja" else "Value Match Score",
            f"{match_ratio:.1%}",
            help=(
                "重みシェアと実現シェアの距離で算出（1 - 0.5×L1距離）。100%に近いほど、重みと選択の配分が近い。"
                if lang == "ja"
                else "Computed by distance between preference-share and achieved-share (1 - 0.5×L1 distance). Closer to 100% means better alignment."
            ),
        )
        st.caption("Value fulfillment by selected items" if lang == "en" else "選択アイテムによる価値観の充足率")
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

    # 選ばれたアイテム一覧
    st.write("### " + T.get("sel_items", "選択されたライフスタイルアイテム"))
    selected = result["selected"]
    if selected:
        cat_items = list(CATEGORIES[lang].items())
        tabs = st.tabs([name for _, name in cat_items])
        for tab, (cat_key, cat_name) in zip(tabs, cat_items):
            with tab:
                by_cat = [it for it in selected if it.get("category") == cat_key]
                if not by_cat:
                    st.caption("該当アイテムなし" if lang == "ja" else "No selected items in this category.")
                    continue

                st.caption(
                    f"{len(by_cat)} item(s) / Initial ${int(sum(float(it.get('initial_cost', 0) or 0) for it in by_cat)):,} / Monthly ${int(sum(float(it.get('monthly_cost', 0) or 0) for it in by_cat)):,}"
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
                        f"  {'初期' if lang == 'ja' else 'Initial'}: `${int(item.get('initial_cost', 0)):,}` / "
                        f"{'月額' if lang == 'ja' else 'Monthly'}: `${int(item.get('monthly_cost', 0)):,}`"
                    )
    else:
        st.write(T.get("none", "なし"))

    # AIライフコーチダッシュボード
    st.divider()
    if not use_ai_for_summary:
        st.caption(T.get("ai_summary_off", "AI summary is turned off."))
    elif summary := get_result_summary(result, user_profile, weights, lang):
        st.subheader(T.get("ai_dashboard", "💡 AI ライフコーチ ダッシュボード"))
        lbl_theme = T.get("theme", "テーマ")
        lbl_analysis = T.get("analysis", "分析")
        lbl_blind_spot = T.get("blind_spot", "死角・リスク")
        lbl_action = T.get("next_action", "次のアクション")

        st.info(f"**{lbl_theme}:** {summary.get('concept', '')}")
        st.write(f"**{lbl_analysis}:** {summary.get('analysis', '')}")
        st.warning(f"**{lbl_blind_spot}:** {summary.get('blind_spot', '')}")
        st.success(f"**{lbl_action}:** {summary.get('next_action', '')}")
    else:
        st.caption(T.get("ai_error_summary", "AIダッシュボードの生成に失敗しました。"))