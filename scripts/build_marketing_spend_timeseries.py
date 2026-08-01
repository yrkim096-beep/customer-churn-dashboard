"""
BigQuery cx_data.marketing_spend(2019-01~2024-06, SELECT만) 과
my-wiki-02/raw/marketing_campaigns.csv(2024-05~07, 채널x캠페인 단위)를 채널x월로 집계해 대조하고,
05·06월이 일치하면 07월만 시계열에 이어붙인다.

최종 결합 시계열은 BigQuery에 쓰지 않고 로컬 CSV로만 남긴다.
캠페인 원본(27행, 예산 포함)은 집행률(실집행/예산) 계산 전용으로 별도 유지하며
이 시계열에는 합치지 않는다.
"""
import csv
import os
from collections import defaultdict
from google.cloud import bigquery

WIKI_DIR = r"C:\Users\mello\OneDrive\바탕 화면\my-wiki-02"

CAMPAIGNS_PATH = os.path.join(WIKI_DIR, "raw", "marketing_campaigns.csv")
OUTPUT_PATH = os.path.join(WIKI_DIR, "02_data", "마케팅캠페인", "marketing_spend_timeseries_2019-01_2024-07.csv")
BQ_MONTHS = ("2019-01", "2024-06")  # BigQuery에서 가져올 범위(이 이후는 BigQuery에 없거나 검증 대상 아님)
VALIDATE_MONTHS = {"2024-05", "2024-06"}
APPEND_MONTH = "2024-07"


def get_bq_marketing_spend():
    client = bigquery.Client()
    query = f"""
        SELECT month, channel, spend, impressions, clicks, signups
        FROM `cx_data.marketing_spend`
        WHERE month <= '{BQ_MONTHS[1]}'
        ORDER BY month, channel
    """
    rows = list(client.query(query).result())
    return [
        {"month": r.month, "channel": r.channel, "spend": r.spend,
         "impressions": r.impressions, "clicks": r.clicks, "signups": r.signups}
        for r in rows
    ]


def aggregate_campaigns(path, months):
    """채널x월로 집계(실집행 합, 유입건수 합). is_completed 무관하게 전체 합산(05·06 대조 때와 동일 방식)."""
    totals = defaultdict(lambda: {"spend": 0, "signups": 0})
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["월"] in months:
                key = (r["월"], r["채널"])
                totals[key]["spend"] += int(r["실집행"])
                totals[key]["signups"] += int(r["유입건수"])
    return totals


def validate(bq_rows, camp_totals, months_to_check):
    bq_lookup = {(r["month"], r["channel"]): r for r in bq_rows}
    checked_keys = sorted(k for k in camp_totals if k[0] in months_to_check)
    print("[검증] BigQuery marketing_spend vs marketing_campaigns.csv 채널x월 집계 대조")
    all_ok = True
    for month, channel in checked_keys:
        agg = camp_totals[(month, channel)]
        bq = bq_lookup.get((month, channel))
        if bq is None:
            print(f"  {month} {channel}: BigQuery에 해당 채널x월 없음 -> MISMATCH")
            all_ok = False
            continue
        ok_spend = bq["spend"] == agg["spend"]
        ok_signup = bq["signups"] == agg["signups"]
        all_ok = all_ok and ok_spend and ok_signup
        print(f"  {month} {channel}: spend {agg['spend']} vs {bq['spend']} "
              f"{'OK' if ok_spend else 'MISMATCH'}, "
              f"signups {agg['signups']} vs {bq['signups']} {'OK' if ok_signup else 'MISMATCH'}")
    print(f"검증 결과: {'전부 일치' if all_ok else '불일치 있음 - 07월을 이어붙이지 않음'}")
    return all_ok


def main():
    bq_rows = get_bq_marketing_spend()
    print(f"BigQuery marketing_spend 조회: {len(bq_rows)}행 (~{BQ_MONTHS[1]})")

    camp_totals = aggregate_campaigns(CAMPAIGNS_PATH, VALIDATE_MONTHS | {APPEND_MONTH})

    ok = validate(bq_rows, camp_totals, VALIDATE_MONTHS)
    if not ok:
        print("\n검증 실패 - 시계열을 만들지 않고 종료합니다.")
        return

    # 검증 통과 -> 07월분만 시계열에 이어붙임 (BigQuery에는 쓰지 않고, 파이썬 메모리 + 로컬 파일에만 반영)
    combined = list(bq_rows)
    appended = 0
    for (month, channel), agg in sorted(camp_totals.items()):
        if month == APPEND_MONTH:
            combined.append({
                "month": month, "channel": channel, "spend": agg["spend"],
                "impressions": None, "clicks": None, "signups": agg["signups"],
            })
            appended += 1

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["month", "channel", "spend", "impressions", "clicks", "signups"])
        writer.writeheader()
        writer.writerows(combined)

    print(f"\n07월 {appended}개 채널 이어붙임 (impressions/clicks는 marketing_campaigns.csv에 없어 NULL)")
    print(f"최종 시계열: {len(combined)}행 (2019-01~{APPEND_MONTH}) -> {OUTPUT_PATH}")
    print("(이 결과는 BigQuery에는 반영하지 않았습니다 - 로컬 CSV로만 존재)")

    print(f"\n캠페인 원본({CAMPAIGNS_PATH}, 27행, 예산 컬럼 포함)은 이 시계열에 합치지 않고 "
          f"집행률(실집행/예산) 계산 전용으로 별도 유지합니다.")


if __name__ == "__main__":
    main()
