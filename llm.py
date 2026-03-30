import os
import google.generativeai as genai
from google.generativeai.types import RequestOptions
import json

# APIキーの設定
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    # 開発環境用のフォールバック（本番環境では必ず環境変数を使用）
    try:
        from keys import GEMINI_API_KEY
        api_key = GEMINI_API_KEY
    except ImportError:
        print("Error: GEMINI_API_KEY not found. Please set the environment variable.")

genai.configure(api_key=api_key)

# モデルの初期化
generation_config = {
    "temperature": 0.3, # 心理判定としてブレを少なくするため低めに設定
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 1024,
}

_client = genai.GenerativeModel(
    model_name="gemini-2.5-flash-lite", # 最新のliteモデル
    generation_config=generation_config,
)

# =====================================================================
# Functions
# =====================================================================

def _clamp_int_weight(x: float) -> int:
    return max(1, min(10, int(round(x))))


def _choice_letter(option_str: str) -> str | None:
    s = (option_str or "").strip()
    if len(s) >= 2 and s[0] in "ABCD" and s[1] == ":":
        return s[0]
    return None


# Step3 Q4（栄養ゼリー）の選択肢に対応する「食」の重み（1〜10）
JELLY_FOOD_WEIGHT = {"A": 1, "B": 5, "C": 9, "D": 3}


def food_weight_from_jelly(q_jelly: str | None) -> int:
    letter = _choice_letter(q_jelly or "")
    v = JELLY_FOOD_WEIGHT.get(letter, 5)
    return max(1, min(10, int(v)))


def infer_weights_from_survey(
    lifestyle_data: dict,
    financial_data: dict,
    value_quiz: dict,
    free_text: str = "",
    food_data: dict | None = None,
) -> dict:
    """
    LLM が使えないとき用のルールベース推定。
    Step2/Step3の回答、貯蓄圧力、自由記述キーワードから重みを推定する。
    """
    h = c = f = g = s = 5.0

    def bump(deltas: dict) -> None:
        nonlocal h, c, f, g, s
        h += deltas.get("health", 0)
        c += deltas.get("connections", 0)
        f += deltas.get("freedom", 0)
        g += deltas.get("growth", 0)
        s += deltas.get("savings", 0)

    qt = _choice_letter(value_quiz.get("q_time", ""))
    if qt == "A":
        bump({"growth": 2.5, "freedom": 1.0})
    elif qt == "B":
        bump({"connections": 3.0})
    elif qt == "C":
        bump({"health": 3.0})
    elif qt == "D":
        bump({"savings": 3.0, "freedom": -0.5})

    qr = _choice_letter(value_quiz.get("q_risk", ""))
    if qr == "A":
        bump({"growth": 2.0})
    elif qr == "B":
        bump({"freedom": 2.0, "connections": 0.5})
    elif qr == "C":
        bump({"health": 2.0})
    elif qr == "D":
        bump({"savings": 3.0})

    ql = _choice_letter(value_quiz.get("q_live", ""))
    if ql == "A":
        bump({"freedom": 3.0})
    elif ql == "B":
        bump({"growth": 3.0})
    elif ql == "C":
        bump({"connections": 3.0})
    elif ql == "D":
        bump({"health": 3.0})

    cq = _choice_letter(lifestyle_data.get("car_necessity", ""))
    if cq == "A":
        bump({"freedom": 2.0})
    elif cq == "C":
        bump({"freedom": -0.5, "savings": 1.0})

    ws = _choice_letter(lifestyle_data.get("work_style", ""))
    if ws == "A":
        bump({"freedom": 1.5, "growth": 0.5})
    elif ws == "C":
        bump({"connections": 1.0})

    food = food_data or lifestyle_data.get("food") or {}
    hm = food.get("home_meal_style", "")
    if hm == "minimalist":
        bump({"health": 1.5, "savings": 1.5})
    elif hm == "health_conscious":
        bump({"health": 2.5, "growth": 0.5})
    elif hm == "time_saving":
        bump({"freedom": 1.5, "connections": 0.5})
    elif hm == "standard":
        bump({"health": 0.5})

    so = _choice_letter(lifestyle_data.get("social", ""))
    if so == "A":
        bump({"connections": 2.5})
    elif so == "C":
        bump({"connections": -1.0, "growth": 1.0})

    le = _choice_letter(lifestyle_data.get("leisure", ""))
    if le == "A":
        bump({"growth": 1.0, "health": 0.5})
    elif le == "B":
        bump({"health": 2.0, "freedom": 1.0})
    elif le == "C":
        bump({"connections": 1.5, "growth": 0.5})

    mb = max(float(financial_data.get("monthly_budget", 0) or 0), 1.0)
    tms = float(financial_data.get("target_monthly_savings", 0) or 0)
    ratio = tms / mb
    if ratio >= 0.25:
        bump({"savings": min(3.0, 1.5 + ratio * 3.0)})
    elif ratio < 0.05:
        bump({"savings": -1.0, "freedom": 0.5})

    blob = free_text or ""
    blob_l = blob.lower()
    kw_rules = [
        (("健康", "ジム", "フィットネス", "gym", "health", "fitness", "wellness"), {"health": 1.8}),
        (("車", "運転", "car", "drive", "driving", "mobility"), {"freedom": 1.8}),
        (("家族", "友人", "パートナー", "family", "friend", "social", "community"), {"connections": 1.5}),
        (("貯金", "節約", "save", "saving", "invest"), {"savings": 1.5}),
        (("学習", "勉強", "スキル", "learn", "course", "study", "資格"), {"growth": 1.5}),
        (("自由", "独立", "freedom", "autonomy"), {"freedom": 1.2}),
        (("推し", "趣味", "hobby", "passion"), {"growth": 0.8, "connections": 0.6}),
    ]
    for keys, delta in kw_rules:
        if any(k in blob for k in keys) or any(
            k.lower() in blob_l for k in keys if k.isascii() and len(k) > 2
        ):
            bump(delta)

    return {
        "health": _clamp_int_weight(h),
        "connections": _clamp_int_weight(c),
        "freedom": _clamp_int_weight(f),
        "growth": _clamp_int_weight(g),
        "savings": _clamp_int_weight(s),
    }

def get_user_profile(age: int, family: str, combined_data_str: str, lang: str) -> dict | None:
    """
    心理学・行動経済学に基づいた定型回答と自由記述を複合解析し、価値観スコア(1-10)を推論する
    """
    
    # 熟練ライフプランナー兼心理学者としてのシステムプロンプト（JSON出力強制）
    sys_prompt = f"""
You are a world-class Life Planner and Behavioral Psychologist with 30 years of experience.
Your task is to deeply analyze the user's survey data and free-text passion statement to extract their latent psychological profile, core value weights, and generate personalized life-enriching items.

【Core Values to Evaluate (Scale 1-10)】
1. 'health' (physical/mental well-being, fitness, vitality)
2. 'connections' (relationships, family, community, social life)
3. 'freedom' (autonomy, leisure, travel, mobility, time-wealth)
4. 'growth' (learning, skill-up, self-actualization, career)
5. 'savings' (security, risk-aversion, future financial planning)
6. 'food' (investment in culinary quality, dining out vs. minimal fuel)

【Analysis Directives】
1. Weight Calculation (Emotion > Logic):
   - Start with a baseline of 5 for all.
   - Use 'value_quiz' answers as the logical foundation.
   - Deeply analyze 'passion_free_text'. In behavioral psychology, emotion overrides logic. If their stated goal is 'savings' (logic) but their passion text burns for 'motorcycles' or 'fandom' (emotion), significantly BOOST 'freedom' or 'connections', and slightly REDUCE 'savings'.
2. The Psychological Conflict (Tug-of-War):
   - Identify the friction between their logical survey answers and their emotional free-text. (e.g., "Logically you want to save for the future, but your soul is currently craving spontaneous adventure.")
3. The Archetype Persona:
   - Give them a sharp, poetic, 1-to-2 word archetype title based on their data (e.g., "Strategic Nomad", "Stoic Provider", "Ambitious Hedonist").
4. Custom Items (The "Devil's Whisper"):
   - Based ONLY on their 'passion_free_text', invent 1 or 2 highly specific items to add to their life plan (e.g., "Premium Gym Membership", "Idol Fandom Expedition Fund").
   - Assign realistic 'initial_cost' and 'monthly_cost' in USD.
   - Provide an 'ai_message' directly addressing the user. Tell them WHY you added this item despite budget constraints. (e.g., "I know you want to save, but reading your passion, I realized this is the engine of your life. I couldn't let you cut this.")

【Output Format】
Must return ONLY a valid JSON object. Do NOT include markdown formatting, backticks, or any conversational text outside the JSON.
The output text values MUST be in {lang}, but do strictly KEEP the EXACT JSON keys in English as shown below.

Example JSON Structure:
{{
  "persona_title": "...",
  "psychological_conflict": "...",
  "weights": {{
    "health": 7,
    "connections": 8,
    "freedom": 10,
    "growth": 5,
    "savings": 4,
    "food": 8
  }},
  "custom_items": [
    {{
      "name_ja": "推し活・遠征資金",
      "name_en": "Fandom Expedition Fund",
      "category": "leisure",
      "initial_cost": 0,
      "monthly_cost": 150,
      "ai_message": "..."
    }}
  ]
}}
"""

    prompt = f"""
Age: {age} / Family: {family}
【User Combined Input Data (Raw dictionary format)】
{combined_data_str}
"""

    try:
        response = _client.generate_content(
            contents=f"{sys_prompt}\n\n{prompt}"
        )
        text = response.text.strip()
        
        # JSON部分を抽出
        start = text.find("{")
        end = text.rfind("}") + 1
        
        if start == -1 or end <= start:
            return None
            
        return json.loads(text[start:end])
    except Exception as e:
        print(f"Gemini Profile Error: {e}")
        return None

def get_result_summary(
    result: dict,
    user_profile: dict,
    weights: dict,
    lang: str,
    context: dict | None = None,
) -> dict | None:
    """
    最適化結果に対するAIライフコーチからのフィードバックを生成する
    """
    
    # ユーザーが見るアイテム名を言語に合わせて抽出
    selected_names = []
    for item in result["selected"]:
        name = item["name_ja"] if lang == "ja" else item["name_en"]
        selected_names.append(name)

    ctx = context or {}
    financial_data = (ctx.get("financial_data") or {}) if isinstance(ctx, dict) else {}
    lifestyle_data = (ctx.get("lifestyle_data") or {}) if isinstance(ctx, dict) else {}
    food_data = (ctx.get("food_data") or {}) if isinstance(ctx, dict) else {}
    candidates = (ctx.get("candidates") or []) if isinstance(ctx, dict) else []

    selected_ids = {item.get("id") for item in result.get("selected", [])}
    not_selected = [
        item for item in candidates
        if item.get("id") not in selected_ids
    ]
    non_selected_high_priority = sorted(
        [item for item in not_selected if int(item.get("priority", 0) or 0) >= 7],
        key=lambda x: (
            int(x.get("priority", 0) or 0),
            -int(x.get("monthly_cost", 0) or 0),
            -int(x.get("initial_cost", 0) or 0),
        ),
        reverse=True,
    )[:8]

    non_selected_high_priority_names = [
        (it.get("name_ja") if lang == "ja" else it.get("name_en")) or it.get("name") or "Unknown"
        for it in non_selected_high_priority
    ]

    food_decision = "Food Upgrade" if int(result.get("food_stage2_monthly_cost", 0) or 0) > 0 else "Minimalist"
    if lang == "ja":
        food_decision = "食のグレードアップ" if food_decision == "Food Upgrade" else "ミニマリスト"

    input_payload = {
        "user_profile": {
            "age": user_profile.get("age"),
            "family": user_profile.get("family"),
            "household_adults": user_profile.get("household_adults"),
            "household_children": user_profile.get("household_children"),
            "household_infants": user_profile.get("household_infants"),
            "car_owned": user_profile.get("car_owned"),
            "consider_risk": user_profile.get("consider_risk"),
        },
        "lifestyle": {
            "car_necessity": lifestyle_data.get("car_necessity"),
            "work_style": lifestyle_data.get("work_style"),
            "social": lifestyle_data.get("social"),
            "leisure": lifestyle_data.get("leisure"),
            "passion_free_text": lifestyle_data.get("passion_free_text"),
        },
        "financial_goals": {
            "monthly_budget": financial_data.get("monthly_budget"),
            "monthly_budget_before_risk": financial_data.get("monthly_budget_before_risk"),
            "target_monthly_savings": financial_data.get("target_monthly_savings"),
            "initial_budget": financial_data.get("initial_budget"),
            "savings_period_years": financial_data.get("savings_period_years"),
            "risk_monthly_total": financial_data.get("risk_monthly_total"),
        },
        "food_context": {
            "home_meal_style": food_data.get("home_meal_style"),
            "minimalist_floor_cost": financial_data.get("food_minimalist_floor"),
            "stage1_cap": financial_data.get("food_stage1_cap"),
            "stage2_cap": financial_data.get("food_stage2_cap"),
            "stage1_used": result.get("food_stage1_monthly_cost", 0),
            "stage2_used": result.get("food_stage2_monthly_cost", 0),
            "decision": food_decision,
        },
        "weights": {
            "health": int(weights.get("health", 5)),
            "connections": int(weights.get("connections", 5)),
            "freedom": int(weights.get("freedom", 5)),
            "growth": int(weights.get("growth", 5)),
            "savings": int(weights.get("savings", 5)),
            "food": int(weights.get("food", 5)),
        },
        "selected_items": selected_names,
        "excluded_high_priority_items": non_selected_high_priority_names,
        "result_metrics": {
            "total_monthly_cost": result.get("total_monthly_cost"),
            "actual_monthly_savings": result.get("actual_monthly_savings"),
            "goal_achievement_rate": result.get("savings_rate", 0),
        },
    }

    sys_prompt = f"""
You are a world-class Life Coach, Financial Planner, and Behavioral Psychologist with 30 years of experience.
Your mission is to provide a "Wake-up Call" analysis that connects mathematical optimization results with the user's soul and deep values.

【Analysis Directives - DO NOT just summarize the data】
1. The AI is the Architect, the User provided the Blueprint:
   DO NOT frame the results as the user's manual choices. Do NOT say "You chose X" or "You sacrificed Y". The user only provided their values; the mathematical Optimizer made the item selections. 
   Instead, explain *WHY* the Optimizer built this specific plan for them. 
   Example: "Because your core values heavily lean towards [Value], the system prioritized [Selected Item]. To make this mathematically possible within your budget, the optimizer had to filter out [Excluded Item]."

2. The Narrative of Trade-offs (Sacrifice):
   Never just say "You bought X". Focus on what they sacrificed. Explain the psychological trade-off: "To protect your [Core Value], you made the difficult choice to let go of [Excluded Item]." Validate this sacrifice as a strategic life choice.

3. The Psychology of Food:
   - If Food is 'Minimalist/Base': Frame it positively as "Strategic Austerity" to buy future freedom or fund their other dreams.
   - If Food is 'Upgraded': Frame it as "Vital Self-Investment", validating that quality food is the engine for their performance and well-being.

4. Savings Reality Check (2026 US Context):
   Evaluate their savings allocation. Contrast it with their 'Savings' weight. Are they hoarding cash out of fear (sacrificing today's joy), or are they saving too little while claiming security is important? Provide a sharp, grounded perspective.

5. The Blind Spot (Psychological Friction):
   Find a contradiction between their stated Core Values and their actual budget allocation (e.g., claiming 'Connections' is a 10, but spending $0 on social activities). Point this out gently but firmly as a risk of burnout or regret.

【Output Format】
Must return ONLY a valid JSON object. Do not include markdown formatting, backticks, or any conversational text outside the JSON.
The output language MUST be in {lang}.

{{
  "concept": "A 1-line catchy, inspiring theme for this AI-proposed life plan (e.g., 'A Strategic Blueprint for Future Freedom').",
  "analysis": "3-4 sentences explaining WHY the optimizer prioritized certain items and excluded others, framing it as a perfect mathematical translation of their core values.",
  "food_advice": "2 sentences explaining the optimizer's logic behind their food budget allocation.",
  "savings_advice": "2 sentences evaluating the calculated savings rate and what it means for their future.",
  "blind_spot": "A sharp psychological insight pointing out a contradiction between their stated values and the actual mathematical limits of their budget.",
  "next_action": "One very specific, non-financial micro-action they can do TODAY based on this proposed plan."
}}
"""

    prompt = """Input Data (JSON):
""" + json.dumps(input_payload, ensure_ascii=False, indent=2)

    try:
        response = _client.generate_content(
            contents=f"{sys_prompt}\n\n{prompt}"
        )
        text = response.text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end <= start:
            return None
        return json.loads(text[start:end])
    except Exception as e:
        print(f"Gemini Summary Error: {e}")
        return None