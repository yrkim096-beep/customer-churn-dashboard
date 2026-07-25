import numpy as np
import plotly.express as px
from google.cloud import bigquery
from plotly.subplots import make_subplots

PROJECT_ID = "project-e6454811-8996-4412-983"
OUTLIER_IDS = ["AG16", "AG20"]

client = bigquery.Client(project=PROJECT_ID)

query = f"""
SELECT
  a.agent_id,
  a.overtime_hours_avg,
  AVG(s.csat) AS csat_avg
FROM `{PROJECT_ID}.cx_data.agents` a
JOIN `{PROJECT_ID}.cx_data.consultations` c ON a.agent_id = c.agent_id
JOIN `{PROJECT_ID}.cx_data.satisfaction` s ON c.consult_id = s.consult_id
GROUP BY a.agent_id, a.overtime_hours_avg
"""

df_all = client.query(query).to_dataframe()
df_excl = df_all[~df_all["agent_id"].isin(OUTLIER_IDS)].reset_index(drop=True)


def fit_stats(data):
    r = data["overtime_hours_avg"].corr(data["csat_avg"])
    slope, intercept = np.polyfit(data["overtime_hours_avg"], data["csat_avg"], 1)
    return r, slope, intercept


r_all, slope_all, _ = fit_stats(df_all)
r_excl, slope_excl, _ = fit_stats(df_excl)

x_pad = (df_all["overtime_hours_avg"].max() - df_all["overtime_hours_avg"].min()) * 0.08
y_pad = (df_all["csat_avg"].max() - df_all["csat_avg"].min()) * 0.08
x_range = [df_all["overtime_hours_avg"].min() - x_pad, df_all["overtime_hours_avg"].max() + x_pad]
y_range = [df_all["csat_avg"].min() - y_pad, df_all["csat_avg"].max() + y_pad]

fig = make_subplots(
    rows=1,
    cols=2,
    subplot_titles=[
        f"전체 포함 (n={len(df_all)})",
        f"AG16·AG20 제외 (n={len(df_excl)})",
    ],
    horizontal_spacing=0.08,
)

panels = [
    (df_all, 1, r_all, slope_all),
    (df_excl, 2, r_excl, slope_excl),
]

for data, col, r, slope in panels:
    panel_fig = px.scatter(
        data,
        x="overtime_hours_avg",
        y="csat_avg",
        trendline="ols",
        custom_data=["agent_id", "overtime_hours_avg", "csat_avg"],
    )
    marker_colors = ["#d03b3b" if aid in OUTLIER_IDS else "#2a78d6" for aid in data["agent_id"]]

    for trace in panel_fig.data:
        if trace.mode == "markers":
            trace.marker = dict(size=10, color=marker_colors, opacity=0.85, line=dict(width=0.5, color="#fcfcfb"))
            trace.hovertemplate = (
                "<b>%{customdata[0]}</b><br>"
                "초과근무 시간: %{customdata[1]}시간<br>"
                "CSAT 평균: %{customdata[2]:.2f}<extra></extra>"
            )
        else:
            trace.line = dict(color="#52514e", width=2)
        trace.showlegend = False
        fig.add_trace(trace, row=1, col=col)

    fig.add_annotation(
        row=1,
        col=col,
        xref="x domain",
        yref="y domain",
        x=0.98,
        y=0.05,
        xanchor="right",
        yanchor="bottom",
        text=f"r = {r:.3f}<br>기울기 = {slope:.4f}",
        showarrow=False,
        align="right",
        font=dict(size=14, color="#0b0b0b"),
        bgcolor="rgba(252, 252, 251, 0.9)",
        bordercolor="#c3c2b7",
        borderwidth=1,
        borderpad=6,
    )

fig.update_xaxes(range=x_range, gridcolor="#e1e0d9", zerolinecolor="#c3c2b7", title="평균 초과근무 시간 (시간)")
fig.update_yaxes(range=y_range, gridcolor="#e1e0d9", zerolinecolor="#c3c2b7", title="CSAT 평균", col=1)
fig.update_yaxes(range=y_range, gridcolor="#e1e0d9", zerolinecolor="#c3c2b7", col=2)

fig.update_layout(
    showlegend=False,
    plot_bgcolor="#fcfcfb",
    paper_bgcolor="#fcfcfb",
    font=dict(family="Malgun Gothic, sans-serif", color="#0b0b0b"),
    title=dict(text="초과근무-CSAT 상관관계: 이상치(AG16·AG20) 포함/제외 비교", x=0.5),
    margin=dict(t=110),
)

fig.show()
