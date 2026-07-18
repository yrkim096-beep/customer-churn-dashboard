import os

import pandas as pd
import plotly.express as px

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

customers = pd.read_csv(os.path.join(DATA_DIR, "data_customers.csv"), encoding="utf-8-sig")
usage = pd.read_csv(os.path.join(DATA_DIR, "data_usage_history.csv"), encoding="utf-8-sig")

REFERENCE_DATE = pd.Timestamp("2024-12-31")
join_date = pd.to_datetime(customers["join_date"])

months_diff = (REFERENCE_DATE.year - join_date.dt.year) * 12 + (REFERENCE_DATE.month - join_date.dt.month)
day_adjustment = (REFERENCE_DATE.day < join_date.dt.day).astype(int)
customers["tenure_months"] = months_diff - day_adjustment

avg_usage = usage.groupby("customer_id")["data_gb"].mean().rename("avg_data_gb")

merged = customers.merge(avg_usage, on="customer_id", how="inner")

fig = px.scatter(
    merged,
    x="tenure_months",
    y="avg_data_gb",
    color="churn_yn",
    color_discrete_map={"N": "#2a78d6", "Y": "#d03b3b"},
    custom_data=["customer_id", "tenure_months", "avg_data_gb", "churn_yn"],
    title="가입기간 vs 평균 데이터 사용량 (이탈 여부별)",
    labels={"tenure_months": "가입기간 (개월)", "avg_data_gb": "평균 데이터 사용량 (GB)", "churn_yn": "이탈 여부"},
)

fig.update_traces(
    marker=dict(size=8, opacity=0.75, line=dict(width=0.5, color="#fcfcfb")),
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        "가입기간: %{customdata[1]}개월<br>"
        "평균 데이터 사용량: %{customdata[2]:.1f}GB<br>"
        "이탈 여부: %{customdata[3]}<extra></extra>"
    ),
)

fig.update_layout(
    plot_bgcolor="#fcfcfb",
    paper_bgcolor="#fcfcfb",
    font=dict(family="Malgun Gothic, sans-serif", color="#0b0b0b"),
    title_x=0.5,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
)
fig.update_xaxes(gridcolor="#e1e0d9", zerolinecolor="#c3c2b7")
fig.update_yaxes(gridcolor="#e1e0d9", zerolinecolor="#c3c2b7")

fig.show()
