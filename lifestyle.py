from typing import Optional

INCOME_REASON_OPTIONS = {
    "ja": ["学校卒業", "資格取得", "転職", "昇給", "その他"],
    "en": ["School Graduation", "Certification", "Job Change", "Promotion", "Other"],
}


def calculate_lifestyle_adjustments(lifestyle: dict, lang: str) -> dict:
    income_increase = lifestyle.get("income_increase", 0)
    income_years    = lifestyle.get("income_years", 0)
    savings_years   = lifestyle.get("savings_years", 99)
    income_reason   = lifestyle.get("income_reason", "")
    current_budget  = lifestyle.get("monthly_budget", 0)

    if income_increase > 0 and income_years <= savings_years:
        future_budget = current_budget + income_increase
        future_note = (
            f"※{income_years}年後に月+${income_increase:,}の収入増を見込んでいます（理由：{income_reason}）"
            if lang == "ja" else
            f"※ Projected income increase of +${income_increase:,}/month in {income_years} year(s) ({income_reason})"
        )
    else:
        future_budget = current_budget
        future_note   = ""

    return {
        "future_monthly_budget": future_budget,
        "future_note":           future_note,
    }