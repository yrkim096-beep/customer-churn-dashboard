import os
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

import pandas as pd

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

voc = pd.read_csv(os.path.join(DATA_DIR, "data_voc.csv"), encoding="utf-8-sig")
customers = pd.read_csv(os.path.join(DATA_DIR, "data_customers.csv"), encoding="utf-8-sig")

target_voc = voc[(voc["category"] == "해지관련") & (voc["sentiment"] == "부정")]
target_customer_ids = target_voc["customer_id"].unique()
target_customers = customers[customers["customer_id"].isin(target_customer_ids)]

overall_total = len(customers)
overall_churned = (customers["churn_yn"] == "Y").sum()
overall_rate = overall_churned / overall_total * 100

target_total = len(target_customers)
target_churned = (target_customers["churn_yn"] == "Y").sum()
target_rate = target_churned / target_total * 100 if target_total > 0 else 0

labels = ["전체 고객", "해지관련 부정 VOC 이력 있음"]
rates = [overall_rate, target_rate]
colors = ["#9e9d97", "#d03b3b"]  # 기본 회색 / 강조 빨강(critical)

fig, ax = plt.subplots(figsize=(6, 5))
bars = ax.bar(labels, rates, color=colors, width=0.5)

for bar, rate in zip(bars, rates):
    ax.annotate(
        f"{rate:.1f}%",
        xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
        xytext=(0, 6),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=13,
        fontweight="bold",
        color="#0b0b0b",
    )

ax.set_ylabel("이탈율 (%)")
ax.set_title("전체 고객 vs 해지관련 부정 VOC 고객 이탈율 비교", fontsize=13, pad=15)
ax.set_ylim(0, max(rates) * 1.3)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_color("#c3c2b7")
ax.spines["bottom"].set_color("#c3c2b7")
ax.tick_params(colors="#52514e")
ax.yaxis.grid(True, color="#e1e0d9", linewidth=0.8)
ax.set_axisbelow(True)

fig.tight_layout()

os.makedirs(OUTPUT_DIR, exist_ok=True)
output_path = os.path.join(OUTPUT_DIR, "01_matplotlib_voc이탈비교.png")
fig.savefig(output_path, dpi=150)
print(f"저장 완료: {output_path}")
print(f"전체 고객 이탈율: {overall_rate:.2f}% ({overall_churned}/{overall_total})")
print(f"해지관련 부정 VOC 고객 이탈율: {target_rate:.2f}% ({target_churned}/{target_total})")
