import os

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account
from plotly.subplots import make_subplots

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

PLOT_BGCOLOR = "#fcfcfb"
GRID_COLOR = "#e1e0d9"
AXIS_COLOR = "#c3c2b7"
GRAY = "#9e9d97"
RED = "#d03b3b"
BLUE = "#2a78d6"
FONT = dict(family="Malgun Gothic, sans-serif", color="#0b0b0b")

PROJECT_ID = "project-e6454811-8996-4412-983"
OUTLIER_AGENT_IDS = ["AG16", "AG20"]
RED_BG = "#fbe4e4"
NEUTRAL_BG = "#f0efec"
GOOD = "#0ca30c"
SECONDARY_INK = "#52514e"


@st.cache_data
def load_data():
    return {
        "customers": pd.read_csv(os.path.join(DATA_DIR, "data_customers.csv"), encoding="utf-8-sig"),
        "voc": pd.read_csv(os.path.join(DATA_DIR, "data_voc.csv"), encoding="utf-8-sig"),
        "consultations": pd.read_csv(os.path.join(DATA_DIR, "data_consultations.csv"), encoding="utf-8-sig"),
        "satisfaction": pd.read_csv(os.path.join(DATA_DIR, "data_satisfaction.csv"), encoding="utf-8-sig"),
        "usage": pd.read_csv(os.path.join(DATA_DIR, "data_usage_history.csv"), encoding="utf-8-sig"),
    }


@st.cache_data
def load_agents():
    if "gcp_service_account" in st.secrets:
        credentials = service_account.Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"])
        )
        client = bigquery.Client(project=PROJECT_ID, credentials=credentials)
    else:
        client = bigquery.Client(project=PROJECT_ID)

    query = f"""
    SELECT agent_id, team, overtime_hours_avg, training_completed_yn, agent_satisfaction
    FROM `{PROJECT_ID}.cx_data.agents`
    """
    return client.query(query).to_dataframe()


@st.cache_data
def load_report():
    report_path = os.path.join(BASE_DIR, "report", "고객서비스_만족도개선_리포트.md")
    with open(report_path, encoding="utf-8") as f:
        return f.read()


def build_voc_chart(customers, voc):
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
        "전체 고객": GRAY,
        "해지관련 부정 VOC 이력 있음": RED,
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
        plot_bgcolor=PLOT_BGCOLOR,
        paper_bgcolor=PLOT_BGCOLOR,
        font=FONT,
        title_x=0.5,
    )
    fig.update_yaxes(gridcolor=GRID_COLOR, zerolinecolor=AXIS_COLOR)
    fig.update_xaxes(showgrid=False)
    return fig


def build_channel_csat_chart(satisfaction, consultations):
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
            marker_color=BLUE,
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
            line=dict(color=RED, width=2),
            marker=dict(size=8, color=RED),
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
        plot_bgcolor=PLOT_BGCOLOR,
        paper_bgcolor=PLOT_BGCOLOR,
        font=FONT,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        hovermode="x unified",
    )
    fig.update_xaxes(title_text="", showgrid=False)
    fig.update_yaxes(title_text="CSAT 평균 (1~5)", secondary_y=False, gridcolor=GRID_COLOR, zerolinecolor=AXIS_COLOR)
    fig.update_yaxes(title_text="재문의율 (%)", secondary_y=True, showgrid=False)
    return fig


def build_recontact_bucket_chart(consultations, customers):
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

    colors = [GRAY, GRAY, RED]

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
        plot_bgcolor=PLOT_BGCOLOR,
        paper_bgcolor=PLOT_BGCOLOR,
        font=FONT,
        yaxis_title="이탈율 (%)",
        xaxis_title="",
    )
    fig.update_xaxes(showgrid=False, categoryorder="array", categoryarray=bucket_order)
    fig.update_yaxes(gridcolor=GRID_COLOR, zerolinecolor=AXIS_COLOR, rangemode="tozero")
    return fig


def build_plan_chart(customers):
    summary = (
        customers.groupby("plan")
        .agg(고객수=("customer_id", "count"), 이탈수=("churn_yn", lambda s: (s == "Y").sum()))
        .reset_index()
        .sort_values("이탈수", ascending=False)
    )
    summary["이탈율"] = summary["이탈수"] / summary["고객수"] * 100

    highlight_plan = "베이직"
    color_map = {plan: (RED if plan == highlight_plan else GRAY) for plan in summary["plan"]}

    fig = px.bar(
        summary,
        x="plan",
        y="이탈율",
        color="plan",
        color_discrete_map=color_map,
        custom_data=["고객수", "이탈수"],
        title="요금제별 이탈율",
        labels={"plan": "", "이탈율": "이탈율 (%)"},
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
        plot_bgcolor=PLOT_BGCOLOR,
        paper_bgcolor=PLOT_BGCOLOR,
        font=FONT,
        title_x=0.5,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor=GRID_COLOR, zerolinecolor=AXIS_COLOR, rangemode="tozero")
    return fig


def build_region_chart(customers):
    summary = (
        customers.groupby("region")
        .agg(고객수=("customer_id", "count"), 이탈수=("churn_yn", lambda s: (s == "Y").sum()))
        .reset_index()
        .sort_values("이탈수", ascending=False)
    )
    summary["이탈율"] = summary["이탈수"] / summary["고객수"] * 100

    highlight_regions = {"부산", "대구"}
    color_map = {
        region: (RED if region in highlight_regions else GRAY) for region in summary["region"]
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
        plot_bgcolor=PLOT_BGCOLOR,
        paper_bgcolor=PLOT_BGCOLOR,
        font=FONT,
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
    fig.update_yaxes(gridcolor=GRID_COLOR, zerolinecolor=AXIS_COLOR, rangemode="tozero")
    return fig


def build_tenure_usage_chart(customers, usage):
    customers = customers.copy()
    reference_date = pd.Timestamp("2024-12-31")
    join_date = pd.to_datetime(customers["join_date"])

    months_diff = (reference_date.year - join_date.dt.year) * 12 + (reference_date.month - join_date.dt.month)
    day_adjustment = (reference_date.day < join_date.dt.day).astype(int)
    customers["tenure_months"] = months_diff - day_adjustment

    avg_usage = usage.groupby("customer_id")["data_gb"].mean().rename("avg_data_gb")
    merged = customers.merge(avg_usage, on="customer_id", how="inner")

    fig = px.scatter(
        merged,
        x="tenure_months",
        y="avg_data_gb",
        color="churn_yn",
        color_discrete_map={"N": BLUE, "Y": RED},
        custom_data=["customer_id", "tenure_months", "avg_data_gb", "churn_yn"],
        title="가입기간 vs 평균 데이터 사용량 (이탈 여부별)",
        labels={
            "tenure_months": "가입기간 (개월)",
            "avg_data_gb": "평균 데이터 사용량 (GB)",
            "churn_yn": "이탈 여부",
        },
    )
    fig.update_traces(
        marker=dict(size=8, opacity=0.75, line=dict(width=0.5, color=PLOT_BGCOLOR)),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "가입기간: %{customdata[1]}개월<br>"
            "평균 데이터 사용량: %{customdata[2]:.1f}GB<br>"
            "이탈 여부: %{customdata[3]}<extra></extra>"
        ),
    )
    fig.update_layout(
        plot_bgcolor=PLOT_BGCOLOR,
        paper_bgcolor=PLOT_BGCOLOR,
        font=FONT,
        title_x=0.5,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    fig.update_xaxes(gridcolor=GRID_COLOR, zerolinecolor=AXIS_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR, zerolinecolor=AXIS_COLOR)
    return fig


def compute_enps(satisfaction_series):
    n = len(satisfaction_series)
    if n == 0:
        return None, 0
    promoters = (satisfaction_series >= 9).sum()
    detractors = (satisfaction_series <= 6).sum()
    return (promoters - detractors) / n * 100, n


def _enps_gauge_kwargs(value):
    color = RED if value < 0 else GOOD
    return dict(
        mode="gauge+number",
        value=value,
        number=dict(font=dict(size=44, color=color)),
        gauge=dict(
            axis=dict(range=[-100, 100], tickcolor=SECONDARY_INK, tickfont=dict(color=SECONDARY_INK)),
            bar=dict(color=color, thickness=0.3),
            bgcolor=PLOT_BGCOLOR,
            borderwidth=0,
            steps=[dict(range=[-100, 0], color=RED_BG), dict(range=[0, 100], color=NEUTRAL_BG)],
            threshold=dict(line=dict(color="#0b0b0b", width=2), thickness=0.75, value=0),
        ),
    )


def build_enps_gauge(agents_scope, agents_all, team_choice):
    if team_choice == "전체":
        overall_enps, n_total = compute_enps(agents_scope["agent_satisfaction"])

        fig = make_subplots(
            rows=1,
            cols=4,
            column_widths=[0.46, 0.18, 0.18, 0.18],
            specs=[[{"type": "indicator"}] * 4],
            horizontal_spacing=0.06,
        )
        fig.add_trace(
            go.Indicator(
                **_enps_gauge_kwargs(overall_enps),
                title={"text": "전체 eNPS", "font": {"size": 18, "color": "#0b0b0b"}},
            ),
            row=1,
            col=1,
        )
        for i, team in enumerate(["1팀", "2팀", "3팀"]):
            team_r, team_n = compute_enps(agents_all.loc[agents_all["team"] == team, "agent_satisfaction"])
            fig.add_trace(
                go.Indicator(
                    mode="number",
                    value=team_r,
                    number={"font": {"size": 34, "color": (RED if team_r < 0 else GOOD)}},
                    title={
                        "text": (
                            f"{team} eNPS<br>"
                            f"<span style='font-size:12px;color:{SECONDARY_INK}'>응답 {team_n}명</span>"
                        ),
                        "font": {"size": 15, "color": "#0b0b0b"},
                    },
                ),
                row=1,
                col=2 + i,
            )
        title_text = "직원 만족도 스코어카드 (eNPS) — 전체"
    else:
        team_enps, n = compute_enps(agents_scope["agent_satisfaction"])
        fig = go.Figure(
            go.Indicator(
                **_enps_gauge_kwargs(team_enps),
                title={"text": f"{team_choice} eNPS (응답 {n}명)", "font": {"size": 18, "color": "#0b0b0b"}},
            )
        )
        title_text = f"직원 만족도 스코어카드 (eNPS) — {team_choice}"

    fig.update_layout(
        title=dict(text=title_text, x=0.5),
        paper_bgcolor=PLOT_BGCOLOR,
        font=FONT,
        height=380,
        margin=dict(t=90, b=30, l=30, r=30),
    )
    return fig


def merge_agent_csat(agents_scope, consultations, satisfaction):
    cons_sat = consultations.merge(satisfaction[["consult_id", "csat"]], on="consult_id", how="inner")
    agent_csat = cons_sat.groupby("agent_id")["csat"].mean().rename("csat_avg")
    return agents_scope.merge(agent_csat, on="agent_id", how="inner")


def build_burnout_scatter(agent_metrics, team_choice):
    r = agent_metrics["overtime_hours_avg"].corr(agent_metrics["csat_avg"])

    fig = px.scatter(
        agent_metrics,
        x="overtime_hours_avg",
        y="csat_avg",
        trendline="ols",
        custom_data=["agent_id", "overtime_hours_avg", "csat_avg"],
        title=f"초과근무 시간 vs 상담원별 CSAT 평균 ({team_choice}, n={len(agent_metrics)})",
        labels={"overtime_hours_avg": "평균 초과근무 시간 (시간)", "csat_avg": "CSAT 평균"},
    )
    fig.update_traces(
        marker=dict(size=10, color=BLUE, opacity=0.8, line=dict(width=0.5, color=PLOT_BGCOLOR)),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "초과근무 시간: %{customdata[1]}시간<br>"
            "CSAT 평균: %{customdata[2]:.2f}<extra></extra>"
        ),
        selector=dict(mode="markers"),
    )
    fig.update_traces(line=dict(color=SECONDARY_INK, width=2), selector=dict(mode="lines"))
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
        bordercolor=AXIS_COLOR,
        borderwidth=1,
        borderpad=6,
    )
    fig.update_layout(
        showlegend=False,
        plot_bgcolor=PLOT_BGCOLOR,
        paper_bgcolor=PLOT_BGCOLOR,
        font=FONT,
        title_x=0.5,
    )
    fig.update_xaxes(gridcolor=GRID_COLOR, zerolinecolor=AXIS_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR, zerolinecolor=AXIS_COLOR)
    return fig


def build_outlier_comparison(agent_metrics):
    outliers_present = [a for a in OUTLIER_AGENT_IDS if a in set(agent_metrics["agent_id"])]
    df_excl = agent_metrics[~agent_metrics["agent_id"].isin(OUTLIER_AGENT_IDS)].reset_index(drop=True)

    def fit_stats(data):
        r = data["overtime_hours_avg"].corr(data["csat_avg"])
        slope, _ = np.polyfit(data["overtime_hours_avg"], data["csat_avg"], 1)
        return r, slope

    r_all, slope_all = fit_stats(agent_metrics)
    r_excl, slope_excl = fit_stats(df_excl) if len(df_excl) >= 2 else (float("nan"), float("nan"))

    x_pad = (agent_metrics["overtime_hours_avg"].max() - agent_metrics["overtime_hours_avg"].min()) * 0.08 or 1
    y_pad = (agent_metrics["csat_avg"].max() - agent_metrics["csat_avg"].min()) * 0.08 or 0.1
    x_range = [agent_metrics["overtime_hours_avg"].min() - x_pad, agent_metrics["overtime_hours_avg"].max() + x_pad]
    y_range = [agent_metrics["csat_avg"].min() - y_pad, agent_metrics["csat_avg"].max() + y_pad]

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=[
            f"전체 포함 (n={len(agent_metrics)})",
            f"이상치 제외 (n={len(df_excl)})",
        ],
        horizontal_spacing=0.08,
    )

    panels = [(agent_metrics, 1, r_all, slope_all), (df_excl, 2, r_excl, slope_excl)]
    for data, col, r, slope in panels:
        if len(data) < 2:
            continue
        panel_fig = px.scatter(
            data,
            x="overtime_hours_avg",
            y="csat_avg",
            trendline="ols",
            custom_data=["agent_id", "overtime_hours_avg", "csat_avg"],
        )
        marker_colors = [RED if aid in OUTLIER_AGENT_IDS else BLUE for aid in data["agent_id"]]
        for trace in panel_fig.data:
            if trace.mode == "markers":
                trace.marker = dict(size=10, color=marker_colors, opacity=0.85, line=dict(width=0.5, color=PLOT_BGCOLOR))
                trace.hovertemplate = (
                    "<b>%{customdata[0]}</b><br>"
                    "초과근무 시간: %{customdata[1]}시간<br>"
                    "CSAT 평균: %{customdata[2]:.2f}<extra></extra>"
                )
            else:
                trace.line = dict(color=SECONDARY_INK, width=2)
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
            bordercolor=AXIS_COLOR,
            borderwidth=1,
            borderpad=6,
        )

    fig.update_xaxes(range=x_range, gridcolor=GRID_COLOR, zerolinecolor=AXIS_COLOR, title="평균 초과근무 시간 (시간)")
    fig.update_yaxes(range=y_range, gridcolor=GRID_COLOR, zerolinecolor=AXIS_COLOR, title="CSAT 평균", col=1)
    fig.update_yaxes(range=y_range, gridcolor=GRID_COLOR, zerolinecolor=AXIS_COLOR, col=2)
    fig.update_layout(
        showlegend=False,
        plot_bgcolor=PLOT_BGCOLOR,
        paper_bgcolor=PLOT_BGCOLOR,
        font=FONT,
        title=dict(text="초과근무-CSAT 상관관계: 이상치(AG16·AG20) 포함/제외 비교", x=0.5),
        margin=dict(t=110),
    )

    if outliers_present:
        note = f"현재 범위 내 이상치(AG16·AG20) 포함 상담원: {', '.join(outliers_present)}"
    else:
        note = "현재 범위에는 AG16·AG20이 포함되어 있지 않아 두 패널이 동일하게 표시됩니다."
    return fig, note


def build_training_chart(agents_scope, consultations, satisfaction):
    cons_scope = consultations.merge(
        agents_scope[["agent_id", "training_completed_yn"]], on="agent_id", how="inner"
    )
    cons_sat_scope = cons_scope.merge(satisfaction[["consult_id", "csat"]], on="consult_id", how="inner")

    csat_by_training = cons_sat_scope.groupby("training_completed_yn")["csat"].mean().rename("csat_avg")
    recontact_by_training = (
        cons_scope.groupby("training_completed_yn")["is_recontact"]
        .apply(lambda s: (s == "Y").mean() * 100)
        .rename("recontact_rate")
    )

    df = pd.concat([csat_by_training, recontact_by_training], axis=1).reset_index()
    df["group"] = df["training_completed_yn"].map({True: "Y (이수)", False: "N (미이수)"})
    df = df.sort_values("training_completed_yn", ascending=False).reset_index(drop=True)
    colors = [RED if v else GRAY for v in df["training_completed_yn"]]

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
        plot_bgcolor=PLOT_BGCOLOR,
        paper_bgcolor=PLOT_BGCOLOR,
        font=FONT,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(
        gridcolor=GRID_COLOR,
        zerolinecolor=AXIS_COLOR,
        rangemode="tozero",
        range=[0, df["csat_avg"].max() * 1.15],
        title="CSAT 평균",
        row=1,
        col=1,
    )
    fig.update_yaxes(
        gridcolor=GRID_COLOR,
        zerolinecolor=AXIS_COLOR,
        rangemode="tozero",
        range=[0, df["recontact_rate"].max() * 1.15],
        title="재문의율 (%)",
        row=1,
        col=2,
    )
    return fig


st.set_page_config(page_title="고객은 왜 이탈하는가", layout="wide")
st.title("고객은 왜 이탈하는가 — 이탈 원인 진단 대시보드")
st.caption("EDATA 7기 김예림")

tab_dashboard, tab_report = st.tabs(["대시보드", "개선 제안 리포트"])

with tab_dashboard:
    data = load_data()
    customers = data["customers"]

    overall_total = len(customers)
    overall_churned = int((customers["churn_yn"] == "Y").sum())
    overall_rate = overall_churned / overall_total * 100

    col1, col2, col3 = st.columns(3)
    col1.metric("전체 고객 수", f"{overall_total:,}명")
    col2.metric("이탈 고객 수", f"{overall_churned:,}명")
    col3.metric("전체 이탈율", f"{overall_rate:.1f}%")

    st.subheader("① VOC로 본 이탈")
    st.plotly_chart(build_voc_chart(data["customers"], data["voc"]), use_container_width=True)

    st.subheader("② 채널·만족도로 본 이탈")
    st.plotly_chart(build_channel_csat_chart(data["satisfaction"], data["consultations"]), use_container_width=True)

    st.subheader("③ 재문의 반복으로 본 이탈")
    st.plotly_chart(build_recontact_bucket_chart(data["consultations"], data["customers"]), use_container_width=True)

    st.subheader("④ 요금제로 본 이탈")
    st.plotly_chart(build_plan_chart(data["customers"]), use_container_width=True)

    st.subheader("⑤ 지역으로 본 이탈")
    st.plotly_chart(build_region_chart(data["customers"]), use_container_width=True)

    st.subheader("⑥ 가입기간·이용량으로 본 이탈")
    st.plotly_chart(build_tenure_usage_chart(data["customers"], data["usage"]), use_container_width=True)

    st.header("상담원 관점: 직원만족도와 고객 경험")

    agents_all = load_agents()
    team_choice = st.selectbox("팀 선택", ["전체", "1팀", "2팀", "3팀"])
    agents_scope = agents_all if team_choice == "전체" else agents_all[agents_all["team"] == team_choice]
    agent_metrics = merge_agent_csat(agents_scope, data["consultations"], data["satisfaction"])

    st.subheader("⑦ eNPS로 본 직원 만족도")
    st.plotly_chart(build_enps_gauge(agents_scope, agents_all, team_choice), use_container_width=True)

    col_scatter, col_training = st.columns(2)
    with col_scatter:
        st.subheader("⑧ 번아웃(초과근무)과 CSAT의 관계")
        st.plotly_chart(build_burnout_scatter(agent_metrics, team_choice), use_container_width=True)
    with col_training:
        st.subheader("⑨ 교육 이수 여부와 CSAT·재문의율")
        st.plotly_chart(
            build_training_chart(agents_scope, data["consultations"], data["satisfaction"]),
            use_container_width=True,
        )

    st.subheader("⑩ 이상치 포함/제외 비교")
    outlier_fig, outlier_note = build_outlier_comparison(agent_metrics)
    st.plotly_chart(outlier_fig, use_container_width=True)
    st.caption(outlier_note)

with tab_report:
    st.markdown(load_report())
