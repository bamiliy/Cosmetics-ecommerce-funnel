# -*- coding: utf-8 -*-
import duckdb, pandas as pd, numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

U = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data/users.parquet"
D = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data"
con = duckdb.connect()

# ---- 修复洛伦兹：全量买家先算累计，再均匀抽样 ----
lor = con.execute(f"""
WITH b AS (SELECT gmv, ROW_NUMBER() OVER (ORDER BY gmv DESC) rn, COUNT(*) OVER() n
           FROM '{U}' WHERE purchases>0),
c AS (SELECT rn, n, 100.0*rn/n AS buyer_pct,
             100.0*SUM(gmv) OVER (ORDER BY rn)/SUM(gmv) OVER() AS gmv_cum
      FROM b)
SELECT buyer_pct, ROUND(gmv_cum,1) AS gmv_cum FROM c ORDER BY rn
""").df()
step = max(1, len(lor)//200)
lor_s = pd.concat([lor.iloc[::step], lor.iloc[[-1]]]).drop_duplicates("buyer_pct")
lor_s.to_csv(f"{D}/act3_lorenz.csv", index=False)
print("lorenz fixed: rows", len(lor_s), "| head:", lor_s.head(3).values.tolist(), "| tail:", lor_s.tail(2).values.tolist())

# ---- K 选型证据：k=2..8 轮廓系数（2万抽样，距离矩阵 O(n²) 需降采样） ----
df = con.execute(f"""
SELECT user_id, views, carts, removes, purchases, gmv, active_days, recency_days, avg_price_viewed
FROM '{U}' WHERE carts > 0 OR purchases > 0 ORDER BY user_id""").df()
feat = pd.DataFrame({
    "log_views": np.log1p(df["views"]), "log_carts": np.log1p(df["carts"]),
    "log_removes": np.log1p(df["removes"]), "log_purchases": np.log1p(df["purchases"]),
    "log_gmv": np.log1p(df["gmv"]), "active_days": df["active_days"],
    "recency": df["recency_days"], "log_price_viewed": np.log1p(df["avg_price_viewed"]),
})
X = StandardScaler().fit_transform(feat)
rng = np.random.RandomState(42)
idx = rng.choice(len(X), 20000, replace=False)
Xs = X[idx]
rows = []
for k in range(2, 9):
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
    sil = silhouette_score(Xs, km.labels_[idx])
    rows.append(dict(k=k, silhouette=round(sil, 4), inertia=round(km.inertia_, 0)))
    print(f"k={k}  silhouette={sil:.4f}  inertia={km.inertia_:,.0f}")
sel = pd.DataFrame(rows)
sel.to_csv(f"{D}/act3_kselect.csv", index=False)
