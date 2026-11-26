# -*- coding: utf-8 -*-
import duckdb, pandas as pd, numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
U = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data/users.parquet"
D = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data"
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
