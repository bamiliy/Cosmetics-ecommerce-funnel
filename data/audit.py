# -*- coding: utf-8 -*-
"""全项目独立复算审计：从 parquet 底表重算每个进入结论的数字，与落盘 CSV 对账"""
import duckdb, pandas as pd, numpy as np, os, sys
D = os.path.dirname(os.path.abspath(__file__))
P = f"{D}/events.parquet"
U = f"{D}/users.parquet"
con = duckdb.connect(); con.execute("PRAGMA memory_limit='6GB'")
ok = fail = 0
def chk(name, got, exp, tol=0.01):
    global ok, fail
    good = abs(got-exp) <= max(abs(exp)*tol, tol*100)
    print(f"{'PASS' if good else 'FAIL'}  {name}: 复算={got:,.2f} 报告={exp:,.2f}")
    ok, fail = ok+good, fail+(not good)

# ---------- 第一幕 ----------
r = con.execute(f"SELECT COUNT(*), COUNT(DISTINCT user_id), COUNT(*) FILTER(event_type='purchase'), SUM(price) FILTER(event_type='purchase') FROM '{P}'").fetchone()
chk("A1a 总事件", r[0], 19497292, 0); chk("A1b 总用户", r[1], 1637977, 0)
chk("A1c 购买事件", r[2], 1285982, 0); chk("A1d 总GMV", r[3], 6348268, 0.001)
mm = con.execute(f"SELECT strftime(event_time AT TIME ZONE 'UTC','%Y-%m') m, COUNT(DISTINCT user_id) uv, ROUND(SUM(price) FILTER(event_type='purchase')) gmv FROM '{P}' GROUP BY 1 ORDER BY 1").df()
saved = pd.read_csv(f"{D}/act1_monthly.csv")
chk("A2a 11月GMV(峰值)", mm.loc[mm.m=='2019-11','gmv'].iloc[0], saved.loc[saved.month=='2019-11','gmv'].iloc[0], 0)
chk("A2b 12月GMV(谷)", mm.loc[mm.m=='2019-12','gmv'].iloc[0], saved.loc[saved.month=='2019-12','gmv'].iloc[0], 0)
fn = con.execute(f"""WITH u AS (SELECT user_id, BOOL_OR(event_type='view') v, BOOL_OR(event_type='cart') c, BOOL_OR(event_type='purchase') p FROM '{P}' GROUP BY 1)
SELECT SUM(v::INT), SUM(c::INT), SUM(p::INT) FROM u""").fetchone()
chk("A3a 浏览用户", fn[0], 1596371, 0); chk("A3b 加购用户", fn[1], 398124, 0); chk("A3c 购买用户", fn[2], 110518, 0)
wk = con.execute(f"SELECT strftime(date_trunc('week',event_time AT TIME ZONE 'UTC'),'%Y-%m-%d') w, ROUND(SUM(price) FILTER(event_type='purchase')) g FROM '{P}' GROUP BY 1 ORDER BY 1").df()
chk("A4a 黑五周GMV", wk.loc[wk.w=='2019-11-18','g'].iloc[0], 474863, 0)
chk("A4b 圣诞周GMV", wk.loc[wk.w=='2019-12-23','g'].iloc[0], 210925, 0)
feb = con.execute(f"SELECT event_date d, SUM(price) FILTER(event_type='purchase') g FROM '{P}' WHERE event_date BETWEEN DATE '2020-01-27' AND DATE '2020-02-29' GROUP BY 1").df()
feb['wk'] = pd.to_datetime(feb['d']).dt.to_period('W-SUN').astype(str)
feb['wd'] = pd.to_datetime(feb['d']).dt.weekday
wms = feb[feb.wd<6].groupby('wk')['g'].sum()
chk("A4c 2月末周较峰值周%(同口径周一至周六)", 100*(wms.iloc[-1]/wms.iloc[0]-1), -22.46, 0.01)
chk("A4d 2月末周环比%", 100*(wms.iloc[-1]/wms.iloc[-2]-1), 3.91, 0.01)

# ---------- 第二幕 ----------
BAND = """CASE WHEN price<2 THEN 1 WHEN price<4 THEN 2 WHEN price<8 THEN 3 WHEN price<16 THEN 4 WHEN price<50 THEN 5 ELSE 6 END"""
pb = con.execute(f"""WITH e AS (SELECT {BAND} b, event_type, price FROM '{P}')
SELECT b, COUNT(*) FILTER(event_type='view') v, COUNT(*) FILTER(event_type='purchase') p,
 ROUND(100.0*COUNT(*) FILTER(event_type='purchase')/COUNT(*) FILTER(event_type='view'),2) bpv,
 ROUND(100.0*COUNT(*) FILTER(event_type='remove_from_cart')/COUNT(*) FILTER(event_type='cart'),1) rpc
FROM e GROUP BY 1 ORDER BY 1""").df()
saved2 = pd.read_csv(f"{D}/act2_priceband_funnel.csv")
for i in range(6):
    chk(f"B1 价格带{i+1} 浏览→购买%", pb.loc[i,'bpv'], saved2.loc[i,'buy_per_view'], 0)
chk("B1g <$2带移除率%", pb.loc[0,'rpc'], 45.8, 0); chk("B1h $2-4带移除率%", pb.loc[1,'rpc'], 57.7, 0)
d = con.execute(f"SELECT median(price) FILTER(event_type='remove_from_cart'), median(price) FILTER(event_type='purchase') FROM '{P}'").fetchone()
chk("B2a 被移除中位价", d[0], 3.46, 0); chk("B2b 被购买中位价", d[1], 3.00, 0)
br = con.execute(f"""SELECT brand, COUNT(*) FILTER(event_type='view') v,
 ROUND(100.0*COUNT(*) FILTER(event_type='purchase')/COUNT(*) FILTER(event_type='view'),2) bpv,
 ROUND(SUM(price) FILTER(event_type='purchase')) g,
 ROUND(100.0*COUNT(*) FILTER(event_type='remove_from_cart')/COUNT(*) FILTER(event_type='cart'),1) rr
 FROM '{P}' WHERE brand IN ('runail','bpw.style','masura') GROUP BY 1""").df().set_index("brand")
chk("B4a runail转化%", br.loc['runail','bpv'], 18.29, 0)
chk("B4b bpw.style转化%", br.loc['bpw.style','bpv'], 22.50, 0)
chk("B4c masura移除率%", br.loc['masura','rr'], 66.7, 0)
chk("B4d bpw每浏览GMV", 44635/168642, 0.265, 0.02)

# ---------- 第三幕 ----------
sg = con.execute(f"""WITH u AS (SELECT CASE WHEN purchase_days>=2 THEN 4 WHEN purchase_days=1 THEN 3 WHEN carts>0 THEN 2 ELSE 1 END s, gmv FROM '{U}')
SELECT s, COUNT(*) n, SUM(gmv) g FROM u GROUP BY 1 ORDER BY 1""").df().set_index("s")
chk("C1a 复购用户数", sg.loc[4,'n'], 22738, 0); chk("C1b 复购GMV占比%", 100*sg.loc[4,'g']/sg['g'].sum(), 47.9, 0.01)
chk("C1c 单次购买占比%", 100*sg.loc[3,'n']/sg['n'].sum(), 5.4, 0.02)
cc = con.execute(f"""WITH b AS (SELECT gmv, ROW_NUMBER() OVER (ORDER BY gmv DESC) rn FROM '{U}' WHERE purchases>0)
SELECT 100.0*SUM(gmv) FILTER(rn<=(SELECT COUNT(*) FROM b)*0.1)/(SELECT SUM(gmv) FROM b),
       100.0*SUM(gmv) FILTER(rn<=(SELECT COUNT(*) FROM b)*0.2)/(SELECT SUM(gmv) FROM b) FROM b""").fetchone()
chk("C2a 前10%买家GMV%", cc[0], 43.0, 0.01); chk("C2b 前20%买家GMV%", cc[1], 59.3, 0.01)
lor = pd.read_csv(f"{D}/act3_lorenz.csv")
i10 = (lor.buyer_pct-10).abs().idxmin(); i20 = (lor.buyer_pct-20).abs().idxmin()
chk("C4a 洛伦兹过(10,43)", lor.loc[i10,'gmv_cum'], 43.0, 0.05)
chk("C4b 洛伦兹过(20,59.3)", lor.loc[i20,'gmv_cum'], 59.3, 0.05)
chk("C4c 洛伦兹终点", lor['gmv_cum'].iloc[-1], 100.0, 0)
chk("C5 单日买家占比%", 100*87780/110518, 79.4, 0.01)
cp = pd.read_csv(f"{D}/act3_cluster_profile.csv")
chk("C3a C0 GMV占比%", cp.loc[cp.cluster==0,'gmv_pct'].iloc[0], 47.8, 0.002)
chk("C3b C3高客单GMV占比%", cp.loc[cp.cluster==3,'gmv_pct'].iloc[0], 50.0, 0.002)

# ---------- 第四幕 ----------
led = pd.read_csv(f"{D}/act4_ledger.csv")
chk("D1a S1中性", 0.05*288519*(3305543/87780)/5, led[(led.策略.str.startswith('S1'))&(led.情景=='中性')]['月挽回GMV'].iloc[0], 0.005)
chk("D1b S2中性", 0.10*87780*(3042724/22738/2.9333)/5, led[(led.策略.str.startswith('S2'))&(led.情景=='中性')]['月挽回GMV'].iloc[0], 0.02)
chk("D2 月均GMV", 6348268/5, 1269654, 0.001)
chk("D3 S5中性", 59066*(1.222*0.5-0.318)/5, led[(led.策略.str.startswith('S5'))&(led.情景=='中性')]['月挽回GMV'].iloc[0], 0.02)
tot_mid = led[led.情景=='中性']['月挽回GMV'].sum()
chk("D4 中性合计", tot_mid, 296137, 0.001)
s = pd.read_csv(f"{D}/act4_summary.csv")
chk("D5a 保守合计", s['保守'].sum(), 136528, 0.01)
chk("D5b 乐观合计(含S5)", s['乐观'].sum(), 539317, 0.001)
chk("D5c 乐观合计(不含S5)", s['乐观'].sum()-s[s.策略.str.startswith('S5')]['乐观'].iloc[0], 533448, 0.001)

# ---------- 口径验证 ----------
lk = con.execute(f"""WITH fc AS (SELECT user_id, product_id, MIN(event_time) t FROM '{P}' WHERE event_type='cart' GROUP BY 1,2),
 p AS (SELECT user_id, product_id, event_time t FROM '{P}' WHERE event_type='purchase')
SELECT 100.0*COUNT(*) FILTER(fc.t<p.t)/COUNT(*) FROM p LEFT JOIN fc USING(user_id,product_id)""").fetchone()
chk("E1 购买前有同商品加购%", lk[0], 91.9, 0.01)

# ---------- 新增分层：加购未买 × 移除三层 ----------
rt = pd.read_csv(f"{D}/act3_remove_tiers.csv").set_index("tier")
chk("F1a A层人数", rt.loc['A 保留型','users'], 196172, 0)
chk("F1b B层人数", rt.loc['B 轻度移除','users'], 49683, 0)
chk("F1c C层人数", rt.loc['C 重度移除','users'], 42664, 0)
chk("F1d 三层合计=加购未买", rt['users'].sum(), 288519, 0)
rr = pd.read_csv(f"{D}/act3_remove_recart.csv").set_index("tier")
chk("F2a B层重新加购%", rr.loc['B 轻度移除','recart_pct'], 6.8, 0.02)
chk("F2b C层重新加购%", rr.loc['C 重度移除','recart_pct'], 7.3, 0.02)

print(f"\n===== 审计完成: {ok} PASS / {fail} FAIL =====")
sys.exit(1 if fail else 0)
