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
pb = pd.read_csv(f"{D}/act2_priceband_funnel.csv")
pb["view_share"] = (100*pb["views"]/pb["views"].sum()).round(1)
pb["gmv_share"]  = (100*pb["gmv"]/pb["gmv"].sum()).round(1)
br = pd.read_csv(f"{D}/act2_brands.csv")

NAVY="#1f3a5f"; BLUE="#4a90d9"; ORANGE="#e8862e"; RED="#c0392b"; GREEN="#27ae60"; GRAY="#95a5a6"
fig, axes = plt.subplots(2, 2, figsize=(13, 8.5))
fig.suptitle("第二幕 · 定位漏点：漏斗 × 价格带 × 品牌（19.5M 事件）", fontsize=15, fontweight="bold")

# 1) 价格带转化：buy_per_view 单调递减 + buy_per_cart 平稳
ax = axes[0,0]
x = np.arange(len(pb))
b1 = ax.bar(x-0.2, pb["buy_per_view"], width=0.4, color=BLUE, label="浏览→购买")
b2 = ax.bar(x+0.2, pb["buy_per_cart"], width=0.4, color=GREEN, label="加购→购买")
for i,v in enumerate(pb["buy_per_view"]): ax.text(i-0.2, v+0.4, f"{v}%", ha="center", fontsize=8, color=BLUE)
ax.set_xticks(x); ax.set_xticklabels([b.split(' ',1)[1] for b in pb["band"]], fontsize=9)
ax.set_title("价格是「加购前」的筛选器：$50+ 转化率仅为 <$2 的 1/21", fontsize=11)
ax.set_ylabel("转化率（%）"); ax.legend(fontsize=9)

# 2) 流量份额 vs GMV 份额
ax = axes[0,1]
ax.bar(x-0.2, pb["view_share"], width=0.4, color=GRAY, label="浏览量份额")
ax.bar(x+0.2, pb["gmv_share"],  width=0.4, color=ORANGE, label="GMV 份额")
for i,(vs,gs) in enumerate(zip(pb["view_share"], pb["gmv_share"])):
    ax.text(i+0.2, gs+0.4, f"{gs}%", ha="center", fontsize=8, color=ORANGE)
ax.set_xticks(x); ax.set_xticklabels([b.split(' ',1)[1] for b in pb["band"]], fontsize=9)
ax.set_title("$8-50 是「高效价格带」：流量占比 < GMV 占比", fontsize=11)
ax.set_ylabel("份额（%）"); ax.legend(fontsize=9)

# 3) 移除率 × 价格带（倒U）
ax = axes[1,0]
bars = ax.bar(x, pb["remove_per_cart"], color=[RED if 4<=i<=5 else BLUE for i in range(6)], alpha=.85)
for i,v in enumerate(pb["remove_per_cart"]): ax.text(i, v+0.8, f"{v}%", ha="center", fontsize=9)
ax.set_xticks(x); ax.set_xticklabels([b.split(' ',1)[1] for b in pb["band"]], fontsize=9)
ax.set_ylim(0, 70)
ax.set_title("被移除最多的是 $2-8：冲动加购 → 冷静后悔", fontsize=11)
ax.set_ylabel("移除 / 加购（%）")
ax.annotate("贵商品移除率反而低：\n加购 $16+ 是深思熟虑", xy=(4.5, 60), fontsize=9, color=NAVY, ha="center")

# 4) 品牌四象限
ax = axes[1,1]
xv = br["views"]; yv = br["buy_per_view"]; sz = np.sqrt(br["gmv"].clip(lower=1))/3
ax.scatter(xv, yv, s=sz, alpha=.55, color=BLUE, edgecolor=NAVY, linewidth=.5)
ax.set_xscale("log")
ax.set_xticks([2e4,5e4,1e5,2e5,4e5,6e5])
ax.set_xticklabels(["2万","5万","10万","20万","40万","60万"], fontsize=8)
ax.axhline(br["buy_per_view"].median(), color=GRAY, ls="--", lw=1)
ax.axvline(br["views"].median(), color=GRAY, ls="--", lw=1)
for _, r in br.iterrows():
    if r["brand"] in ["runail","irisk","bpw.style","jessnail","estel","kapous","masura","ingarden"]:
        ax.annotate(r["brand"], (r["views"], r["buy_per_view"]), fontsize=8,
                    textcoords="offset points", xytext=(4,4), color=RED if r["buy_per_view"]<9 else NAVY)
ax.set_title("品牌四象限（气泡=GMV）：右上明星，右下漏量", fontsize=11)
ax.set_xlabel("浏览量（对数轴）"); ax.set_ylabel("浏览→购买（%）")
ax.text(3e5, 24, "明星区", fontsize=10, color=GREEN, fontweight="bold")
ax.text(3e5, 4, "流量浪费区", fontsize=10, color=RED, fontweight="bold")

plt.tight_layout(rect=[0,0,1,0.96])
out = f"{D}/act2_dashboard.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
print("saved", out)
