# -*- coding: utf-8 -*-
"""K-Means AI 质量指标（11-25 新增）：内部指标 + 稳定性 + 外部一致性
产出：act3_kmetrics_by_k.csv（k=2~8 内部指标）、act3_k4_metrics.csv（k=4 汇总）、
      act3_kmeans_metrics.png（指标图）
口径：与 act3_kmeans.py 同一特征管道、同一 ORDER BY user_id 输入；
      轮廓系数等在 2 万随机子样上计算（距离矩阵 O(n²)，全量 39.9 万不可行），RandomState(42) 与 k 选型一致。
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd, numpy as np, duckdb, os
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import (silhouette_score, silhouette_samples,
                             calinski_harabasz_score, davies_bouldin_score,
                             adjusted_rand_score, normalized_mutual_info_score)

cands = ["PingFang SC","Hiragino Sans GB","Noto Sans CJK SC","Source Han Sans SC"]
avail = {f.name for f in font_manager.fontManager.ttflist}
use = next((c for c in cands if c in avail), None)
if use: plt.rcParams["font.family"] = use
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["text.parse_math"] = False

D = os.path.dirname(os.path.abspath(__file__))
U = f"{D}/users.parquet"
con = duckdb.connect()

# 与 act3_kmeans.py 完全一致的特征管道（ORDER BY 保证确定性）
df = con.execute(f"""
SELECT user_id, purchase_days, views, carts, removes, purchases, gmv, active_days, recency_days, avg_price_viewed, avg_price_bought
FROM '{U}' WHERE carts > 0 OR purchases > 0 ORDER BY user_id""").df()
feat = pd.DataFrame({
    "log_views": np.log1p(df["views"]), "log_carts": np.log1p(df["carts"]),
    "log_removes": np.log1p(df["removes"]), "log_purchases": np.log1p(df["purchases"]),
    "log_gmv": np.log1p(df["gmv"]), "active_days": df["active_days"],
    "recency": df["recency_days"], "log_price_viewed": np.log1p(df["avg_price_viewed"]),
})
X = StandardScaler().fit_transform(feat)

cl = pd.read_csv(f"{D}/act3_clusters.csv").sort_values("user_id")
assert (cl["user_id"].to_numpy() == df["user_id"].to_numpy()).all(), "聚类标签与用户表顺序不一致"
y4 = cl["cluster"].to_numpy()

rng = np.random.RandomState(42)
idx = rng.choice(len(X), 20000, replace=False)
Xs = X[idx]

# ---------- 1. k=2~8 内部指标（与 act3_kselect 同一子样口径，另加 CH 与 DB） ----------
rows = []
for k in range(2, 9):
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
    rows.append(dict(
        k=k,
        silhouette=round(silhouette_score(Xs, km.labels_[idx]), 4),
        calinski_harabasz=round(calinski_harabasz_score(Xs, km.labels_[idx]), 1),
        davies_bouldin=round(davies_bouldin_score(Xs, km.labels_[idx]), 4),
        inertia=round(km.inertia_, 0),
    ))
by_k = pd.DataFrame(rows)
by_k.to_csv(f"{D}/act3_kmetrics_by_k.csv", index=False)
print("== k=2~8 内部指标 =="); print(by_k.to_string(index=False))

# ---------- 2. k=4 细化指标 ----------
km4 = KMeans(n_clusters=4, n_init=10, random_state=42).fit(X)
# 原始标签每次运行可能整体置换（ARI=1.0、解相同），先按业务键固定映射再对账
_m = df.assign(cluster=km4.labels_).groupby("cluster").agg(
    p=("purchases","mean"), v=("views","mean"), pb=("avg_price_bought","mean"))
_rem = list(_m.index)
_loyal = _m["p"].idxmax(); _rem.remove(_loyal)
_hival = _m.loc[_rem, "pb"].idxmax(); _rem.remove(_hival)
_curious = _m.loc[_rem, "v"].idxmin(); _rem.remove(_curious)
_map = {_loyal: 0, _curious: 1, _rem[0]: 2, _hival: 3}
mapped = pd.Series(km4.labels_).map(_map).to_numpy()
assert (mapped == y4).all(), f"k=4 复跑与落盘标签不一致（确定性检查失败）"
print(f"确定性检查通过（原始标签置换 {dict((int(k),int(v)) for k,v in _map.items())}，映射后与落盘一致）")
sil_overall = silhouette_score(Xs, y4[idx])
sil_per = silhouette_samples(Xs, y4[idx])

# 分簇轮廓（用全量标签在子样上的归属）
per_cluster = {}
for c in range(4):
    m = y4[idx] == c
    per_cluster[c] = round(float(sil_per[m].mean()), 3)

ch = calinski_harabasz_score(Xs, y4[idx])
db = davies_bouldin_score(Xs, y4[idx])

# ---------- 3. split-half 稳定性（AI 指标核心：聚类可复现性） ----------
rng7 = np.random.RandomState(7)
perm = rng7.permutation(len(X))
half = perm[:len(perm)//2]
km_h = KMeans(n_clusters=4, n_init=10, random_state=42).fit(X[half])
stab_ari = adjusted_rand_score(y4[half], km_h.labels_)

# ---------- 4. 外部一致性：与行为分群的 ARI / NMI / Cramér's V ----------
seg = np.select([df.purchase_days>=2, df.purchase_days==1, df.carts>0], [3,2,1], default=0)  # 0纯逛 1加购未买 2单次 3复购
ari_ext = adjusted_rand_score(seg, y4)
nmi_ext = normalized_mutual_info_score(seg, y4)
ct = pd.crosstab(seg, y4)
exp_ = np.outer(ct.sum(1).to_numpy(), ct.sum(0).to_numpy()) / ct.to_numpy().sum()
chi2 = ((ct.to_numpy() - exp_)**2 / exp_).sum()
n = ct.to_numpy().sum()
cramers_v = np.sqrt(chi2 / n / (min(ct.shape) - 1))

k4 = pd.DataFrame([dict(
    n_users=len(df), n_features=X.shape[1],
    silhouette_overall=round(sil_overall, 4),
    silhouette_C0=per_cluster[0], silhouette_C1=per_cluster[1],
    silhouette_C2=per_cluster[2], silhouette_C3=per_cluster[3],
    calinski_harabasz=round(ch, 1), davies_bouldin=round(db, 4),
    split_half_ari=round(stab_ari, 4),
    ari_vs_segments=round(ari_ext, 4), nmi_vs_segments=round(nmi_ext, 4),
    cramers_v_vs_segments=round(cramers_v, 4),
)])
k4.to_csv(f"{D}/act3_k4_metrics.csv", index=False)
print("\n== k=4 汇总 =="); print(k4.T.to_string())

# ---------- 5. 指标图 ----------
NAVY="#1f3a5f"; BLUE="#4a90d9"; ORANGE="#e8862e"; RED="#c0392b"; GREEN="#27ae60"; GRAY="#95a5a6"
fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
fig.suptitle("K-Means 聚类质量指标（k=2~8 扫描与 k=4 定案，39.9 万意向用户，2 万子样评估）",
             fontsize=13, fontweight="bold")

ax = axes[0]
ax.plot(by_k["k"], by_k["silhouette"], "o-", color=NAVY, lw=2, label="轮廓系数")
ax.set_xlabel("k"); ax.set_ylabel("Silhouette", color=NAVY)
ax2 = ax.twinx()
ax2.plot(by_k["k"], by_k["davies_bouldin"], "s--", color=RED, lw=1.5, label="Davies-Bouldin（越低越好）")
ax2.set_ylabel("Davies-Bouldin", color=RED)
ax.axvline(4, color=ORANGE, ls=":", lw=1.5)
ax.set_title("① 内部指标：k≥3 进入平台期\n（k=2 最高但只是买/没买二分）", fontsize=10)
ax.text(4.1, max(by_k["silhouette"])*0.98, "k=4 选定", color=ORANGE, fontsize=9)

ax = axes[1]
cl_names = ["C0 忠诚", "C1 好奇", "C2 犹豫", "C3 高客单"]
vals = [per_cluster[c] for c in range(4)]
bars = ax.bar(cl_names, vals, color=[BLUE, GRAY, ORANGE, GREEN])
for b, v in zip(bars, vals):
    ax.text(b.get_x()+b.get_width()/2, v+0.01, f"{v:.3f}", ha="center", fontsize=9)
ax.axhline(sil_overall, color=RED, ls="--", lw=1.2)
ax.text(0.02, sil_overall+0.012, f"总体 {sil_overall:.3f}", color=RED, fontsize=9)
ax.set_title(f"② 分簇轮廓系数：各簇均 >0\n（凝聚度可接受，C1/C2 天然贴近）", fontsize=10)
ax.set_ylim(0, max(vals)*1.25)

ax = axes[2]
labels = ["split-half\n稳定性 ARI", "vs 行为分群\nARI", "vs 行为分群\nNMI", "vs 行为分群\nCramér's V"]
vals2 = [stab_ari, ari_ext, nmi_ext, cramers_v]
bars = ax.bar(labels, vals2, color=[NAVY, BLUE, GREEN, ORANGE])
for b, v in zip(bars, vals2):
    ax.text(b.get_x()+b.get_width()/2, v+0.02, f"{v:.3f}", ha="center", fontsize=9)
ax.set_ylim(0, 1.15)
ax.set_title("③ 稳定性与外部一致性\n（ARI/NMI/Cramér's V 越接近 1 越一致）", fontsize=10)
ax.tick_params(axis='x', labelsize=8)

plt.tight_layout(rect=[0, 0, 1, 0.90])
plt.savefig(f"{D}/act3_kmeans_metrics.png", dpi=150, bbox_inches="tight")
print("\nsaved act3_kmeans_metrics.png / act3_kmetrics_by_k.csv / act3_k4_metrics.csv")
