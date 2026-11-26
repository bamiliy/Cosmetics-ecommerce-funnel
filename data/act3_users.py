# -*- coding: utf-8 -*-
import duckdb, time
P = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data/events.parquet"
D = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data"
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
