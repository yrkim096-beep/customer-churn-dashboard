import os

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

satisfaction = pd.read_csv(os.path.join(DATA_DIR, "data_satisfaction.csv"), encoding="utf-8-sig")
consultations = pd.read_csv(os.path.join(DATA_DIR, "data_consultations.csv"), encoding="utf-8-sig")

merged = satisfaction.merge(
    consultations[["consult_id", "channel", "is_recontact"]],
    on="consult_id",
    how="inner",
)

summary = (
    merged.groupby("channel")
    .agg(
        csat_avg=("csat", "mean"),
        recontact_rate=("is_recontact", lambda s: (s == "Y").mean() * 100),
        건수=("consult_id", "count"),
    )
    .reset_index()
    .sort_values("csat_avg", ascending=True)
)

fig = make_subplots(specs=[[{"secondary_y": True}]])

fig.add_trace(
    go.Bar(
        x=summary["channel"],
        y=summary["csat_avg"],
        name="CSAT 평균",
        marker_color="#2a78d6",
        customdata=summary[["recontact_rate", "건수"]],
        hovertemplate=(
            "<b>%{x}</b><br>"
            "CSAT 평균: %{y:.2f}<br>"
            "재문의율: %{customdata[0]:.1f}%<br>"
            "상담 건수: %{customdata[1]}건<extra></extra>"
        ),
    ),
    secondary_y=False,
)

fig.add_trace(
    go.Scatter(
        x=summary["channel"],
        y=summary["recontact_rate"],
        name="재문의율",
        mode="lines+markers",
        line=dict(color="#d03b3b", width=2),
        marker=dict(size=8, color="#d03b3b"),
        customdata=summary[["csat_avg", "건수"]],
        hovertemplate=(
            "<b>%{x}</b><br>"
            "재문의율: %{y:.1f}%<br>"
            "CSAT 평균: %{customdata[0]:.2f}<br>"
            "상담 건수: %{customdata[1]}건<extra></extra>"
        ),
    ),
    secondary_y=True,
)

fig.update_layout(
    title=dict(text="채널별 CSAT 평균 vs 재문의율 (CSAT 낮은 순)", x=0.5),
    plot_bgcolor="#fcfcfb",
    paper_bgcolor="#fcfcfb",
    font=dict(family="Malgun Gothic, sans-serif", color="#0b0b0b"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    hovermode="x unified",
)
fig.update_xaxes(title_text="", showgrid=False)
fig.update_yaxes(
    title_text="CSAT 평균 (1~5)",
    secondary_y=False,
    gridcolor="#e1e0d9",
    zerolinecolor="#c3c2b7",
)
fig.update_yaxes(
    title_text="재문의율 (%)",
    secondary_y=True,
    showgrid=False,
)

fig.show()
