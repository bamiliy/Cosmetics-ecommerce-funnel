# -*- coding: utf-8 -*-
import duckdb
P = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data/events.parquet"
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
