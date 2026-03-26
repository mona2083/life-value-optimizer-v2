# 💰 Life-Value Optimizer

> Maximize your life quality within a limited budget — powered by AI + Mathematical Optimization.

A Streamlit app that finds the optimal combination of lifestyle spending — gym, travel fund, bicycle, subscriptions, and more — within your real monthly budget. Unlike a simple budget tracker, this app treats every expense as an **investment decision** and mathematically proves the best allocation.

---

## Live Demo

🔗 [Open App](https://life-value-optimizer-mh.streamlit.app/)

---

## The Problem It Solves

Most budgeting tools just track spending. This app answers a harder question: **given your income, goals, and values — what should you actually spend money on?**

- A bicycle isn't just "$500" — it saves commute time, builds health, and brings satisfaction
- Savings aren't just "leftover money" — they compete directly with other items for priority
- Your lifestyle habits (diet, exercise) affect the health scores of every item you select

The optimizer finds the combination that **maximizes your total life value**, not just minimizes spending.

---

## Features

### Step 1 — Profile & Fixed Costs
- Monthly income → auto-calculates disposable income after fixed costs (rent, utilities, groceries, insurance)
- Household structure, age, and lifestyle inputs

### Step 2 — Goals & Value Weights
- Savings goal (e.g. "$5,000 in 2 years" → $208/month target)
- Four value axes: Time Saving / Health / Satisfaction / Savings (1–10 sliders)
- Presets: 今を豊かに生きる / 将来に備える / 健康に長生きする / 自己成長・キャリア / Custom

### Step 3 — Item Selection
- 50+ items across 9 categories with editable costs and priority scores
- Transport as **packages** — mutually exclusive (Car / E-Bike+Uber / Bicycle Only / etc.)
- Mandatory checkbox to force-include any item
- **AI auto-fill**: type any item name → Gemini suggests costs and scores automatically

### Results
- AI-generated summary in natural language (Gemini)
- Selected items grouped by category with total cost breakdown
- Savings rate vs. savings goal
- Top 5 next-best unselected items
- Budget sensitivity analysis — how total value changes as budget increases

### Risk Cost Estimation
- Medical, housing repair, car repair, education, emergency fund
- Calculated from age, household structure, and car ownership
- Fully editable

---

## Tech Stack

| Component | Technology |
|---|---|
| UI | `streamlit` |
| Optimization | `ortools` CP-SAT (Google OR-Tools) |
| LLM | Google Gemini 2.5 Flash Lite API (`google-genai`) |
| Visualization | `plotly` |
| i18n | Custom dictionary-based (Japanese / English) |

---

## The Optimization Model

For each item $i$, a binary decision variable $x_i \in \{0,1\}$ is created. The solver maximizes:

$$\text{Maximize} \sum_i x_i \cdot u_i + \text{savings\_value}$$

Where item utility combines four value axes with priority-weighted bonuses, and savings utility competes directly with items — making the trade-off between spending and saving mathematically explicit.

**Hard constraints** include budget limits (one-time + monthly), exactly one transport package, and dependency constraints (pet insurance requires pet, car insurance requires car).

---

## Project Structure

```
life-value-optimizer/
├── app.py              # Streamlit UI + session state management
├── optimizer.py        # OR-Tools CP-SAT model (utility theory)
├── sensitivity.py      # What-if analysis (budget sensitivity)
├── llm.py              # Gemini API (item auto-fill + summary)
├── lang.py             # Bilingual text dictionary (ja/en)
├── default_items.py    # 50+ items across 9 categories
├── lifestyle.py        # Lifestyle-based score adjustments
├── risk_cost.py        # Future risk cost estimation
├── requirements.txt
└── .streamlit/
    └── secrets.toml    # GEMINI_API_KEY (not committed)
```

---

## Getting Started

### Prerequisites
- Python 3.12+
- Gemini API key ([Get one free](https://aistudio.google.com/app/apikey))

### Installation

```bash
git clone https://github.com/mona2083/life-value-optimizer.git
cd life-value-optimizer
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

Create `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "your-api-key-here"
```

### Run

```bash
streamlit run app.py
```

---

## Security Notes

- API keys are stored in `.streamlit/secrets.toml` (gitignored — never committed)
- No user data is persisted (session-only)
- Gemini free tier: 1,500 requests/day — sufficient for demo use

---

## Author

**Manami Oyama** — AI Engineer / Product Manager  
🌺 Honolulu, Hawaii  
🔗 [Portfolio](https://mona2083.github.io/portfolio-2026/index.html) | [GitHub](https://github.com/mona2083) | [LinkedIn](https://www.linkedin.com/in/manami-oyama/)
