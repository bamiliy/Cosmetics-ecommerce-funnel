# 流量去哪了：化妆品电商转化漏点诊断与分群运营策略

> 基于 1,950 万行真实电商行为数据（2019.10–2020.02），用漏斗分析定位转化漏点，
> 用三层人群分群（规则分层 + K-Means）识别流失人群，最终给出按 ROI 排序的策略矩阵。

**数据集**：[eCommerce Events History in Cosmetics Shop (Kaggle)](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop) — REES46 发布的中型化妆品电商全量事件流，每行 = 一次用户行为事件（view / cart / remove_from_cart / purchase）。

## 核心数字（独立复算口径）

| 指标 | 数值 |
|---|---|
| 事件总量 | 19,497,292 |
| 独立用户 | 1,637,977 |
| 购买事件 / 购买用户 | 1,285,982 / 110,518 |
| 购买金额合计 | $6,348,268 |
| 加购用户 / 加购且购买 | 398,124 / 109,605 |

完整分析过程与结论见仓库内报告 [`交接文档.pdf`](交接文档.pdf)。

## 分析框架（五幕结构）

1. **盘面诊断**：月度趋势 + 双口径漏斗（session / user），确认漏点位置
2. **漏斗 × 特征下钻**：按价格带、品牌、类目切开漏斗，重点分析 `remove_from_cart`（加购后悔信号）
3. **人群分群**：规则筛除长尾 → 行为分层（纯浏览 / 加购未买 / 复购）→ 层内 K-Means 聚类，含轮廓系数与稳定性检验
4. **策略矩阵**：人群 × 漏点环节 × 干预动作，按预期挽回 GMV 排序
5. **审计与验证**：`audit.py` 自审计 53 项校验全部通过；另附独立复算说明（见下文局限）

## 目录结构

```
├── 6301_all_in_one.py   # 全流程单文件版（由 20 个脚本合并，约 5–8 分钟跑完）
├── run_all.sh           # 一键分幕复现入口
├── make_handoff.py      # 报告生成脚本
├── 交接文档.pdf          # 完整分析报告
└── data/                # 代码与数据目录（数据不进 Git，见下方复现步骤）
    ├── to_parquet.py    # CSV → Parquet 底座
    ├── act1*.py         # 第一幕：盘面诊断
    ├── act2*.py         # 第二幕：漏斗下钻
    ├── act3*.py         # 第三幕：分群与聚类
    ├── act4*.py         # 第四幕：策略测算
    ├── act5.py          # 第五幕：汇总
    └── audit.py         # 自审计（53 项校验）
```

## 如何复现

```bash
# 1. 安装依赖（Python 3.10+，16GB 内存足够，DuckDB 核外计算）
pip install -r requirements.txt

# 2. 从 Kaggle 下载数据集（5 个月 CSV），清洗后放入 data/
#    命名格式：2019-Oct_cleaned.csv.gz ... 2020-Feb_cleaned.csv.gz

# 3. 一键复现（约 2–3 分钟）
bash run_all.sh

# 或跑单文件版（约 5–8 分钟）
python 6301_all_in_one.py
```

## 局限与口径声明（Limitations）

- 数据无订单 ID 与商品数量字段：`orders` 为 purchase **事件数**，`aov` 为购买事件的平均价格，不等同于真实订单数与客单价
- 用户级「购买/加购人数比」不是严格时序转化率；事件级 purchase/view 为数量比，不保证同用户、同商品、先加购后购买
- 聚类 k=4 用于业务解释（轮廓系数 0.253），并非轮廓系数最优解（k=2 为 0.407）；因特征含购买与 GMV 变量，群间购买差异为描述性结果，非独立预测证据
- 策略挽回 GMV 为**人为设定提升幅度下的情景测算**，非因果收益；多策略目标人群存在重叠，合计未去重
- 「冲动加购」「冷静后悔」等心理标签为业务命名，行为日志无法直接证实心理动机

## 技术栈

DuckDB（SQL 主引擎，核外计算）· pandas · scikit-learn（K-Means）· matplotlib · reportlab
