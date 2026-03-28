import os
import streamlit as st
from pydantic import BaseModel, Field
from openai import OpenAI

# OpenAIクライアントの初期化（本番環境では st.secrets または環境変数から取得）
client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY")))

# ── Pydanticスキーマの定義 ────────────────────────────────────────
class ItemDefaults(BaseModel):
    initial_cost: int = Field(description="One-time USD cost (e.g., 500)", default=0)
    monthly_cost: int = Field(description="Monthly USD cost (e.g., 50)", default=0)
    health: int = Field(description="Physical & mental health impact. Score from -10 to +10", default=0)
    connections: int = Field(description="Social connection & relationships score. Score from -10 to +10", default=0)
    freedom: int = Field(description="Time freedom & autonomy score. Score from -10 to +10", default=0)
    growth: int = Field(description="Personal growth & purpose score. Score from -10 to +10", default=0)

# ── AI推論関数 ──────────────────────────────────────────────────
def get_item_defaults(item_name: str, lang: str) -> dict | None:
    """
    ユーザーが入力したアイテム名から、現実的なコストと価値観スコアを推論する
    """
    system_prompt = """
    You are a financial and lifestyle advisor.
    Estimate realistic costs and value scores (-10 to 10) for the given item.
    Ensure strict adherence to the output schema.
    """
    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini", # コストと速度のバランスで最適
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Item to evaluate: {item_name}"}
            ],
            response_format=ItemDefaults,
            temperature=0.0, # 再現性確保
            seed=42          # 実験管理・再現性のためのシード固定
        )
        
        # Pydanticモデルから辞書型へ安全に変換して返す
        parsed_data = response.choices[0].message.parsed
        return parsed_data.model_dump()
        
    except Exception as e:
        print(f"[Error] OpenAI API parsing failed: {e}")
        return None

def get_result_summary(
    result: dict,
    user_profile: dict,
    weights: dict,
    lang: str,
) -> str | None:
    """
    最適化結果の数値を読み解き、自然言語で要約を生成する
    """
    selected_names = [item["name"] for item in result["selected"]]
    
    # 既存のプロンプトテキストをそのまま流用
    if lang == "ja":
        prompt_text = f"""
あなたはライフスタイルアドバイザーです。以下の最適化結果を2〜3文で要約してください。専門用語は使わず、わかりやすく前向きなトーンで。

ユーザー: {user_profile.get('age')}歳 / {user_profile.get('family')}
価値観の重み: 健康={weights['health']}, つながり={weights['connections']}, 自由={weights['freedom']}, 成長={weights['growth']}, 貯蓄={weights['savings']}, 食={weights.get('food', 5)}
選ばれたアイテム: {', '.join(selected_names) or 'なし'}
月次費用合計: ${result['total_monthly_cost']}
実際の月次貯蓄: ${result['actual_monthly_savings']}
貯蓄目標達成率: {result['savings_rate']:.0%}
"""
    else:
        prompt_text = f"""
You are a lifestyle advisor. Summarize the following optimization result in 2-3 sentences. Use simple, friendly, and encouraging language. No jargon.

User: Age {user_profile.get('age')} / {user_profile.get('family')}
Value weights: Health={weights['health']}, Connections={weights['connections']}, Freedom={weights['freedom']}, Growth={weights['growth']}, Savings={weights['savings']}, Food={weights.get('food', 5)}
Selected: {', '.join(selected_names) or 'None'}
Total monthly cost: ${result['total_monthly_cost']}
Actual monthly savings: ${result['actual_monthly_savings']}
Savings goal rate: {result['savings_rate']:.0%}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt_text}
            ],
            temperature=0.3, # 要約のトーンにわずかな柔軟性を持たせるため0.3とする
            seed=42
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Error] OpenAI summary generation failed: {e}")
        return None