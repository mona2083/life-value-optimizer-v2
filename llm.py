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
You are an expert Life Planner and Behavioral Psychologist with 30 years of experience.
Your task is to analyze the provided user data to infer their core values for optimization weights.

Determine a weight from 1 to 10 for each of the following five values:
- 'health'
- 'connections' (relationships, family, community)
- 'freedom' (autonomy, leisure, mobility)
- 'growth' (learning, skill-up, self-actualization)
- 'savings' (security, future planning)

【Analysis Logic】
1. Start with a baseline (all 5) and use 'value_quiz' answers (based on established psychological trade-offs) as primary indicators.
2. Analyze 'passion_free_text' for 'passion points'. If they mentioned specific passion (e.g., 'fandom', 'motorcycle', 'gym'), significantly increase the relevant value weight.
3. Consider 'lifestyle_fact' (e.g., work style, food habits) and 'financial_goal' as constraints and context.
4. If there is a contradiction between their stated goal (e.g., 'savings' high) and their passion text (e.g., 'traveling a lot'), prioritize the passion text as the latent value, and slightly reduce the stated goal weight.

Must return ONLY a valid JSON object. Do not include markdown or backticks.
Language of the data is {lang}. Output must be {lang}.

Example JSON Output:
{{
  "health": 7,
  "connections": 8,
  "freedom": 10,
  "growth": 5,
  "savings": 4
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

def get_result_summary(result: dict, user_profile: dict, weights: dict, lang: str) -> dict | None:
    """
    最適化結果に対するAIライフコーチからのフィードバックを生成する
    """
    
    # ユーザーが見るアイテム名を言語に合わせて抽出
    selected_names = []
    for item in result["selected"]:
        name = item["name_ja"] if lang == "ja" else item["name_en"]
        selected_names.append(name)

    sys_prompt = f"""
You are an expert Life Coach and Behavioral Economist.
Analyze the optimization result for the user based on their value weights.
Generate a summary dashboard with four sections:
1. 'concept': A catchy title for this lifestyle strategy (in 15 chars or 4-5 words).
2. 'analysis': A logical explanation of why this selection aligns well with their specified value weights (2-3 sentences).
3. 'blind_spot': One psychological or lifestyle risk/blind spot caused by this selection (1 sentence).
4. 'next_action': One specific, immediate action they should take starting tomorrow (1 sentence).

Must return ONLY a valid JSON object. Do not include markdown.
Language must be {lang}. Output value must be {lang}.

Example JSON Output (JA):
{{
  "concept": "自由と成長の両立プラン",
  "analysis": "高い成長意欲と自由への欲求に基づき、オンライン講座とバイクメインの移動を選択しました。貯蓄目標は未達成ですが、自己投資を優先するあなたの価値観を体現しています。",
  "blind_spot": "自己投資に偏りすぎて、長期的な資産形成が疎かになる恐れがあります。",
  "next_action": "明日、Udemyで興味のある講座を1つリストアップしてください。"
}}
"""

    prompt = f"""
User: Age {user_profile.get('age', 'N/A')} / {user_profile.get('family', 'N/A')}
Value Weights: Health={weights['health']}, Connections={weights['connections']}, Freedom={weights['freedom']}, Growth={weights['growth']}, Savings={weights['savings']}, Food={weights.get('food', 5)}

Optimization Result:
- Items selected: {', '.join(selected_names) or 'None'}
- Total Monthly Cost: ${result['total_monthly_cost']}
- Actual Monthly Savings: ${result['actual_monthly_savings']}
- Goal Achievement Rate: {result.get('savings_rate', 0):.0%}
"""

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