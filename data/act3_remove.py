# -*- coding: utf-8 -*-
"""加购未买 × 移除行为三层细分（11-25 新增，第三幕补充）
口径：用户级（users.parquet 全期汇总）；重新加购为「商品对」级（user×product，严格时间序）
产出：act3_remove_tiers.csv / act3_remove_recart.csv
"""
import duckdb, pandas as pd, os

D = os.path.dirname(os.path.abspath(__file__))
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
