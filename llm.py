import json
import streamlit as st
from google import genai
from google.genai import types

_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def get_item_defaults(item_name: str, lang: str) -> dict | None:
    prompt = f"""
You are a financial and lifestyle advisor.
Return ONLY a JSON object. No explanation, no markdown, no backticks.

Estimate realistic values for: "{item_name}"
{{
  "initial_cost":  <one-time USD cost, integer>,
  "monthly_cost":  <monthly USD cost, integer>,
  "health":        <physical & mental health impact, -10 to 10, integer>,
  "connections":   <social connection & relationships score, -10 to 10, integer>,
  "freedom":       <time freedom & autonomy score, -10 to 10, integer>,
  "growth":        <personal growth & purpose score, -10 to 10, integer>
}}
"""
    try:
        response = _client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            # 【追加】パラメータのブレをなくし、より厳密な出力を強制
            config=types.GenerateContentConfig(temperature=0.1)
        )
        text  = response.text.strip()
        start = text.find("{")
        end   = text.rfind("}") + 1
        
        # 【追加】LLMが予期せぬテキスト（謝罪やエラー文）を返した際、アプリのクラッシュを防ぐ
        if start == -1 or end <= start:
            return None
            
        raw = json.loads(text[start:end])

        def _coerce_int(v):
            return int(float(v))

        def _clamp(x, lo, hi):
            return max(lo, min(hi, x))

        for k in ("initial_cost", "monthly_cost"):
            if k in raw:
                try:
                    raw[k] = _clamp(_coerce_int(raw[k]), 0, 10**12)
                except Exception:
                    raw.pop(k, None)

        for k in ("health", "connections", "freedom", "growth"):
            if k in raw:
                try:
                    raw[k] = _clamp(_coerce_int(raw[k]), -10, 10)
                except Exception:
                    raw.pop(k, None)

        return raw
    except Exception as e:
        print(f"LLM parsing error: {e}")
        return None

def get_result_summary(
    result: dict,
    user_profile: dict,
    weights: dict,
    lang: str,
) -> dict | None:
    """
    Generate a structured life coaching summary in JSON format.
    """
    selected_names = [item["name"] for item in result["selected"]]

    if lang == "ja":
        prompt = f"""
                あなたは一流のライフコーチ兼行動経済学者です。
                以下の最適化結果を分析し、JSONオブジェクトのみを返してください。
                マークダウンやバッククォートは含めないでください。

                ユーザー: {user_profile.get('age')}歳 / {user_profile.get('family')}
                価値観の重み: 健康={weights['health']}, つながり={weights['connections']}, 自由={weights['freedom']}, 成長={weights['growth']}, 貯蓄={weights['savings']}
                選ばれたアイテム: {', '.join(selected_names) or 'なし'}
                月次費用合計: ${result['total_monthly_cost']}
                実際の月次貯蓄: ${result['actual_monthly_savings']}
                貯蓄目標達成率: {result['savings_rate']:.0%}

                【必須のJSONフォーマット】※値はすべて日本語で記述してください
                {{
                "concept": "<このライフスタイル戦略を表す15文字以内のキャッチーなテーマ>",
                "analysis": "<この選択がユーザーの価値観の重みとどう合致しているかの論理的な説明（2〜3文）>",
                "blind_spot": "<この選択によって生じる心理的または生活上の死角・リスク（例：社会的な時間が不足している等）を1つ>",
                "next_action": "<明日から始められる具体的で直ぐに実行可能なアクションを1つ>"
                }}
                """
    else:
        prompt = f"""
                You are an expert life coach and behavioral economist.
                Analyze the following optimization result and return ONLY a JSON object.
                Do not include markdown formatting or backticks.

                User: Age {user_profile.get('age')} / {user_profile.get('family')}
                Value weights: Health={weights['health']}, Connections={weights['connections']}, Freedom={weights['freedom']}, Growth={weights['growth']}, Savings={weights['savings']}
                Selected items: {', '.join(selected_names) or 'None'}
                Total monthly cost: ${result['total_monthly_cost']}
                Actual monthly savings: ${result['actual_monthly_savings']}
                Savings goal rate: {result['savings_rate']:.0%}

                Required JSON format:
                {{
                "concept": "<A catchy title for this lifestyle strategy in 4-5 words>",
                "analysis": "<Logical explanation of why this selection aligns with their value weights in 2-3 sentences>",
                "blind_spot": "<One psychological or lifestyle risk/blind spot caused by this selection (e.g., lack of social time)>",
                "next_action": "<One specific, immediate action to take starting tomorrow>"
                }}
                """
    try:
        response = _client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1)
        )
        text  = response.text.strip()
        start = text.find("{")
        end   = text.rfind("}") + 1
        
        if start == -1 or end <= start:
            return None
            
        raw = json.loads(text[start:end])
        return raw
    except Exception as e:
        print(f"LLM summary error: {e}")
        return None

def get_user_profile_from_chat(chat_text: str, lang: str) -> dict | None:
    """
    ユーザーの自由記述チャットから、価値観の重み（1〜10）と
    おすすめのカスタムアイテムを抽出する関数。
    """
    prompt = f"""
You are an expert behavioral economist and lifestyle profiler.
Analyze the user's text about their lifestyle/recent purchases.

User Text: "{chat_text}"

Task 1: Score their core values from 1 to 10 based on their text.
- health: Physical/mental wellness.
- connections: Socializing, family, community.
- freedom: Time flexibility, autonomy, travel.
- growth: Learning, career, new experiences.
- savings: Financial security, risk aversion.

Task 2: Suggest exactly ONE custom lifestyle item they would love, which is NOT in a standard budget (e.g., "Monthly Spa", "Coffee Roasting Beans").

Return ONLY a JSON object in the following format. Do not use markdown blocks, no backticks, no explanations.
{{
  "weights": {{
    "health": <int 1-10>,
    "connections": <int 1-10>,
    "freedom": <int 1-10>,
    "growth": <int 1-10>,
    "savings": <int 1-10>
  }},
  "custom_item": {{
    "name": "<string>",
    "initial_cost": <int USD>,
    "monthly_cost": <int USD>,
    "health": <int -10 to 10>,
    "connections": <int -10 to 10>,
    "freedom": <int -10 to 10>,
    "growth": <int -10 to 10>
  }}
}}
"""
    try:
        response = _client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            # 推論のブレを抑えるため、既存関数と同じく0.1に設定
            config=types.GenerateContentConfig(temperature=0.1)
        )
        text  = response.text.strip()
        start = text.find("{")
        end   = text.rfind("}") + 1
        
        if start == -1 or end <= start:
            return None
            
        raw = json.loads(text[start:end])
        return raw
        
    except Exception as e:
        print(f"LLM profiling error: {e}")
        return None