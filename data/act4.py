# -*- coding: utf-8 -*-
import duckdb, pandas as pd
P = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data/events.parquet"
U = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data/users.parquet"
D = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data"
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
