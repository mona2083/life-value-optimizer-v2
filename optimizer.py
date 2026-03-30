from ortools.sat.python import cp_model


def food_related_score(item: dict) -> int:
    """
    食生活に結びつきやすいアイテムほど高いスコア（0〜20程度）。
    living / 一部 wellbeing・leisure を対象。
    """
    cat = item.get("category", "") or ""
    h = int(item.get("health", 0) or 0)
    c = int(item.get("connections", 0) or 0)
    g = int(item.get("growth", 0) or 0)
    if cat == "living":
        return max(0, min(20, (h + c + g + 27) // 3))
    if cat == "wellbeing":
        return max(0, min(15, (h + 5) // 2))
    if cat == "leisure":
        n = (item.get("name_ja") or "") + (item.get("name_en") or "")
        if any(
            k in n
            for k in (
                "飲み",
                "交際",
                "Dining",
                "Social",
                "Coffee",
                "カフェ",
                "Cafe",
            )
        ):
            return max(0, min(15, (c + h + 10) // 2))
    return 0


def _calc_priority_weights(candidates: list[dict]) -> list[float]:
    priorities = [item.get("priority", 1) for item in candidates]
    unique_p   = sorted(set(priorities))
    n_unique   = len(unique_p)
    weights    = []
    for item in candidates:
        p    = item.get("priority", 1)
        rank = unique_p.index(p)
        w    = 1.5 if n_unique == 1 else 2.0 - (rank / (n_unique - 1))
        weights.append(w)
    return weights

def _base_utility(item: dict, weights: dict) -> int:
    # Fix: Prevent unconditional exclusion bugs due to negative utilities by adding +10 to all scores
    fw = int(weights.get("food", 5))
    fr = food_related_score(item)
    food_term = fw * (fr + 10) * 40
    return (
        weights["health"]      * (int(item["health"]) + 10)      * 100 +
        weights["connections"] * (int(item["connections"]) + 10) * 100 +
        weights["freedom"]     * (int(item["freedom"]) + 10)     * 100 +
        weights["growth"]      * (int(item["growth"]) + 10)      * 100
        + food_term
    )

def run_optimizer(
    items: list[dict],
    total_budget: int,
    monthly_budget: int,
    target_monthly_savings: int,
    weights: dict,
    food_stage1_max: int = 0,
    food_stage2_max: int = 0,
    require_transport: bool = True,
) -> dict:
    candidates = [
        item for item in items
        if item.get("priority", 0) > 0 or item.get("mandatory", False)
    ]

    if not candidates:
        return _no_solution(monthly_budget, target_monthly_savings)

    n = len(candidates)
    priority_weights_int = [int(w * 100) for w in _calc_priority_weights(candidates)]
    base_utils           = [_base_utility(item, weights) for item in candidates]
    utilities            = [(base_utils[i] * priority_weights_int[i]) // 100 for i in range(n)]

    model = cp_model.CpModel()
    x     = [model.NewBoolVar(f"x_{i}") for i in range(n)]

    for i, item in enumerate(candidates):
        if item.get("mandatory", False):
            model.Add(x[i] == 1)

    model.Add(sum(x[i] * candidates[i]["initial_cost"] for i in range(n)) <= total_budget)
    food_stage1_max = max(int(food_stage1_max or 0), 0)
    food_stage2_max = max(int(food_stage2_max or 0), 0)
    food_stage1_var = model.NewIntVar(0, food_stage1_max, "food_stage1_var")
    food_stage2_var = model.NewIntVar(0, food_stage2_max, "food_stage2_var")
    model.Add(
        sum(x[i] * candidates[i]["monthly_cost"] for i in range(n))
        + food_stage1_var
        + food_stage2_var
        <= monthly_budget
    )

    transport_idx = [i for i, item in enumerate(candidates) if item.get("category") == "transport"]
    if transport_idx:
        if require_transport:
            model.Add(sum(x[i] for i in transport_idx) >= 1)
        model.Add(sum(x[i] for i in transport_idx) <= 1)

    pet_idx = [i for i, item in enumerate(candidates)
               if item.get("name", "") in ("ペット", "Pet") and item.get("category") == "wellness"]
    pet_insurance_idx = [i for i, item in enumerate(candidates)
                         if item.get("name", "") in ("ペット保険", "Pet Insurance")]
    if pet_insurance_idx:
        for pi in pet_insurance_idx:
            model.Add(x[pi] <= sum(x[i] for i in pet_idx)) if pet_idx else model.Add(x[pi] == 0)

    car_primary_idx = [i for i, item in enumerate(candidates)
                       if item.get("name", "") in ("車メイン", "Car (Primary)")]
    car_insurance_idx = [i for i, item in enumerate(candidates)
                         if item.get("name", "") in ("車保険", "Car Insurance")]
    if car_insurance_idx:
        for ci in car_insurance_idx:
            model.Add(x[ci] <= sum(x[i] for i in car_primary_idx)) if car_primary_idx else model.Add(x[ci] == 0)

    items_value = sum(x[i] * utilities[i] for i in range(n))

    total_monthly_cost_var = model.NewIntVar(0, monthly_budget, "total_monthly_cost")
    model.Add(
        total_monthly_cost_var
        == sum(x[i] * candidates[i]["monthly_cost"] for i in range(n))
        + food_stage1_var
        + food_stage2_var
    )
    actual_savings_var = model.NewIntVar(0, monthly_budget, "actual_savings")
    model.Add(actual_savings_var == monthly_budget - total_monthly_cost_var)

    total_max_utility = sum(utilities)
    
    # Fix: Safely use float division, ensuring multiplier is at least >= 1 when weight > 0
    _raw_savings_coefficient = (total_max_utility * weights["savings"]) / (10 * max(monthly_budget, 1))
    savings_coefficient = max(1 if weights["savings"] > 0 else 0, int(_raw_savings_coefficient))
    
    # Utility of savings heavily focuses only on the target achievement part.
    # If overachieved parts linearly scale the same way, the objective function
    # skews towards 'save more' over Stage2 (Upgrade), resulting in Stage2 often being 0.
    if target_monthly_savings > 0:
        ts = model.NewIntVar(0, monthly_budget, "target_monthly_savings_fixed")
        model.Add(ts == target_monthly_savings)
        savings_to_goal = model.NewIntVar(0, monthly_budget, "savings_to_goal")
        model.AddMinEquality(savings_to_goal, [actual_savings_var, ts])
        savings_value = model.NewIntVar(0, int(monthly_budget * savings_coefficient) + 1, "savings_value")
        model.Add(savings_value == savings_to_goal * savings_coefficient)
    else:
        savings_value = model.NewIntVar(0, int(monthly_budget * savings_coefficient) + 1, "savings_value")
        model.Add(savings_value == actual_savings_var * savings_coefficient)

    # ===== Reflect 2-stage food model in the objective function =====
    # Stage1: C_min -> C_survey (Strongly encourage reaching the requested standard)
    # Stage2: C_survey -> C_max (Luxury upgrade proportional to 'food weight')
    food_weight = max(int(weights.get("food", 5) or 0), 1)
    # Vary strictness of Stage1 realization based on food_weight(1-10)
    # Low weight: Fulfill if possible / High weight: Fulfill with top priority
    _fw_norm = (food_weight - 1) / 9.0  # 0.0 .. 1.0
    FOOD_STAGE1_VALUE_PER_DOLLAR = int(80 + 560 * _fw_norm)  # 80 .. 640
    FOOD_STAGE2_VALUE_PER_DOLLAR_BASE = 32  # Stage2は食の重みに比例

    food_stage1_value_var = model.NewIntVar(
        0,
        food_stage1_max * FOOD_STAGE1_VALUE_PER_DOLLAR,
        "food_stage1_value",
    )
    model.Add(food_stage1_value_var == food_stage1_var * FOOD_STAGE1_VALUE_PER_DOLLAR)

    food_stage2_value_var = model.NewIntVar(
        0,
        food_stage2_max * food_weight * FOOD_STAGE2_VALUE_PER_DOLLAR_BASE,
        "food_stage2_value",
    )
    model.Add(
        food_stage2_value_var
        == food_stage2_var * food_weight * FOOD_STAGE2_VALUE_PER_DOLLAR_BASE
    )

    # Fulfill Stage1 (up to requested standard) with absolute priority.
    # Allow deficiency only if restricted by budget constraint, penalizing the unfulfilled amount.
    food_stage1_deficit_var = model.NewIntVar(0, food_stage1_max, "food_stage1_deficit")
    model.Add(food_stage1_deficit_var == food_stage1_max - food_stage1_var)
    FOOD_STAGE1_DEFICIT_PENALTY = int(5000 + 95000 * _fw_norm)  # 5,000 .. 100,000
    food_stage1_deficit_penalty_var = model.NewIntVar(
        0,
        food_stage1_max * FOOD_STAGE1_DEFICIT_PENALTY,
        "food_stage1_deficit_penalty",
    )
    model.Add(
        food_stage1_deficit_penalty_var
        == food_stage1_deficit_var * FOOD_STAGE1_DEFICIT_PENALTY
    )

    # =====================================================================
    # Formulation of Diminishing Returns (Step-wise Penalty)
    # =====================================================================
    # Base penalty value. Scaled according to the overall utilities.
    DIMINISHING_PENALTY_BASE = 500 

    categories = set(item.get("category") for item in candidates)
    category_penalties = []
    
    for cat in categories:
        if cat in ("transport", "insurance"):
            continue
            
        cat_indices = [i for i, item in enumerate(candidates) if item.get("category") == cat]
        if len(cat_indices) <= 1:
            continue
            
        cat_count_var = model.NewIntVar(0, len(cat_indices), f"count_{cat}")
        model.Add(cat_count_var == sum(x[i] for i in cat_indices))
        
        diff_var = model.NewIntVar(-1, len(cat_indices), f"diff_{cat}")
        model.Add(diff_var == cat_count_var - 1)
        
        over_count_var = model.NewIntVar(0, len(cat_indices), f"over_count_{cat}")
        model.AddMaxEquality(over_count_var, [0, diff_var])
        
        cat_penalty = model.NewIntVar(0, 100000, f"penalty_{cat}")
        model.Add(cat_penalty == over_count_var * DIMINISHING_PENALTY_BASE)
        category_penalties.append(cat_penalty)
    
    total_penalty = model.NewIntVar(0, 1000000, "total_penalty")
    model.Add(total_penalty == sum(category_penalties))
    
    # =====================================================================
    # Update Objective Function: Maximize (Total Utility + Savings Value - Total Penalty)
    # =====================================================================
    model.Maximize(
        items_value
        + savings_value
        + food_stage1_value_var
        + food_stage2_value_var
        - food_stage1_deficit_penalty_var
        - total_penalty
    )

    solver = cp_model.CpSolver()
    solver.parameters.random_seed = 42 
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected       = [candidates[i] for i in range(n) if solver.Value(x[i]) == 1]
        total_initial = sum(item["initial_cost"] for item in selected)
        total_monthly = solver.Value(total_monthly_cost_var)
        actual_savings = solver.Value(actual_savings_var)
        savings_rate   = min(actual_savings / target_monthly_savings, 1.0) if target_monthly_savings > 0 else 1.0

        return {
            "status":                "ok",
            "selected":              selected,
            "total_initial_cost":    total_initial,
            "total_monthly_cost":    total_monthly,
            "food_stage1_monthly_cost": solver.Value(food_stage1_var),
            "food_stage2_monthly_cost": solver.Value(food_stage2_var),
            "food_stage1_deficit": solver.Value(food_stage1_deficit_var),
            "food_extra_monthly_cost": solver.Value(food_stage1_var + food_stage2_var),
            "actual_monthly_savings":actual_savings,
            "target_monthly_savings":target_monthly_savings,
            "savings_rate":          savings_rate,
            "savings_shortfall":     max(target_monthly_savings - actual_savings, 0),
            "total_value":           solver.ObjectiveValue(),
        }
    return _no_solution(monthly_budget, target_monthly_savings)

def _no_solution(monthly_budget: int, target_monthly_savings: int) -> dict:
    return {
        "status":                "no_solution",
        "selected":              [],
        "total_initial_cost":    0,
        "total_monthly_cost":    0,
        "actual_monthly_savings":monthly_budget,
        "target_monthly_savings":target_monthly_savings,
        "savings_rate":          1.0 if target_monthly_savings == 0 else 0.0,
        "savings_shortfall":     target_monthly_savings,
        "total_value":           0,
        "food_stage1_monthly_cost": 0,
        "food_stage2_monthly_cost": 0,
        "food_stage1_deficit": 0,
        "food_extra_monthly_cost": 0,
    }