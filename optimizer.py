from ortools.sat.python import cp_model

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
    # 【修正】すべてのスコアに +10 を加算し、マイナス効用による無条件除外バグを防止
    return (
        weights["health"]      * (int(item["health"]) + 10)      * 100 +
        weights["connections"] * (int(item["connections"]) + 10) * 100 +
        weights["freedom"]     * (int(item["freedom"]) + 10)     * 100 +
        weights["growth"]      * (int(item["growth"]) + 10)      * 100
    )

def run_optimizer(
    items: list[dict],
    total_budget: int,
    monthly_budget: int,
    target_monthly_savings: int,
    weights: dict,
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
    model.Add(sum(x[i] * candidates[i]["monthly_cost"]  for i in range(n)) <= monthly_budget)

    transport_idx = [i for i, item in enumerate(candidates) if item.get("category") == "transport"]
    if transport_idx:
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
    model.Add(total_monthly_cost_var == sum(x[i] * candidates[i]["monthly_cost"] for i in range(n)))
    actual_savings_var = model.NewIntVar(0, monthly_budget, "actual_savings")
    model.Add(actual_savings_var == monthly_budget - total_monthly_cost_var)

    total_max_utility = sum(utilities)
    
    # 【修正】割り算をfloatで行い、重みが0より大きければ必ず係数が1以上になるように安全措置を追加
    _raw_savings_coefficient = (total_max_utility * weights["savings"]) / (10 * max(monthly_budget, 1))
    savings_coefficient = max(1 if weights["savings"] > 0 else 0, int(_raw_savings_coefficient))
    
    savings_value = model.NewIntVar(0, int(monthly_budget * savings_coefficient) + 1, "savings_value")
    model.Add(savings_value == actual_savings_var * savings_coefficient)

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
    model.Maximize(items_value + savings_value - total_penalty)

    solver = cp_model.CpSolver()
    solver.parameters.random_seed = 42 
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        selected       = [candidates[i] for i in range(n) if solver.Value(x[i]) == 1]
        total_initial  = sum(item["initial_cost"] for item in selected)
        total_monthly  = sum(item["monthly_cost"]  for item in selected)
        actual_savings = monthly_budget - total_monthly
        savings_rate   = min(actual_savings / target_monthly_savings, 1.0) if target_monthly_savings > 0 else 1.0

        return {
            "status":                "ok",
            "selected":              selected,
            "total_initial_cost":    total_initial,
            "total_monthly_cost":    total_monthly,
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
    }