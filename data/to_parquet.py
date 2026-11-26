import duckdb, time, os
D = os.path.dirname(os.path.abspath(__file__))
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
