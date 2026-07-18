import os

import pandas as pd
import plotly.express as px

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

customers = pd.read_csv(os.path.join(DATA_DIR, "data_customers.csv"), encoding="utf-8-sig")

summary = (
    customers.groupby("region")
    .agg(고객수=("customer_id", "count"), 이탈수=("churn_yn", lambda s: (s == "Y").sum()))
    .reset_index()
    .sort_values("이탈수", ascending=False)
)
summary["이탈율"] = summary["이탈수"] / summary["고객수"] * 100

highlight_regions = {"부산", "대구"}
color_map = {
    region: ("#d03b3b" if region in highlight_regions else "#9e9d97") for region in summary["region"]
}

fig = px.bar(
    summary,
    x="region",
    y="이탈율",
    color="region",
    color_discrete_map=color_map,
    custom_data=["고객수", "이탈수"],
    title="지역별 이탈율",
    labels={"region": "", "이탈율": "이탈율 (%)"},
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

incheon = summary[summary["region"] == "인천"].iloc[0]
caption = (
    f"* 인천은 표본이 {int(incheon['고객수'])}건이지만 이탈은 {int(incheon['이탈수'])}건뿐이라 "
    "이탈율이 낮게 보일 수 있음 (해석 주의)"
)

fig.update_layout(
    showlegend=False,
    plot_bgcolor="#fcfcfb",
    paper_bgcolor="#fcfcfb",
    font=dict(family="Malgun Gothic, sans-serif", color="#0b0b0b"),
    title_x=0.5,
    margin=dict(b=120),
    annotations=[
        dict(
            text=caption,
            xref="paper",
            yref="paper",
            x=0,
            y=-0.18,
            showarrow=False,
            font=dict(size=12, color="#52514e"),
            align="left",
        )
    ],
)
fig.update_xaxes(showgrid=False)
fig.update_yaxes(gridcolor="#e1e0d9", zerolinecolor="#c3c2b7", rangemode="tozero")

fig.show()
