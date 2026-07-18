import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
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


@st.cache_data
def load_data():
    return {
        "customers": pd.read_csv(os.path.join(DATA_DIR, "data_customers.csv"), encoding="utf-8-sig"),
        "voc": pd.read_csv(os.path.join(DATA_DIR, "data_voc.csv"), encoding="utf-8-sig"),
        "consultations": pd.read_csv(os.path.join(DATA_DIR, "data_consultations.csv"), encoding="utf-8-sig"),
        "satisfaction": pd.read_csv(os.path.join(DATA_DIR, "data_satisfaction.csv"), encoding="utf-8-sig"),
        "usage": pd.read_csv(os.path.join(DATA_DIR, "data_usage_history.csv"), encoding="utf-8-sig"),
    }


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


st.set_page_config(page_title="고객은 왜 이탈하는가", layout="wide")
st.title("고객은 왜 이탈하는가 — 이탈 원인 진단 대시보드")
st.caption("EDATA 7기 김예림")

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
