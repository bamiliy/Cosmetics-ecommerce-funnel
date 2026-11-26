# -*- coding: utf-8 -*-
import duckdb
P = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data/events.parquet"
con = duckdb.connect(); con.execute("PRAGMA memory_limit='8GB'")
D = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data"

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
