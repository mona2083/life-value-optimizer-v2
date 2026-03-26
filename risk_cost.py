# risk_cost.py
# 現実的コスト予測テーブル（月次・USD）
# 医療費 = 保険でカバーされない自己負担分（コプレイ・免責）
# horizon_years依存を廃止し固定値を使用

MEDICAL = {
    "18-35": {"single": 50,  "couple": 100, "kids1": 150, "kids2": 200, "kids3": 250, "kids4": 300},
    "36-50": {"single": 100, "couple": 200, "kids1": 250, "kids2": 300, "kids3": 350, "kids4": 400},
    "51-65": {"single": 200, "couple": 400, "kids1": 450, "kids2": 500, "kids3": 550, "kids4": 600},
    "66+":   {"single": 400, "couple": 800, "kids1": 850, "kids2": 900, "kids3": 950, "kids4": 1000},
}

# 固定値（中央値相当）
HOUSING_DEFAULT   = 80
CAR_REPAIR_DEFAULT = 80

EDUCATION = {
    1:  {1: 100, 2: 180, 3: 250, 4: 320},
    5:  {1: 200, 2: 360, 3: 500, 4: 640},
    10: {1: 400, 2: 700, 3: 950, 4: 1200},
    20: {1: 500, 2: 880, 3: 1200, 4: 1500},
    50: {1: 500, 2: 880, 3: 1200, 4: 1500},
}

EMERGENCY = [
    (500,   30),
    (1000,  60),
    (2000, 100),
    (float("inf"), 150),
]


def get_age_band(age: int) -> str:
    if age <= 35: return "18-35"
    if age <= 50: return "36-50"
    if age <= 65: return "51-65"
    return "66+"


def get_family_key(family: str) -> tuple[str, int]:
    mapping = {
        "一人暮らし":      ("single", 0),
        "夫婦":            ("couple", 0),
        "夫婦＋子供1人":   ("kids1",  1),
        "夫婦＋子供2人":   ("kids2",  2),
        "夫婦＋子供3人":   ("kids3",  3),
        "夫婦＋子供4人":   ("kids4",  4),
        "Single":          ("single", 0),
        "Couple":          ("couple", 0),
        "Couple + 1 Kid":  ("kids1",  1),
        "Couple + 2 Kids": ("kids2",  2),
        "Couple + 3 Kids": ("kids3",  3),
        "Couple + 4 Kids": ("kids4",  4),
    }
    return mapping.get(family, ("single", 0))


def get_emergency_cost(monthly_budget: int) -> int:
    for threshold, cost in EMERGENCY:
        if monthly_budget <= threshold:
            return cost
    return 150


def calculate_risk_costs(
    age: int,
    family: str,
    savings_period_years: int,
    monthly_budget: int,
    car_selected: bool,
) -> list[dict]:
    """
    savings_period_yearsは教育費の計算にのみ使用
    住居修繕費・車の修理費は固定値（中央値）を使用
    """
    age_band = get_age_band(age)
    family_key, num_kids = get_family_key(family)
    costs = []

    costs.append({"category": "medical",
                  "monthly_cost": MEDICAL[age_band][family_key]})
    costs.append({"category": "housing",
                  "monthly_cost": HOUSING_DEFAULT})

    if car_selected:
        costs.append({"category": "car_repair",
                      "monthly_cost": CAR_REPAIR_DEFAULT})

    if num_kids > 0:
        # 教育費は貯蓄期間に依存
        edu_key = min(savings_period_years, 20,
                      key=lambda y: abs(y - savings_period_years))
        valid_keys = [1, 5, 10, 20, 50]
        edu_key = min(valid_keys, key=lambda y: abs(y - savings_period_years))
        costs.append({"category": "education",
                      "monthly_cost": EDUCATION[edu_key][num_kids]})

    costs.append({"category": "emergency",
                  "monthly_cost": get_emergency_cost(monthly_budget)})

    return costs