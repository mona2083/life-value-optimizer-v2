# sensitivity.py
import numpy as np
import plotly.graph_objects as go
from optimizer import run_optimizer


def run_sensitivity(
    items: list[dict],
    monthly_budget: int,
    total_budget: int,
    target_monthly_savings: int,
    weights: dict,
    steps: int = 20,
) -> dict:
    """
    月次予算・初期費用上限を変化させて合計バリューの推移を収集する
    ヒートマップ廃止のためアイテム選択追跡は不要
    """
    monthly_range = np.linspace(
        monthly_budget * 0.5, monthly_budget * 2.0, steps
    ).astype(int)
    initial_range = np.linspace(
        total_budget * 0.5, total_budget * 2.0, steps
    ).astype(int)

    monthly_values = []
    for mb in monthly_range:
        result = run_optimizer(
            items, total_budget, int(mb), target_monthly_savings, weights
        )
        monthly_values.append(result["total_value"])

    initial_values = []
    for ib in initial_range:
        result = run_optimizer(
            items, int(ib), monthly_budget, target_monthly_savings, weights
        )
        initial_values.append(result["total_value"])

    return {
        "monthly_range":  monthly_range,
        "monthly_values": monthly_values,
        "initial_range":  initial_range,
        "initial_values": initial_values,
    }


def make_line_chart(
    x_values, y_values, current_x: int,
    x_label: str, y_label: str, title: str
):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_values, y=y_values,
        mode="lines+markers",
        line=dict(color="#4F8EF7", width=2),
    ))
    fig.add_vline(
        x=current_x,
        line_dash="dash",
        line_color="orange",
        annotation_text=f"Current: ${current_x:,}",
        annotation_position="top right",
    )
    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis_title=y_label,
        height=350,
        margin=dict(t=50, b=40),
    )
    return fig