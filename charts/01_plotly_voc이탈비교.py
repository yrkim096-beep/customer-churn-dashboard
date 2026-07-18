import os

import pandas as pd
import plotly.express as px

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

voc = pd.read_csv(os.path.join(DATA_DIR, "data_voc.csv"), encoding="utf-8-sig")
customers = pd.read_csv(os.path.join(DATA_DIR, "data_customers.csv"), encoding="utf-8-sig")

target_voc = voc[(voc["category"] == "해지관련") & (voc["sentiment"] == "부정")]
target_customer_ids = target_voc["customer_id"].unique()
target_customers = customers[customers["customer_id"].isin(target_customer_ids)]

overall_total = len(customers)
overall_churned = (customers["churn_yn"] == "Y").sum()
overall_rate = overall_churned / overall_total * 100

target_total = len(target_customers)
target_churned = (target_customers["churn_yn"] == "Y").sum()
target_rate = target_churned / target_total * 100 if target_total > 0 else 0

df = pd.DataFrame(
    {
        "group": ["전체 고객", "해지관련 부정 VOC 이력 있음"],
        "이탈율": [overall_rate, target_rate],
        "고객수": [overall_total, target_total],
        "이탈고객수": [overall_churned, target_churned],
    }
)

color_map = {
    "전체 고객": "#9e9d97",
    "해지관련 부정 VOC 이력 있음": "#d03b3b",
}

fig = px.bar(
    df,
    x="group",
    y="이탈율",
    color="group",
    color_discrete_map=color_map,
    custom_data=["고객수", "이탈고객수"],
    title="전체 고객 vs 해지관련 부정 VOC 고객 이탈율 비교",
    labels={"group": "", "이탈율": "이탈율 (%)"},
)

fig.update_traces(
    hovertemplate=(
        "<b>%{x}</b><br>"
        "고객 수: %{customdata[0]}명<br>"
        "이탈 고객 수: %{customdata[1]}명<br>"
        "이탈율: %{y:.1f}%<extra></extra>"
    ),
    width=0.5,
)

fig.update_layout(
    showlegend=False,
    yaxis_range=[0, df["이탈율"].max() * 1.3],
    plot_bgcolor="#fcfcfb",
    paper_bgcolor="#fcfcfb",
    font=dict(family="Malgun Gothic, sans-serif", color="#0b0b0b"),
    title_x=0.5,
)
fig.update_yaxes(gridcolor="#e1e0d9", zerolinecolor="#c3c2b7")
fig.update_xaxes(showgrid=False)

fig.show()
