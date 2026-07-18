import os

import pandas as pd
import plotly.graph_objects as go

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

consultations = pd.read_csv(os.path.join(DATA_DIR, "data_consultations.csv"), encoding="utf-8-sig")
customers = pd.read_csv(os.path.join(DATA_DIR, "data_customers.csv"), encoding="utf-8-sig")

recontact_count = (
    consultations[consultations["is_recontact"] == "Y"]
    .groupby("customer_id")
    .size()
    .rename("recontact_count")
)

merged = customers.merge(recontact_count, on="customer_id", how="left")
merged["recontact_count"] = merged["recontact_count"].fillna(0).astype(int)


def bucket(n):
    if n == 0:
        return "0회"
    if n == 1:
        return "1회"
    return "2회 이상"


merged["recontact_bucket"] = merged["recontact_count"].apply(bucket)

bucket_order = ["0회", "1회", "2회 이상"]
summary = (
    merged.groupby("recontact_bucket")
    .agg(고객수=("customer_id", "count"), 이탈수=("churn_yn", lambda s: (s == "Y").sum()))
    .reindex(bucket_order)
    .reset_index()
)
summary["이탈율"] = summary["이탈수"] / summary["고객수"] * 100

overall_total = len(customers)
overall_churned = (customers["churn_yn"] == "Y").sum()
overall_rate = overall_churned / overall_total * 100

colors = ["#9e9d97", "#9e9d97", "#d03b3b"]

fig = go.Figure()

fig.add_trace(
    go.Bar(
        x=summary["recontact_bucket"],
        y=summary["이탈율"],
        marker_color=colors,
        customdata=summary[["고객수", "이탈수"]],
        hovertemplate=(
            "<b>%{x}</b><br>"
            "이탈율: %{y:.1f}%<br>"
            "고객 수: %{customdata[0]}명<br>"
            "이탈 고객 수: %{customdata[1]}명<extra></extra>"
        ),
        showlegend=False,
    )
)

fig.add_hline(
    y=overall_rate,
    line_dash="dash",
    line_color="#52514e",
    annotation_text=f"전체 평균 이탈율 {overall_rate:.1f}%",
    annotation_position="top left",
)

fig.update_layout(
    title=dict(text="재문의 횟수 구간별 이탈율", x=0.5),
    plot_bgcolor="#fcfcfb",
    paper_bgcolor="#fcfcfb",
    font=dict(family="Malgun Gothic, sans-serif", color="#0b0b0b"),
    yaxis_title="이탈율 (%)",
    xaxis_title="",
)
fig.update_xaxes(showgrid=False, categoryorder="array", categoryarray=bucket_order)
fig.update_yaxes(gridcolor="#e1e0d9", zerolinecolor="#c3c2b7", rangemode="tozero")

fig.show()
