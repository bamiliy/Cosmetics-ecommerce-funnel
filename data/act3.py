# -*- coding: utf-8 -*-
import duckdb, pandas as pd
U = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data/users.parquet"
D = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data"
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
