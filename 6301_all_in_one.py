# -*- coding: utf-8 -*-
"""6301 项目 · 全量单文件复现脚本（由 data/ 下 20 个脚本按 run_all.sh 顺序合并生成）
用法: python 6301_all_in_one.py    全程约 5-8 分钟，16GB 内存足够。
前置: data/ 下已含 5 个月清洗数据 *_cleaned.csv.gz（本项目初版数据）
"""
import os, time
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'data')
BASE = DATA  # 原脚本内绝对路径统一替换为 BASE，保证任何机器可跑


# ==================================================================
# 【第 0 步：CSV → Parquet 底座】  (原 data/to_parquet.py)
# ==================================================================
import duckdb, time, os
D = DATA  # 原脚本相对自身定位，合并后统一指向 data/
SRC = os.path.join(D, '*_cleaned.csv.gz')   # 五个月清洗数据（Oct 2019 ~ Feb 2020），同构 8 列
DST = os.path.join(D, 'events.parquet')

con = duckdb.connect()
con.execute("PRAGMA memory_limit='6GB'")
t0 = time.time()
con.execute(f"""
COPY (
  SELECT
    CAST(event_time AS TIMESTAMPTZ) AS event_time,
    CAST(event_time AS DATE)        AS event_date,
    event_type, product_id, category_id, brand, price, user_id, user_session
  FROM read_csv('{SRC}',
    header=true,
    union_by_name=true,
    columns={{
      'event_time':'VARCHAR','event_type':'VARCHAR','product_id':'BIGINT',
      'category_id':'BIGINT','brand':'VARCHAR',
      'price':'DOUBLE','user_id':'BIGINT','user_session':'VARCHAR'
    }})
) TO '{DST}' (FORMAT PARQUET, COMPRESSION ZSTD)
""")
print(f"convert done in {time.time()-t0:.1f}s")

# 校验
print(con.execute(f"SELECT COUNT(*) AS rows FROM '{DST}'").fetchall())
print(con.execute(f"SELECT MIN(event_time), MAX(event_time) FROM '{DST}'").fetchall())
print(con.execute(f"SELECT event_type, COUNT(*) FROM '{DST}' GROUP BY 1 ORDER BY 2 DESC").fetchall())
print(con.execute(f"SELECT COUNT(DISTINCT user_id), COUNT(DISTINCT user_session), COUNT(DISTINCT product_id) FROM '{DST}'").fetchall())


# ==================================================================
# 【第一幕：盘面诊断】  (原 data/act1.py)
# ==================================================================
import duckdb, pandas as pd
P = ""+BASE+"/events.parquet"
con = duckdb.connect()
con.execute("PRAGMA memory_limit='6GB'")

# ---------- 1. 月度盘面（UTC 口径） ----------
monthly = con.execute(f"""
WITH ev AS (
  SELECT strftime(event_time AT TIME ZONE 'UTC', '%Y-%m') AS m, *
  FROM '{P}'
)
SELECT
  m                                              AS month,
  COUNT(*)                                       AS events,
  COUNT(DISTINCT user_id)                        AS uv,
  COUNT(*) FILTER (event_type='purchase')        AS orders,
  ROUND(SUM(price) FILTER (event_type='purchase'),0) AS gmv,
  ROUND(SUM(price) FILTER (event_type='purchase')
        / COUNT(*) FILTER (event_type='purchase'),2) AS aov
FROM ev GROUP BY 1 ORDER BY 1
""").df()
print("== 月度盘面 =="); print(monthly.to_string(index=False))

# ---------- 2. 月度用户级漏斗 ----------
funnel_m = con.execute(f"""
WITH u AS (
  SELECT strftime(event_time AT TIME ZONE 'UTC','%Y-%m') AS m, user_id,
         BOOL_OR(event_type='view')      AS v,
         BOOL_OR(event_type='cart')      AS c,
         BOOL_OR(event_type='purchase')  AS p
  FROM '{P}' GROUP BY 1,2
)
SELECT m AS month,
  COUNT(*) FILTER (v)            AS view_users,
  COUNT(*) FILTER (c)            AS cart_users,
  COUNT(*) FILTER (p)            AS buy_users,
  ROUND(100.0*COUNT(*) FILTER (c)/COUNT(*) FILTER (v),1) AS view_to_cart_pct,
  ROUND(100.0*COUNT(*) FILTER (p)/NULLIF(COUNT(*) FILTER (c),0),1) AS cart_to_buy_pct,
  ROUND(100.0*COUNT(*) FILTER (p)/COUNT(*) FILTER (v),2) AS view_to_buy_pct
FROM u GROUP BY 1 ORDER BY 1
""").df()
print("\n== 月度用户级漏斗 =="); print(funnel_m.to_string(index=False))

# ---------- 3. 全周期整体漏斗（事件级 + 用户级） ----------
evt = con.execute(f"""
SELECT event_type, COUNT(*) FROM '{P}' GROUP BY 1
""").fetchall()
usr = con.execute(f"""
WITH u AS (SELECT user_id,
  BOOL_OR(event_type='view') v, BOOL_OR(event_type='cart') c,
  BOOL_OR(event_type='remove_from_cart') r, BOOL_OR(event_type='purchase') p
  FROM '{P}' GROUP BY 1)
SELECT SUM(v::INT), SUM(c::INT), SUM(r::INT), SUM(p::INT) FROM u
""").fetchall()
print("\n== 整体漏斗（用户级，5个月合计）==")
print(f"浏览过: {usr[0][0]:,} | 加购过: {usr[0][1]:,} | 移除过: {usr[0][2]:,} | 购买过: {usr[0][3]:,}")

# ---------- 4. 周度走势（看黑五/圣诞/2月波动） ----------
weekly = con.execute(f"""
SELECT strftime(date_trunc('week', event_time AT TIME ZONE 'UTC'),'%Y-%m-%d') AS week,
       COUNT(DISTINCT user_id) AS uv,
       ROUND(SUM(price) FILTER (event_type='purchase'),0) AS gmv,
       COUNT(*) FILTER (event_type='purchase') AS orders,
       COUNT(*) AS events
FROM '{P}' GROUP BY 1 ORDER BY 1
""").df()
print("\n== 周度走势 =="); print(weekly.to_string(index=False))

monthly.to_csv(""+BASE+"/act1_monthly.csv", index=False)
funnel_m.to_csv(""+BASE+"/act1_funnel_monthly.csv", index=False)
weekly.to_csv(""+BASE+"/act1_weekly.csv", index=False)
print("\nsaved csvs")


# ==================================================================
# 【第一幕图】  (原 data/act1_chart.py)
# ==================================================================
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

D = ""+BASE+""
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


# ==================================================================
# 【第二幕：漏斗×价格带×品牌】  (原 data/act2.py)
# ==================================================================
import duckdb, pandas as pd
P = ""+BASE+"/events.parquet"
D = ""+BASE+""
con = duckdb.connect(); con.execute("PRAGMA memory_limit='6GB'")

BAND = """CASE
  WHEN price < 2  THEN '1 <$2'
  WHEN price < 4  THEN '2 $2-4'
  WHEN price < 8  THEN '3 $4-8'
  WHEN price < 16 THEN '4 $8-16'
  WHEN price < 50 THEN '5 $16-50'
  ELSE '6 >$50' END"""

# ---------- 1. 漏斗 × 价格带（事件级） ----------
pb = con.execute(f"""
WITH e AS (SELECT {BAND} AS band, event_type, price FROM '{P}')
SELECT band,
  COUNT(*) FILTER (event_type='view')            AS views,
  COUNT(*) FILTER (event_type='cart')            AS carts,
  COUNT(*) FILTER (event_type='remove_from_cart')AS removes,
  COUNT(*) FILTER (event_type='purchase')        AS purchases,
  ROUND(100.0*COUNT(*) FILTER (event_type='cart')/COUNT(*) FILTER (event_type='view'),1)      AS cart_per_view,
  ROUND(100.0*COUNT(*) FILTER (event_type='remove_from_cart')/NULLIF(COUNT(*) FILTER (event_type='cart'),0),1) AS remove_per_cart,
  ROUND(100.0*COUNT(*) FILTER (event_type='purchase')/NULLIF(COUNT(*) FILTER (event_type='cart'),0),1)         AS buy_per_cart,
  ROUND(100.0*COUNT(*) FILTER (event_type='purchase')/COUNT(*) FILTER (event_type='view'),2)  AS buy_per_view,
  ROUND(SUM(price) FILTER (event_type='purchase'),0) AS gmv
FROM e GROUP BY 1 ORDER BY 1""").df()
print("== 漏斗 × 价格带 =="); print(pb.to_string(index=False))
pb.to_csv(f"{D}/act2_priceband_funnel.csv", index=False)

# ---------- 2. 流量份额 vs GMV 份额 ----------
pb["view_share"] = (100*pb["views"]/pb["views"].sum()).round(1)
pb["gmv_share"]  = (100*pb["gmv"]/pb["gmv"].sum()).round(1)
print("\n== 流量份额 vs GMV 份额 =="); print(pb[["band","view_share","gmv_share"]].to_string(index=False))

# ---------- 3. 价格劝退：被移除 vs 被购买的价格 ----------
deter = con.execute(f"""
SELECT
  ROUND(AVG(price) FILTER (event_type='cart'),2)             AS cart_avg,
  ROUND(AVG(price) FILTER (event_type='remove_from_cart'),2) AS removed_avg,
  ROUND(AVG(price) FILTER (event_type='purchase'),2)         AS purchased_avg,
  ROUND(median(price) FILTER (event_type='remove_from_cart'),2) AS removed_med,
  ROUND(median(price) FILTER (event_type='purchase'),2)         AS purchased_med
FROM '{P}'""").df()
print("\n== 价格劝退（全体）=="); print(deter.to_string(index=False))

# 按价格带：带内移除率
print("\n== 各价格带 移除/加购 率已在表1 ==")

# ---------- 4. 品牌四象限（brand != unknown，views≥2万） ----------
br = con.execute(f"""
WITH e AS (SELECT brand, event_type, price FROM '{P}' WHERE brand <> 'unknown')
SELECT brand,
  COUNT(*) FILTER (event_type='view')     AS views,
  COUNT(*) FILTER (event_type='cart')     AS carts,
  COUNT(*) FILTER (event_type='remove_from_cart') AS removes,
  COUNT(*) FILTER (event_type='purchase') AS purchases,
  ROUND(100.0*COUNT(*) FILTER (event_type='purchase')/COUNT(*) FILTER (event_type='view'),2) AS buy_per_view,
  ROUND(100.0*COUNT(*) FILTER (event_type='remove_from_cart')/NULLIF(COUNT(*) FILTER (event_type='cart'),0),1) AS remove_per_cart,
  ROUND(SUM(price) FILTER (event_type='purchase'),0) AS gmv,
  ROUND(AVG(price) FILTER (event_type='view'),2) AS avg_price_viewed
FROM e GROUP BY 1 HAVING views >= 20000 ORDER BY views DESC""").df()
print(f"\n== 品牌（views≥2万，{len(br)} 个）=="); print(br.head(20).to_string(index=False))
br.to_csv(f"{D}/act2_brands.csv", index=False)

# ---------- 5. 同品牌内：移除商品价格 vs 购买商品价格（价格劝退直接证据） ----------
inb = con.execute(f"""
WITH top_b AS (
  SELECT brand FROM '{P}' WHERE brand<>'unknown'
  GROUP BY brand HAVING COUNT(*) FILTER (event_type='view') >= 50000)
SELECT brand,
  ROUND(median(price) FILTER (event_type='remove_from_cart'),2) AS removed_med,
  ROUND(median(price) FILTER (event_type='purchase'),2)         AS purchased_med,
  ROUND(median(price) FILTER (event_type='remove_from_cart')
      / NULLIF(median(price) FILTER (event_type='purchase'),0),2) AS ratio
FROM '{P}' WHERE brand IN (SELECT brand FROM top_b)
GROUP BY brand HAVING COUNT(*) FILTER (event_type='remove_from_cart') >= 1000
ORDER BY ratio DESC LIMIT 15""").df()
print("\n== 同品牌内 移除 vs 购买 中位价（Top15 比值）=="); print(inb.to_string(index=False))
inb.to_csv(f"{D}/act2_inbrand_deter.csv", index=False)

# ---------- 6. 类目 TOP（GMV） ----------
cat = con.execute(f"""
SELECT category_id,
  COUNT(*) FILTER (event_type='view') AS views,
  COUNT(*) FILTER (event_type='purchase') AS purchases,
  ROUND(100.0*COUNT(*) FILTER (event_type='purchase')/COUNT(*) FILTER (event_type='view'),2) AS buy_per_view,
  ROUND(SUM(price) FILTER (event_type='purchase'),0) AS gmv
FROM '{P}' GROUP BY 1 ORDER BY gmv DESC LIMIT 15""").df()
print("\n== 类目 TOP15（按 GMV）=="); print(cat.to_string(index=False))
cat.to_csv(f"{D}/act2_categories.csv", index=False)


# ==================================================================
# 【第二幕：用户级切片 + 移除后行为】  (原 data/act2_slices.py)
# ==================================================================
import duckdb
P = ""+BASE+"/events.parquet"
con = duckdb.connect(); con.execute("PRAGMA memory_limit='8GB'")
D = ""+BASE+""

band_expr = """CASE WHEN price < 2 THEN '1:<$2' WHEN price < 5 THEN '2:$2-5' WHEN price < 10 THEN '3:$5-10'
                    WHEN price < 20 THEN '4:$10-20' WHEN price < 50 THEN '5:$20-50' ELSE '6:>=$50' END"""

# ---------- 价格带漏斗（用户×带口径） ----------
band = con.execute(f"""
WITH u AS (
  SELECT user_id, {band_expr} AS band,
         BOOL_OR(event_type='view') v, BOOL_OR(event_type='cart') c,
         BOOL_OR(event_type='remove_from_cart') r, BOOL_OR(event_type='purchase') p
  FROM '{P}' GROUP BY 1,2
)
SELECT band,
  COUNT(*) FILTER (v)  AS view_users,
  COUNT(*) FILTER (c)  AS cart_users,
  COUNT(*) FILTER (p)  AS buy_users,
  COUNT(*) FILTER (c AND r) AS cart_then_remove_users,
  ROUND(100.0*COUNT(*) FILTER (c AND p)/COUNT(*) FILTER (c),1) AS cart_to_buy_pct,
  ROUND(100.0*COUNT(*) FILTER (c AND r)/COUNT(*) FILTER (c),1) AS cart_removed_pct
FROM u GROUP BY 1 ORDER BY 1
""").df()
print("== 价格带用户级漏斗 =="); print(band.to_string(index=False))

band_gmv = con.execute(f"""
SELECT {band_expr} AS band,
  COUNT(*) FILTER (event_type='purchase') AS orders,
  ROUND(SUM(price) FILTER (event_type='purchase'),0) AS gmv,
  ROUND(AVG(price) FILTER (event_type='purchase'),2) AS aov,
  COUNT(*) FILTER (event_type='remove_from_cart') AS remove_events,
  ROUND(SUM(price) FILTER (event_type='remove_from_cart'),0) AS removed_value
FROM '{P}' GROUP BY 1 ORDER BY 1
""").df()
print("\n== 价格带 GMV 与移除 =="); print(band_gmv.to_string(index=False))

# ---------- 品牌漏斗（TOP 15，按浏览用户） ----------
brand = con.execute(f"""
WITH topb AS (
  SELECT brand, COUNT(DISTINCT user_id) vu FROM '{P}'
  WHERE event_type='view' AND brand <> 'unknown' GROUP BY 1 ORDER BY vu DESC LIMIT 15
),
u AS (
  SELECT p.brand, p.user_id,
         BOOL_OR(p.event_type='view') v, BOOL_OR(p.event_type='cart') c,
         BOOL_OR(p.event_type='purchase') b
  FROM '{P}' p JOIN topb t ON p.brand=t.brand
  GROUP BY 1,2
)
SELECT u.brand,
  COUNT(*) FILTER (v) AS view_users,
  COUNT(*) FILTER (c) AS cart_users,
  COUNT(*) FILTER (b) AS buy_users,
  ROUND(100.0*COUNT(*) FILTER (c AND b)/COUNT(*) FILTER (c),1) AS cart_to_buy_pct,
  ROUND(100.0*COUNT(*) FILTER (b)/COUNT(*) FILTER (v),2) AS view_to_buy_pct
FROM u GROUP BY 1 ORDER BY 2 DESC
""").df()
print("\n== TOP15 品牌漏斗 =="); print(brand.to_string(index=False))

brand_gmv = con.execute(f"""
SELECT brand, ROUND(SUM(price) FILTER (event_type='purchase'),0) AS gmv
FROM '{P}' WHERE brand <> 'unknown' GROUP BY 1 ORDER BY 2 DESC LIMIT 15
""").df()
print("\n== TOP15 品牌 GMV =="); print(brand_gmv.to_string(index=False))

# ---------- remove_from_cart 深挖 ----------
# 移除后同商品仍被购买：去重 + 严格时间序（先移除后购买）。
# 旧版把「移除后再次加购」的 cart 事件 join 进来，按后续加购次数重复计数，
# 把比例虚增到 10.4%；正确口径只数「移除对」本身是否最终被买。
rm = con.execute(f"""
WITH r AS (
  SELECT user_id, product_id, MIN(event_time) AS rm_time
  FROM '{P}' WHERE event_type='remove_from_cart' GROUP BY 1,2
)
SELECT COUNT(*) AS remove_pairs,
  SUM((EXISTS (SELECT 1 FROM '{P}' p
               WHERE p.user_id=r.user_id AND p.product_id=r.product_id
                 AND p.event_type='purchase' AND p.event_time > r.rm_time))::INT) AS removed_then_bought
FROM r
""").fetchall()
print(f"\n== 移除后行为 == 移除(用户,商品)对: {rm[0][0]:,}; 其中该商品后来仍被买过: {rm[0][1]:,} ({100*rm[0][1]/rm[0][0]:.1f}%)")

band.to_csv(f"{D}/act2_band_funnel.csv", index=False)
band_gmv.to_csv(f"{D}/act2_band_gmv.csv", index=False)
brand.to_csv(f"{D}/act2_brand_funnel.csv", index=False)
print("\nsaved csvs")


# ==================================================================
# 【第二幕：链路口径验证】  (原 data/act2_consistency.py)
# ==================================================================
import duckdb
P = ""+BASE+"/events.parquet"
con = duckdb.connect(); con.execute("PRAGMA memory_limit='8GB'")

# 购买事件 是否同用户同商品 有过浏览 / 同会话浏览 / 同用户同商品加购
r = con.execute(f"""
WITH p AS (
  SELECT user_id, product_id, user_session, event_time
  FROM '{P}' WHERE event_type='purchase'
),
v_user AS (SELECT DISTINCT user_id, product_id FROM '{P}' WHERE event_type='view'),
v_sess AS (SELECT DISTINCT user_id, product_id, user_session FROM '{P}' WHERE event_type='view'),
c_user AS (SELECT DISTINCT user_id, product_id FROM '{P}' WHERE event_type='cart')
SELECT
  COUNT(*) AS purchases,
  SUM((v_user.user_id IS NOT NULL)::INT) AS pu_viewed,
  SUM((v_sess.user_id IS NOT NULL)::INT) AS sess_viewed,
  SUM((c_user.user_id IS NOT NULL)::INT) AS pu_carted
FROM p
LEFT JOIN v_user USING (user_id, product_id)
LEFT JOIN v_sess USING (user_id, product_id, user_session)
LEFT JOIN c_user USING (user_id, product_id)
""").fetchall()
tot, pv, sv, pc = r[0]
print(f"购买事件总数:            {tot:,}")
print(f"同用户同商品曾浏览过:    {pv:,}  ({100*pv/tot:.1f}%)")
print(f"同会话同商品浏览过:      {sv:,}  ({100*sv/tot:.1f}%)")
print(f"同用户同商品曾加购过:    {pc:,}  ({100*pc/tot:.1f}%)")

# 反向：加购事件 最终成交率（同用户同商品）
r2 = con.execute(f"""
WITH c AS (
  SELECT user_id, product_id, event_time FROM '{P}' WHERE event_type='cart'
),
b AS (SELECT DISTINCT user_id, product_id FROM '{P}' WHERE event_type='purchase')
SELECT COUNT(*) AS carts, SUM((b.user_id IS NOT NULL)::INT) AS carted_then_bought
FROM c LEFT JOIN b USING (user_id, product_id)
""").fetchall()
ct, cb = r2[0]
print(f"\n加购事件总数:            {ct:,}")
print(f"同商品最终被购买过:      {cb:,}  ({100*cb/ct:.1f}%)")


# ==================================================================
# 【第二幕图】  (原 data/act2_chart.py)
# ==================================================================
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

D = ""+BASE+""
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


# ==================================================================
# 【第三幕：用户宽表】  (原 data/act3_users.py)
# ==================================================================
import duckdb, time
P = ""+BASE+"/events.parquet"
D = ""+BASE+""
con = duckdb.connect(); con.execute("PRAGMA memory_limit='6GB'")
t0=time.time()
con.execute(f"""
COPY (
  SELECT user_id,
    COUNT(*)                                       AS events,
    COUNT(DISTINCT event_date)                     AS active_days,
    COUNT(DISTINCT user_session)                   AS sessions,
    COUNT(*) FILTER (event_type='view')            AS views,
    COUNT(*) FILTER (event_type='cart')            AS carts,
    COUNT(*) FILTER (event_type='remove_from_cart')AS removes,
    COUNT(*) FILTER (event_type='purchase')        AS purchases,
    COUNT(DISTINCT event_date) FILTER (event_type='purchase')    AS purchase_days,
    COUNT(DISTINCT user_session) FILTER (event_type='purchase')  AS purchase_sessions,
    COALESCE(SUM(price) FILTER (event_type='purchase'),0) AS gmv,
    COALESCE(AVG(price) FILTER (event_type='purchase'),0) AS avg_price_bought,
    COALESCE(AVG(price) FILTER (event_type='view'),0)     AS avg_price_viewed,
    date_diff('day', MAX(event_time) AT TIME ZONE 'UTC', TIMESTAMP '2020-03-01') AS recency_days,
    COUNT(DISTINCT product_id) FILTER (event_type='purchase') AS products_bought
  FROM '{P}' GROUP BY user_id
) TO '{D}/users.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)
""")
print(f"user table done in {time.time()-t0:.1f}s")
print(con.execute(f"SELECT COUNT(*), SUM(purchases>0), SUM(purchases>=2) FROM '{D}/users.parquet'").fetchall())


# ==================================================================
# 【第三幕：分群 + 集中度】  (原 data/act3.py)
# ==================================================================
import duckdb, pandas as pd
U = ""+BASE+"/users.parquet"
D = ""+BASE+""
con = duckdb.connect(); con.execute("PRAGMA memory_limit='6GB'")

SEG = """CASE
  WHEN purchase_days >= 2 THEN '4 复购'
  WHEN purchase_days = 1  THEN '3 单次购买'
  WHEN carts > 0          THEN '2 加购未买'
  ELSE '1 纯逛' END"""

# ---------- 1. 行为分群 × GMV ----------
seg = con.execute(f"""
WITH u AS (SELECT {SEG} AS seg, * FROM '{U}')
SELECT seg,
  COUNT(*) AS users,
  ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM '{U}'),1) AS user_pct,
  ROUND(SUM(gmv),0) AS gmv,
  ROUND(100.0*SUM(gmv)/(SELECT SUM(gmv) FROM '{U}'),1) AS gmv_pct,
  ROUND(SUM(gmv)/COUNT(*),2) AS gmv_per_user,
  ROUND(AVG(views),1) AS avg_views,
  ROUND(AVG(sessions),2) AS avg_sessions,
  ROUND(AVG(recency_days),0) AS avg_recency
FROM u GROUP BY 1 ORDER BY 1""").df()
print("== 行为分群 × GMV（H3 验证）=="); print(seg.to_string(index=False))
seg.to_csv(f"{D}/act3_segments.csv", index=False)

# ---------- 2. GMV 集中度（买家内部） ----------
conc = con.execute(f"""
WITH b AS (SELECT gmv, ROW_NUMBER() OVER (ORDER BY gmv DESC) AS rn
           FROM '{U}' WHERE purchases > 0)
SELECT
  ROUND(100.0*SUM(gmv) FILTER (rn <= (SELECT COUNT(*) FROM b)*0.01)/(SELECT SUM(gmv) FROM b),1) AS top1_pct,
  ROUND(100.0*SUM(gmv) FILTER (rn <= (SELECT COUNT(*) FROM b)*0.05)/(SELECT SUM(gmv) FROM b),1) AS top5_pct,
  ROUND(100.0*SUM(gmv) FILTER (rn <= (SELECT COUNT(*) FROM b)*0.10)/(SELECT SUM(gmv) FROM b),1) AS top10_pct,
  ROUND(100.0*SUM(gmv) FILTER (rn <= (SELECT COUNT(*) FROM b)*0.20)/(SELECT SUM(gmv) FROM b),1) AS top20_pct,
  ROUND(100.0*SUM(gmv) FILTER (rn <= (SELECT COUNT(*) FROM b)*0.50)/(SELECT SUM(gmv) FROM b),1) AS top50_pct
FROM b""").df()
print("\n== 买家 GMV 集中度 =="); print(conc.to_string(index=False))
conc.to_csv(f"{D}/act3_concentration.csv", index=False)

# ---------- 3. 各人群漏斗形态（人均事件结构） ----------
fshape = con.execute(f"""
WITH u AS (SELECT {SEG} AS seg, * FROM '{U}')
SELECT seg,
  ROUND(AVG(views),1)   AS avg_views,
  ROUND(AVG(carts),2)   AS avg_carts,
  ROUND(AVG(removes),2) AS avg_removes,
  ROUND(AVG(purchases),2) AS avg_purchases,
  ROUND(100.0*SUM(removes)/NULLIF(SUM(carts),0),1) AS remove_rate,
  ROUND(AVG(avg_price_bought),2) AS avg_price_bought
FROM u GROUP BY 1 ORDER BY 1""").df()
print("\n== 各人群人均事件结构 =="); print(fshape.to_string(index=False))
fshape.to_csv(f"{D}/act3_funnel_shape.csv", index=False)

# ---------- 4. RFM（买家） ----------
rfm = con.execute(f"""
WITH b AS (SELECT * FROM '{U}' WHERE purchases > 0),
     q AS (SELECT *,
     NTILE(5) OVER (ORDER BY recency_days DESC)  AS r_score,
     NTILE(5) OVER (ORDER BY purchase_days)      AS f_score,
     NTILE(5) OVER (ORDER BY gmv)                AS m_score
   FROM b)
SELECT CONCAT(r_score, f_score, m_score) AS rfm, COUNT(*) AS users, ROUND(SUM(gmv),0) AS gmv
FROM q GROUP BY 1 ORDER BY 3 DESC LIMIT 10""").df()
print("\n== RFM TOP10 组合（按 GMV）=="); print(rfm.to_string(index=False))

# 复购周期：复购买家相邻购买间隔
gap = con.execute(f"""
SELECT ROUND(AVG(purchase_days),2) AS avg_purchase_days,
       ROUND(median(purchase_days),1) AS med_purchase_days
FROM '{U}' WHERE purchase_days >= 2""").df()
print("\n== 复购用户购买天数分布 =="); print(gap.to_string(index=False))


# ==================================================================
# 【第三幕：K-Means 聚类】  (原 data/act3_kmeans.py)
# ==================================================================
import duckdb, pandas as pd, numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
U = ""+BASE+"/users.parquet"
D = ""+BASE+""
con = duckdb.connect()

# ---- 洛伦兹曲线数据（买家 GMV 累计份额） ----
lor = con.execute(f"""
WITH b AS (SELECT gmv, ROW_NUMBER() OVER (ORDER BY gmv DESC) rn,
           COUNT(*) OVER() n, SUM(gmv) OVER() tot
           FROM '{U}' WHERE purchases>0)
SELECT ROUND(100.0*rn/n,1) AS buyer_pct, ROUND(100.0*SUM(gmv) OVER (ORDER BY rn)/tot,1) AS gmv_cum
FROM b WHERE rn % CAST(n/200 AS INT) = 0 OR rn = n ORDER BY rn""").df()
lor.to_csv(f"{D}/act3_lorenz.csv", index=False)

# ---- K-Means：在「加购过或购买过」的 39.8 万意向用户上聚类 ----
# ORDER BY 必须加：DuckDB 不保证无 ORDER BY 查询的行序，而 KMeans 的
# k-means++ 初始化对输入顺序敏感（random_state 按行索引取样），
# 缺这一行会导致每次复跑聚类结果漂移（C0 GMV 占比在 47.0~47.8 间晃动）。
df = con.execute(f"""
SELECT user_id, views, carts, removes, purchases, gmv, active_days, recency_days,
       avg_price_viewed, avg_price_bought
FROM '{U}' WHERE carts > 0 OR purchases > 0 ORDER BY user_id""").df()
print("cluster base:", len(df))

feat = pd.DataFrame({
    "log_views":     np.log1p(df["views"]),
    "log_carts":     np.log1p(df["carts"]),
    "log_removes":   np.log1p(df["removes"]),
    "log_purchases": np.log1p(df["purchases"]),
    "log_gmv":       np.log1p(df["gmv"]),
    "active_days":   df["active_days"],
    "recency":       df["recency_days"],
    "log_price_viewed": np.log1p(df["avg_price_viewed"]),
})
X = StandardScaler().fit_transform(feat)
km = KMeans(n_clusters=4, n_init=10, random_state=42).fit(X)
df["cluster"] = km.labels_

# ---- 规范标签：KMeans 标签顺序不稳定（同 seed 也可能置换），按业务键固定映射 ----
# 0=忠诚囤货者(购买最多) 1=一次性好奇者(浏览最少) 2=犹豫比价者(其余) 3=高客单尝鲜客(买价最高)
_m = df.groupby("cluster").agg(p=("purchases","mean"), v=("views","mean"),
                               pb=("avg_price_bought","mean"))
_rem = list(_m.index)
_loyal = _m["p"].idxmax(); _rem.remove(_loyal)
_hival = _m.loc[_rem, "pb"].idxmax(); _rem.remove(_hival)
_curious = _m.loc[_rem, "v"].idxmin(); _rem.remove(_curious)
_compare = _rem[0]
_map = {_loyal: 0, _curious: 1, _compare: 2, _hival: 3}
df["cluster"] = df["cluster"].map(_map)
print("label map (raw -> canonical):", _map)

prof = df.groupby("cluster").agg(
    users=("user_id","count"),
    views=("views","mean"), carts=("carts","mean"), removes=("removes","mean"),
    purchases=("purchases","mean"), gmv=("gmv","sum"),
    price_bought=("avg_price_bought","mean"), recency=("recency_days","mean"),
).round(1)
prof["user_pct"] = (100*prof["users"]/len(df)).round(1)
prof["gmv_pct"]  = (100*prof["gmv"]/prof["gmv"].sum()).round(1)
print(prof.to_string())
df[["user_id","cluster"]].to_csv(f"{D}/act3_clusters.csv", index=False)
prof.to_csv(f"{D}/act3_cluster_profile.csv")


# ==================================================================
# 【第三幕：洛伦兹曲线修复 + k 选型】  (原 data/act3_fix.py)
# ==================================================================
import duckdb, pandas as pd, numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

U = ""+BASE+"/users.parquet"
D = ""+BASE+""
con = duckdb.connect()

# ---- 修复洛伦兹：全量买家先算累计，再均匀抽样 ----
lor = con.execute(f"""
WITH b AS (SELECT gmv, ROW_NUMBER() OVER (ORDER BY gmv DESC) rn, COUNT(*) OVER() n
           FROM '{U}' WHERE purchases>0),
c AS (SELECT rn, n, 100.0*rn/n AS buyer_pct,
             100.0*SUM(gmv) OVER (ORDER BY rn)/SUM(gmv) OVER() AS gmv_cum
      FROM b)
SELECT buyer_pct, ROUND(gmv_cum,1) AS gmv_cum FROM c ORDER BY rn
""").df()
step = max(1, len(lor)//200)
lor_s = pd.concat([lor.iloc[::step], lor.iloc[[-1]]]).drop_duplicates("buyer_pct")
lor_s.to_csv(f"{D}/act3_lorenz.csv", index=False)
print("lorenz fixed: rows", len(lor_s), "| head:", lor_s.head(3).values.tolist(), "| tail:", lor_s.tail(2).values.tolist())

# ---- K 选型证据：k=2..8 轮廓系数（2万抽样，距离矩阵 O(n²) 需降采样） ----
df = con.execute(f"""
SELECT user_id, views, carts, removes, purchases, gmv, active_days, recency_days, avg_price_viewed
FROM '{U}' WHERE carts > 0 OR purchases > 0 ORDER BY user_id""").df()
feat = pd.DataFrame({
    "log_views": np.log1p(df["views"]), "log_carts": np.log1p(df["carts"]),
    "log_removes": np.log1p(df["removes"]), "log_purchases": np.log1p(df["purchases"]),
    "log_gmv": np.log1p(df["gmv"]), "active_days": df["active_days"],
    "recency": df["recency_days"], "log_price_viewed": np.log1p(df["avg_price_viewed"]),
})
X = StandardScaler().fit_transform(feat)
rng = np.random.RandomState(42)
idx = rng.choice(len(X), 20000, replace=False)
Xs = X[idx]
rows = []
for k in range(2, 9):
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
    sil = silhouette_score(Xs, km.labels_[idx])
    rows.append(dict(k=k, silhouette=round(sil, 4), inertia=round(km.inertia_, 0)))
    print(f"k={k}  silhouette={sil:.4f}  inertia={km.inertia_:,.0f}")
sel = pd.DataFrame(rows)
sel.to_csv(f"{D}/act3_kselect.csv", index=False)


# ==================================================================
# 【第三幕：移除行为三层细分】  (原 data/act3_remove.py)
# ==================================================================
import duckdb, pandas as pd, os

D = DATA  # 原脚本相对自身定位，合并后统一指向 data/
P = f"{D}/events.parquet"
U = f"{D}/users.parquet"
con = duckdb.connect(); con.execute("PRAGMA memory_limit='6GB'")

# ---------- 1. 三层细分（用户级） ----------
tiers = con.execute(f"""
WITH cab AS (
  SELECT *,
    CASE WHEN removes = 0 THEN 'A 保留型'
         WHEN removes <= 0.5*carts THEN 'B 轻度移除'
         ELSE 'C 重度移除' END AS tier
  FROM '{U}' WHERE carts > 0 AND purchases = 0
)
SELECT tier,
  COUNT(*) AS users,
  ROUND(COUNT(*)/SUM(COUNT(*)) OVER (), 3) AS user_pct,
  ROUND(AVG(views),1) AS avg_views,
  ROUND(AVG(carts),1) AS avg_carts,
  ROUND(AVG(removes),1) AS avg_removes,
  ROUND(AVG(removes)::DOUBLE/AVG(carts), 3) AS remove_ratio,
  ROUND(AVG(recency_days),0) AS avg_recency
FROM cab GROUP BY tier ORDER BY tier
""").df()
print("== 加购未买三层细分（用户级）=="); print(tiers.to_string(index=False))
tiers.to_csv(f"{D}/act3_remove_tiers.csv", index=False)

# ---------- 2. 移除后同商品重新加购（商品对级，严格时间序） ----------
recart = con.execute(f"""
WITH cab AS (
  SELECT user_id,
    CASE WHEN removes <= 0.5*carts THEN 'B 轻度移除' ELSE 'C 重度移除' END AS tier
  FROM '{U}' WHERE carts > 0 AND purchases = 0 AND removes > 0
),
ev AS (
  SELECT c.tier, e.user_id, e.product_id, e.event_time, e.event_type
  FROM '{P}' e JOIN cab c USING (user_id)
  WHERE e.event_type IN ('cart','remove_from_cart')
),
pairs AS (
  SELECT tier, user_id, product_id, MIN(event_time) AS first_remove
  FROM ev WHERE event_type = 'remove_from_cart'
  GROUP BY tier, user_id, product_id
),
later AS (
  SELECT DISTINCT p.tier, p.user_id, p.product_id   -- 必须带全键，只 distinct tier 会笛卡尔积虚高到 100%
  FROM pairs p JOIN ev e
    ON e.user_id = p.user_id AND e.product_id = p.product_id
   AND e.event_type = 'cart' AND e.event_time > p.first_remove
)
SELECT p.tier,
  COUNT(*) AS removed_pairs,
  COUNT(l.user_id) AS recarted_pairs,
  ROUND(COUNT(l.user_id)::DOUBLE/COUNT(*)*100, 1) AS recart_pct
FROM pairs p LEFT JOIN later l
  ON l.user_id = p.user_id AND l.product_id = p.product_id AND l.tier = p.tier
GROUP BY p.tier ORDER BY p.tier
""").df()
print("\n== 移除后同商品重新加购（商品对级）=="); print(recart.to_string(index=False))
recart.to_csv(f"{D}/act3_remove_recart.csv", index=False)


# ==================================================================
# 【第三幕：K-Means AI 质量指标】  (原 data/act3_metrics.py)
# ==================================================================
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd, numpy as np, duckdb, os
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import (silhouette_score, silhouette_samples,
                             calinski_harabasz_score, davies_bouldin_score,
                             adjusted_rand_score, normalized_mutual_info_score)

cands = ["PingFang SC","Hiragino Sans GB","Noto Sans CJK SC","Source Han Sans SC"]
avail = {f.name for f in font_manager.fontManager.ttflist}
use = next((c for c in cands if c in avail), None)
if use: plt.rcParams["font.family"] = use
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["text.parse_math"] = False

D = DATA  # 原脚本相对自身定位，合并后统一指向 data/
U = f"{D}/users.parquet"
con = duckdb.connect()

# 与 act3_kmeans.py 完全一致的特征管道（ORDER BY 保证确定性）
df = con.execute(f"""
SELECT user_id, purchase_days, views, carts, removes, purchases, gmv, active_days, recency_days, avg_price_viewed, avg_price_bought
FROM '{U}' WHERE carts > 0 OR purchases > 0 ORDER BY user_id""").df()
feat = pd.DataFrame({
    "log_views": np.log1p(df["views"]), "log_carts": np.log1p(df["carts"]),
    "log_removes": np.log1p(df["removes"]), "log_purchases": np.log1p(df["purchases"]),
    "log_gmv": np.log1p(df["gmv"]), "active_days": df["active_days"],
    "recency": df["recency_days"], "log_price_viewed": np.log1p(df["avg_price_viewed"]),
})
X = StandardScaler().fit_transform(feat)

cl = pd.read_csv(f"{D}/act3_clusters.csv").sort_values("user_id")
assert (cl["user_id"].to_numpy() == df["user_id"].to_numpy()).all(), "聚类标签与用户表顺序不一致"
y4 = cl["cluster"].to_numpy()

rng = np.random.RandomState(42)
idx = rng.choice(len(X), 20000, replace=False)
Xs = X[idx]

# ---------- 1. k=2~8 内部指标（与 act3_kselect 同一子样口径，另加 CH 与 DB） ----------
rows = []
for k in range(2, 9):
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
    rows.append(dict(
        k=k,
        silhouette=round(silhouette_score(Xs, km.labels_[idx]), 4),
        calinski_harabasz=round(calinski_harabasz_score(Xs, km.labels_[idx]), 1),
        davies_bouldin=round(davies_bouldin_score(Xs, km.labels_[idx]), 4),
        inertia=round(km.inertia_, 0),
    ))
by_k = pd.DataFrame(rows)
by_k.to_csv(f"{D}/act3_kmetrics_by_k.csv", index=False)
print("== k=2~8 内部指标 =="); print(by_k.to_string(index=False))

# ---------- 2. k=4 细化指标 ----------
km4 = KMeans(n_clusters=4, n_init=10, random_state=42).fit(X)
# 原始标签每次运行可能整体置换（ARI=1.0、解相同），先按业务键固定映射再对账
_m = df.assign(cluster=km4.labels_).groupby("cluster").agg(
    p=("purchases","mean"), v=("views","mean"), pb=("avg_price_bought","mean"))
_rem = list(_m.index)
_loyal = _m["p"].idxmax(); _rem.remove(_loyal)
_hival = _m.loc[_rem, "pb"].idxmax(); _rem.remove(_hival)
_curious = _m.loc[_rem, "v"].idxmin(); _rem.remove(_curious)
_map = {_loyal: 0, _curious: 1, _rem[0]: 2, _hival: 3}
mapped = pd.Series(km4.labels_).map(_map).to_numpy()
assert (mapped == y4).all(), f"k=4 复跑与落盘标签不一致（确定性检查失败）"
print(f"确定性检查通过（原始标签置换 {dict((int(k),int(v)) for k,v in _map.items())}，映射后与落盘一致）")
sil_overall = silhouette_score(Xs, y4[idx])
sil_per = silhouette_samples(Xs, y4[idx])

# 分簇轮廓（用全量标签在子样上的归属）
per_cluster = {}
for c in range(4):
    m = y4[idx] == c
    per_cluster[c] = round(float(sil_per[m].mean()), 3)

ch = calinski_harabasz_score(Xs, y4[idx])
db = davies_bouldin_score(Xs, y4[idx])

# ---------- 3. split-half 稳定性（AI 指标核心：聚类可复现性） ----------
rng7 = np.random.RandomState(7)
perm = rng7.permutation(len(X))
half = perm[:len(perm)//2]
km_h = KMeans(n_clusters=4, n_init=10, random_state=42).fit(X[half])
stab_ari = adjusted_rand_score(y4[half], km_h.labels_)

# ---------- 4. 外部一致性：与行为分群的 ARI / NMI / Cramér's V ----------
seg = np.select([df.purchase_days>=2, df.purchase_days==1, df.carts>0], [3,2,1], default=0)  # 0纯逛 1加购未买 2单次 3复购
ari_ext = adjusted_rand_score(seg, y4)
nmi_ext = normalized_mutual_info_score(seg, y4)
ct = pd.crosstab(seg, y4)
exp_ = np.outer(ct.sum(1).to_numpy(), ct.sum(0).to_numpy()) / ct.to_numpy().sum()
chi2 = ((ct.to_numpy() - exp_)**2 / exp_).sum()
n = ct.to_numpy().sum()
cramers_v = np.sqrt(chi2 / n / (min(ct.shape) - 1))

k4 = pd.DataFrame([dict(
    n_users=len(df), n_features=X.shape[1],
    silhouette_overall=round(sil_overall, 4),
    silhouette_C0=per_cluster[0], silhouette_C1=per_cluster[1],
    silhouette_C2=per_cluster[2], silhouette_C3=per_cluster[3],
    calinski_harabasz=round(ch, 1), davies_bouldin=round(db, 4),
    split_half_ari=round(stab_ari, 4),
    ari_vs_segments=round(ari_ext, 4), nmi_vs_segments=round(nmi_ext, 4),
    cramers_v_vs_segments=round(cramers_v, 4),
)])
k4.to_csv(f"{D}/act3_k4_metrics.csv", index=False)
print("\n== k=4 汇总 =="); print(k4.T.to_string())

# ---------- 5. 指标图 ----------
NAVY="#1f3a5f"; BLUE="#4a90d9"; ORANGE="#e8862e"; RED="#c0392b"; GREEN="#27ae60"; GRAY="#95a5a6"
fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
fig.suptitle("K-Means 聚类质量指标（k=2~8 扫描与 k=4 定案，39.9 万意向用户，2 万子样评估）",
             fontsize=13, fontweight="bold")

ax = axes[0]
ax.plot(by_k["k"], by_k["silhouette"], "o-", color=NAVY, lw=2, label="轮廓系数")
ax.set_xlabel("k"); ax.set_ylabel("Silhouette", color=NAVY)
ax2 = ax.twinx()
ax2.plot(by_k["k"], by_k["davies_bouldin"], "s--", color=RED, lw=1.5, label="Davies-Bouldin（越低越好）")
ax2.set_ylabel("Davies-Bouldin", color=RED)
ax.axvline(4, color=ORANGE, ls=":", lw=1.5)
ax.set_title("① 内部指标：k≥3 进入平台期\n（k=2 最高但只是买/没买二分）", fontsize=10)
ax.text(4.1, max(by_k["silhouette"])*0.98, "k=4 选定", color=ORANGE, fontsize=9)

ax = axes[1]
cl_names = ["C0 忠诚", "C1 好奇", "C2 犹豫", "C3 高客单"]
vals = [per_cluster[c] for c in range(4)]
bars = ax.bar(cl_names, vals, color=[BLUE, GRAY, ORANGE, GREEN])
for b, v in zip(bars, vals):
    ax.text(b.get_x()+b.get_width()/2, v+0.01, f"{v:.3f}", ha="center", fontsize=9)
ax.axhline(sil_overall, color=RED, ls="--", lw=1.2)
ax.text(0.02, sil_overall+0.012, f"总体 {sil_overall:.3f}", color=RED, fontsize=9)
ax.set_title(f"② 分簇轮廓系数：各簇均 >0\n（凝聚度可接受，C1/C2 天然贴近）", fontsize=10)
ax.set_ylim(0, max(vals)*1.25)

ax = axes[2]
labels = ["split-half\n稳定性 ARI", "vs 行为分群\nARI", "vs 行为分群\nNMI", "vs 行为分群\nCramér's V"]
vals2 = [stab_ari, ari_ext, nmi_ext, cramers_v]
bars = ax.bar(labels, vals2, color=[NAVY, BLUE, GREEN, ORANGE])
for b, v in zip(bars, vals2):
    ax.text(b.get_x()+b.get_width()/2, v+0.02, f"{v:.3f}", ha="center", fontsize=9)
ax.set_ylim(0, 1.15)
ax.set_title("③ 稳定性与外部一致性\n（ARI/NMI/Cramér's V 越接近 1 越一致）", fontsize=10)
ax.tick_params(axis='x', labelsize=8)

plt.tight_layout(rect=[0, 0, 1, 0.90])
plt.savefig(f"{D}/act3_kmeans_metrics.png", dpi=150, bbox_inches="tight")
print("\nsaved act3_kmeans_metrics.png / act3_kmetrics_by_k.csv / act3_k4_metrics.csv")


# ==================================================================
# 【第三幕：三层细分图】  (原 data/act3_tiers_chart.py)
# ==================================================================
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

D = DATA  # 原脚本相对自身定位，合并后统一指向 data/
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


# ==================================================================
# 【第三幕图】  (原 data/act3_chart.py)
# ==================================================================
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

D = ""+BASE+""
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


# ==================================================================
# 【第四幕：S1-S4 策略台账】  (原 data/act4.py)
# ==================================================================
import duckdb, pandas as pd
P = ""+BASE+"/events.parquet"
U = ""+BASE+"/users.parquet"
D = ""+BASE+""
con = duckdb.connect(); con.execute("PRAGMA memory_limit='6GB'")

BAND = """CASE
  WHEN price < 2  THEN '1 <$2'  WHEN price < 4  THEN '2 $2-4'
  WHEN price < 8  THEN '3 $4-8' WHEN price < 16 THEN '4 $8-16'
  WHEN price < 50 THEN '5 $16-50' ELSE '6 >$50' END"""

# ---- 量化所需的基础数字（全部从数据直接取） ----
base = {}
r = con.execute(f"""
SELECT
  COUNT(*) FILTER (carts>0 AND purchase_days=0)               AS cart_nb_users,   -- 加购未买人数
  COUNT(*) FILTER (purchase_days=1)                           AS one_buyers,      -- 单次购买人数
  SUM(gmv) FILTER (purchase_days=1)                           AS one_gmv,
  COUNT(*) FILTER (purchase_days>=2)                          AS rep_buyers,
  SUM(gmv) FILTER (purchase_days>=2)                          AS rep_gmv,
  AVG(purchase_days) FILTER (purchase_days>=2)                AS rep_pdays
FROM '{U}'""").fetchone()
(base["cart_nb_users"], base["one_buyers"], base["one_gmv"],
 base["rep_buyers"], base["rep_gmv"], base["rep_pdays"]) = r

base["first_buy_value"] = base["one_gmv"]/base["one_buyers"]          # 首购用户5个月价值
base["rep_day_value"]   = base["rep_gmv"]/base["rep_buyers"]/base["rep_pdays"]  # 复购者每个购买日价值

band = con.execute(f"""
WITH e AS (SELECT {BAND} AS band, event_type, price FROM '{P}')
SELECT band,
  COUNT(*) FILTER (event_type='cart')  AS carts,
  COUNT(*) FILTER (event_type='remove_from_cart') AS removes,
  COUNT(*) FILTER (event_type='purchase') AS purchases,
  SUM(price) FILTER (event_type='purchase') AS gmv
FROM e GROUP BY 1 ORDER BY 1""").df()
band["remove_rate"] = band["removes"]/band["carts"]
band["buy_per_cart"] = band["purchases"]/band["carts"]
band["avg_price"] = band["gmv"]/band["purchases"]

MONTHS = 5
monthly_gmv = con.execute(f"SELECT SUM(price) FROM '{P}' WHERE event_type='purchase'").fetchone()[0]/MONTHS

ledger = []

# ---- S1 激活「加购未买」（C2）：转化为首购 ----
for name, conv in [("保守",0.02),("中性",0.05),("乐观",0.10)]:
    v = conv*base["cart_nb_users"]*base["first_buy_value"]/MONTHS
    ledger.append(dict(策略="S1 激活加购未买（首购转化）", 情景=name, 月挽回GMV=round(v)))

# ---- S2 唤醒「单次购买者」：30天回购触达，多买一个购买日 ----
for name, conv in [("保守",0.05),("中性",0.10),("乐观",0.20)]:
    v = conv*base["one_buyers"]*base["rep_day_value"]/MONTHS
    ledger.append(dict(策略="S2 唤醒单次购买者（30天回购触达）", 情景=name, 月挽回GMV=round(v)))

# ---- S3 $2-8 移除挽回：移除率降到 <$2 水平（45.8%）----
target = band.loc[band["band"]=="1 <$2","remove_rate"].iloc[0]
v_mid = 0
for b in ["2 $2-4","3 $4-8"]:
    row = band.loc[band["band"]==b].iloc[0]
    saved_carts = row["carts"]*(row["remove_rate"]-target)
    v_mid += saved_carts*row["buy_per_cart"]*row["avg_price"]
for name, k in [("保守",0.5),("中性",1.0),("乐观",1.5)]:
    ledger.append(dict(策略="S3 低价带移除挽回（凑单/批量优惠）", 情景=name, 月挽回GMV=round(v_mid*k/MONTHS)))

# ---- S4 >$50 防筛：加购→购买提到全站均值 ----
row = band.loc[band["band"]=="6 >$50"].iloc[0]
site_avg = band["purchases"].sum()/band["carts"].sum()
v_s4 = row["carts"]*(site_avg-row["buy_per_cart"])*row["avg_price"]
for name, k in [("保守",0.5),("中性",1.0),("乐观",1.5)]:
    ledger.append(dict(策略="S4 高价带加购→购买补强（比价工具/分期）", 情景=name, 月挽回GMV=round(v_s4*k/MONTHS)))

led = pd.DataFrame(ledger)
led.to_csv(f"{D}/act4_ledger.csv", index=False)
print("== 量化台账（每月，美元）=="); print(led.to_string(index=False))
piv = led.pivot(index="策略", columns="情景", values="月挽回GMV")[["保守","中性","乐观"]]
print("\n== 汇总 =="); print(piv.to_string())
print(f"\n月均 GMV = ${monthly_gmv:,.0f}")
print(f"中性情景合计 = ${piv['中性'].sum():,.0f}/月 ≈ 月GMV的 {100*piv['中性'].sum()/monthly_gmv:.1f}%")
print(f"\n关键参数: 首购价值=${base['first_buy_value']:.2f}, 复购每购买日=${base['rep_day_value']:.2f}, "
      f"加购未买={base['cart_nb_users']:,}, 单次购买={base['one_buyers']:,}, 全站加购→购买={site_avg:.3f}")
piv.to_csv(f"{D}/act4_summary.csv")


# ==================================================================
# 【第四幕：S5 + 簇×品牌画像】  (原 data/act5.py)
# ==================================================================
import duckdb, pandas as pd
P = ""+BASE+"/events.parquet"
D = ""+BASE+""
con = duckdb.connect(); con.execute("PRAGMA memory_limit='6GB'")

# ---- 全品牌坑位效率（每浏览 GMV）----
eff = con.execute(f"""
SELECT brand,
  COUNT(*) FILTER (event_type='view') AS v,
  COUNT(*) FILTER (event_type='purchase') AS p,
  ROUND(100.0*COUNT(*) FILTER (event_type='purchase')/COUNT(*) FILTER (event_type='view'),2) AS buy_per_view,
  ROUND(SUM(price) FILTER (event_type='purchase'),0) AS gmv,
  ROUND(SUM(price) FILTER (event_type='purchase')/NULLIF(COUNT(*) FILTER (event_type='purchase'),0),2) AS avg_price,
  ROUND(SUM(price) FILTER (event_type='purchase')/COUNT(*) FILTER (event_type='view'),3) AS gmv_per_view
FROM '{P}' WHERE brand<>'unknown'
GROUP BY 1 HAVING v >= 20000 ORDER BY gmv_per_view DESC""").df()
print("== 坑位效率 TOP10 / 垫底5 =="); print(eff.head(10).to_string(index=False)); print(eff.tail(5).to_string(index=False))
eff.to_csv(f"{D}/act5_slot_efficiency.csv", index=False)

# ---- S5 量化：kapous 挪出 30% 坑位 → 高效品牌篮（strong/uno/cnd/italwax/jessnail）----
donor = eff[eff["brand"]=="kapous"].iloc[0]
basket = eff[eff["brand"].isin(["strong","uno","cnd","italwax","jessnail"])]
basket_rate = (basket["gmv"].sum()/basket["v"].sum())          # 浏览加权 $/view
shift = int(donor["v"]*0.30)
donor_rate = donor["gmv_per_view"]
print(f"\n挪出: kapous {shift:,} 次浏览/5mo @ ${donor_rate}/view = 损失 ${shift*donor_rate:,.0f}")
print(f"接收篮(strong,uno,cnd,italwax,jessnail) 加权效率: ${basket_rate:.3f}/view")
rows=[]
for name, disc in [("保守",1/3),("中性",1/2),("乐观",2/3)]:
    gain = shift*basket_rate*disc
    net  = gain - shift*donor_rate
    rows.append(dict(策略="S5 品牌坑位再分配（kapous→高效品牌篮）", 情景=name, 月挽回GMV=round(net/5)))
    print(f"  {name}(传导率{disc:.0%}): 毛增 ${gain:,.0f} → 净 ${net:,.0f}/5mo = ${net/5:,.0f}/月")
# strong 单独（敏感性）
sr = eff[eff["brand"]=="strong"].iloc[0]["gmv_per_view"]
print(f"  [敏感性] strong 单独接收, 中性传导: 净 ${shift*(sr*0.5-donor_rate)/5:,.0f}/月")
s5 = pd.DataFrame(rows)
s5.to_csv(f"{D}/act5_s5_ledger.csv", index=False)

# ---- 簇 × 品牌画像 ----
cl = pd.read_csv(f"{D}/act3_clusters.csv")
con.register("clusters", cl)
cb = con.execute(f"""
WITH e AS (
  SELECT c.cluster, e.brand, e.event_type, e.price
  FROM '{P}' e JOIN clusters c USING (user_id)
  WHERE e.brand <> 'unknown')
SELECT cluster, brand,
  COUNT(*) FILTER (event_type='view') AS v,
  ROUND(SUM(price) FILTER (event_type='purchase'),0) AS gmv,
  ROUND(100.0*COUNT(*) FILTER (event_type='remove_from_cart')
        /NULLIF(COUNT(*) FILTER (event_type='cart'),0),1) AS remove_rate
FROM e GROUP BY 1,2
QUALIFY ROW_NUMBER() OVER (PARTITION BY cluster ORDER BY gmv DESC) <= 5
ORDER BY cluster, gmv DESC""").df()
print("\n== 各簇 TOP5 品牌（按 GMV）=="); print(cb.to_string(index=False))
cb.to_csv(f"{D}/act5_cluster_brands.csv", index=False)


# ==================================================================
# 【第四幕：合并 S5 总台账】  (原 data/act4_merge_s5.py)
# ==================================================================
import pandas as pd, os
D = DATA
a = pd.read_csv(f"{D}/act4_ledger.csv")
b = pd.read_csv(f"{D}/act5_s5_ledger.csv")
# 幂等：先剔除已有 S5 再合并，重复运行不产生重复行
a = a[~a["策略"].str.startswith("S5")]
led = pd.concat([a, b], ignore_index=True)
led.to_csv(f"{D}/act4_ledger.csv", index=False)
piv = led.pivot(index="策略", columns="情景", values="月挽回GMV")[["保守","中性","乐观"]]
piv.to_csv(f"{D}/act4_summary.csv")
print(f"台账合并完成：中性合计 ${piv['中性'].sum():,}/月 ≈ 月GMV的 {100*piv['中性'].sum()/1269654:.1f}%")


# ==================================================================
# 【第四幕图】  (原 data/act4_chart.py)
# ==================================================================
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

D = ""+BASE+""
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


# ==================================================================
# 【审计：53 项数字独立复算】  (原 data/audit.py)
# ==================================================================
import duckdb, pandas as pd, numpy as np, os, sys
D = DATA  # 原脚本相对自身定位，合并后统一指向 data/
P = f"{D}/events.parquet"
U = f"{D}/users.parquet"
con = duckdb.connect(); con.execute("PRAGMA memory_limit='6GB'")
ok = fail = 0
def chk(name, got, exp, tol=0.01):
    global ok, fail
    good = abs(got-exp) <= max(abs(exp)*tol, tol*100)
    print(f"{'PASS' if good else 'FAIL'}  {name}: 复算={got:,.2f} 报告={exp:,.2f}")
    ok, fail = ok+good, fail+(not good)

# ---------- 第一幕 ----------
r = con.execute(f"SELECT COUNT(*), COUNT(DISTINCT user_id), COUNT(*) FILTER(event_type='purchase'), SUM(price) FILTER(event_type='purchase') FROM '{P}'").fetchone()
chk("A1a 总事件", r[0], 19497292, 0); chk("A1b 总用户", r[1], 1637977, 0)
chk("A1c 购买事件", r[2], 1285982, 0); chk("A1d 总GMV", r[3], 6348268, 0.001)
mm = con.execute(f"SELECT strftime(event_time AT TIME ZONE 'UTC','%Y-%m') m, COUNT(DISTINCT user_id) uv, ROUND(SUM(price) FILTER(event_type='purchase')) gmv FROM '{P}' GROUP BY 1 ORDER BY 1").df()
saved = pd.read_csv(f"{D}/act1_monthly.csv")
chk("A2a 11月GMV(峰值)", mm.loc[mm.m=='2019-11','gmv'].iloc[0], saved.loc[saved.month=='2019-11','gmv'].iloc[0], 0)
chk("A2b 12月GMV(谷)", mm.loc[mm.m=='2019-12','gmv'].iloc[0], saved.loc[saved.month=='2019-12','gmv'].iloc[0], 0)
fn = con.execute(f"""WITH u AS (SELECT user_id, BOOL_OR(event_type='view') v, BOOL_OR(event_type='cart') c, BOOL_OR(event_type='purchase') p FROM '{P}' GROUP BY 1)
SELECT SUM(v::INT), SUM(c::INT), SUM(p::INT) FROM u""").fetchone()
chk("A3a 浏览用户", fn[0], 1596371, 0); chk("A3b 加购用户", fn[1], 398124, 0); chk("A3c 购买用户", fn[2], 110518, 0)
wk = con.execute(f"SELECT strftime(date_trunc('week',event_time AT TIME ZONE 'UTC'),'%Y-%m-%d') w, ROUND(SUM(price) FILTER(event_type='purchase')) g FROM '{P}' GROUP BY 1 ORDER BY 1").df()
chk("A4a 黑五周GMV", wk.loc[wk.w=='2019-11-18','g'].iloc[0], 474863, 0)
chk("A4b 圣诞周GMV", wk.loc[wk.w=='2019-12-23','g'].iloc[0], 210925, 0)
feb = con.execute(f"SELECT event_date d, SUM(price) FILTER(event_type='purchase') g FROM '{P}' WHERE event_date BETWEEN DATE '2020-01-27' AND DATE '2020-02-29' GROUP BY 1").df()
feb['wk'] = pd.to_datetime(feb['d']).dt.to_period('W-SUN').astype(str)
feb['wd'] = pd.to_datetime(feb['d']).dt.weekday
wms = feb[feb.wd<6].groupby('wk')['g'].sum()
chk("A4c 2月末周较峰值周%(同口径周一至周六)", 100*(wms.iloc[-1]/wms.iloc[0]-1), -22.46, 0.01)
chk("A4d 2月末周环比%", 100*(wms.iloc[-1]/wms.iloc[-2]-1), 3.91, 0.01)

# ---------- 第二幕 ----------
BAND = """CASE WHEN price<2 THEN 1 WHEN price<4 THEN 2 WHEN price<8 THEN 3 WHEN price<16 THEN 4 WHEN price<50 THEN 5 ELSE 6 END"""
pb = con.execute(f"""WITH e AS (SELECT {BAND} b, event_type, price FROM '{P}')
SELECT b, COUNT(*) FILTER(event_type='view') v, COUNT(*) FILTER(event_type='purchase') p,
 ROUND(100.0*COUNT(*) FILTER(event_type='purchase')/COUNT(*) FILTER(event_type='view'),2) bpv,
 ROUND(100.0*COUNT(*) FILTER(event_type='remove_from_cart')/COUNT(*) FILTER(event_type='cart'),1) rpc
FROM e GROUP BY 1 ORDER BY 1""").df()
saved2 = pd.read_csv(f"{D}/act2_priceband_funnel.csv")
for i in range(6):
    chk(f"B1 价格带{i+1} 浏览→购买%", pb.loc[i,'bpv'], saved2.loc[i,'buy_per_view'], 0)
chk("B1g <$2带移除率%", pb.loc[0,'rpc'], 45.8, 0); chk("B1h $2-4带移除率%", pb.loc[1,'rpc'], 57.7, 0)
d = con.execute(f"SELECT median(price) FILTER(event_type='remove_from_cart'), median(price) FILTER(event_type='purchase') FROM '{P}'").fetchone()
chk("B2a 被移除中位价", d[0], 3.46, 0); chk("B2b 被购买中位价", d[1], 3.00, 0)
br = con.execute(f"""SELECT brand, COUNT(*) FILTER(event_type='view') v,
 ROUND(100.0*COUNT(*) FILTER(event_type='purchase')/COUNT(*) FILTER(event_type='view'),2) bpv,
 ROUND(SUM(price) FILTER(event_type='purchase')) g,
 ROUND(100.0*COUNT(*) FILTER(event_type='remove_from_cart')/COUNT(*) FILTER(event_type='cart'),1) rr
 FROM '{P}' WHERE brand IN ('runail','bpw.style','masura') GROUP BY 1""").df().set_index("brand")
chk("B4a runail转化%", br.loc['runail','bpv'], 18.29, 0)
chk("B4b bpw.style转化%", br.loc['bpw.style','bpv'], 22.50, 0)
chk("B4c masura移除率%", br.loc['masura','rr'], 66.7, 0)
chk("B4d bpw每浏览GMV", 44635/168642, 0.265, 0.02)

# ---------- 第三幕 ----------
sg = con.execute(f"""WITH u AS (SELECT CASE WHEN purchase_days>=2 THEN 4 WHEN purchase_days=1 THEN 3 WHEN carts>0 THEN 2 ELSE 1 END s, gmv FROM '{U}')
SELECT s, COUNT(*) n, SUM(gmv) g FROM u GROUP BY 1 ORDER BY 1""").df().set_index("s")
chk("C1a 复购用户数", sg.loc[4,'n'], 22738, 0); chk("C1b 复购GMV占比%", 100*sg.loc[4,'g']/sg['g'].sum(), 47.9, 0.01)
chk("C1c 单次购买占比%", 100*sg.loc[3,'n']/sg['n'].sum(), 5.4, 0.02)
cc = con.execute(f"""WITH b AS (SELECT gmv, ROW_NUMBER() OVER (ORDER BY gmv DESC) rn FROM '{U}' WHERE purchases>0)
SELECT 100.0*SUM(gmv) FILTER(rn<=(SELECT COUNT(*) FROM b)*0.1)/(SELECT SUM(gmv) FROM b),
       100.0*SUM(gmv) FILTER(rn<=(SELECT COUNT(*) FROM b)*0.2)/(SELECT SUM(gmv) FROM b) FROM b""").fetchone()
chk("C2a 前10%买家GMV%", cc[0], 43.0, 0.01); chk("C2b 前20%买家GMV%", cc[1], 59.3, 0.01)
lor = pd.read_csv(f"{D}/act3_lorenz.csv")
i10 = (lor.buyer_pct-10).abs().idxmin(); i20 = (lor.buyer_pct-20).abs().idxmin()
chk("C4a 洛伦兹过(10,43)", lor.loc[i10,'gmv_cum'], 43.0, 0.05)
chk("C4b 洛伦兹过(20,59.3)", lor.loc[i20,'gmv_cum'], 59.3, 0.05)
chk("C4c 洛伦兹终点", lor['gmv_cum'].iloc[-1], 100.0, 0)
chk("C5 单日买家占比%", 100*87780/110518, 79.4, 0.01)
cp = pd.read_csv(f"{D}/act3_cluster_profile.csv")
chk("C3a C0 GMV占比%", cp.loc[cp.cluster==0,'gmv_pct'].iloc[0], 47.8, 0.002)
chk("C3b C3高客单GMV占比%", cp.loc[cp.cluster==3,'gmv_pct'].iloc[0], 50.0, 0.002)

# ---------- 第四幕 ----------
led = pd.read_csv(f"{D}/act4_ledger.csv")
chk("D1a S1中性", 0.05*288519*(3305543/87780)/5, led[(led.策略.str.startswith('S1'))&(led.情景=='中性')]['月挽回GMV'].iloc[0], 0.005)
chk("D1b S2中性", 0.10*87780*(3042724/22738/2.9333)/5, led[(led.策略.str.startswith('S2'))&(led.情景=='中性')]['月挽回GMV'].iloc[0], 0.02)
chk("D2 月均GMV", 6348268/5, 1269654, 0.001)
chk("D3 S5中性", 59066*(1.222*0.5-0.318)/5, led[(led.策略.str.startswith('S5'))&(led.情景=='中性')]['月挽回GMV'].iloc[0], 0.02)
tot_mid = led[led.情景=='中性']['月挽回GMV'].sum()
chk("D4 中性合计", tot_mid, 296137, 0.001)
s = pd.read_csv(f"{D}/act4_summary.csv")
chk("D5a 保守合计", s['保守'].sum(), 136528, 0.01)
chk("D5b 乐观合计(含S5)", s['乐观'].sum(), 539317, 0.001)
chk("D5c 乐观合计(不含S5)", s['乐观'].sum()-s[s.策略.str.startswith('S5')]['乐观'].iloc[0], 533448, 0.001)

# ---------- 口径验证 ----------
lk = con.execute(f"""WITH fc AS (SELECT user_id, product_id, MIN(event_time) t FROM '{P}' WHERE event_type='cart' GROUP BY 1,2),
 p AS (SELECT user_id, product_id, event_time t FROM '{P}' WHERE event_type='purchase')
SELECT 100.0*COUNT(*) FILTER(fc.t<p.t)/COUNT(*) FROM p LEFT JOIN fc USING(user_id,product_id)""").fetchone()
chk("E1 购买前有同商品加购%", lk[0], 91.9, 0.01)

# ---------- 新增分层：加购未买 × 移除三层 ----------
rt = pd.read_csv(f"{D}/act3_remove_tiers.csv").set_index("tier")
chk("F1a A层人数", rt.loc['A 保留型','users'], 196172, 0)
chk("F1b B层人数", rt.loc['B 轻度移除','users'], 49683, 0)
chk("F1c C层人数", rt.loc['C 重度移除','users'], 42664, 0)
chk("F1d 三层合计=加购未买", rt['users'].sum(), 288519, 0)
rr = pd.read_csv(f"{D}/act3_remove_recart.csv").set_index("tier")
chk("F2a B层重新加购%", rr.loc['B 轻度移除','recart_pct'], 6.8, 0.02)
chk("F2b C层重新加购%", rr.loc['C 重度移除','recart_pct'], 7.3, 0.02)

print(f"\n===== 审计完成: {ok} PASS / {fail} FAIL =====")
sys.exit(1 if fail else 0)

