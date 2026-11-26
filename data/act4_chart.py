# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd, numpy as np

cands = ["PingFang SC","Hiragino Sans GB","Noto Sans CJK SC","Source Han Sans SC"]
avail = {f.name for f in font_manager.fontManager.ttflist}
use = next((c for c in cands if c in avail), None)
if use: plt.rcParams["font.family"] = use
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["text.parse_math"] = False

D = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data"
led = pd.read_csv(f"{D}/act4_ledger.csv")
NAVY="#1f3a5f"; BLUE="#4a90d9"; ORANGE="#e8862e"; GREEN="#27ae60"; GRAY="#95a5a6"

fig = plt.figure(figsize=(14, 7.2))
fig.suptitle("第四幕 · 钱该花在哪：策略矩阵与 GMV 挽回空间", fontsize=15, fontweight="bold")

# 左：策略 × 情景 横向条形
ax = fig.add_subplot(1, 2, 1)
order = ["S1 激活加购未买（首购转化）","S2 唤醒单次购买者（30天回购触达）",
         "S3 低价带移除挽回（凑单/批量优惠）","S4 高价带加购→购买补强（比价工具/分期）",
         "S5 品牌坑位再分配（kapous→高效品牌篮）"]
short = ["S1 激活加购未买","S2 唤醒单次购买者","S3 低价带移除挽回","S4 高价带转化补强","S5 品牌坑位再分配"]
colors = {"保守":GRAY,"中性":BLUE,"乐观":GREEN}
y = np.arange(len(order))
for k, sc in enumerate(["保守","中性","乐观"]):
    vals = [led[(led["策略"]==s)&(led["情景"]==sc)]["月挽回GMV"].iloc[0]/1e4 for s in order]
    ax.barh(y+(k-1)*0.26, vals, height=0.24, color=colors[sc], label=sc)
    for i,v in enumerate(vals):
        if sc=="中性": ax.text(v+0.3, i, f"${v:.1f}万/月", va="center", fontsize=9, color=NAVY, fontweight="bold")
ax.set_yticks(y); ax.set_yticklabels(short, fontsize=10)
ax.invert_yaxis()
ax.axvline(0, color="black", lw=.6)
ax.set_title("每月可挽回 GMV：三情景（万美元）｜中性合计 $29.6万/月 ≈ 月GMV的23.3%", fontsize=11)
ax.legend(fontsize=9, loc="lower right")
ax.set_xlabel("万美元 / 月")

# 右：策略矩阵表
ax2 = fig.add_subplot(1, 2, 2); ax2.axis("off")
rows = [
    ["目标人群", "卡点", "策略动作", "月挽回(中性)"],
    ["C2 犹豫比价者\n（28.9万加购未买）", "加购→购买\n$2-8 低价带犹豫", "定向券 + 降价提醒\n+ 凑单门槛", "$10.9万"],
    ["C3 高客单尝鲜客\n（8.8万单次购买）", "买完不回来\n无复购触达", "30天回购触达\n（消耗品补货周期）", "$8.0万"],
    ["复购策展者\n（2.3万）", "低价区反复挑拣\n移除率61%", "批量优惠/订阅制\n减少决策成本", "$6.5万"],
    ["高价带浏览者", "$50+ 加购后\n转化仅17.5%", "比价工具/分期/评价\n前置打消顾虑", "$3.9万"],
    ["全站（结构性）", "kapous 每坑位\n$0.32 vs 高效篮 $1.22", "减 kapous 坑位\n→ strong/uno/cnd 等", "$0.3万"],
    ["C1 一次性好奇者\n（15.8万）", "已流失109天", "不花钱\n（止损也是策略）", "$0"],
]
tbl = ax2.table(cellText=rows, loc="center", cellLoc="center")
tbl.auto_set_font_size(False); tbl.set_fontsize(8.5); tbl.scale(1, 2.4)
for j in range(4):
    c = tbl[0, j]; c.set_facecolor(NAVY); c.set_text_props(color="white", fontweight="bold")
for i in range(1, 7):
    tbl[i, 3].set_text_props(color="#c0392b", fontweight="bold")
    if i == 6:
        for j in range(4): tbl[i, j].set_facecolor("#f2f2f2")
ax2.set_title("人群 × 卡点 × 策略矩阵", fontsize=11)

plt.tight_layout(rect=[0,0,1,0.94])
out = f"{D}/act4_dashboard.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
print("saved", out)
