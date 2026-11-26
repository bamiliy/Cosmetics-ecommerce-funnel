# -*- coding: utf-8 -*-
import duckdb, pandas as pd
P = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data/events.parquet"
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

monthly.to_csv("/Users/yun/Documents/Kimi/Workspaces/6301项目/data/act1_monthly.csv", index=False)
funnel_m.to_csv("/Users/yun/Documents/Kimi/Workspaces/6301项目/data/act1_funnel_monthly.csv", index=False)
weekly.to_csv("/Users/yun/Documents/Kimi/Workspaces/6301项目/data/act1_weekly.csv", index=False)
print("\nsaved csvs")
