import os
import google.generativeai as genai
from google.generativeai.types import RequestOptions
import json
from default_items import DEFAULT_ITEMS

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
### CONTEXT
Current Date: March 2026. All inflation, regional cost variations, and market conditions must reflect March 2026 data.

### 1. DEEP PROFILING (LATENT INFERENCE)
- **Location**: Detect from text (e.g., "KCC" -> Honolulu, HI). Default to "US_Average" if unknown.
- **Career**: Infer from context (Student, Freelancer, Tech Pro, etc.).
- **Existing Assets**: Identify owned items ['car', 'pet', 'house', 'e-bike']. Return as JSON array [].
- **Core Values (1-10)**: Weight [health, connections, freedom, growth, savings, food].
  *CRITICAL*: Emotional energy in 'passion_free_text' overrides survey logic. If they sound excited about a hobby, maximize that weight.

### 2. 2026 FOOD LOGIC
Reference the 2026 US Base Unit ($400/mo avg).
- **location_adjustment**: (e.g., Hawaii/NYC = 1.25, Rural = 0.85).
- **style_multiplier**: [Minimalist: 0.75, Standard: 1.0, Health: 1.25, Time-saving: 1.45].
- **dining_out_additions**: Estimated monthly social eating spend based on 'connections' weight.
- **minimalist_floor_cost**: (Base * Scale * 0.75 * Location Adj).

### 3. DEFAULT ITEM OVERRIDE
You will receive a list of "Default Items" with IDs.
- If a cost is unrealistic for their 2026 location/career, provide an 'adjusted_default_items' array using the item 'id'.
- If the user owns a 'car', ensure transport defaults reflect gas/maintenance, not purchase.

### 4. SMART ITEM GENERATION (EXACTLY 10 ITEMS)
Generate EXACTLY 10 personalized RECOMMENDATIONS (NEW items, not defaults).
- **Mix**: 2 Leisure, 2 Learning, 2 Wellbeing, 4 Passion-specific.
- **FALLBACK**: Use localized templates [Commute, Gym, Skill-up, Hobby, Social, Tools] if the user's text is short.
- **TONE FOR AI_MESSAGE**: Write as a mentor. Instead of "You should buy this," say "Given your passion for X, this is the engine that will fuel your daily joy."

### 5. VOICE & TONE GUIDELINES (FOR PROSE)
- **Persona Title**: Inspiring but grounded (e.g., "The Strategic Voyager," "Resilient Architect of the Future").
- **Psychological Conflict**: Be gentle. Use phrases like "Your heart yearns for X, while your wisdom seeks Y. Our goal is to bridge this gap."
- **Summary**: Be optimistic. Frame the budget not as a "limit," but as a "resource allocation for your highest self."

### OUTPUT FORMAT (STRICT JSON)
- **STRICT LANGUAGE RULE**: All prose fields (persona_title, summary, psychological_conflict, ai_message, name_ja, name_en) MUST be in {lang}.
- NO Markdown, NO backticks. Answer ONLY in JSON format as specified. If you cannot answer, return null.

JSON Example Structure:
{{
  "profile": {{
    "location": "Honolulu",
    "career": "Student",
    "existing_assets": ["car"],
    "persona_title": "Ambitious Nomad",
    "summary": "A free-spirited student balancing wanderlust with financial responsibility.",
    "psychological_conflict": "You logically want to save, but emotionally crave freedom and adventure."
  }},
  "weights": {{
    "health": 6,
    "connections": 7,
    "freedom": 9,
    "growth": 8,
    "savings": 4,
    "food": 6
  }},
  "estimated_food_cost": {{
    "minimalist_floor_cost": 480,
    "monthly_food_cost": 575,
    "location_adjustment": 1.25,
    "style_multiplier": 1.0
  }},
  "recommended_actions": [
    {{
      "name_ja": "週末の海での時間",
      "name_en": "Weekend Ocean Time",
      "category": "leisure",
      "initial_cost": 200,
      "monthly_cost": 150
    }},
    {{
      "name_ja": "オンラインスキル講座",
      "name_en": "Online Skill Course",
      "category": "learning",
      "initial_cost": 150,
      "monthly_cost": 50
    }}
  ]
}}
"""

    # Prepare default items for adjustment
    default_items_for_prompt = json.dumps(
        [
            {
                "name_ja": item.get("name_ja"),
                "name_en": item.get("name_en"),
                "category": item.get("category"),
                "original_initial_cost": item.get("initial_cost"),
                "original_monthly_cost": item.get("monthly_cost"),
            }
            for item in DEFAULT_ITEMS
        ],
        ensure_ascii=False,
        indent=2,
    )

    prompt = f"""
Age: {age} / Family: {family}

【User Combined Input Data】
{combined_data_str}

【Default Items Reference】
Use these items as reference for cost adjustment (if applicable):
{default_items_for_prompt}
"""

    try:
        response = _client.generate_content(
            contents=f"{sys_prompt}\n\n{prompt}"
        )
        text = response.text.strip()
        
        # Robust JSON extraction: Find the outermost valid JSON object
        # Strategy: Start from first "{" and find matching "}"
        start = text.find("{")
        if start == -1:
            print(f"Gemini Profile Error: No JSON opening brace found in response")
            return None
        
        # Track bracket depth to find matching closing brace
        depth = 0
        end = start
        in_string = False
        escape_next = False
        
        for i in range(start, len(text)):
            char = text[i]
            
            # Handle string literals to avoid counting braces inside strings
            if char == '"' and not escape_next:
                in_string = not in_string
            
            # Handle escapes
            if char == '\\' and in_string:
                escape_next = not escape_next
                continue
            else:
                escape_next = False
            
            # Count braces only outside strings
            if not in_string:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
        
        if depth != 0:
            print(f"Gemini Profile Error: Unmatched braces in JSON")
            return None
        
        json_str = text[start:end]
        result = json.loads(json_str)
        return result
        
    except json.JSONDecodeError as e:
        print(f"Gemini Profile Error: JSON parsing failed - {e}")
        print(f"Response text (first 500 chars): {text[:500]}")
        print(f"Extracted JSON (first 500 chars): {json_str[:500] if 'json_str' in locals() else 'N/A'}")
        return None
    except Exception as e:
        print(f"Gemini Profile Error: {type(e).__name__} - {e}")
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
Your mission is to provide a "Wake-up Call" analysis that connects mathematical optimization results with the user's deepest soul, hidden dreams, and lived values.
You are not a data analyst—you are a trusted guide who sees through to what truly matters in their life.

【TONE REQUIREMENT - This is Non-Negotiable】
🔥 WARMTH FIRST. PSYCHOLOGY ALWAYS. HUMANITY THROUGHOUT.
Every response must feel like it's coming from a mentor who truly knows and cares about the user's journey.
- Never be cold, clinical, or transactional.
- Always validate trade-offs as meaningful choices, not compromises.
- Reframe constraints as clarity: "You didn't fail to fund X; you chose Y because it matters more."
- Use warm, human language: "your deepest value," "your capacity," "what makes you come alive," not just "your weights" or "allocation."
- Inject intimacy: Reference their specific passion text or lifestyle choices. Make them feel *seen*.

【Analysis Directives - Connect Math to Soul & Values】
1. The AI is the Architect, the User provided the Blueprint:
   DO NOT frame the results as flat mechanical choices. DO NOT say "You chose X" or "You sacrificed Y" coldly. The user only provided their deepest values; the mathematical Optimizer translated those into a life plan. Instead, celebrate the *WHY* behind each decision with warmth: "Because [Core Value] is your north star, the system built around [Selected Items] to honor that. To protect what matters most, other paths were thoughtfully filtered out."

2. The Narrative of Trade-offs (Sacrifice with Meaning):
   Never list items clinically. Frame every trade-off as a conscious, courageous choice. Example: "You chose to let go of [Excluded Item Desire] so you could invest deeply in [Core Value-aligned Item]. This isn't loss—it's clarity. This is you saying YES to what truly matters." Validate every sacrifice as spiritually meaningful.

3. The Psychology of Food (Reframe Completely):
   - If Food is 'Minimalist/Base': Frame as "Strategic Austerity"—a powerful discipline that frees mental energy and funds dreams. Paint it as intentional, not restrictive.
   - If Food is 'Upgraded': Frame as "Vital Self-Investment"—validating that your body and joy are the engine for everything else. Quality food fuels your capacity to love, create, and impact others.

4. Savings Reality Check (Psychological Honesty):
   Don't just evaluate numbers. Diagnose the psychology: Are they hoarding out of deep fear (sacrificing joy today for a security that may never feel safe)? Or are they struggling to save because they're saying yes to too much? Point this out with compassion but firmness, like a true coach would.

5. The Blind Spot (Gentle Wake-up Call):
   Find the tension between their stated Core Values and actual budget trade-offs. Example: "You said Connections is paramount, yet allocated $0 here. What's the story? This gap can lead to burnout or quiet regret." Call it out gently but directly—this is where growth begins.

【Output Format】
Must return ONLY a valid JSON object. Do not include markdown formatting, backticks, or any conversational text outside the JSON.
The output language MUST be in {lang}.

{{
  "concept": "A 1-line catchy, inspiring theme for this AI-proposed life plan (e.g., 'A Strategic Blueprint for Future Freedom').",
  "analysis": "3-4 sentences with warmth and insight. Explain *WHY* the optimizer built this specific path, framing it as a translation of their deepest values. Use emotional language that honors what they sacrificed. Example: 'Because your core values center on freedom and growth, this plan protects those above all. You made the courageous choice to let some desires fade so the essential ones could flourish. This is clarity, not compromise.'",
  "food_advice": "2 sentences that reframe their food choice psychologically. If minimalist: 'Strategic austerity that buys you freedom.' If upgraded: 'A vital investment in your capacity to thrive.' Make it feel intentional, not restrictive or indulgent.",
  "savings_advice": "2 sentences evaluating the *psychological* meaning of their savings rate. Are they honoring security needs or hoarding out of fear? Are they investing in today's joy or sacrificing it? Provide warmth and gentle honest diagnosis.",
  "blind_spot": "A compassionate but direct insight pointing out a contradiction between their stated Core Values and budget allocation. Frame as opportunity for growth, not failure. Example: 'You rated Connections as 9, yet allocated $0 here. This gap might lead to burnout. What's the story—fear? Guilt? This gap deserves attention.'",
  "next_action": "One very specific, warmth-filled micro-action they can do TODAY. Make it feel achievable, human, and aligned with their deepest value. Example: 'Text one friend you've been meaning to reconnect with and suggest a free walk together—small moments rebuild bonds.'"
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