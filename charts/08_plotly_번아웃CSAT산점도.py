from google.cloud import bigquery
import plotly.express as px

PROJECT_ID = "project-e6454811-8996-4412-983"

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

df = client.query(query).to_dataframe()

r = df["overtime_hours_avg"].corr(df["csat_avg"])

fig = px.scatter(
    df,
    x="overtime_hours_avg",
    y="csat_avg",
    trendline="ols",
    custom_data=["agent_id", "overtime_hours_avg", "csat_avg"],
    title="초과근무 시간 vs 상담원별 CSAT 평균",
    labels={"overtime_hours_avg": "평균 초과근무 시간 (시간)", "csat_avg": "CSAT 평균"},
)

fig.update_traces(
    marker=dict(size=10, color="#2a78d6", opacity=0.8, line=dict(width=0.5, color="#fcfcfb")),
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        "초과근무 시간: %{customdata[1]}시간<br>"
        "CSAT 평균: %{customdata[2]:.2f}<extra></extra>"
    ),
    selector=dict(mode="markers"),
)

fig.update_traces(
    line=dict(color="#52514e", width=2),
    selector=dict(mode="lines"),
)

fig.add_annotation(
    xref="paper",
    yref="paper",
    x=0.99,
    y=0.97,
    xanchor="right",
    yanchor="top",
    text=f"r = {r:.2f}",
    showarrow=False,
    align="right",
    font=dict(size=16, color="#0b0b0b"),
    bgcolor="rgba(252, 252, 251, 0.9)",
    bordercolor="#c3c2b7",
    borderwidth=1,
    borderpad=6,
)

fig.update_layout(
    showlegend=False,
    plot_bgcolor="#fcfcfb",
    paper_bgcolor="#fcfcfb",
    font=dict(family="Malgun Gothic, sans-serif", color="#0b0b0b"),
    title_x=0.5,
)
fig.update_xaxes(gridcolor="#e1e0d9", zerolinecolor="#c3c2b7")
fig.update_yaxes(gridcolor="#e1e0d9", zerolinecolor="#c3c2b7")

fig.show()
