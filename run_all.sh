#!/bin/bash
# ============================================================
# 6301 项目 · 一键复现脚本
# 用法：bash run_all.sh
# 前提：已完成《复现指南.md》第 1、2 步（装依赖 + 路径替换）
# 全程约 2-3 分钟（DuckDB 核外计算，16GB 内存足够）
# ============================================================
set -e
cd "$(dirname "$0")"

echo "== 第一幕：盘面诊断 =="
python data/act1.py
python data/act1_chart.py

echo "== 第二幕：漏斗 × 价格带 × 品牌 =="
python data/act2.py
python data/act2_slices.py      # 价格带/品牌用户级切片 + 移除后行为
python data/act2_consistency.py # 链路口径验证
python data/act2_chart.py

echo "== 第三幕：用户宽表 + 分群 + 聚类 =="
python data/act3_users.py     # 若 users.parquet 已存在可跳过
python data/act3.py
python data/act3_kmeans.py
python data/act3_fix.py       # 洛伦兹曲线 + k 选型证据
python data/act3_remove.py    # 加购未买 × 移除三层细分（11-25 新增）
python data/act3_metrics.py   # K-Means AI 质量指标（11-25 新增）
python data/act3_tiers_chart.py  # 三层细分图（11-25 新增）
python data/act3_chart.py

echo "== 第四幕：策略矩阵与量化 =="
python data/act4.py           # S1-S4 台账
python data/act5.py           # S5 台账 + 簇×品牌画像
python data/act4_merge_s5.py  # 合并 S5 进总台账
python data/act4_chart.py

echo "== 审计：53 项数字独立复算 =="
python data/audit.py

echo "全部完成。产物在 data/ 下，主图：act1~act4_dashboard.png"
