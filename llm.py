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
        
        # Within string: replace actual newlines with escaped \n
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
            # For Japanese, split by common separators and extract keywords
            keywords = name.replace("・", " ").replace("・", " ").split()
            default_keywords.update(keywords)
        else:
            # For English, split by spaces and '/'
            keywords = name.replace("/", " ").replace("-", " ").split()
            default_keywords.update([kw.lower() for kw in keywords if len(kw) > 2])
    
    # Filter recommended items
    filtered = []
    for item in recommended_actions:
        name_key = "name_ja" if lang == "ja" else "name_en"
        item_name = item.get(name_key, "").lower()
        
        # Extract keywords from recommended item
        if lang == "ja":
            item_keywords = set(item_name.replace("・", " ").split())
        else:
            item_keywords = set(word.lower() for word in item_name.replace("/", " ").replace("-", " ").split() if len(word) > 2)
        
        # Check overlap ratio
        if default_keywords and item_keywords:
            overlap = len(item_keywords & default_keywords)
            overlap_ratio = overlap / len(item_keywords)
            
            # Filter out if > 30% keyword overlap (too similar)
            if overlap_ratio <= 0.3:
                filtered.append(item)
        else:
            filtered.append(item)
    
    return filtered


def get_user_profile(age: int, family: str, combined_data_str: str, lang: str) -> dict | None:
    """
    心理学・行動経済学に基づいた定型回答と自由記述を複合解析し、価値観スコア(1-10)を推論する
    """
    
    # Build list of items to EXCLUDE from recommendations
    excluded_items_ja = [item.get("name_ja") for item in DEFAULT_ITEMS if item.get("name_ja")]
    excluded_items_en = [item.get("name_en") for item in DEFAULT_ITEMS if item.get("name_en")]
    excluded_items_str_ja = "\n".join([f"  • {name}" for name in excluded_items_ja])
    excluded_items_str_en = "\n".join([f"  • {name}" for name in excluded_items_en])
    
    # 熟練ライフプランナー兼心理学者としてのシステムプロンプト（JSON出力強制）
    sys_prompt = f"""
OUTPUT LANGUAGE: {lang.upper()}
CRITICAL: Write all content in {lang.upper()}, not English. If lang='ja', respond entirely in Japanese. Do NOT create duplicate fields (no persona_title_ja, summary_ja, etc.).

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
- **CRITICAL RULE**: Do NOT recommend ANY items that are already in the following Default Items list. Also avoid items with SIMILAR keywords or concepts:

DEFAULT ITEMS TO EXCLUDE (Existing in the system):
Japanese Names:
{excluded_items_str_ja}

English Names:
{excluded_items_str_en}

⚠️ STRICT FILTERING: If the user mentions "travel" and you want to recommend travel, check the list above first. 
If "旅行・リトリート積立" or "Travel / Retreat Fund" exists, DO NOT generate a similar item like "週末旅行積立" or "Weekend Travel Fund".
Always generate TRULY UNIQUE items that complement the defaults, not duplicate them.

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

【Profile Analysis Requirements】
The profile fields MUST deliver genuine psychological insights, not just summaries:

1. "persona_title": A 2-4 word archetype that captures their deepest identity (e.g., "The Purposeful Pioneer", "The Harmony Seeker")

2. "summary": Write 2-3 sentences that go DEEP. NO line breaks within the text—write as a continuous paragraph. Explain:
   - Their core psychological drivers based on the data (e.g., "Your high Growth weight reveals a person driven by self-improvement, but your moderate Connections weight suggests you're still learning to balance personal ambition with deeper relationships")
   - What patterns emerge from their choices and passions (e.g., their freedom-seeking behavior, their values alignment)
   - Their unique positioning in life right now (context, life stage, what they're really searching for)
   - Include a forward-looking element that shows their potential growth
   Use warm, validating language that shows you *understand* them as a whole person.

3. "psychological_conflict": Write 2-3 sentences (NO line breaks between) that reveal a REAL tension, then frame it as growth:
   - Start by naming the conflict honestly (e.g., "You claim Connections is important, yet your budget shows minimal social spending, risking isolation")
   - Explain the psychological ROOTS of this conflict (e.g., "This suggests a subconscious belief that investing in yourself must come at the cost of building relationships")
   - END with a HOPEFUL reframe that shows this is actually a strength or opportunity (e.g., "But this awareness is your superpower—you're now positioned to deliberately strengthen BOTH your independence AND your bonds, creating a more integrated life")
   Never be harsh. Be a therapist, not a critic.

JSON Example Structure (LANGUAGE: {lang}):
{{
  "profile": {{
    "location": "Honolulu",
    "career": "Professional",
    "existing_assets": ["car"],
    "persona_title": "{"探求とバランスの調和者" if lang == "ja" else "The Purposeful Pioneer"}",
    "summary": "{"あなたは、新しい経験への探求心と、日々の生活における調和を大切にする、バランスの取れた人物です。..." if lang == "ja" else "You are fundamentally a self-directed learner with an adventurous spirit..."}",
    "psychological_conflict": "{"あなたの独立心と、他者との繋がりのバランスについて..." if lang == "ja" else "There is a creative tension in your profile..."}"
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
        start = text.find("{")
        if start == -1:
            print(f"Gemini Profile Error: No JSON opening brace found in response")
            return None
        
        # Find matching closing brace more carefully
        depth = 0
        end = start
        in_string = False
        escape_next = False
        
        for i in range(start, len(text)):
            char = text[i]
            
            # Handle escape sequences
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            # Handle string literals
            if char == '"':
                in_string = not in_string
                continue
            
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
            print(f"Gemini Profile Error: Unmatched braces in JSON (depth={depth})")
            print(f"Response text (first 1000 chars): {text[:1000]}")
            return None
        
        json_str = text[start:end]
        # Additional cleaning as failsafe
        json_str = _clean_json_string(json_str)
        
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"Gemini Profile Error: JSON parsing failed - {e}")
            print(f"Response text (first 500 chars): {text[:500]}")
            print(f"Extracted JSON (first 500 chars): {json_str[:500] if json_str else 'N/A'}")
            return None
        
        # Filter out recommended items that are similar to DEFAULT_ITEMS
        # (Temporarily disabled - relying on LLM prompt to avoid duplicates. Can be re-enabled if needed)
        # if "recommended_actions" in result and result["recommended_actions"]:
        #     result["recommended_actions"] = _filter_out_duplicate_items(
        #         result["recommended_actions"],
        #         lang=lang
        #     )
        
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
LANGUAGE: {lang.upper()} ONLY. No English.
{f'出力は全て日本語です。' if lang == 'ja' else ''}

🚨 EXTREME BREVITY REQUIREMENT - MANDATORY 🚨
EVERY field MUST be EXACTLY 1 sentence. NO exceptions. NO longer responses.
- concept: UNDER 12 words
- analysis: UNDER 20 words
- food_advice: UNDER 20 words
- savings_advice: UNDER 20 words
- blind_spot: UNDER 20 words
- next_action: UNDER 20 words

You are a Life Coach providing SHORT, SHARP insights.
Be warm but CONCISE. Reference specific items but keep EVERY response to 1 sentence max.

Examples of CORRECT length:
- concept: "Freedom through Strategic Choice" (3 words)
- analysis: "Your system protected relationships over solo pursuits, honoring your core value." (11 words)
- next_action: "Text one friend about doing a free activity together this week." (11 words)

CRITICAL: Responses longer than these examples will FAIL. Keep everything SHORT.

【Output Format - ULTRA-BRIEF & PUNCHY】
Must return ONLY a valid JSON object. No markdown, backticks, or text outside JSON.
⚠️ RESPOND ENTIRELY IN {lang.upper()}.
{f'日本語で全て書いてください。英語は絶対に使わないでください。' if lang == 'ja' else ''}

STRICT WORD LIMITS (these are HARD caps, not suggestions):
{{
  "concept": "UNDER 12 WORDS. One punchy theme.",
  "analysis": "1 SENTENCE MAX (under 20 words). Why this optimization matters.",
  "food_advice": "1 SENTENCE MAX (under 20 words). One insight on their choice.",
  "savings_advice": "1 SENTENCE MAX (under 20 words). One insight on their rate.",
  "blind_spot": "1 SENTENCE MAX (under 20 words). One tension + reframe.",
  "next_action": "1 SENTENCE MAX (under 20 words). Specific action for TODAY."
}}

FAILURE CRITERIA: If ANY field exceeds word limits or has multiple sentences, response is incorrect.
"""

    prompt = """Input Data (JSON):
""" + json.dumps(input_payload, ensure_ascii=False, indent=2)

    try:
        response = _client.generate_content(
            contents=f"{sys_prompt}\n\n{prompt}"
        )
        text = response.text.strip()
        
        # Pre-process: Replace raw newlines with spaces to prevent JSON parsing issues
        text = text.replace('\r\n', ' ').replace('\r', ' ')
        # Replace multiple spaces with single space
        while '  ' in text:
            text = text.replace('  ', ' ')
        
        start = text.find("{")
        if start == -1:
            print(f"Gemini Summary Error: No JSON opening brace found")
            return None
        
        # Find matching closing brace
        depth = 0
        end = start
        in_string = False
        escape_next = False
        
        for i in range(start, len(text)):
            char = text[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
        
        if depth != 0:
            print(f"Gemini Summary Error: Unmatched braces in JSON (depth={depth})")
            return None
        
        json_str = text[start:end]
        # Additional cleaning as failsafe
        json_str = _clean_json_string(json_str)
        return json.loads(json_str)
        
    except json.JSONDecodeError as e:
        print(f"Gemini Summary Error: JSON parsing failed - {e}")
        return None