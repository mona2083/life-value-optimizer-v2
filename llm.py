import os
from openai import OpenAI
import json
from default_items import DEFAULT_ITEMS
import streamlit as st

def _resolve_openai_api_key() -> str | None:
    try:
        return st.secrets.get("OPENAI_API_KEY")
    except (AttributeError, FileNotFoundError):
        pass

    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return api_key

    try:
        from keys import OPENAI_API_KEY
        return OPENAI_API_KEY
    except ImportError:
        return None


_api_key = _resolve_openai_api_key()
_client = OpenAI(api_key=_api_key) if _api_key else None

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


def _build_default_item_avoidance_block() -> str:
    """
    Build a compact prompt block that tells the LLM which default items to avoid
    or treat as off-limits for recommendation generation.
    """
    grouped = {}
    for item in DEFAULT_ITEMS:
        grouped.setdefault(item.get("category", "other"), []).append(item)

    category_labels = {
        "transport": "transport",
        "living": "living",
        "wellbeing": "wellbeing",
        "leisure": "leisure",
        "learning": "learning",
    }

    lines = ["### DEFAULT ITEM AVOIDANCE"]
    lines.append("Avoid proposing anything that is a renamed, narrowed, or obvious substitute for these default items:")

    for category in ["transport", "living", "wellbeing", "leisure", "learning"]:
        items = grouped.get(category, [])
        if not items:
            continue

        names = []
        for item in items:
            name_ja = item.get("name_ja") or ""
            name_en = item.get("name_en") or ""
            if name_ja and name_en:
                names.append(f"{name_en} / {name_ja}")
            else:
                names.append(name_en or name_ja)

        lines.append(f"- {category_labels.get(category, category)}: {', '.join(names)}")

    lines.append("Hard rules:")
    lines.append("- Do NOT return items that are essentially the same purpose as a default item, even if the name is changed.")
    lines.append("- Do NOT return direct duplicates, close synonyms, or costume changes of default items.")
    lines.append("- If the obvious idea is already covered by defaults, choose a clearly different angle, context, or life function.")
    lines.append("- Prefer unique, situation-specific, passion-specific ideas that a default catalog would not already cover.")
    lines.append("- When in doubt, pick something more distinct rather than more familiar.")
    lines.append("")
    lines.append("### OCCUPIED ARCHETYPES (FORBIDDEN FOR GENERIC VARIANTS)")
    lines.append("- Mobility: Car (Primary), Motorcycle (Primary), Car Share + Bicycle, E-Bike + Uber, Public Transit, Bicycle Only, Uber/Lyft Only")
    lines.append("- Time-Reclamation: Time-saving Appliances, Housekeeping Service")
    lines.append("- Body-Maintenance: Gym / Yoga, Massage / Spa / Sauna, Travel / Retreat Fund")
    lines.append("- Social-Consumption: Coffee / Cafe, Socializing / Drinks, Home Drinks, Fashion / Beauty")
    lines.append("- Knowledge/Craft: Books / Audible")
    lines.append("- If a candidate recommendation maps to one of these archetypes as the same life function, reject it and generate a distinct alternative.")

    lines.append("")
    lines.append("### NEGATIVE EXAMPLES")
    lines.append("- Bad: 'Inspiration trip fund' -> same life function as Travel / Retreat Fund.")
    lines.append("- Bad: 'Flexible mobility subscription (car-share/bike-share)' -> same life function as Car Share + Bicycle.")
    lines.append("- Bad: 'Alternative fitness membership' -> same life function as Gym / Yoga.")

    return "\n".join(lines)


def _build_default_items_reference() -> str:
    """Build a compact JSON reference for prompt grounding."""
    return json.dumps(
        [
            {
                "id": item.get("id"),
                "category": item.get("category"),
                "name_ja": item.get("name_ja"),
                "name_en": item.get("name_en"),
                "priority": item.get("priority"),
            }
            for item in DEFAULT_ITEMS
        ],
        ensure_ascii=False,
        indent=2,
    )


CANONICAL_CATEGORIES = ("transport", "living", "wellbeing", "leisure", "learning")

_CATEGORY_ALIAS_TO_CANONICAL = {
    # transport
    "transport": "transport",
    "transportation": "transport",
    "mobility": "transport",
    "commute": "transport",
    "commuting": "transport",
    "car": "transport",
    "bike": "transport",
    "bicycle": "transport",
    "transit": "transport",
    "travel": "transport",
    "traffic": "transport",
    "rideshare": "transport",
    "uber": "transport",
    "taxi": "transport",
    "moving": "transport",
    "移動": "transport",
    "交通": "transport",
    # living
    "living": "living",
    "life": "living",
    "lifestyle": "living",
    "housing": "living",
    "house": "living",
    "home": "living",
    "household": "living",
    "rent": "living",
    "utilities": "living",
    "food": "living",
    "meal": "living",
    "meals": "living",
    "dining": "living",
    "生活": "living",
    "住居": "living",
    # wellbeing
    "wellbeing": "wellbeing",
    "well-being": "wellbeing",
    "wellness": "wellbeing",
    "health": "wellbeing",
    "healthy": "wellbeing",
    "fitness": "wellbeing",
    "exercise": "wellbeing",
    "mental health": "wellbeing",
    "self care": "wellbeing",
    "self-care": "wellbeing",
    "medical": "wellbeing",
    "healthcare": "wellbeing",
    "care": "wellbeing",
    "relaxation": "wellbeing",
    "健康": "wellbeing",
    "ウェルビーイング": "wellbeing",
    # leisure
    "leisure": "leisure",
    "hobby": "leisure",
    "hobbies": "leisure",
    "entertainment": "leisure",
    "fun": "leisure",
    "recreation": "leisure",
    "social": "leisure",
    "socializing": "leisure",
    "community": "leisure",
    "culture": "leisure",
    "play": "leisure",
    "games": "leisure",
    "music": "leisure",
    "movie": "leisure",
    "movies": "leisure",
    "streaming": "leisure",
    "休暇": "leisure",
    "余暇": "leisure",
    "娯楽": "leisure",
    "趣味": "leisure",
    # learning
    "learning": "learning",
    "learn": "learning",
    "education": "learning",
    "study": "learning",
    "skill": "learning",
    "skills": "learning",
    "course": "learning",
    "courses": "learning",
    "training": "learning",
    "development": "learning",
    "growth": "learning",
    "reading": "learning",
    "books": "learning",
    "certification": "learning",
    "学習": "learning",
    "教育": "learning",
    "勉強": "learning",
    "スキル": "learning",
}


def _normalize_category(raw_category: object, fallback: str = "leisure") -> str:
    if not isinstance(raw_category, str):
        return fallback

    normalized = " ".join(
        raw_category.strip().lower().replace("_", " ").replace("-", " ").split()
    )
    if not normalized:
        return fallback

    if normalized in CANONICAL_CATEGORIES:
        return normalized

    alias_match = _CATEGORY_ALIAS_TO_CANONICAL.get(normalized)
    if alias_match:
        return alias_match

    keyword_map = {
        "transport": ("transport", "commute", "mobility", "ride", "車", "交通", "移動"),
        "living": ("living", "home", "house", "rent", "food", "meal", "生活", "住居"),
        "wellbeing": ("well", "health", "fitness", "care", "mental", "健康"),
        "leisure": ("leisure", "hobby", "entertain", "social", "fun", "余暇", "娯楽", "趣味"),
        "learning": ("learn", "study", "education", "skill", "growth", "学習", "教育", "勉強"),
    }
    for canonical, keywords in keyword_map.items():
        if any(k in normalized for k in keywords):
            return canonical

    return fallback


def _normalize_profile_payload(result: object) -> object:
    if not isinstance(result, dict):
        return result

    actions = result.get("recommended_actions")
    if not isinstance(actions, list):
        return result

    for item in actions:
        if isinstance(item, dict):
            item["category"] = _normalize_category(item.get("category"))

    return result


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
        
        # Within string: replace actual newlines with spaces
        if in_string and char in '\n\r':
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


def get_user_profile(age: int, family: str, combined_data_str: str, lang: str) -> dict | None:
    """
    心理学・行動経済学に基づいた定型回答と自由記述を複合解析し、価値観スコア(1-10)を推論する
    """
    
    # 熟練ライフプランナー兼心理学者としてのシステムプロンプト（JSON出力強制）
    sys_prompt = f"""
### ROLE & ARCHETYPE
You are a World-Class Senior Life Planner and Behavioral Psychologist (30+ years experience).
- TONE: Considerate, Optimistic, yet highly Professional. 
- MISSION: Connect 2026 economic reality with the user's emotional "Passion."

### CONTEXT
- Current Date: March 2026. (Reflect 2026 inflation, market prices, and cost-of-living indices).
- Language: You MUST output all prose in {lang}.

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

### 3. DYNAMIC DEFAULT ITEM OVERRIDE
You will receive "Default Items" with IDs.
- Adjust costs ONLY if unrealistic for the inferred 2026 location/career.
- If 'car' is owned, adjust transport defaults to reflect gas/maintenance only, not purchase.

### 4. ITEM GENERATION (EXACTLY 10 ITEMS)
Generate EXACTLY 10 personalized RECOMMENDATIONS (NOT in defaults).
- **Split**: 2 Leisure, 2 Learning, 2 Wellbeing, 4 Passion-specific.
- **FALLBACK**: If input is short, use templates [Commute, Gym, Skill-up, Hobby, Social, Tools] but LOCALISE them (e.g., 'Gym' in Hawaii -> 'Ocean/Hiking activities').
- **TONE**: Write 'ai_message' as a mentor. Use: "Given your passion for X, this is the engine for your joy."
- **NOVELTY RULE**: The 10 recommendations must be meaningfully different from defaults. Do not rename a default item, narrow it slightly, or swap in a near-synonym.
- **ANTI-DUPLICATION RULE**: If a candidate overlaps with a default item in purpose, use case, or category function, reject it and generate a distinct alternative.
- **DISTINCTNESS TARGET**: Favor items that are passion-specific, contextual, or experiential rather than generic life-utility items already in the catalog.

### 4A. OCCUPIED ARCHETYPE FILTER
Treat the following as already-covered functions that must NOT be re-proposed in generic form:
- Mobility, Time-Reclamation, Body-Maintenance, Social-Consumption, Knowledge/Craft.
If a draft recommendation is a renamed variant of one of these occupied functions, reject it before output.

### 4B. PER-ITEM SELF-CHECK (MANDATORY)
Before finalizing each recommendation, pass all gates:
1. **Passion Match**: Directly tied to user passion/core-value signal, not generic utility.
2. **Forbidden Archetype Test**: Not a functional substitute for any default item.
3. **Situational Specificity**: Specific to user context (location/career/lifestyle), not reusable for anyone.
If any gate fails, regenerate the item.

### 4C. CATEGORY CONSTRAINT (STRICT)
For every item in recommended_actions, category MUST be one of:
["transport", "living", "wellbeing", "leisure", "learning"]

Do NOT use any other labels (e.g., wellness, health, hobby, passion, growth, social, entertainment).
If unsure, map to the nearest valid category above.
Any item with an invalid category is considered a failed output.

### 5. VOICE & TONE GUIDELINES
- **Persona Title**: Inspiring (e.g., "The Strategic Voyager," "Architect of Dreams").
- **Psychological Conflict**: Be empathetic. Frame it as "bridging the gap between heart and wisdom."
- **Summary**: Be optimistic. Frame the budget as "fueling your highest potential."

### OUTPUT FORMAT (STRICT JSON)
- **STRICT LANGUAGE RULE**: All prose fields (persona_title, summary, psychological_conflict, ai_message, name_ja, name_en) MUST follow {lang}.
- NO Markdown, NO backticks.

JSON Example Structure:
{{
  "profile": {{
    "location": "Honolulu",
    "career": "Student",
    "existing_assets": ["car"],
    "persona_title": "Ambitious Nomad",
    "summary": "Create a 2-sentence 'Strategic Blueprint' that synthesizes the entire optimized plan. 
    Do not just list costs. Instead, explain how this specific allocation of resources directly empowers the user's 'Persona Title' to achieve their primary life mission. 
    Focus on the synergy between their budget and their highest 'Core Value' score.",

    "psychological_conflict": "Identify the specific 2-sentence tension between the user's emotional passion and their financial/logical constraints. 
    Avoid generic 'want vs. save' templates. Instead, pinpoint the exact friction between two competing 'Core Values' (e.g., the high weight of 'Freedom' vs. the necessity of 'Savings'). 
    Frame it as a 'noble struggle' that this specific optimized plan is designed to resolve.",
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

    default_items_for_prompt = _build_default_items_reference()
    default_items_avoidance_block = _build_default_item_avoidance_block()

    prompt = f"""
Age: {age} / Family: {family}

【User Combined Input Data】
{combined_data_str}

【Default Items Reference】
Use these items as reference for cost adjustment (if applicable):
{default_items_for_prompt}

{default_items_avoidance_block}

【Recommendation Boundary】
- Recommend only items that would not already be covered by the default catalog.
- If a draft recommendation feels like "default item + adjective" or "default item + setting change", replace it.
- A good recommendation should feel like a new life move, not a catalog variant.
"""

    if not _client:
        print("OpenAI Profile Error: API key not configured")
        return None

    try:
        response = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        text = response.choices[0].message.content.strip()
        
        # Robust JSON extraction: Find the outermost valid JSON object
        # Strategy: Start from first "{" and find matching "}"
        start = text.find("{")
        if start == -1:
            print(f"OpenAI Profile Error: No JSON opening brace found in response")
            return None
        
        # Find matching closing brace, but fall back to last } if incomplete
        depth = 0
        end = start
        in_string = False
        escape_next = False
        last_closing_brace = -1
        
        for i in range(start, len(text)):
            char = text[i]
            
            # Handle escapes first (before checking quotes)
            if escape_next:
                escape_next = False
                continue
            
            # Handle string literals to avoid counting braces inside strings
            if char == '"':
                in_string = not in_string
            elif char == '\\' and in_string:
                escape_next = True
                continue
            
            # Count braces only outside strings
            if not in_string:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    last_closing_brace = i + 1
                    if depth == 0:
                        end = i + 1
                        break
        
        # If we reached end and depth != 0, use the last closing brace we found
        if depth != 0:
            if last_closing_brace > start:
                print(f"⚠️  JSON incomplete (depth={depth}), using last closing brace at position {last_closing_brace}")
                end = last_closing_brace
            else:
                print(f"OpenAI Profile Error: No closing brace found in JSON")
                print(f"Response text (first 1000 chars): {text[:1000]}")
                return None
        
        json_str = text[start:end]
        json_str = _clean_json_string(json_str)
        
        try:
            result = json.loads(json_str)
            result = _normalize_profile_payload(result)
            return result
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON decode error: {e}")
            # Try to fix by adding closing braces
            json_str_fixed = json_str + "}" * 5  # Add closing braces to close
            try:
                result = json.loads(json_str_fixed)
                result = _normalize_profile_payload(result)
                print(f"✅ Fixed JSON by adding closing braces")
                return result
            except:
                print(f"OpenAI Profile Error: JSON parsing failed even after fixing")
                print(f"Original JSON (first 500 chars): {json_str[:500]}")
                return None
        
    except Exception as e:
        print(f"OpenAI Profile Error: {type(e).__name__} - {e}")
        print(f"Response text snippet: {text[:300] if 'text' in locals() else 'N/A'}")
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
  "food_advice": "Create a 2-sentence psychological insight that bridges the user's chosen food style with their primary 'Core Value' and 'Career'. 
    Avoid generic templates. Instead, explain WHY this specific choice is a tactical advantage for their 'Persona Title'. 
    For example, if they are an 'Ambitious Student,' explain how their food choice specifically fuels their 'Growth' or 'Freedom' goals. 
    Frame it as a conscious, empowering decision that supports their long-term blueprint."
  "savings_advice": "2 sentences evaluating the *psychological* meaning of their savings rate. Are they honoring security needs or hoarding out of fear? Are they investing in today's joy or sacrificing it? Provide warmth and gentle honest diagnosis.",
  "blind_spot": "A compassionate but direct insight pointing out a contradiction between their stated Core Values and budget allocation. Frame as opportunity for growth, not failure. Example: 'You rated Connections as 9, yet allocated $0 here. This gap might lead to burnout. What's the story—fear? Guilt? This gap deserves attention.'",
  "next_action": "One very specific, warmth-filled micro-action they can do TODAY. Make it feel achievable, human, and aligned with their deepest value. Example: 'Text one friend you've been meaning to reconnect with and suggest a free walk together—small moments rebuild bonds.'"
}}
"""

    prompt = """Input Data (JSON):
""" + json.dumps(input_payload, ensure_ascii=False, indent=2)

    if not _client:
        print("OpenAI Summary Error: API key not configured")
        return None

    try:
        response = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        text = response.choices[0].message.content.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end <= start:
            return None
        return json.loads(text[start:end])
    except Exception as e:
        print(f"OpenAI Summary Error: {e}")
        return None