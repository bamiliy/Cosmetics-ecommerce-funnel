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
seg  = pd.read_csv(f"{D}/act3_segments.csv")
lor  = pd.read_csv(f"{D}/act3_lorenz.csv")
fs   = pd.read_csv(f"{D}/act3_funnel_shape.csv")
prof = pd.read_csv(f"{D}/act3_cluster_profile.csv")

NAVY="#1f3a5f"; BLUE="#4a90d9"; ORANGE="#e8862e"; RED="#c0392b"; GREEN="#27ae60"; GRAY="#95a5a6"
fig, axes = plt.subplots(2, 2, figsize=(13, 8.5))
fig.suptitle("第三幕 · 谁在漏：人群分群与 GMV 集中度（163.8 万用户）", fontsize=15, fontweight="bold")

# 1) 人群：用户份额 vs GMV 份额
ax = axes[0,0]
names = [s.split(' ',1)[1] for s in seg["seg"]]
y = np.arange(len(seg))
ax.barh(y+0.2, seg["user_pct"], height=0.38, color=GRAY, label="用户占比")
ax.barh(y-0.2, seg["gmv_pct"],  height=0.38, color=ORANGE, label="GMV 占比")
for i,(u,g) in enumerate(zip(seg["user_pct"], seg["gmv_pct"])):
    ax.text(u+0.6, i+0.2, f"{u}%", va="center", fontsize=9, color=GRAY)
    if g>0: ax.text(g+0.6, i-0.2, f"{g}%", va="center", fontsize=9, color=ORANGE)
ax.set_yticks(y); ax.set_yticklabels(names, fontsize=10)
ax.set_title("1.4% 的复购用户贡献 47.9% 的 GMV", fontsize=11)
ax.legend(fontsize=9, loc="lower right"); ax.set_xlabel("占比（%）")

# 2) 洛伦兹曲线
ax = axes[0,1]
ax.plot(lor["buyer_pct"], lor["gmv_cum"], color=NAVY, lw=2)
ax.fill_between(lor["buyer_pct"], lor["gmv_cum"], alpha=.1, color=NAVY)
ax.plot([0,100],[0,100], ls="--", color=GRAY, lw=1)
ax.scatter([10,20],[43.0,59.3], color=RED, zorder=5)
ax.annotate("前 10% 买家\n= 43% GMV", xy=(10,43), xytext=(30,25), fontsize=10, color=RED,
            arrowprops=dict(arrowstyle="->", color=RED))
ax.annotate("前 20% = 59.3%", xy=(20,59.3), xytext=(38,50), fontsize=9, color=RED,
            arrowprops=dict(arrowstyle="->", color=RED))
ax.set_title("买家 GMV 洛伦兹曲线", fontsize=11)
ax.set_xlabel("买家累计占比（%，按 GMV 降序）"); ax.set_ylabel("GMV 累计占比（%）")
ax.set_xlim(0,100); ax.set_ylim(0,100)

# 3) 人群人均行为结构
ax = axes[1,0]
x = np.arange(len(fs))
wdt=0.2
for k,(col,c) in enumerate([("avg_views",BLUE),("avg_carts",ORANGE),("avg_removes",RED),("avg_purchases",GREEN)]):
    ax.bar(x+(k-1.5)*wdt, fs[col], width=wdt, color=c,
           label=dict(avg_views="浏览",avg_carts="加购",avg_removes="移除",avg_purchases="购买")[col])
ax.set_yscale("log")
ax.set_yticks([0.01,0.1,1,10,100])
ax.set_yticklabels(["0.01","0.1","1","10","100"], fontsize=8)
ax.set_xticks(x); ax.set_xticklabels([s.split(' ',1)[1] for s in fs["seg"]], fontsize=9)
ax.set_title("人群行为结构：复购者是「重度策展者」（对数轴）", fontsize=11)
ax.set_ylabel("人均事件数"); ax.legend(fontsize=8)

# 4) 聚类画像：用户占比 vs GMV 占比
ax = axes[1,1]
cnames = {0:"C0 忠诚囤货者",1:"C1 一次性好奇者",2:"C2 犹豫比价者",3:"C3 高客单尝鲜客"}
prof = prof.sort_values("cluster")
labels = [cnames[c] for c in prof["cluster"]]
x = np.arange(len(prof))
ax.bar(x-0.2, prof["user_pct"], width=0.38, color=GRAY, label="用户占比（意向用户内）")
ax.bar(x+0.2, prof["gmv_pct"],  width=0.38, color=GREEN, label="GMV 占比")
for i,(u,g) in enumerate(zip(prof["user_pct"], prof["gmv_pct"])):
    ax.text(i-0.2, u+0.5, f"{u}%", ha="center", fontsize=8, color=GRAY)
    ax.text(i+0.2, g+0.5, f"{g}%", ha="center", fontsize=8, color=GREEN)
ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
ax.set_title("K-Means 四人群：两群养活全店，两群待激活", fontsize=11)
ax.legend(fontsize=8); ax.set_ylabel("占比（%）")

plt.tight_layout(rect=[0,0,1,0.96])
out = f"{D}/act3_dashboard.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
print("saved", out)
