import os
import streamlit as st
from pydantic import BaseModel, Field
from openai import OpenAI

# OpenAI client initialization (optional - None when API key is unavailable)
_api_key = st.secrets.get("OPENAI_API_KEY") if "OPENAI_API_KEY" in st.secrets else os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=_api_key) if _api_key else None

# -- Pydantic schema definitions -------------------------------------
class ItemDefaults(BaseModel):
    initial_cost: int = Field(description="One-time USD cost (e.g., 500)", default=0)
    monthly_cost: int = Field(description="Monthly USD cost (e.g., 50)", default=0)
    health: int = Field(description="Physical & mental health impact. Score from -10 to +10", default=0)
    connections: int = Field(description="Social connection & relationships score. Score from -10 to +10", default=0)
    freedom: int = Field(description="Time freedom & autonomy score. Score from -10 to +10", default=0)
    growth: int = Field(description="Personal growth & purpose score. Score from -10 to +10", default=0)

class UserProfileFromPassion(BaseModel):
    location: str = Field(description="Geographic location (e.g., 'Hawaii', 'Tokyo', 'Unknown')")
    career: str = Field(description="Job title or career / education status (e.g., 'Software Engineer', 'Student', 'Unknown')")
    existing_assets: str = Field(description="Existing possessions/assets (e.g., 'Car, Apartment', 'Unknown')")
    interests: str = Field(description="Hobbies and interests (e.g., 'Surfing, Coffee, Coding', 'Unknown')")

# -- AI inference functions -------------------------------------------
def get_item_defaults(item_name: str, lang: str) -> dict | None:
    """
    Infer realistic costs and value scores from a user-provided item name.
    """
    system_prompt = """
    You are a financial and lifestyle advisor.
    Estimate realistic costs and value scores (-10 to 10) for the given item.
    Ensure strict adherence to the output schema.
    """
    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini", # Balanced for cost and speed
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Item to evaluate: {item_name}"}
            ],
            response_format=ItemDefaults,
            temperature=0.0, # Ensure reproducibility
            seed=42          # Fixed seed for experiment control/reproducibility
        )
        
        # Safely convert Pydantic model output to a dictionary
        parsed_data = response.choices[0].message.parsed
        return parsed_data.model_dump()
        
    except Exception as e:
        print(f"[Error] OpenAI API parsing failed: {e}")
        return None

def extract_user_profile_from_passion(passion_text: str, lang: str) -> dict:
    """
    Extract Location, Career, Existing Assets, and Interests from user free text.
    
    Args:
        passion_text: Free-text input provided by the user.
        lang: Language ('ja' or 'en').
    
    Returns:
        { "location": "...", "career": "...", "existing_assets": "...", "interests": "..." }
    """
    # Skip if no OpenAI API key is available
    if client is None:
        return {
            "location": "Unknown",
            "career": "Unknown",
            "existing_assets": "Unknown",
            "interests": "Unknown",
        }
    
    if lang == "ja":
        system_prompt = """
あなたはライフスタイル分析専門家です。
ユーザーの自由記述テキストから以下の4つの項目を抽出してください：
- Location（所在地）: どこに住んでいるか、または計画しているか
- Career（職業/職種）: 現在の職業、職種、または学生などの状態
- Existing Assets（既存資産）: 既に持っている車、不動産、スキルなど
- Interests（興味・趣味）: 好きなこと、やりたいこと、趣味

記述がない場合は 'Unknown' と記入してください。
"""
    else:
        system_prompt = """
You are a lifestyle analysis expert.
From the user's free text, extract the following 4 items:
- Location: Where they live or plan to live
- Career: Current job, profession, or status (e.g., student)
- Existing Assets: Things they already own (car, home, skills, etc.)
- Interests: Hobbies, things they want to do, interests

If an item is not mentioned, write 'Unknown'.
"""
    
    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": passion_text or ""}
            ],
            response_format=UserProfileFromPassion,
            temperature=0.0,
            seed=42
        )
        
        parsed_data = response.choices[0].message.parsed
        return parsed_data.model_dump()
        
    except Exception as e:
        print(f"[Error] Failed to extract user profile: {e}")
        return {
            "location": "Unknown",
            "career": "Unknown",
            "existing_assets": "Unknown",
            "interests": "Unknown",
        }

def get_result_summary(
    result: dict,
    user_profile: dict,
    weights: dict,
    lang: str,
) -> str | None:
    """
    Interpret optimization metrics and generate a natural-language summary.
    """
    # Skip if no OpenAI API key is available
    if client is None:
        return None
    
    selected_names = [item["name"] for item in result["selected"]]
    
    # Reuse the existing prompt text as-is
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
            temperature=0.3, # Slight flexibility in summary tone
            seed=42
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Error] OpenAI summary generation failed: {e}")
        return None