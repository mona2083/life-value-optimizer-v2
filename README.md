# 💰 Life-Value Optimizer

> Maximize your life quality within a limited budget — powered by AI + Mathematical Optimization.

A Streamlit app that helps users make intentional spending decisions by balancing life quality, budget limits, and long-term goals. It treats each expense as an investment decision and uses optimization plus AI feedback to surface the best allocation.

---

## Live Demo

🔗 [Open App](https://life-value-optimizer-mh.streamlit.app/)

---

## What It Does

Most budgeting tools only track expenses. This app answers a harder question: **given your income, values, and lifestyle, what should you actually spend money on?**

- A bicycle is not just a cost item; it affects commute time, health, and satisfaction
- Savings compete directly with other items for priority and utility
- Food and lifestyle habits influence the optimization result through AI-assisted estimation

The optimizer finds the combination that **maximizes your total life value**, not just the lowest spend.

---

## Features

### Step 1 — Budget & Goals
- Monthly budget setup from income and fixed costs
- Household structure, age, debt, and savings target inputs

### Step 2 — Current Lifestyle
- Lifestyle and mobility questions
- Car ownership and social/leisure preferences

### Step 3 — Values & Passion
- AI-assisted value inference from survey answers and free-form passion text
- Food estimate integration and value-weight refinement

### Step 4 — AI-Recommended Items
- Review and adjust AI-proposed items
- Toggle include/skip per item before optimization

### Step 5 — Summary & Optimization
- Run OR-Tools optimization with budget and category constraints
- AI life-coach summary, savings outlook, and value fulfillment view

### Risk Cost Estimation
- Medical, housing repair, car repair, education, emergency fund
- Calculated from age, household structure, and car ownership
- Fully editable

---

## Current Categories

The optimizer currently uses 5 canonical categories:

- Transport
- Living & Dining
- Well-being
- Leisure & Play
- Growth & Learning

The default catalog contains **17 curated items** across these categories.

---

## Tech Stack

| Component | Technology |
|---|---|
| UI | `streamlit` |
| Optimization | `ortools` CP-SAT |
| LLM | OpenAI GPT-4o-mini API (`openai`) |
| Visualization | `plotly` |
| Data Processing | `pandas`, `numpy` |
| i18n | Dictionary-based (Japanese / English) |

---

## Optimization Model

For each item $i$, a binary decision variable $x_i \in \{0,1\}$ is created. The solver maximizes:

$$\text{Maximize } \sum_i x_i \cdot u_i + \text{savings value}$$

Where item utility combines value-axis weights, priority-weighted bonuses, and budget-aware trade-offs.

**Hard constraints** include budget limits, exactly one transport package when required, mandatory items, and dependency constraints.

---

## Project Structure

```
life-value-optimizer/
├── app.py
├── default_items.py
├── lang.py
├── llm.py
├── openai_handler.py
├── optimizer.py
├── risk_cost.py
├── sensitivity.py
├── requirements.txt
├── ai/
│   ├── __init__.py
│   ├── llm_client.py
│   └── profile_extractor.py
├── core/
│   ├── __init__.py
│   ├── food_calculator.py
│   └── models.py
├── state/
│   ├── __init__.py
│   └── session.py
└── ui/
    ├── __init__.py
    ├── lifestyle.py
    ├── logic.py
    ├── results.py
    ├── review.py
    ├── setup.py
    └── pages/
        ├── __init__.py
        ├── items.py
        └── summary.py
```

---

## Getting Started

### Prerequisites
- Python 3.12+
- OpenAI API key

### Installation

```bash
git clone https://github.com/mona2083/life-value-optimizer-v2.git
cd LVO2
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Create `.streamlit/secrets.toml`:

```toml
OPENAI_API_KEY = "your-api-key-here"
```

### Run

```bash
streamlit run app.py
```

---

## Security Notes

- API keys are read from `.streamlit/secrets.toml` or environment variables
- No persistent user data is stored
- OpenAI GPT-4o-mini is used for AI-generated summaries and profile inference

---

## Author

**Manami Oyama** — AI Engineer / Product Manager  
🌺 Honolulu, Hawaii  
🔗 [Portfolio](https://mona2083.github.io/portfolio-2026/index.html) | [GitHub](https://github.com/mona2083) | [LinkedIn](https://www.linkedin.com/in/manami-oyama/)
