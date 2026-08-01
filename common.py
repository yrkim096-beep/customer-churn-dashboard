"""공통 색상·데이터 로딩·차트 생성 함수 모음 (app.py의 대시보드/리포트 페이지가 함께 사용)."""
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dateutil.relativedelta import relativedelta
from google.cloud import bigquery
from google.oauth2 import service_account
from plotly.subplots import make_subplots

import pdf_export

# 색상 (트렌디한 팔레트 — Tailwind 500 스텝 기준, 채도 있는 블루/로즈/에메랄드/앰버 조합)
COLOR_NEUTRAL = "#64748b"       # slate-500
COLOR_CRITICAL = "#f43f5e"      # rose-500
COLOR_ACTIVE = "#10b981"        # emerald-500
COLOR_GOOD = "#10b981"          # emerald-500
COLOR_BAR = "#3b82f6"           # blue-500
COLOR_LINE = "#f97316"          # orange-500 (critical/rose와 구분되는 두 번째 강조색)
COLOR_GRID = "#e2e8f0"          # slate-200
COLOR_HIGHLIGHT = "#3b82f6"     # blue-500
COLOR_NEGATIVE_ZONE = "#fecdd3" # rose-200
COLOR_POSITIVE_ZONE = "#e2e8f0" # slate-200

# confidence 등급별 색 (리포트 페이지 카드/배지에 공통 사용)
CONFIDENCE_COLORS = {
    "높음": "#10b981",
    "중간": "#f59e0b",
    "낮음": "#f43f5e",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORT_PATH = os.path.join(BASE_DIR, "report", "고객서비스_만족도개선_리포트.md")

BQ_PROJECT = "project-e6454811-8996-4412-983"
BQ_DATASET = "cx_data"

SNAPSHOT_DATE = "2026-07-24"
AGENT_SNAPSHOT_PATH = os.path.join(DATA_DIR, "agents_snapshot.csv")
CONSULT_SNAPSHOT_PATH = os.path.join(DATA_DIR, "agent_consultations_snapshot.csv")

# recent = 최근 3개월(2024-05~07) 완료 캠페인 기준, cumulative = 2019-01~2024-07 누적 marketing_spend 기준
CHANNEL_EFFICIENCY_SNAPSHOT_PATH = os.path.join(DATA_DIR, "channel_efficiency_snapshot.csv")
MARKETING_SPEND_SNAPSHOT_PATH = os.path.join(DATA_DIR, "marketing_spend_snapshot.csv")
MARKETING_CAMPAIGNS_PATH = os.path.join(DATA_DIR, "marketing_campaigns.csv")

FONT_STACK = "Pretendard, 'Malgun Gothic', sans-serif"

CHART_LAYOUT = dict(
    plot_bgcolor="#f8fafc",
    paper_bgcolor="#f8fafc",
    font=dict(family=FONT_STACK, color="#0f172a", size=13),
    title_font=dict(family=FONT_STACK, size=17, color="#0f172a"),
    hoverlabel=dict(
        bgcolor="white",
        bordercolor="#e2e8f0",
        font=dict(family=FONT_STACK, size=13, color="#0f172a"),
    ),
)

# st.plotly_chart(..., config=PLOTLY_CONFIG)로 모든 차트에 공통 적용:
# Plotly 로고/불필요한 도구는 지우고 확대·축소·다운로드 등 유용한 기능만 남긴다.
PLOTLY_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
}


GLOBAL_CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

/* 본문 전체(제목뿐 아니라 문단·리스트·표·라벨까지) 강제 적용.
   Streamlit 내부 컴포넌트가 자체 font-family를 지정하는 경우가 있어
   와일드카드 + !important로 확실히 덮어쓴다.
   단, Material 아이콘(stIconMaterial)은 전용 아이콘 폰트를 써야 글자가 아니라
   아이콘 글리프로 렌더링되므로 반드시 제외한다. */
.stApp, .stApp *:not([data-testid="stIconMaterial"]) {
    font-family: 'Pretendard', 'Malgun Gothic', sans-serif !important;
}

/* ── Hero 배너 ── */
.hero-banner {
    background: linear-gradient(135deg, #3b82f6 0%, #4338ca 100%);
    color: #ffffff;
    padding: 2.2rem 2.4rem;
    border-radius: 18px;
    margin-bottom: 1.6rem;
    box-shadow: 0 8px 24px rgba(67, 56, 202, 0.20);
}
.hero-banner h1 {
    color: #ffffff;
    margin: 0;
    font-size: 1.9rem;
    font-weight: 800;
    letter-spacing: -0.01em;
}
.hero-banner p {
    color: rgba(255, 255, 255, 0.88);
    margin: 0.55rem 0 0 0;
    font-size: 0.98rem;
}

/* ── 통계 타일 (KPI 카드) ── */
.stat-tile {
    background: #fcfcfb;
    border: 1px solid rgba(11, 11, 11, 0.08);
    border-left: 5px solid #3b82f6;
    border-radius: 14px;
    padding: 1.15rem 1.35rem;
    box-shadow: 0 1px 3px rgba(11, 11, 11, 0.05);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    height: 100%;
}
.stat-tile:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 20px rgba(11, 11, 11, 0.10);
}
.stat-tile.critical { border-left-color: #f43f5e; }
.stat-tile.good { border-left-color: #10b981; }
.stat-tile .stat-label {
    font-size: 0.83rem;
    color: #52514e;
    margin-bottom: 0.35rem;
    font-weight: 500;
}
.stat-tile .stat-value {
    font-size: 2.1rem;
    font-weight: 800;
    color: #0b0b0b;
    line-height: 1.15;
    letter-spacing: -0.02em;
}

/* ── 카드형 컨테이너 (st.container(key=...)) 호버 효과 ── */
[class*="st-key-summary-card"],
[class*="st-key-cause-card"] {
    border-radius: 14px !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
[class*="st-key-summary-card"]:hover,
[class*="st-key-cause-card"]:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 22px rgba(11, 11, 11, 0.09);
}
[class*="st-key-cause-card"] {
    text-align: center;
}
[class*="st-key-cause-card"] p {
    text-align: left;
}

/* ── 리포트 우선순위 표 (커스텀 HTML) ── */
.report-table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.5rem 0 1rem 0;
}
.report-table th {
    text-align: center;
    font-weight: 700;
    background: #f1f5f9;
    padding: 0.6rem 0.8rem;
    border-bottom: 2px solid #cbd5e1;
    font-size: 0.92rem;
    white-space: nowrap;
}
.report-table td {
    padding: 0.6rem 0.8rem;
    border-bottom: 1px solid #e2e8f0;
    vertical-align: top;
    font-size: 0.92rem;
}
.report-table td.center {
    text-align: center;
}
.report-table code {
    background: #f1f5f9;
    padding: 0.1rem 0.35rem;
    border-radius: 4px;
    font-size: 0.85em;
}

/* ── 리포트 페이지: "문서" 느낌(연아이보리 배경 + 그림자)만 내고,
   실제 폭은 넉넉하게 둬서 차트·표 안에 스크롤이 생기지 않게 한다. */
[class*="st-key-report-page"] {
    max-width: 1200px;
    margin: 0 auto;
    background: #fbf8f2;
    padding: 3rem 3.5rem;
    border-radius: 6px;
    box-shadow: 0 0 2px rgba(15, 23, 42, 0.06), 0 12px 40px rgba(15, 23, 42, 0.10);
}

/* ── 카드(요약·원인분석) 안 본문 글자는 리포트 본문보다 1pt 작게 ──
   Streamlit 기본 본문 글자가 14px(=10.5pt)라, 카드는 9.5pt로 맞춘다. */
[class*="st-key-summary-card"] p,
[class*="st-key-cause-card"] p {
    font-size: 9.5pt;
}

/* ── 구분선 ── */
hr {
    height: 3px;
    border: none;
    border-radius: 3px;
    background: linear-gradient(90deg, #3b82f6, rgba(59, 130, 246, 0.05));
}

/* ── expander / dataframe 라운딩 ── */
[data-testid="stExpander"] {
    border-radius: 12px;
    overflow: hidden;
}
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

/* ── 배지 살짝 확대 ── */
[data-testid="stBadge"] {
    font-size: 0.85rem;
    padding: 0.15rem 0.65rem;
}
</style>
"""


def inject_global_css():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_hero(title: str, subtitle: str = ""):
    subtitle_html = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f'<div class="hero-banner"><h1>{title}</h1>{subtitle_html}</div>',
        unsafe_allow_html=True,
    )


def render_stat_tile(label: str, value: str, status: str = ""):
    """status: '', 'critical', 'good' — 왼쪽 강조 바 색을 결정한다."""
    st.markdown(
        f'<div class="stat-tile {status}">'
        f'<div class="stat-label">{label}</div>'
        f'<div class="stat-value">{value}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


@st.cache_data
def load_data():
    customers = pd.read_csv(os.path.join(DATA_DIR, "data_customers.csv"))
    voc = pd.read_csv(os.path.join(DATA_DIR, "data_voc.csv"))
    consultations = pd.read_csv(os.path.join(DATA_DIR, "data_consultations.csv"))
    satisfaction = pd.read_csv(os.path.join(DATA_DIR, "data_satisfaction.csv"))
    usage = pd.read_csv(os.path.join(DATA_DIR, "data_usage_history.csv"))
    return customers, voc, consultations, satisfaction, usage


@st.cache_data
def load_report_markdown():
    """report/고객서비스_만족도개선_리포트.md 전체 내용을 읽어온다."""
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        return f.read()


@st.cache_data
def get_report_pdf_bytes(raw_markdown: str) -> bytes:
    """리포트 PDF를 생성해 캐싱한다(매 rerun마다 다시 만들지 않도록)."""
    return pdf_export.build_report_pdf(raw_markdown)


def has_bigquery_credentials() -> bool:
    """BigQuery 인증 정보가 있을 가능성이 있는지 빠르게(네트워크 호출 없이) 확인한다.
    st.secrets에 서비스 계정이 없고 로컬 ADC 파일도 없으면, google-auth의 다단계
    자격증명 탐색(특히 GCE 메타데이터 서버 타임아웃)을 굳이 기다리지 않고 바로
    스냅샷으로 넘어가기 위한 사전 체크다."""
    try:
        if "gcp_service_account" in st.secrets:
            return True
    except Exception:
        pass  # secrets.toml 자체가 없는 로컬 환경

    env_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if env_path and os.path.isfile(env_path):
        return True

    default_adc_path = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")), "gcloud", "application_default_credentials.json"
    )
    if os.path.isfile(default_adc_path):
        return True
    posix_adc_path = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
    return os.path.isfile(posix_adc_path)


def get_bigquery_client():
    """Streamlit Cloud에서는 st.secrets의 서비스 계정으로, 로컬에서는 ADC로 인증한다."""
    try:
        has_secret = "gcp_service_account" in st.secrets
    except Exception:
        has_secret = False  # secrets.toml 자체가 없는 로컬 환경

    if has_secret:
        credentials = service_account.Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"])
        )
        return bigquery.Client(project=BQ_PROJECT, credentials=credentials)
    return bigquery.Client(project=BQ_PROJECT)


@st.cache_data
def load_bigquery_agent_data():
    """BigQuery agents/consultations/satisfaction을 조인해 상담원 단위·상담 단위 데이터를 가져온다."""
    client = get_bigquery_client()

    agent_query = f"""
    WITH agent_csat AS (
      SELECT c.agent_id, AVG(s.csat) AS avg_csat
      FROM `{BQ_PROJECT}.{BQ_DATASET}.consultations` c
      JOIN `{BQ_PROJECT}.{BQ_DATASET}.satisfaction` s ON c.consult_id = s.consult_id
      WHERE c.agent_id IS NOT NULL
      GROUP BY c.agent_id
    )
    SELECT
      a.agent_id,
      a.team,
      a.overtime_hours_avg,
      a.agent_satisfaction,
      ac.avg_csat
    FROM `{BQ_PROJECT}.{BQ_DATASET}.agents` a
    JOIN agent_csat ac ON a.agent_id = ac.agent_id
    """

    consult_query = f"""
    SELECT
      c.agent_id,
      a.team,
      a.training_completed_yn,
      c.is_recontact,
      s.csat
    FROM `{BQ_PROJECT}.{BQ_DATASET}.consultations` c
    JOIN `{BQ_PROJECT}.{BQ_DATASET}.satisfaction` s ON c.consult_id = s.consult_id
    JOIN `{BQ_PROJECT}.{BQ_DATASET}.agents` a ON c.agent_id = a.agent_id
    """

    agent_df = client.query(agent_query).result().to_dataframe()
    consult_df = client.query(consult_query).result().to_dataframe()
    return agent_df, consult_df


@st.cache_data
def load_agent_snapshot():
    """BigQuery에 연결할 수 없을 때 쓸 로컬 스냅샷(data/*_snapshot.csv)을 읽는다.
    스냅샷은 SNAPSHOT_DATE 시점에 load_bigquery_agent_data()와 동일한 쿼리로 미리 내려받아 둔 것이라
    실시간 데이터가 아니다."""
    agent_df = pd.read_csv(AGENT_SNAPSHOT_PATH)
    consult_df = pd.read_csv(CONSULT_SNAPSHOT_PATH)
    return agent_df, consult_df


FORCE_SNAPSHOT = True  # True면 로컬 인증 정보가 있어도 BigQuery 라이브 조회를 아예 시도하지 않는다.


def load_agent_data_with_fallback():
    """인증 정보가 있을 때만 BigQuery 라이브 조회를 시도하고, 없거나 실패하면 로컬 스냅샷으로 대체한다.
    (agent_df, consult_df, is_live) 튜플을 반환한다.
    인증 정보가 아예 없는 게 확인되면 라이브 시도 자체를 건너뛰어, google-auth가 GCE
    메타데이터 서버 응답을 기다리며 매번 몇 초씩 지연되는 것을 방지한다."""
    if FORCE_SNAPSHOT or not has_bigquery_credentials():
        agent_df, consult_df = load_agent_snapshot()
        return agent_df, consult_df, False

    try:
        agent_df, consult_df = load_bigquery_agent_data()
        return agent_df, consult_df, True
    except Exception:
        agent_df, consult_df = load_agent_snapshot()
        return agent_df, consult_df, False


def compute_enps(satisfaction_scores):
    promoters = (satisfaction_scores >= 9).sum()
    detractors = (satisfaction_scores <= 6).sum()
    return (promoters - detractors) * 100.0 / len(satisfaction_scores)


def build_enps_gauge(agent_df, title):
    enps = compute_enps(agent_df["agent_satisfaction"])
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=enps,
            title={"text": title, "font": {"size": 18}},
            number={"font": {"size": 36, "color": COLOR_CRITICAL if enps < 0 else COLOR_GOOD}},
            gauge={
                "axis": {"range": [-100, 100]},
                "bar": {"color": COLOR_CRITICAL if enps < 0 else COLOR_GOOD},
                "steps": [
                    {"range": [-100, 0], "color": COLOR_NEGATIVE_ZONE},
                    {"range": [0, 100], "color": COLOR_POSITIVE_ZONE},
                ],
                "threshold": {"line": {"color": "#52514e", "width": 2}, "thickness": 0.8, "value": 0},
            },
        )
    )
    # go.Indicator는 자체 title(위 title={...})만 쓰고 피규어 레벨 title은 없는데,
    # CHART_LAYOUT의 title_font를 그대로 스프레드하면 text 없는 빈 title 객체가
    # 생겨 Plotly가 "undefined"를 문자 그대로 렌더링한다 — title_font는 제외한다.
    gauge_layout = {k: v for k, v in CHART_LAYOUT.items() if k != "title_font"}
    fig.update_layout(height=280, margin=dict(l=30, r=30, t=50, b=10), **gauge_layout)
    return fig


def build_burnout_csat_chart(agent_df, title):
    fig = px.scatter(
        agent_df,
        x="overtime_hours_avg",
        y="avg_csat",
        trendline="ols" if agent_df["overtime_hours_avg"].nunique() >= 2 else None,
        custom_data=["agent_id", "overtime_hours_avg", "avg_csat"],
        title=title,
        labels={"overtime_hours_avg": "초과근무 시간 (평균, 시간)", "avg_csat": "CSAT 평균"},
    )
    fig.update_traces(
        selector=dict(mode="markers"),
        marker=dict(size=10, color=COLOR_HIGHLIGHT, opacity=0.85),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>초과근무: %{customdata[1]}시간<br>CSAT 평균: %{customdata[2]:.2f}<extra></extra>"
        ),
    )
    fig.update_traces(selector=dict(mode="lines"), line=dict(color=COLOR_CRITICAL, width=2))
    if agent_df["overtime_hours_avg"].nunique() >= 2 and agent_df["overtime_hours_avg"].std() > 0:
        r = agent_df["overtime_hours_avg"].corr(agent_df["avg_csat"])
        fig.add_annotation(
            xref="paper", yref="paper", x=0.98, y=0.98,
            text=f"r = {r:.2f}", showarrow=False, font=dict(size=14),
        )
    fig.update_layout(xaxis=dict(gridcolor=COLOR_GRID), yaxis=dict(gridcolor=COLOR_GRID), **CHART_LAYOUT)
    return fig


def build_training_compare_chart(consult_df, title):
    summary = (
        consult_df.groupby("training_completed_yn")
        .agg(n=("csat", "count"), avg_csat=("csat", "mean"), recontact_rate=("is_recontact", "mean"))
        .reset_index()
    )
    summary["recontact_rate"] *= 100
    summary["label"] = summary["training_completed_yn"].map({True: "Y (이수)", False: "N (미이수)"})
    summary = summary.sort_values("training_completed_yn", ascending=False)
    bar_colors = summary["label"].map({"Y (이수)": COLOR_HIGHLIGHT, "N (미이수)": COLOR_NEUTRAL})

    fig = make_subplots(rows=1, cols=2, subplot_titles=("CSAT 평균", "재문의율 평균 (%)"))
    fig.add_trace(
        go.Bar(
            x=summary["label"], y=summary["avg_csat"], marker_color=bar_colors,
            text=summary["avg_csat"].map(lambda v: f"{v:.2f}"), textposition="outside", showlegend=False,
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Bar(
            x=summary["label"], y=summary["recontact_rate"], marker_color=bar_colors,
            text=summary["recontact_rate"].map(lambda v: f"{v:.1f}%"), textposition="outside", showlegend=False,
        ),
        row=1, col=2,
    )
    fig.update_yaxes(range=[0, summary["avg_csat"].max() * 1.3], gridcolor=COLOR_GRID, row=1, col=1)
    fig.update_yaxes(range=[0, summary["recontact_rate"].max() * 1.3], gridcolor=COLOR_GRID, row=1, col=2)
    fig.update_layout(title=title, **CHART_LAYOUT)
    return fig


# ── ① VOC로 본 이탈 ──────────────────────────────────────────────
def build_voc_chart(customers, voc):
    target_ids = voc.loc[
        (voc["category"] == "해지관련") & (voc["sentiment"] == "부정"), "customer_id"
    ].unique()
    target_customers = customers[customers["customer_id"].isin(target_ids)]
    target_total = len(target_customers)
    target_churned = int((target_customers["churn_yn"] == "Y").sum())
    target_rate = target_churned / target_total * 100

    overall_total = len(customers)
    overall_churned = int((customers["churn_yn"] == "Y").sum())
    overall_rate = overall_churned / overall_total * 100

    df = pd.DataFrame(
        {
            "category": ["전체 고객", "해지관련 부정 VOC 이력 있음"],
            "churn_rate": [overall_rate, target_rate],
            "total_customers": [overall_total, target_total],
            "churned_customers": [overall_churned, target_churned],
        }
    )

    fig = px.bar(
        df,
        x="category",
        y="churn_rate",
        color="category",
        color_discrete_map={
            "전체 고객": COLOR_NEUTRAL,
            "해지관련 부정 VOC 이력 있음": COLOR_CRITICAL,
        },
        text=df["churn_rate"].map(lambda v: f"{v:.1f}%"),
        custom_data=["total_customers", "churned_customers", "churn_rate"],
        title="전체 고객 vs 해지관련 부정 VOC 이력 고객 이탈률 비교",
        labels={"category": "", "churn_rate": "이탈률 (%)"},
    )
    fig.update_traces(
        textposition="outside",
        hovertemplate=(
            "<b>%{x}</b><br>고객 수: %{customdata[0]:,}명<br>"
            "이탈 고객 수: %{customdata[1]:,}명<br>이탈률: %{customdata[2]:.2f}%<extra></extra>"
        ),
    )
    fig.update_layout(
        showlegend=False,
        yaxis=dict(range=[0, max(df["churn_rate"]) * 1.25], gridcolor=COLOR_GRID),
        **CHART_LAYOUT,
    )
    return fig


# ── ② 채널·만족도로 본 이탈 ──────────────────────────────────────
def build_channel_csat_chart(consultations, satisfaction):
    merged = satisfaction.merge(
        consultations[["consult_id", "channel", "is_recontact"]], on="consult_id", how="inner"
    )
    summary = (
        merged.groupby("channel")
        .agg(
            csat_mean=("csat", "mean"),
            recontact_rate=("is_recontact", lambda s: (s == "Y").mean() * 100),
            count=("consult_id", "count"),
        )
        .reset_index()
        .sort_values("csat_mean", ascending=True)
    )

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=summary["channel"],
            y=summary["csat_mean"],
            name="CSAT 평균",
            marker_color=COLOR_BAR,
            customdata=summary[["recontact_rate", "count"]],
            hovertemplate="<b>%{x}</b><br>CSAT 평균: %{y:.2f}<br>재문의율: %{customdata[0]:.1f}%<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=summary["channel"],
            y=summary["recontact_rate"],
            name="재문의율",
            mode="lines+markers",
            line=dict(color=COLOR_LINE, width=2),
            marker=dict(size=8, color=COLOR_LINE),
            customdata=summary[["csat_mean", "count"]],
            hovertemplate="<b>%{x}</b><br>재문의율: %{y:.1f}%<br>CSAT 평균: %{customdata[0]:.2f}<extra></extra>",
        ),
        secondary_y=True,
    )
    fig.update_layout(
        title="채널별 CSAT 평균 vs 재문의율 (CSAT 낮은 순)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        **CHART_LAYOUT,
    )
    fig.update_yaxes(title_text="CSAT 평균", secondary_y=False, gridcolor=COLOR_GRID)
    fig.update_yaxes(title_text="재문의율 (%)", secondary_y=True, showgrid=False)
    fig.update_xaxes(title_text="")
    return fig


# ── ③ 재문의 반복으로 본 이탈 ────────────────────────────────────
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
        .agg(
            total_customers=("customer_id", "count"),
            churned_customers=("churn_yn", lambda s: (s == "Y").sum()),
        )
        .reindex(bucket_order)
        .reset_index()
    )
    summary["churn_rate"] = summary["churned_customers"] / summary["total_customers"] * 100
    overall_rate = (customers["churn_yn"] == "Y").mean() * 100

    fig = px.bar(
        summary,
        x="recontact_bucket",
        y="churn_rate",
        color="recontact_bucket",
        color_discrete_map={"0회": COLOR_NEUTRAL, "1회": COLOR_NEUTRAL, "2회 이상": COLOR_CRITICAL},
        text=summary["churn_rate"].map(lambda v: f"{v:.1f}%"),
        custom_data=["total_customers", "churned_customers"],
        title="재문의 횟수 구간별 이탈률",
        labels={"recontact_bucket": "재문의 횟수", "churn_rate": "이탈률 (%)"},
        category_orders={"recontact_bucket": bucket_order},
    )
    fig.update_traces(
        textposition="outside",
        hovertemplate=(
            "<b>%{x}</b><br>고객 수: %{customdata[0]:,}명<br>"
            "이탈 고객 수: %{customdata[1]:,}명<br>이탈률: %{y:.2f}%<extra></extra>"
        ),
    )
    fig.add_hline(
        y=overall_rate,
        line_dash="dash",
        line_color="#52514e",
        annotation_text=f"전체 평균 이탈률 {overall_rate:.1f}%",
        annotation_position="top right",
    )
    fig.update_layout(
        showlegend=False,
        yaxis=dict(range=[0, max(summary["churn_rate"].max(), overall_rate) * 1.3], gridcolor=COLOR_GRID),
        **CHART_LAYOUT,
    )
    return fig


# ── ④ 요금제로 본 이탈 ───────────────────────────────────────────
def build_plan_chart(customers):
    highlight_plan = "베이직"
    summary = (
        customers.groupby("plan")
        .agg(
            total_customers=("customer_id", "count"),
            churned_customers=("churn_yn", lambda s: (s == "Y").sum()),
        )
        .reset_index()
    )
    summary["churn_rate"] = summary["churned_customers"] / summary["total_customers"] * 100
    summary = summary.sort_values("churn_rate", ascending=False)

    color_map = {plan: (COLOR_CRITICAL if plan == highlight_plan else COLOR_NEUTRAL) for plan in summary["plan"]}

    fig = px.bar(
        summary,
        x="plan",
        y="churn_rate",
        color="plan",
        color_discrete_map=color_map,
        text=summary["churn_rate"].map(lambda v: f"{v:.1f}%"),
        custom_data=["total_customers", "churned_customers"],
        title="요금제(plan)별 이탈률",
        labels={"plan": "요금제", "churn_rate": "이탈률 (%)"},
        category_orders={"plan": list(summary["plan"])},
    )
    fig.update_traces(
        textposition="outside",
        hovertemplate=(
            "<b>%{x}</b><br>고객 수: %{customdata[0]:,}명<br>"
            "이탈 고객 수: %{customdata[1]:,}명<br>이탈률: %{y:.2f}%<extra></extra>"
        ),
    )
    fig.update_layout(
        showlegend=False,
        yaxis=dict(range=[0, summary["churn_rate"].max() * 1.25], gridcolor=COLOR_GRID),
        **CHART_LAYOUT,
    )
    return fig


# ── ⑤ 지역으로 본 이탈 ───────────────────────────────────────────
def build_region_chart(customers):
    highlight_regions = ["부산", "대구"]
    summary = (
        customers.groupby("region")
        .agg(
            total_customers=("customer_id", "count"),
            churned_customers=("churn_yn", lambda s: (s == "Y").sum()),
        )
        .reset_index()
    )
    summary["churn_rate"] = summary["churned_customers"] / summary["total_customers"] * 100
    summary = summary.sort_values("churn_rate", ascending=False)

    color_map = {
        region: (COLOR_CRITICAL if region in highlight_regions else COLOR_NEUTRAL)
        for region in summary["region"]
    }

    fig = px.bar(
        summary,
        x="region",
        y="churn_rate",
        color="region",
        color_discrete_map=color_map,
        text=summary["churn_rate"].map(lambda v: f"{v:.1f}%"),
        custom_data=["total_customers", "churned_customers"],
        title="지역(region)별 이탈률",
        labels={"region": "지역", "churn_rate": "이탈률 (%)"},
        category_orders={"region": list(summary["region"])},
    )
    fig.update_traces(
        textposition="outside",
        hovertemplate=(
            "<b>%{x}</b><br>고객 수: %{customdata[0]:,}명<br>"
            "이탈 고객 수: %{customdata[1]:,}명<br>이탈률: %{y:.2f}%<extra></extra>"
        ),
    )

    incheon = summary.loc[summary["region"] == "인천"].iloc[0]
    caption = (
        f"※ 인천은 표본이 {int(incheon['total_customers'])}건이지만 "
        f"이탈은 {int(incheon['churned_customers'])}건뿐이라 이탈률 해석에 주의가 필요합니다."
    )

    fig.update_layout(
        showlegend=False,
        yaxis=dict(range=[0, summary["churn_rate"].max() * 1.3], gridcolor=COLOR_GRID),
        margin=dict(b=100),
        **CHART_LAYOUT,
    )
    fig.add_annotation(
        text=caption, xref="paper", yref="paper", x=0, y=-0.28,
        showarrow=False, align="left", font=dict(size=12, color="#52514e"),
    )
    return fig


# ── ⑥ 가입기간·이용량으로 본 이탈 ────────────────────────────────
def build_tenure_usage_chart(customers, usage):
    reference_date = pd.Timestamp("2024-12-31")
    customers = customers.copy()
    customers["join_date"] = pd.to_datetime(customers["join_date"])
    customers["tenure_months"] = customers["join_date"].apply(
        lambda d: relativedelta(reference_date, d).years * 12 + relativedelta(reference_date, d).months
    )
    avg_usage = usage.groupby("customer_id")["data_gb"].mean().rename("avg_data_gb")
    merged = customers.merge(avg_usage, on="customer_id", how="inner")

    fig = px.scatter(
        merged,
        x="tenure_months",
        y="avg_data_gb",
        color="churn_yn",
        color_discrete_map={"N": COLOR_ACTIVE, "Y": COLOR_CRITICAL},
        category_orders={"churn_yn": ["N", "Y"]},
        custom_data=["customer_id", "tenure_months", "avg_data_gb", "churn_yn"],
        title="가입기간 vs 평균 데이터 사용량 (이탈 여부)",
        labels={"tenure_months": "가입기간 (개월)", "avg_data_gb": "평균 데이터 사용량 (GB)", "churn_yn": "이탈 여부"},
    )
    fig.update_traces(
        marker=dict(size=8, opacity=0.8),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>가입기간: %{customdata[1]}개월<br>"
            "평균 데이터 사용량: %{customdata[2]:.2f}GB<br>이탈 여부: %{customdata[3]}<extra></extra>"
        ),
    )
    fig.update_layout(
        xaxis=dict(gridcolor=COLOR_GRID),
        yaxis=dict(gridcolor=COLOR_GRID),
        legend_title_text="이탈 여부",
        **CHART_LAYOUT,
    )
    return fig


def build_agents_reproducibility_chart():
    """agents 테이블 재생성 전후(07-22 vs 07-23) 상관계수·eNPS가 얼마나 달라졌는지 보여주는 비교 차트.
    i-004/q-009에서 다룬 재현성 문제를 리포트 4-5절에서 시각적으로 뒷받침하기 위한 신규 차트."""
    df = pd.DataFrame(
        {
            "지표": ["전체 eNPS", "만족도↔재문의율 r", "번아웃↔CSAT r"],
            "07-22": [-60.0, -0.233, -0.086],
            "07-23": [-45.0, -0.845, -0.834],
        }
    )
    df_melted = df.melt(id_vars="지표", var_name="시점", value_name="값")

    fig = px.bar(
        df_melted,
        x="지표",
        y="값",
        color="시점",
        barmode="group",
        color_discrete_map={"07-22": COLOR_NEUTRAL, "07-23": COLOR_CRITICAL},
        text=df_melted["값"].map(lambda v: f"{v:.2f}" if abs(v) < 1 else f"{v:.1f}"),
        title="agents 테이블 재생성 전후 비교 — 같은 쿼리, 다른 결과",
        labels={"값": "값 (eNPS: -100~100 / r: -1~1)"},
    )
    fig.update_traces(textposition="outside")
    fig.add_hline(y=0, line_color=COLOR_GRID, line_width=1)
    fig.update_layout(
        legend_title_text="조회 시점",
        yaxis=dict(gridcolor=COLOR_GRID),
        **CHART_LAYOUT,
    )
    return fig


# ── 채널 효율(마케팅 집행) ────────────────────────────────────────
@st.cache_data
def load_bigquery_marketing_spend():
    """BigQuery marketing_spend을 SELECT로 조회한다 (읽기 전용 — INSERT/UPDATE/DELETE 없음)."""
    client = get_bigquery_client()
    query = f"""
    SELECT month, channel, spend, impressions, clicks, signups
    FROM `{BQ_PROJECT}.{BQ_DATASET}.marketing_spend`
    ORDER BY month, channel
    """
    return client.query(query).result().to_dataframe()


@st.cache_data
def load_marketing_spend_snapshot():
    """BigQuery 인증 정보가 없는 배포 환경 등에서 쓰는 로컬 스냅샷 폴백."""
    return pd.read_csv(MARKETING_SPEND_SNAPSHOT_PATH)


def load_marketing_spend_with_fallback():
    """load_agent_data_with_fallback()과 같은 구조 — 인증 정보가 있을 때만 BigQuery 라이브 조회를
    시도하고, 없거나 실패하면 로컬 스냅샷으로 대체한다. (df, is_live) 튜플을 반환한다."""
    if FORCE_SNAPSHOT or not has_bigquery_credentials():
        return load_marketing_spend_snapshot(), False

    try:
        return load_bigquery_marketing_spend(), True
    except Exception:
        return load_marketing_spend_snapshot(), False


@st.cache_data
def load_marketing_campaigns():
    """data/marketing_campaigns.csv(채널×캠페인 단위, 예산·실집행 포함)를 읽는다."""
    return pd.read_csv(MARKETING_CAMPAIGNS_PATH)


def verify_overlap(spend_df, campaigns_df, months=("2024-05", "2024-06")):
    """캠페인 원본(marketing_campaigns.csv)을 채널×월로 집계(실집행 합, 유입건수 합)한 뒤,
    같은 채널×월의 marketing_spend(spend_df) 값과 일치하는지 대조해 표로 반환한다.
    채널명 표기 차이(앞뒤 공백 등)는 비교 전에 통일한다. 두 쪽 중 한쪽에만 있는 채널×월은
    다른 쪽 값이 NaN으로 남고, match 열도 (불일치가 아니라 "대조 불가"를 뜻하는) NA로
    남는다 — 값이 달라서 불일치인 경우만 match=False가 된다."""
    months = list(months)

    campaigns = campaigns_df.copy()
    campaigns["월"] = campaigns["월"].astype(str).str.strip()
    campaigns["채널"] = campaigns["채널"].astype(str).str.strip()
    campaign_agg = (
        campaigns[campaigns["월"].isin(months)]
        .groupby(["월", "채널"], as_index=False)
        .agg(campaign_spend=("실집행", "sum"), campaign_signups=("유입건수", "sum"))
        .rename(columns={"월": "month", "채널": "channel"})
    )

    spend = spend_df.copy()
    spend["month"] = spend["month"].astype(str).str.strip()
    spend["channel"] = spend["channel"].astype(str).str.strip()
    spend_agg = (
        spend[spend["month"].isin(months)]
        .groupby(["month", "channel"], as_index=False)
        .agg(bq_spend=("spend", "sum"), bq_signups=("signups", "sum"))
    )

    result = campaign_agg.merge(spend_agg, on=["month", "channel"], how="outer")
    result["spend_match"] = result["campaign_spend"] == result["bq_spend"]
    result["signups_match"] = result["campaign_signups"] == result["bq_signups"]
    result["match"] = result["spend_match"] & result["signups_match"]

    return result.sort_values(["month", "channel"]).reset_index(drop=True)


def build_marketing_spend_timeseries(spend_df, campaigns_df, append_month="2024-07", validate_months=("2024-05", "2024-06")):
    """spend_df(BigQuery marketing_spend, ~2024-06)에 marketing_campaigns.csv의
    append_month(기본 07월)분을 채널×월로 집계해 이어붙인 데이터프레임을 반환한다.

    이어붙이기 전에 validate_months 구간을 verify_overlap()으로 다시 검증하고,
    하나라도 불일치하면 ValueError를 내고 이어붙이지 않는다(호출하는 쪽에서
    "검증을 통과했다"고 가정하고 넘어가지 않도록, 실제로 다시 확인한다).

    impressions·clicks는 marketing_campaigns.csv에 해당 데이터가 없어
    이어붙인 07월 행에서는 NaN으로 남는다.
    """
    check = verify_overlap(spend_df, campaigns_df, months=validate_months)
    if not check["match"].fillna(False).all():
        mismatches = check[~check["match"].fillna(False)]
        raise ValueError(f"{list(validate_months)} 구간 대조에 불일치가 있어 {append_month}을 이어붙이지 않습니다:\n{mismatches}")

    campaigns = campaigns_df.copy()
    campaigns["월"] = campaigns["월"].astype(str).str.strip()
    campaigns["채널"] = campaigns["채널"].astype(str).str.strip()

    appended = (
        campaigns[campaigns["월"] == append_month]
        .groupby("채널", as_index=False)
        .agg(spend=("실집행", "sum"), signups=("유입건수", "sum"))
        .rename(columns={"채널": "channel"})
    )
    appended["month"] = append_month
    appended["impressions"] = pd.NA
    appended["clicks"] = pd.NA
    appended = appended[["month", "channel", "spend", "impressions", "clicks", "signups"]]

    base = spend_df[["month", "channel", "spend", "impressions", "clicks", "signups"]]
    combined = pd.concat([base, appended], ignore_index=True)
    return combined.sort_values(["channel", "month"]).reset_index(drop=True)


def compute_channel_cost_efficiency(combined_df, recent_months=("2024-05", "2024-06", "2024-07")):
    """build_marketing_spend_timeseries()가 반환한 combined_df(채널×월, 2019-01~2024-07
    전체 이력)에서 채널별 recent(최근 3개월 합계)·cumulative(전체 이력 합계) 유입 1건당
    비용을 계산한다."""
    df = combined_df.copy()
    df["month"] = df["month"].astype(str)

    recent = (
        df[df["month"].isin(recent_months)]
        .groupby("channel", as_index=False)
        .agg(spend_recent=("spend", "sum"), signups_recent=("signups", "sum"))
    )
    cumulative = df.groupby("channel", as_index=False).agg(
        spend_cumulative=("spend", "sum"), signups_cumulative=("signups", "sum")
    )

    result = recent.merge(cumulative, on="channel", how="left")
    result["cost_recent"] = result["spend_recent"] / result["signups_recent"]
    result["cost_cumulative"] = result["spend_cumulative"] / result["signups_cumulative"]
    return result


@st.cache_data
def load_channel_efficiency():
    """채널별 유입 1건당 비용 스냅샷을 읽어 recent/cumulative 단가를 계산한다.
    recent=최근 3개월(2024-05~07) 완료 캠페인 기준, cumulative=2019-01~2024-07 누적 기준."""
    df = pd.read_csv(CHANNEL_EFFICIENCY_SNAPSHOT_PATH)
    df["cost_recent"] = df["spend_recent"] / df["signups_recent"]
    df["cost_cumulative"] = df["spend_cumulative"] / df["signups_cumulative"]
    return df


def build_channel_cost_chart(df):
    """px.bar(color="channel")는 채널마다 별도 트레이스를 만든다 — 이러면
    Plotly가 "카테고리당 최대 6개 막대가 나란히 들어갈 그룹 막대"로 폭을
    계산해서, 실제로는 카테고리당 막대가 1개뿐인데도 막대가 그 1/6
    너비로 얇게 그려진다. color= 대신 marker_color에 색상 리스트를
    직접 넘겨 단일 트레이스로 만들면 막대가 카테고리 폭 전체를 쓴다."""
    highlight_channel = "SNS광고"
    summary = df.sort_values("cost_recent", ascending=False)
    colors = [COLOR_CRITICAL if ch == highlight_channel else COLOR_NEUTRAL for ch in summary["channel"]]

    fig = go.Figure(
        go.Bar(
            x=summary["channel"],
            y=summary["cost_recent"],
            marker_color=colors,
            text=summary["cost_recent"].map(lambda v: f"{v:,.0f}원"),
            textposition="outside",
            customdata=summary[["spend_recent", "signups_recent"]],
            hovertemplate=(
                "<b>%{x}</b><br>실집행: %{customdata[0]:,.0f}원<br>"
                "유입건수: %{customdata[1]:,.0f}건<br>유입 1건당 비용: %{y:,.0f}원<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title="채널별 유입 1건당 비용 (최근 3개월 기준)",
        xaxis=dict(title=""),
        yaxis=dict(
            title="유입 1건당 비용 (원)",
            range=[0, summary["cost_recent"].max() * 1.25],
            gridcolor=COLOR_GRID,
        ),
        bargap=0.15,
        **CHART_LAYOUT,
    )
    return fig


def build_channel_cost_compare_chart(df):
    label_map = {"cost_recent": "최근 3개월", "cost_cumulative": "누적(2019-01~2024-07)"}
    melted = df.melt(id_vars="channel", value_vars=list(label_map), var_name="구분", value_name="cost")
    melted["구분"] = melted["구분"].map(label_map)
    channel_order = list(df.sort_values("cost_recent", ascending=False)["channel"])

    fig = px.bar(
        melted,
        x="channel",
        y="cost",
        color="구분",
        barmode="group",
        color_discrete_map={label_map["cost_recent"]: COLOR_NEUTRAL, label_map["cost_cumulative"]: COLOR_BAR},
        text=melted["cost"].map(lambda v: f"{v:,.0f}"),
        title="채널별 유입 1건당 비용 — 최근 3개월 vs 누적",
        labels={"channel": "", "cost": "유입 1건당 비용 (원)"},
        category_orders={"channel": channel_order},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        legend_title_text="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(gridcolor=COLOR_GRID),
        **CHART_LAYOUT,
    )
    return fig


def build_channel_execution_rate_chart(campaigns_df):
    """marketing_campaigns.csv의 완료 캠페인(is_completed=True)만으로 채널별
    집행률(실집행 합계 ÷ 예산 합계)을 계산해 100% 기준선과 함께 보여준다."""
    completed = campaigns_df[campaigns_df["is_completed"] == True]
    summary = (
        completed.groupby("채널", as_index=False)
        .agg(budget=("예산", "sum"), actual=("실집행", "sum"))
        .rename(columns={"채널": "channel"})
    )
    summary["execution_rate"] = summary["actual"] / summary["budget"] * 100
    summary = summary.sort_values("execution_rate", ascending=False)

    fig = px.bar(
        summary,
        x="channel",
        y="execution_rate",
        text=summary["execution_rate"].map(lambda v: f"{v:.1f}%"),
        title="채널별 집행률 (완료 캠페인 기준, 실집행 ÷ 예산)",
        labels={"channel": "", "execution_rate": "집행률 (%)"},
    )
    fig.update_traces(marker_color=COLOR_BAR, textposition="outside")
    fig.add_hline(
        y=100,
        line_dash="dash",
        line_color=COLOR_NEUTRAL,
        annotation_text="예산 100%",
        annotation_position="top right",
    )
    fig.update_layout(
        showlegend=False,
        yaxis=dict(gridcolor=COLOR_GRID),
        **CHART_LAYOUT,
    )
    return fig


@st.cache_data
def load_monthly_channel_cost():
    """marketing_spend(월별, ~2024-06)과 marketing_campaigns의 2024-07월분
    집계를 이어붙여 채널×월 단가(실집행/유입) 시계열을 만든다.

    07월은 완료 여부와 무관하게 전체 합계를 쓴다 — marketing_spend의
    spend·signups도 원래 완료 여부를 구분하지 않는 값이라, 기준을
    맞추기 위함이다(Day4_추가교안.md 참고). BigQuery에는 쓰지 않는다."""
    spend_df = pd.read_csv(MARKETING_SPEND_SNAPSHOT_PATH)[["month", "channel", "spend", "signups"]]

    campaigns_df = pd.read_csv(MARKETING_CAMPAIGNS_PATH)
    july = campaigns_df[campaigns_df["월"] == "2024-07"]
    july_agg = (
        july.groupby("채널", as_index=False)
        .agg(spend=("실집행", "sum"), signups=("유입건수", "sum"))
        .rename(columns={"채널": "channel"})
    )
    july_agg["month"] = "2024-07"
    july_agg = july_agg[["month", "channel", "spend", "signups"]]

    combined = pd.concat([spend_df, july_agg], ignore_index=True)
    combined["cost"] = combined.apply(
        lambda r: r["spend"] / r["signups"] if r["signups"] > 0 else None, axis=1
    )
    return combined.sort_values(["channel", "month"]).reset_index(drop=True)


def build_channel_trend_chart(df, channel):
    """선택한 채널 하나의 연도별 단가 추이(2019~2024).

    월별로 보면 표본이 너무 작아(채널당 월 0~수 건) 등락이 심해 추세를
    읽기 어려웠다. 연 단위로 묶어 spend·signups를 각각 합산한 뒤
    단가를 다시 계산한다 — 연도별 단가의 평균이 아니라, 그 해 전체
    지출·유입 합계로 계산한 값이라는 점이 다르다(월별 단가의 평균과는
    미묘하게 다를 수 있음)."""
    sub = df[df["channel"] == channel].copy()
    sub["year"] = sub["month"].str[:4]

    yearly = sub.groupby("year", as_index=False).agg(spend=("spend", "sum"), signups=("signups", "sum"))
    yearly["cost"] = yearly.apply(lambda r: r["spend"] / r["signups"] if r["signups"] > 0 else None, axis=1)

    is_2024_partial = "2024" in yearly["year"].values
    yearly["연도"] = yearly["year"] + yearly["year"].apply(lambda y: " (~07월)" if y == "2024" else "")

    fig = px.line(
        yearly,
        x="연도",
        y="cost",
        markers=True,
        custom_data=["spend", "signups"],
        title=f"{channel} — 연도별 유입 1건당 비용 추이 (2019~2024)",
        labels={"연도": "", "cost": "유입 1건당 비용 (원)"},
    )
    fig.update_traces(
        line=dict(color=COLOR_LINE, width=2),
        marker=dict(size=8, color=COLOR_LINE),
        connectgaps=False,
        hovertemplate=(
            "%{x}<br>연간 실집행: %{customdata[0]:,.0f}원<br>연간 유입: %{customdata[1]:,.0f}건"
            "<br>유입 1건당 비용: %{y:,.0f}원<extra></extra>"
        ),
    )
    fig.update_layout(
        # "2019".."2023"이 숫자로 보여서 x축이 자동으로 연속형 숫자 축이
        # 되어버리면, 문자열인 "2024 (~07월)"이 빠지고 중간에 "2,019.5"
        # 같은 눈금이 생긴다. 범주형으로 고정해서 순서·전체 연도를 보장한다.
        xaxis=dict(type="category", categoryorder="array", categoryarray=list(yearly["연도"]), gridcolor=COLOR_GRID),
        yaxis=dict(gridcolor=COLOR_GRID),
        **CHART_LAYOUT,
    )
    if is_2024_partial:
        fig.add_annotation(
            text="※ 2024년은 7월까지 7개월치만 반영된 값입니다 — 다른 해(12개월)와 절대 비교 시 주의하세요.",
            xref="paper", yref="paper", x=0, y=-0.28,
            showarrow=False, align="left", font=dict(size=12, color="#52514e"),
        )
        fig.update_layout(margin=dict(b=80))
    return fig
