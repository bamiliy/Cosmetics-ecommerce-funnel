# -*- coding: utf-8 -*-
"""三层细分图（11-25 新增）：结构 + 行为对比 + 移除后回头
产出：act3_tiers.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd, numpy as np, os

cands = ["PingFang SC","Hiragino Sans GB","Noto Sans CJK SC","Source Han Sans SC"]
avail = {f.name for f in font_manager.fontManager.ttflist}
use = next((c for c in cands if c in avail), None)
if use: plt.rcParams["font.family"] = use
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["text.parse_math"] = False

D = os.path.dirname(os.path.abspath(__file__))
t = pd.read_csv(f"{D}/act3_remove_tiers.csv")
r = pd.read_csv(f"{D}/act3_remove_recart.csv")

NAVY="#1f3a5f"; BLUE="#4a90d9"; ORANGE="#e8862e"; RED="#c0392b"; GREEN="#27ae60"; GRAY="#95a5a6"
fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
fig.suptitle("加购未买 × 移除行为三层细分（288,519 人，用户级口径）", fontsize=13, fontweight="bold")

names = [x.split(' ',1)[1] for x in t["tier"]]
colors = [GREEN, ORANGE, RED]

# 1) 人数结构
ax = axes[0]
wedges, _, autot = ax.pie(t["users"], labels=names, colors=colors, autopct="%1.1f%%",
                          startangle=90, textprops={"fontsize": 10},
                          wedgeprops={"width": 0.55, "edgecolor": "white"})
for a in autot: a.set_fontsize(9)
ax.set_title("① 结构：68% 从没删过购物车\n（A 保留型＝「忘了买」）", fontsize=10)

# 2) 行为对比（人均）
ax = axes[1]
x = np.arange(3); wdt = 0.27
ax.bar(x-wdt, t["avg_views"], wdt, label="人均浏览", color=GRAY)
ax.bar(x,     t["avg_carts"], wdt, label="人均加购", color=BLUE)
ax.bar(x+wdt, t["avg_removes"], wdt, label="人均移除", color=RED)
for i, (v, c, m) in enumerate(zip(t["avg_recency"], t["avg_carts"], t["avg_removes"])):
    pass  # 最近活跃天数并入 x 轴标签，避免标注互相重叠
ax.set_xticks(x)
ax.set_xticklabels([f"{n}\n最近活跃 {int(v)} 天" for n, v in zip(names, t["avg_recency"])], fontsize=9.5)
ax.set_ylim(0, max(t["avg_views"].max(), 27)*1.18)
ax.set_title("② 行为：B/C 加购量是 A 的 4~5 倍\n但 C 近乎「加一件删一件」（移除率 93%）", fontsize=10)
ax.legend(fontsize=8.5, loc="upper left")

# 3) 移除后回头
ax = axes[2]
bars = ax.bar([x.split(' ',1)[1] for x in r["tier"]], r["recart_pct"], 0.5, color=ORANGE)
for b, v in zip(bars, r["recart_pct"]):
    ax.text(b.get_x()+b.get_width()/2, v+0.2, f"{v}%", ha="center", fontsize=10)
ax.axhline(10, color=RED, ls="--", lw=1.2)
ax.text(0.02, 10.4, "10%", color=RED, fontsize=9)
ax.set_ylim(0, 12)
ax.set_title("③ 移除后同商品重新加购比例\n（移除≈终局信号，回头 <8%）", fontsize=10)
ax.set_ylabel("重新加购比例（%）")

plt.tight_layout(rect=[0, 0, 1, 0.90])
plt.savefig(f"{D}/act3_tiers.png", dpi=150, bbox_inches="tight")
print("saved act3_tiers.png")
