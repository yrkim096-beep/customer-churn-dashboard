from google.cloud import bigquery
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PROJECT_ID = "project-e6454811-8996-4412-983"

client = bigquery.Client(project=PROJECT_ID)

query = f"""
WITH csat_by_training AS (
  SELECT a.training_completed_yn, AVG(s.csat) AS csat_avg
  FROM `{PROJECT_ID}.cx_data.agents` a
  JOIN `{PROJECT_ID}.cx_data.consultations` c ON a.agent_id = c.agent_id
  JOIN `{PROJECT_ID}.cx_data.satisfaction` s ON c.consult_id = s.consult_id
  GROUP BY a.training_completed_yn
),
recontact_by_training AS (
  SELECT
    a.training_completed_yn,
    SUM(CASE WHEN c.is_recontact THEN 1 ELSE 0 END) / COUNT(*) * 100 AS recontact_rate
  FROM `{PROJECT_ID}.cx_data.agents` a
  JOIN `{PROJECT_ID}.cx_data.consultations` c ON a.agent_id = c.agent_id
  GROUP BY a.training_completed_yn
)
SELECT c.training_completed_yn, c.csat_avg, r.recontact_rate
FROM csat_by_training c
JOIN recontact_by_training r USING (training_completed_yn)
"""

df = client.query(query).to_dataframe()
df["group"] = df["training_completed_yn"].map({True: "Y (이수)", False: "N (미이수)"})
df = df.sort_values("training_completed_yn", ascending=False).reset_index(drop=True)

HIGHLIGHT = "#d03b3b"
NEUTRAL = "#9e9d97"
colors = [HIGHLIGHT, NEUTRAL]

fig = make_subplots(rows=1, cols=2, subplot_titles=["CSAT 평균", "재문의율 평균"])

fig.add_trace(
    go.Bar(
        x=df["group"],
        y=df["csat_avg"],
        marker_color=colors,
        text=[f"{v:.2f}" for v in df["csat_avg"]],
        textposition="outside",
        showlegend=False,
        width=0.5,
    ),
    row=1,
    col=1,
)

fig.add_trace(
    go.Bar(
        x=df["group"],
        y=df["recontact_rate"],
        marker_color=colors,
        text=[f"{v:.1f}%" for v in df["recontact_rate"]],
        textposition="outside",
        showlegend=False,
        width=0.5,
    ),
    row=1,
    col=2,
)

fig.update_layout(
    title=dict(text="교육 이수 여부에 따른 CSAT 평균 · 재문의율 비교", x=0.5),
    plot_bgcolor="#fcfcfb",
    paper_bgcolor="#fcfcfb",
    font=dict(family="Malgun Gothic, sans-serif", color="#0b0b0b"),
)
fig.update_xaxes(showgrid=False)
fig.update_yaxes(
    gridcolor="#e1e0d9",
    zerolinecolor="#c3c2b7",
    rangemode="tozero",
    range=[0, df["csat_avg"].max() * 1.15],
    title="CSAT 평균",
    row=1,
    col=1,
)
fig.update_yaxes(
    gridcolor="#e1e0d9",
    zerolinecolor="#c3c2b7",
    rangemode="tozero",
    range=[0, df["recontact_rate"].max() * 1.15],
    title="재문의율 (%)",
    row=1,
    col=2,
)

fig.show()
