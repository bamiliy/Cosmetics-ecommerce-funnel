# -*- coding: utf-8 -*-
"""把 S5 并入 act4 台账（act4.py 只生成 S1-S4，S5 由 act5.py 生成，这里合并）"""
import pandas as pd, os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)))
a = pd.read_csv(f"{D}/act4_ledger.csv")
b = pd.read_csv(f"{D}/act5_s5_ledger.csv")
# 幂等：先剔除已有 S5 再合并，重复运行不产生重复行
a = a[~a["策略"].str.startswith("S5")]
led = pd.concat([a, b], ignore_index=True)
led.to_csv(f"{D}/act4_ledger.csv", index=False)
piv = led.pivot(index="策略", columns="情景", values="月挽回GMV")[["保守","中性","乐观"]]
piv.to_csv(f"{D}/act4_summary.csv")
print(f"台账合并完成：中性合计 ${piv['中性'].sum():,}/月 ≈ 月GMV的 {100*piv['中性'].sum()/1269654:.1f}%")
