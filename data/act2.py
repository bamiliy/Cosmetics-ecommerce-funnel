# -*- coding: utf-8 -*-
import duckdb, pandas as pd
P = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data/events.parquet"
D = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data"
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
