from google.cloud import bigquery
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PROJECT_ID = "project-e6454811-8996-4412-983"

client = bigquery.Client(project=PROJECT_ID)

query = f"""
SELECT
  team,
  COUNT(*) AS n,
  ROUND(
    (SUM(CASE WHEN agent_satisfaction >= 9 THEN 1 ELSE 0 END)
     - SUM(CASE WHEN agent_satisfaction <= 6 THEN 1 ELSE 0 END))
    / COUNT(*) * 100,
    1
  ) AS enps
FROM `{PROJECT_ID}.cx_data.agents`
GROUP BY GROUPING SETS ((), (team))
"""

df = client.query(query).to_dataframe()

overall_enps = df.loc[df["team"].isna(), "enps"].iloc[0]
by_team = df.loc[df["team"].notna()].sort_values("team").reset_index(drop=True)

INK = "#0b0b0b"
SECONDARY_INK = "#52514e"
SURFACE = "#fcfcfb"
RED = "#d03b3b"
RED_BG = "#fbe4e4"
GOOD = "#0ca30c"
NEUTRAL_BG = "#f0efec"


def value_color(v):
    return RED if v < 0 else GOOD


fig = make_subplots(
    rows=1,
    cols=4,
    column_widths=[0.46, 0.18, 0.18, 0.18],
    specs=[[{"type": "indicator"}] * 4],
    horizontal_spacing=0.06,
)

fig.add_trace(
    go.Indicator(
        mode="gauge+number",
        value=overall_enps,
        number={"font": {"size": 44, "color": value_color(overall_enps)}},
        title={"text": "전체 eNPS", "font": {"size": 18, "color": INK}},
        gauge={
            "axis": {"range": [-100, 100], "tickcolor": SECONDARY_INK, "tickfont": {"color": SECONDARY_INK}},
            "bar": {"color": value_color(overall_enps), "thickness": 0.3},
            "bgcolor": SURFACE,
            "borderwidth": 0,
            "steps": [
                {"range": [-100, 0], "color": RED_BG},
                {"range": [0, 100], "color": NEUTRAL_BG},
            ],
            "threshold": {"line": {"color": INK, "width": 2}, "thickness": 0.75, "value": 0},
        },
    ),
    row=1,
    col=1,
)

for i, row in by_team.iterrows():
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=row["enps"],
            number={"font": {"size": 34, "color": value_color(row["enps"])}},
            title={
                "text": (
                    f"{row['team']} eNPS<br>"
                    f"<span style='font-size:12px;color:{SECONDARY_INK}'>응답 {int(row['n'])}명</span>"
                ),
                "font": {"size": 15, "color": INK},
            },
        ),
        row=1,
        col=2 + i,
    )

fig.update_layout(
    title=dict(text="직원 만족도 스코어카드 (eNPS)", x=0.5),
    paper_bgcolor=SURFACE,
    font=dict(family="Malgun Gothic, sans-serif", color=INK),
    height=380,
    margin=dict(t=90, b=30, l=30, r=30),
)

fig.show()
