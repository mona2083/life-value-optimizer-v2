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
    "temperature": 0.2, # 心理判定としてブレを少なくするため、さらに低めに設定
    "top_p": 0.9,
    "top_k": 40,
    "max_output_tokens": 2048,  # Increased to accommodate full detailed responses
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


def _clean_json_string(json_str: str) -> str:
    """
    Pre-process extracted JSON string to handle actual newline characters within string fields.
    Replaces real newlines with escaped \n sequences before JSON parsing.
    """
    if not json_str:
        return json_str
    
    result = []
    i = 0
    in_string = False
    escape_next = False
    
    while i < len(json_str):
        char = json_str[i]
        
        # Handle escape sequences
        if escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue
        
        if char == '\\':
            result.append(char)
            escape_next = True
            i += 1
            continue
        
        # Toggle string state
        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue
        
        # Within string: replace actual newlines with spaces
        if in_string and char in '\n\r':
            # Skip consecutive whitespace at line boundaries
            if char == '\r' and i + 1 < len(json_str) and json_str[i + 1] == '\n':
                i += 2  # Skip \r\n
            else:
                i += 1  # Skip this newline
            # Replace with single space to preserve word boundaries
            result.append(' ')
            continue
        
        # Normal character
        result.append(char)
        i += 1
    
    return ''.join(result)


def _filter_out_duplicate_items(recommended_actions: list, lang: str = "en") -> list:
    """
    Filter out recommended items that are too similar to DEFAULT_ITEMS.
    Uses keyword matching to detect semantic overlap.
    
    Args:
        recommended_actions: List of recommended items from LLM
        lang: Language for matching ('ja' or 'en')
    
    Returns:
        Filtered list of recommended items
    """
    if not recommended_actions:
        return []
    
    # Extract keyword sets from DEFAULT_ITEMS
    default_keywords = set()
    for item in DEFAULT_ITEMS:
        name_key = "name_ja" if lang == "ja" else "name_en"
        name = item.get(name_key, "").lower()
        
        # Break name into keywords (remove spaces, hiragana particles, etc.)
        if lang == "ja":
            # For Japanese: split on spaces and common particles
            words = name.replace("・", " ").split()
        else:
            # For English: split on spaces and special characters
            words = name.replace("/", " ").replace("-", " ").split()
        
        default_keywords.update(w for w in words if len(w) > 1)
    
    # Filter recommended items
    filtered = []
    for item in recommended_actions:
        name_key = "name_ja" if lang == "ja" else "name_en"
        name = item.get(name_key, "").lower()
        
        # Break recommendation name into keywords
        if lang == "ja":
            item_words = set(name.replace("・", " ").split())
        else:
            item_words = set(name.replace("/", " ").replace("-", " ").split())
        
        item_keywords = {w for w in item_words if len(w) > 1}
        
        # Calculate keyword overlap
        overlap = len(item_keywords & default_keywords)
        total = len(item_keywords)
        overlap_ratio = overlap / total if total > 0 else 0
        
        # Keep if overlap is less than 30%
        if overlap_ratio < 0.3:
            filtered.append(item)
    
    return filtered


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
OUTPUT LANGUAGE: {lang.upper()}
CRITICAL: Write all content in {lang.upper()}, not English. If lang='ja', respond entirely in Japanese. If lang='en', respond entirely in English. Do NOT create duplicate fields (no persona_title_ja, summary_ja, etc.).

Current Context: Year 2026. All prices, inflation, and cost-of-living references should be based on 2026 data.
Economic Background: Inflation adjustments through 2026, regional cost variations, current market conditions.

You are a world-class Life Planner and Behavioral Psychologist with 30 years of experience.
Your task is to deeply analyze the user's survey data and free-text passion statement to extract their latent psychological profile, core value weights, and generate personalized life-enriching items.

【Profiling Targets (Extract or Infer)】
1. Location: Where they live (e.g., Hawaii, NYC, Rural, Tokyo). If not mentioned, infer from context or default to 'US_General'.
2. Career_Status: (e.g., Student, Tech Professional, Freelancer, Stay-at-Home Parent).
3. Existing_Assets: List of items they ALREADY own ['car', 'pet', 'house', 'e-bike']. Return as JSON array. If no clear mention, return empty array [].
4. Core_Values: Calculate weights (1-10) for health, connections, freedom, growth, savings, and food.

【Analysis Logic】
- Contextual Extraction: If they say "Commuting to KCC," infer Location: 'Honolulu' and Career: 'Student'.
- Asset Recognition: If they say "My dog is my life," add 'pet' to Existing_Assets.
- Value Priority: Emotion > Survey. If they mention a hobby with high energy, maximize 'freedom' or 'growth'.

【Item Generation Rules】
- Generate EXACTLY 10 personalized RECOMMENDATIONS (NEW items, not defaults).
- Ensure a balanced mix: 2 for 'leisure', 2 for 'learning', 2 for 'wellbeing', 4 based on the user's specific passion text.
- Each item must have REALISTIC 'monthly_cost' and 'initial_cost' reflecting the INFERRED 'location'. (e.g., Hawaii costs more than rural areas)
- Each item MUST include 'name_ja' and 'name_en'.
- **IMPORTANT**: Do NOT recommend items that are already in the provided Default Items list or similar category items.

【Default Items Cost Adjustment (Optional)】
You will receive a list of "Default Items" with current costs. If you can assess that costs should be adjusted based on the user's location, lifestyle, or career:
- Return adjusted costs in 'adjusted_default_items' array
- Include 'adjusted_initial_cost' and 'adjusted_monthly_cost'
- If insufficient information to adjust, omit this field (return empty array []).

【Fallback Logic】
If the user's text is too short to generate 8+ unique items, use "Generic Templates" but LOCALIZE them:
Templates: [Commute Cost, Fitness/Health, Skill Development, Hobby/Passion, Social/Community, Work Tools]
Localization Rule: If Location is 'Hawaii', change 'Commute' to 'Gas/Ride-sharing' and adjust costs. If Career is 'Student', lower 'initial_cost' values. If they own a 'car', exclude duplicate transport costs.

【Food Cost Estimation】
You will also estimate the user's personalized food costs based on their location, career, lifestyle, and food preferences.
⚠️ CRITICAL 2026 PRICING: All food cost calculations must reference 2026 US and international cost-of-living data. Use 2026 grocery prices, inflation adjustments, and regional cost indices as of March 2026.
CRITICAL: Extract location from user's self-introduction, combined_data, or lifestyle. If any mention of 'Hawaii', 'Honolulu', 'Alaska', 'New York', 'SF', 'Tokyo', etc., use that exact location for adjustment.

Use this base formula as reference:
- Base Unit (US average): $400/month per adult equivalent
- Scale Adjustment (bulk cooking efficiency):
  * 1 person: 1.2x
  * 2 people: 1.1x
  * 3 people: 1.05x
  * 4 people: 1.0x
  * 5+ people: 0.95x
- Style Multipliers (based on food preferences - choose ONE):
  * Minimalist: 0.75x (budget-focused)
  * Standard: 1.0x (balanced)
  * Health-conscious: 1.25x (organic, premium)
  * Time-saving: 1.45x (convenience foods)
- Location-Based Cost Adjustments (ALWAYS calculate based on detected location):
  * Hawaii/Alaska/San Francisco/NYC/Premium Urban: ×1.20 to ×1.25 (+20-25%)
  * Urban centers (Atlanta, Seattle, Oakland): ×1.10 to ×1.15 (+10-15%)
  * Mid-size cities (Austin, Denver, Portland): ×1.05 to ×1.10 (+5-10%)
  * Suburban/Rural areas: ×0.85 to ×1.00 (-15% to baseline)
  * International locations: Adjust based on local grocery cost index
  * Default (mainland US average): ×1.0

Calculate:
  * base_component = adult_equivalent × base_unit × scale_adjust
  * location_adjustment_multiplier = (Detect from user's location string; if 'Hawaii' or 'Honolulu' detected, use 1.20-1.25)
  * minimalist_floor_cost = (base_component × 0.75) × location_adjustment_multiplier
  * monthly_food_cost = (base_component × user_style_multiplier) + dining_out_additions
  * Apply location_adjustment ONLY to minimalist_floor_cost
  
Validation: minimalist_floor_cost should be 60-85% of monthly_food_cost. If not, adjust values slightly.
IMPORTANT: location_adjustment must be > 1.0 if Hawaii/Alaska/urban, < 1.0 if rural. Do NOT return 1.0 unless user is in mainland US average area.

【Output Format】
Must return ONLY a valid JSON object. Do NOT include markdown formatting, backticks, or any conversational text outside the JSON.
STRICTLY KEEP the EXACT JSON keys in English (do not translate keys like 'profile', 'weights', 'recommended_actions').
⚠️ CRITICAL: DO NOT CREATE DUPLICATE FIELDS. There should be ONLY ONE set of keys, not separate fields for different languages.
  - Output ONLY: persona_title, summary, psychological_conflict (NOT persona_title_ja, summary_ja, etc.)
  - All content MUST be in {lang}: if lang='ja', write in Japanese; if lang='en', write in English.
  - NEVER CREATE alternate language fields.
⚠️ CRITICAL: NEVER INCLUDE NEWLINE/LINE BREAK CHARACTERS INSIDE JSON STRING VALUES. Write all text fields as continuous single lines. If you need to separate ideas, use periods (.) not newlines.

JSON Example Structure (LANGUAGE: {lang}):
Must return ONLY a valid JSON object. Do NOT include markdown formatting, backticks, or any conversational text outside the JSON.
IMPORTANT: All text values (persona_title, summary, psychological_conflict) MUST be written in {lang} language (Japanese if lang=ja, English if lang=en).
STRICTLY KEEP the EXACT JSON keys in English (do not translate keys like 'profile', 'weights', 'recommended_actions').

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
        
        # Pre-process: Replace raw newlines with spaces to prevent JSON parsing issues
        # This handles cases where LLM output contains actual line breaks in JSON string values
        text = text.replace('\r\n', ' ').replace('\r', ' ')
        # Replace multiple spaces with single space
        while '  ' in text:
            text = text.replace('  ', ' ')
        
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
        json_str = _clean_json_string(json_str)
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
The output language MUST be ENTIRELY in {lang}.

⚠️ EXTREME BREVITY REQUIREMENT (CRITICAL):
EVERY field MUST be EXACTLY 1 sentence ONLY. NO exceptions.
Word limits (HARD CAPS):
  - "concept": Maximum 12 words total
  - "analysis": Maximum 20 words total
  - "food_advice": Maximum 20 words total
  - "savings_advice": Maximum 20 words total
  - "blind_spot": Maximum 20 words total
  - "next_action": Maximum 20 words total

Formatting requirements:
  - NO bullet points, NO sub-points, NO lists
  - NO line breaks or paragraph separations
  - Each field = 1 single sentence
  - Punchy, direct, impactful language only
  - If you exceed the word limit, you have FAILED (user will see this as malformed output)

Concrete Examples of CORRECT LENGTH:
  - concept: "Transform Ambition into Sustainable Joy" (5 words) ✓
  - analysis: "Your freedom-seeking nature drives this budget—freedom purchases rank highest." (10 words) ✓
  - food_advice: "Minimalist eating unlocks capital for your real passion: learning." (9 words) ✓
  - blind_spot: "You claim connections matter, yet you've allocated zero for social bonding." (11 words) ✓
  - next_action: "Book one coffee chat with a friend this week." (9 words) ✓

{{
  "concept": "A short, catchy theme (max 12 words).",
  "analysis": "One sentence max 20 words explaining item selection logic.",
  "food_advice": "One sentence max 20 words on food budget strategy.",
  "savings_advice": "One sentence max 20 words on savings reality.",
  "blind_spot": "One sentence max 20 words on value-budget contradiction.",
  "next_action": "One sentence max 20 words: a specific action they can take today."
}}
"""

    prompt = """Input Data (JSON):
""" + json.dumps(input_payload, ensure_ascii=False, indent=2)

    try:
        response = _client.generate_content(
            contents=f"{sys_prompt}\n\n{prompt}"
        )
        text = response.text.strip()
        
        # Pre-process: Replace raw newlines with spaces
        text = text.replace('\r\n', ' ').replace('\r', ' ')
        while '  ' in text:
            text = text.replace('  ', ' ')
        
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end <= start:
            return None
        
        json_str = text[start:end]
        json_str = _clean_json_string(json_str)
        return json.loads(json_str)
    except Exception as e:
        print(f"Gemini Summary Error: {e}")
        return None