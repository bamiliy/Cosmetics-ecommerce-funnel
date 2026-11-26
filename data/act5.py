# -*- coding: utf-8 -*-
import duckdb, pandas as pd
P = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data/events.parquet"
D = "/Users/yun/Documents/Kimi/Workspaces/6301项目/data"
con = duckdb.connect(); con.execute("PRAGMA memory_limit='6GB'")

# ---- 全品牌坑位效率（每浏览 GMV）----
eff = con.execute(f"""
SELECT brand,
  COUNT(*) FILTER (event_type='view') AS v,
  COUNT(*) FILTER (event_type='purchase') AS p,
  ROUND(100.0*COUNT(*) FILTER (event_type='purchase')/COUNT(*) FILTER (event_type='view'),2) AS buy_per_view,
  ROUND(SUM(price) FILTER (event_type='purchase'),0) AS gmv,
  ROUND(SUM(price) FILTER (event_type='purchase')/NULLIF(COUNT(*) FILTER (event_type='purchase'),0),2) AS avg_price,
  ROUND(SUM(price) FILTER (event_type='purchase')/COUNT(*) FILTER (event_type='view'),3) AS gmv_per_view
FROM '{P}' WHERE brand<>'unknown'
GROUP BY 1 HAVING v >= 20000 ORDER BY gmv_per_view DESC""").df()
print("== 坑位效率 TOP10 / 垫底5 =="); print(eff.head(10).to_string(index=False)); print(eff.tail(5).to_string(index=False))
eff.to_csv(f"{D}/act5_slot_efficiency.csv", index=False)

# ---- S5 量化：kapous 挪出 30% 坑位 → 高效品牌篮（strong/uno/cnd/italwax/jessnail）----
donor = eff[eff["brand"]=="kapous"].iloc[0]
basket = eff[eff["brand"].isin(["strong","uno","cnd","italwax","jessnail"])]
basket_rate = (basket["gmv"].sum()/basket["v"].sum())          # 浏览加权 $/view
shift = int(donor["v"]*0.30)
donor_rate = donor["gmv_per_view"]
print(f"\n挪出: kapous {shift:,} 次浏览/5mo @ ${donor_rate}/view = 损失 ${shift*donor_rate:,.0f}")
print(f"接收篮(strong,uno,cnd,italwax,jessnail) 加权效率: ${basket_rate:.3f}/view")
rows=[]
for name, disc in [("保守",1/3),("中性",1/2),("乐观",2/3)]:
    gain = shift*basket_rate*disc
    net  = gain - shift*donor_rate
    rows.append(dict(策略="S5 品牌坑位再分配（kapous→高效品牌篮）", 情景=name, 月挽回GMV=round(net/5)))
    print(f"  {name}(传导率{disc:.0%}): 毛增 ${gain:,.0f} → 净 ${net:,.0f}/5mo = ${net/5:,.0f}/月")
# strong 单独（敏感性）
sr = eff[eff["brand"]=="strong"].iloc[0]["gmv_per_view"]
print(f"  [敏感性] strong 单独接收, 中性传导: 净 ${shift*(sr*0.5-donor_rate)/5:,.0f}/月")
s5 = pd.DataFrame(rows)
s5.to_csv(f"{D}/act5_s5_ledger.csv", index=False)

# ---- 簇 × 品牌画像 ----
cl = pd.read_csv(f"{D}/act3_clusters.csv")
con.register("clusters", cl)
cb = con.execute(f"""
WITH e AS (
  SELECT c.cluster, e.brand, e.event_type, e.price
  FROM '{P}' e JOIN clusters c USING (user_id)
  WHERE e.brand <> 'unknown')
SELECT cluster, brand,
  COUNT(*) FILTER (event_type='view') AS v,
  ROUND(SUM(price) FILTER (event_type='purchase'),0) AS gmv,
  ROUND(100.0*COUNT(*) FILTER (event_type='remove_from_cart')
        /NULLIF(COUNT(*) FILTER (event_type='cart'),0),1) AS remove_rate
FROM e GROUP BY 1,2
QUALIFY ROW_NUMBER() OVER (PARTITION BY cluster ORDER BY gmv DESC) <= 5
ORDER BY cluster, gmv DESC""").df()
print("\n== 各簇 TOP5 品牌（按 GMV）=="); print(cb.to_string(index=False))
cb.to_csv(f"{D}/act5_cluster_brands.csv", index=False)
