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
) -> str | None:
    selected_names = [item["name"] for item in result["selected"]]

    if lang == "ja":
        prompt = f"""
あなたはライフスタイルアドバイザーです。
以下の最適化結果を2〜3文で要約してください。
専門用語は使わず、わかりやすく前向きなトーンで。

ユーザー: {user_profile.get('age')}歳 / {user_profile.get('family')}
価値観の重み: 健康={weights['health']}, つながり={weights['connections']}, 自由={weights['freedom']}, 成長={weights['growth']}, 貯蓄={weights['savings']}
選ばれたアイテム: {', '.join(selected_names) or 'なし'}
月次費用合計: ${result['total_monthly_cost']}
実際の月次貯蓄: ${result['actual_monthly_savings']}
貯蓄目標達成率: {result['savings_rate']:.0%}
"""
    else:
        prompt = f"""
You are a lifestyle advisor.
Summarize the following optimization result in 2-3 sentences.
Use simple, friendly, and encouraging language. No jargon.

User: Age {user_profile.get('age')} / {user_profile.get('family')}
Value weights: Health={weights['health']}, Connections={weights['connections']}, Freedom={weights['freedom']}, Growth={weights['growth']}, Savings={weights['savings']}
Selected: {', '.join(selected_names) or 'None'}
Total monthly cost: ${result['total_monthly_cost']}
Actual monthly savings: ${result['actual_monthly_savings']}
Savings goal rate: {result['savings_rate']:.0%}
"""
    try:
        response = _client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        print(f"LLM summary error: {e}")
        return None