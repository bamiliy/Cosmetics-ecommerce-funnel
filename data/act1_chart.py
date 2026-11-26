# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd

# ---- 找可用的中文字体 ----
cands = ["PingFang SC","Hiragino Sans GB","Noto Sans CJK SC","Source Han Sans SC","Arial Unicode MS","WenQuanYi Zen Hei"]
avail = {f.name for f in font_manager.fontManager.ttflist}
use = next((c for c in cands if c in avail), None)
print("font:", use)
if use: plt.rcParams["font.family"] = use
plt.rcParams["axes.unicode_minus"] = False

D = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data"
m  = pd.read_csv(f"{D}/act1_monthly.csv")
f  = pd.read_csv(f"{D}/act1_funnel_monthly.csv")
w  = pd.read_csv(f"{D}/act1_weekly.csv")

fig, axes = plt.subplots(2, 2, figsize=(13, 8.5))
fig.suptitle("化妆品电商盘面诊断（2019-10 ~ 2020-02，19.5M 事件）", fontsize=15, fontweight="bold")

NAVY="#1f3a5f"; BLUE="#4a90d9"; ORANGE="#e8862e"; RED="#c0392b"; GREEN="#27ae60"; GRAY="#95a5a6"

# 1) 月度 GMV + UV
ax = axes[0,0]
x = range(len(m))
ax.bar(x, m["gmv"]/1e4, color=BLUE, alpha=.85, width=.55, label="GMV（万美元）")
ax.set_xticks(x); ax.set_xticklabels(m["month"], fontsize=9)
for i,v in enumerate(m["gmv"]/1e4): ax.text(i, v+2, f"{v:.0f}", ha="center", fontsize=9)
ax2 = ax.twinx()
ax2.plot(x, m["uv"]/1e4, color=ORANGE, marker="o", lw=2, label="UV（万）")
ax2.set_ylim(0, 55)
ax.set_title("月度 GMV 与 UV：11 月冲顶，12 月回落", fontsize=11)
ax.set_ylabel("GMV（万美元）"); ax2.set_ylabel("UV（万）")
ax.legend(loc="upper left", fontsize=8); ax2.legend(loc="upper right", fontsize=8)

# 2) 漏斗转化率月度走势
ax = axes[0,1]
ax.plot(f["month"], f["view_to_cart_pct"], marker="o", color=BLUE,  lw=2, label="浏览→加购")
ax.plot(f["month"], f["cart_to_buy_pct"],  marker="s", color=GREEN, lw=2, label="加购→购买")
ax.plot(f["month"], f["view_to_buy_pct"],  marker="^", color=RED,   lw=2, label="浏览→购买")
for _, r in f.iterrows():
    ax.annotate(f"{r['cart_to_buy_pct']}%", (r["month"], r["cart_to_buy_pct"]), textcoords="offset points", xytext=(0,7), fontsize=8, ha="center")
ax.set_title("漏斗转化率：10 月结构突变后趋稳", fontsize=11)
ax.legend(fontsize=8); ax.set_ylabel("转化率（%）"); ax.tick_params(axis='x', labelsize=9)

# 3) 周度 GMV + 事件标注
ax = axes[1,0]
wx = range(len(w))
ax.plot(wx, w["gmv"]/1e4, color=NAVY, lw=2, marker=".", ms=5)
ax.fill_between(wx, w["gmv"]/1e4, alpha=.12, color=NAVY)
ax.set_xticks(wx[::3]); ax.set_xticklabels(w["week"][::3], rotation=30, fontsize=8)
notes = {7:"黑五大促周", 8:"黑五当周", 12:"圣诞周", 17:"1月峰值", 21:"2月末"}
for i, lab in notes.items():
    off = (0,-18) if i==7 else (0,10)
    ax.annotate(lab, (i, w["gmv"][i]/1e4), textcoords="offset points", xytext=off, ha="center", fontsize=8, color=RED)
ax.set_title("周度 GMV：圣诞是低谷，2 月连续 4 周下滑", fontsize=11)
ax.set_ylabel("GMV（万美元）")

# 4) 整体用户漏斗
ax = axes[1,1]
stages = ["浏览过", "加购过", "购买过"]
vals   = [1596371, 398124, 110518]
colors = [GRAY, BLUE, GREEN]
bars = ax.barh(stages[::-1], [v/1e4 for v in vals[::-1]], color=colors[::-1], height=.55)
for b, v in zip(bars, vals[::-1]):
    ax.text(b.get_width()+3, b.get_y()+b.get_height()/2, f"{v/1e4:.1f} 万", va="center", fontsize=10)
ax.text(60, 1.0, "加购→购买仅 27.8%", fontsize=10, color=RED, fontweight="bold")
ax.text(60, 0.35, "每月约 6.5 万加购用户流失", fontsize=10, color=RED)
ax.set_title("五个月整体用户漏斗", fontsize=11)
ax.set_xlabel("用户数（万）"); ax.invert_yaxis()

plt.tight_layout(rect=[0,0,1,0.96])
out = f"{D}/act1_dashboard.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
print("saved", out)
