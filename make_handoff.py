# -*- coding: utf-8 -*-
"""6301 项目交接文档生成器"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, PageBreak, KeepTogether)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

D = "/Users/yun/Documents/Kimi/Workspaces/6301项目"
OUT = f"{D}/交接文档.pdf"

pdfmetrics.registerFont(TTFont('CJK', os.environ['DAIMON_CJK_FONT_REGULAR']))
pdfmetrics.registerFont(TTFont('CJK-B', os.environ['DAIMON_CJK_FONT_BOLD']))
pdfmetrics.registerFontFamily('CJK', normal='CJK', bold='CJK-B', italic='CJK', boldItalic='CJK-B')

NAVY = HexColor('#1f3a5f'); GRAY = HexColor('#666666'); RED = HexColor('#c0392b')
ss = getSampleStyleSheet()
def st(name, **kw):
    base = kw.pop('parent', ss['Normal'])
    fn = kw.pop('fontName', 'CJK')
    return ParagraphStyle(name, parent=base, fontName=fn, **kw)
TITLE = st('t', fontSize=22, leading=30, textColor=NAVY, alignment=1, fontName='CJK-B')
SUB   = st('s', fontSize=12, leading=18, textColor=GRAY, alignment=1)
H1 = st('h1', fontSize=15, leading=20, textColor=NAVY, spaceBefore=14, spaceAfter=6, fontName='CJK-B')
H2 = st('h2', fontSize=12, leading=16, textColor=NAVY, spaceBefore=10, spaceAfter=4, fontName='CJK-B')
B  = st('b', fontSize=10, leading=16, spaceAfter=4)
BS = st('bs', fontSize=9.5, leading=15, spaceAfter=3, leftIndent=14)
CAP= st('cap', fontSize=8.5, leading=12, textColor=GRAY, alignment=1, spaceBefore=3)
NOTE=st('n', fontSize=9, leading=14, textColor=GRAY, spaceAfter=3)

def h1(t): return Paragraph(t, H1)
def h2(t): return Paragraph(t, H2)
def p(t):  return Paragraph(t, B)
def ps(t): return Paragraph(t, BS)
def cap(t):return Paragraph(t, CAP)

def tbl(header, rows, widths, fs=8.5, red_cols=()):
    data = [header] + rows
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [('FONTNAME', (0,0), (-1,-1), 'CJK'), ('FONTSIZE', (0,0), (-1,-1), fs),
             ('FONTNAME', (0,0), (-1,0), 'CJK-B'),
             ('LINEABOVE', (0,0), (-1,0), 1.2, NAVY),
             ('LINEBELOW', (0,0), (-1,0), 0.6, NAVY),
             ('LINEBELOW', (0,-1), (-1,-1), 1.2, NAVY),
             ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4),
             ('ALIGN', (1,0), (-1,-1), 'CENTER')]
    for c in red_cols:
        style.append(('TEXTCOLOR', (c,1), (c,-1), RED))
        style.append(('FONTNAME', (c,1), (c,-1), 'CJK-B'))
    t.setStyle(TableStyle(style))
    return t

def img(path, w=13.2*cm, ratio=None):
    from PIL import Image as PImage
    pw, ph = PImage.open(path).size
    return Image(path, width=w, height=w*ph/pw)

story = []

# ============ 封面 ============
story += [Spacer(1, 4.5*cm),
    Paragraph("化妆品电商转化诊断项目", TITLE),
    Spacer(1, 0.4*cm),
    Paragraph("工作交接文档：做了什么 · 结果是什么 · 思路是什么", SUB),
    Spacer(1, 1.2*cm),
    Paragraph("数据：eCommerce Events History in Cosmetics Shop（Kaggle）", SUB),
    Paragraph("2019-10 ~ 2020-02 全量五个月 · 1,950 万事件 · 163.8 万用户", SUB),
    Spacer(1, 1.2*cm),
    Paragraph("交接日期：2026-11-25", SUB),
    Paragraph("交接人：包云天（L01-Group 11）", SUB),
    PageBreak()]

# ============ 0 导读 ============
story += [h1("怎么读这份文档"),
 p("这份文档回答三件事：<b>我做了什么</b>（第 1–2 章）、<b>结果是什么</b>（第 3–6 章，含全部图表和数字）、<b>思路是什么</b>（贯穿各章开头，第 7 章是必须遵守的口径纪律）。第 8 章是文件地图和复跑方法——所有数字都能用一条命令重新算出来，你不用信我，可以验我。"),
 p("一句话项目：这家化妆品电商<b>不缺流量，缺的是转化</b>。我找到了钱漏在哪一环（漏斗）、漏在什么货上（价格带/品牌）、漏在谁身上（人群分群），并给出了量化到美元的策略矩阵。"),
 p("三个先记住的数字：① <b>1.4%</b> 的复购用户贡献 <b>47.9%</b> 的 GMV；② <b>$2–8</b> 价格带的加购移除率 <b>57%</b>，是全场最高的犹豫区；③ 中性情景下五条策略每月可挽回 <b>$29.6 万</b>，约等于月 GMV 的 <b>23.3%</b>。"),
 Spacer(1, 0.3*cm),
 h2("分析的四幕结构（也是报告的建议结构）"),
 tbl(["幕", "问题", "方法", "核心产出"],
     [["第一幕 · 起", "生意健康吗？", "月度趋势 + 整体漏斗", "盘面诊断"],
      ["第二幕 · 承", "钱漏在什么货上？", "漏斗 × 价格带 × 品牌", "漏点定位"],
      ["第三幕 · 转", "漏的是谁？", "行为分群 + RFM + K-Means", "人群画像"],
      ["第四幕 · 合", "钱该花在哪？", "策略矩阵 + GMV 量化", "五策合计 $29.6万/月"]],
     [2.6*cm, 3.6*cm, 5.4*cm, 4.4*cm]),
 Spacer(1, 0.3*cm),
 h2("开工前的三个假设（H1–H3）"),
 ps("H1：流失主要集中在「加购 → 购买」环节（结果：方向成立，但量级上最大漏点在浏览→加购，金额上最痛在加购→购买）"),
 ps("H2：高价与低价商品的流失模式完全不同，一刀切促销是浪费（结果：强成立，转化率差 21 倍，且价格筛选发生在加购之前）"),
 ps("H3：大部分成交由一小撮高价值用户贡献，拉新不如激活存量（结果：强成立，1.4% 复购用户 = 47.9% GMV）"),
 PageBreak()]

# ============ 1 数据 ============
story += [h1("1 ｜ 数据与底座"),
 p("数据源：Kaggle「eCommerce Events History in Cosmetics Shop」，一家中型欧美化妆品电商的全埋点行为日志。原始五个 CSV（每月一个，共约 2.5 GB）已由我合并清洗为 <b>five_months_cleaned.csv</b>（2.37 GB），并转成 Parquet 供分析（<b>events.parquet</b>，299 MB）。"),
 tbl(["字段", "含义", "备注"],
     [["event_time", "事件时间（UTC）", "范围恰好 2019-10-01 ~ 2020-02-29"],
      ["event_type", "view / cart / remove_from_cart / purchase", "四类事件"],
      ["product_id / category_id", "商品 / 类目 ID", "category_code 清洗时丢失（见第 7 章）"],
      ["brand", "品牌", "42% 事件为 unknown（局限，见第 7 章）"],
      ["price", "商品价格（美元）", "中位数 $4.13，件单价约 $5（GMV/购买事件，非客单价）"],
      ["user_id / user_session", "用户 / 会话", "163.8 万用户、452 万会话"]],
     [4.2*cm, 6.2*cm, 5.6*cm]),
 Spacer(1, 0.2*cm),
 p("事件构成：view 962.6 万 · cart 561.6 万 · remove_from_cart 296.9 万 · purchase 128.6 万。"),
 p("分析底座两张表：<b>events.parquet</b>（事件级）与 <b>users.parquet</b>（用户级宽表，163.8 万行 × 每人浏览/加购/移除/购买/GMV/活跃天数/recency 等指标）。第三、四幕全在用户宽表上跑。"),
 PageBreak()]

# ============ 2 我做了什么 ============
story += [h1("2 ｜ 我做了什么（工作概览）"),
 ps("<b>第一幕（11-20）</b>：CSV→Parquet 固化类型；月度 UV/GMV/购买事件/件单价；用户级整体漏斗；周度走势。产出 act1_dashboard.png。"),
 ps("<b>第二幕（11-20）</b>：漏斗 × 六档价格带；流量份额 vs GMV 份额；remove_from_cart 深挖（价格劝退）；品牌四象限（52 个品牌）。产出 act2_dashboard.png。"),
 ps("<b>第三幕（11-22）</b>：用户宽表；行为四分群 × GMV；买家 GMV 洛伦兹集中度；K-Means（k=4）聚类并业务命名。产出 act3_dashboard.png。"),
 ps("<b>第四幕（11-22）</b>：人群 × 卡点 × 策略矩阵；五条策略的 GMV 挽回量化（三情景）。产出 act4_dashboard.png。"),
 ps("<b>S5 修正与簇×品牌画像（11-23）</b>：按「每坑位 GMV」重算品牌坑位再分配；四个簇的 TOP 品牌构成。"),
 ps("<b>全项目审计（11-23 首跑 43 项，11-25 升级版 53 项）</b>：audit.py 从底表独立重算进入结论的数字，与落盘文件逐条对账：<b>53 PASS / 0 FAIL</b>（含三情景合计校验与三层细分校验，防心算与口径错误）。"),
 Spacer(1, 0.2*cm),
 h2("一条命令验证所有结论"),
 p("在工作区根目录运行：<b>python data/audit.py</b>。它独立重算本文档引用的每个关键数字并输出 PASS/FAIL。改任何分析后请复跑。"),
 PageBreak()]

# ============ 3 第一幕 ============
story += [h1("3 ｜ 第一幕结果：盘面诊断"),
 p("<b>思路</b>：先回答「生意健不健康」，再谈细节。看月度大盘 + 整体漏斗 + 周度波动。"),
 img(f"{D}/data/act1_dashboard.png"),
 cap("图 1 ｜ 盘面诊断四格：月度 GMV/UV、漏斗转化率、周度走势、整体用户漏斗"),
 Spacer(1, 0.2*cm),
 tbl(["月份", "UV", "购买事件", "GMV", "件单价", "浏览→加购", "加购→购买", "浏览→购买"],
     [["2019-10", "39.9万", "24.5万", "$121万", "$4.94", "34.5%", "19.3%", "6.64%"],
      ["2019-11", "36.8万", "32.2万", "$153万", "$4.75", "27.0%", "32.9%", "8.87%"],
      ["2019-12", "37.0万", "21.3万", "$108万", "$5.06", "23.3%", "30.7%", "7.16%"],
      ["2020-01", "41.0万", "26.4万", "$132万", "$5.02", "23.3%", "30.5%", "7.10%"],
      ["2020-02", "39.1万", "24.2万", "$121万", "$4.99", "23.5%", "28.9%", "6.80%"]],
     [2.1*cm, 1.7*cm, 1.7*cm, 1.9*cm, 1.7*cm, 2.4*cm, 2.4*cm, 2.4*cm], red_cols=(6,)),
 cap("表 1 ｜ 月度盘面与用户级漏斗"),
 Spacer(1, 0.2*cm),
 h2("结论"),
 ps("① 生意画像：<b>件单价 $5 的纯走量生意</b>，月均 39 万访客、$127 万 GMV，赚周转率。"),
 ps("② 整体漏斗：159.6 万浏览 → 39.8 万加购（24.9%）→ 11.1 万购买（6.9%）。<b>量漏在第一道闸（75% 不加购），钱漏在第二道闸（加购者 72% 没付钱，每月约 6.5 万高意向用户流失）</b>。"),
 ps("③ 黑五真实有效（大促周 $47.5 万全期峰值），<b>圣诞反而是低谷</b>（$16.4 万全期最低）——黑五可能预支了 12 月需求。"),
 ps("④ 2 月从峰值走弱：<b>同口径（周一至周六）末周较峰值周（1/27）-22.5%，但较上一周回升 +3.9%</b>。原「连续 4 周下滑 31%」系末周仅 6 天的口径错误。成因待查，报告只能写「走弱后回稳」，不能断言与疫情有关。"),
 ps("⑤ <b>数据质量：10 月漏斗结构与其他四个月显著不同</b>（浏览→加购 34.5% vs 23%），疑似埋点或页面改版，报告必须做口径说明。"),
 PageBreak()]

# ============ 4 第二幕 ============
story += [h1("4 ｜ 第二幕结果：钱漏在什么货上"),
 p("<b>思路</b>：把漏斗按价格带和品牌切开。价格带按数据分布切（中位数 $4.13、P90 $15.71），不拍脑袋。重点用 remove_from_cart——被加购又被移除的商品是「动了心但被劝退」，离钱最近。"),
 img(f"{D}/data/act2_dashboard.png"),
 cap("图 2 ｜ 漏斗 × 价格带 × 品牌四象限"),
 Spacer(1, 0.2*cm),
 tbl(["价格带", "浏览→购买", "加购→购买", "移除/加购", "流量份额", "GMV份额"],
     [["<$2", "28.7%", "24.3%", "45.8%", "15.4%", "7.3%"],
      ["$2–4", "15.6%", "22.6%", "57.7%", "23.3%", "16.2%"],
      ["$4–8", "11.4%", "21.9%", "56.7%", "30.9%", "29.2%"],
      ["$8–16", "8.6%", "22.8%", "52.3%", "14.9%", "21.3%"],
      ["$16–50", "4.3%", "21.6%", "49.0%", "10.2%", "16.1%"],
      [">$50", "1.35%", "17.5%", "51.2%", "5.2%", "9.9%"]],
     [2.2*cm, 2.6*cm, 2.6*cm, 2.6*cm, 2.6*cm, 2.6*cm], red_cols=(3,5)),
 cap("表 2 ｜ 漏斗 × 价格带（事件级口径）"),
 Spacer(1, 0.2*cm),
 h2("结论"),
 ps("① <b>价格是「加购前」的筛选器</b>：浏览→购买随价格单调递减（28.7%→1.35%，21 倍差距），但加购→购买各价格带几乎持平（约 22%）。用户在加购前已完成价格筛选——「加购后发券」打偏了靶心。"),
 ps("② <b>$8–50 是高效价格带</b>（GMV 份额 > 流量份额），引流资源应向此倾斜。"),
 ps("③ <b>移除率最高的是 $2–8（约 57%），不是贵商品（49%）</b>：低价是「冲动加购→冷静后悔」，高价加购反而是深思熟虑。防移除要打低价带的犹豫场景（凑单/批量优惠）。"),
 ps("④ 价格劝退直接证据（温和）：同品牌内被移除商品中位价比被购买商品高 10–58%（jessnail 1.58×、masura 1.37×）。如实写，别夸大为「主因」。"),
 ps("⑤ 品牌四象限：<b>runail/irisk</b> 明星（18%+ 转化、GMV 前二）；<b>bpw.style</b> 购买/浏览 22.5% 属第一梯队（severina 34.8%、de.lux 23.8% 更高）但件单仅 $1.16，问题是提客单不是加曝光；<b>estel/kapous</b> 流量浪费区；<b>masura 移除率 66.7% 全场第二</b>。"),
 PageBreak()]

# ============ 5 第三幕 ============
story += [h1("5 ｜ 第三幕结果：漏的是谁"),
 p("<b>思路</b>：漏点不是均匀分布的，所以不该用一套策略补。行为分群定骨架，K-Means 做深化画像。「复购」严格定义为 ≥2 个不同日期有购买（排除同单多件）。"),
 img(f"{D}/data/act3_dashboard.png", w=12.2*cm),
 cap("图 3 ｜ 行为分群、GMV 洛伦兹曲线、人群行为结构、K-Means 四人群"),
 Spacer(1, 0.2*cm),
 tbl(["人群", "用户占比", "GMV占比", "人均GMV", "人均浏览", "末次活跃"],
     [["纯逛", "75.6%", "0%", "$0", "2.4", "71 天前"],
      ["加购未买", "17.6%", "0%", "$0", "8.6", "80 天前"],
      ["单次购买", "5.4%", "52.1%", "$37.66", "23.5", "63 天前"],
      ["复购（≥2购买日）", "1.4%", "47.9%", "$133.82", "93.9", "33 天前"]],
     [3.4*cm, 2.4*cm, 2.4*cm, 2.4*cm, 2.4*cm, 2.6*cm], red_cols=(2,)),
 cap("表 3 ｜ 行为分群 × GMV（H3 验证：1.4% 复购用户 = 47.9% GMV）"),
 Spacer(1, 0.2*cm),
 tbl(["聚类", "业务命名", "占意向用户", "GMV占比", "画像", "末次活跃"],
     [["C0", "忠诚囤货者", "6.8%", "47.8%", "人均95加购、25购买，买便宜消耗品", "28 天前"],
      ["C1", "一次性好奇者", "39.4%", "1.7%", "加购一两次即走", "109 天前（已流失）"],
      ["C2", "犹豫比价者", "34.8%", "0.6%", "人均10.5加购、4.6移除，零购买", "49 天前（可触达）"],
      ["C3", "高客单尝鲜客", "19.0%", "50.0%", "人均购买价 $8.9，买完未回", "63 天前（唤醒价值最高）"]],
     [1.2*cm, 2.6*cm, 2.4*cm, 2.0*cm, 5.2*cm, 2.6*cm], red_cols=(3,)),
 cap("表 4 ｜ K-Means 四人群（k=4：k≥3 后轮廓系数进入平台期，按业务可解释性选定）"),
 Spacer(1, 0.2*cm),
 h2("结论"),
 ps("① <b>H3 强成立</b>：1.4% 复购用户 = 47.9% GMV；买家内部前 10% = 43%、前 20% = 59.3%。"),
 ps("② <b>79.4% 的买家五个月内只有 1 个购买日</b>——化妆品是消耗品，天然有 30–60 天复购周期，这家店几乎没接住回购。这是全场最大的结构性问题。"),
 ps("③ 复购者件单价 $5.91 < 单次购买者 $8.67：<b>复购买便宜消耗品（补货），单次购买买贵的（尝鲜）</b>。"),
 ps("④ 移除率随参与度递增（43%→57%→61%）：复购者是「重度策展者」，加得多、删得狠、买得准。"),
 ps("⑤ C3 与 C0 的 GMV 几乎相等（50.0% vs 47.8%）但 C3 人数是 C0 的 2.8 倍——<b>C3 的沉默是全场最贵的流失</b>。"),
 PageBreak()]

# ============ 5+ 第三幕补充：三层细分 + K-Means AI 指标（11-25 新增） ============
story += [h1("5+ ｜ 第三幕补充：三层细分与聚类 AI 指标（11-25）"),
 p("<b>思路</b>：「加购未买」只回答了卡在哪，没说清为什么卡——用移除行为再切一刀（用户级口径）；同时给 K-Means 补上完整的质量指标，让「k=4 可用」从经验判断变成可辩护的结论。"),
 img(f"{D}/data/act3_tiers.png", w=16.4*cm),
 cap("图 3+ ｜ 加购未买 × 移除行为三层细分：结构、行为对比、移除后回头（A=忘了买 68%，B/C=想了又不要 32%；回头 <8%，移除≈终局信号）"),
 Spacer(1, 0.25*cm),
 img(f"{D}/data/act3_kmeans_metrics.png", w=16.4*cm),
 cap("图 3++ ｜ K-Means 质量指标：左=k=2~8 扫描（轮廓 + Davies-Bouldin），中=k=4 分簇轮廓，右=稳定性与外部一致性"),
 Spacer(1, 0.2*cm),
 tbl(["指标", "数值", "解读"],
     [["轮廓系数（k=4，总体）", "0.253", "k≥3 进入 0.23~0.28 平台期；k=2 的 0.407 只是买/没买二分，无业务价值"],
      ["分簇轮廓", "C0 0.188 / C1 0.354 / C2 0.153 / C3 0.249", "各簇均 >0，凝聚度可接受；C1/C2 天然贴近（本就难分离）"],
      ["Calinski-Harabasz（k=4）", "7,731", "类间/类内离差比，k=2 后递减，k=4 处于平台期"],
      ["Davies-Bouldin（k=4）", "1.376", "k=6~7 略更低但业务不可解释，平台期内取 k=4"],
      ["split-half 稳定性 ARI", "0.996", "随机一半用户重跑聚类，标签一致性 99.6%——结论不依赖抽样"],
      ["vs 行为分群：ARI / NMI / Cramér's V", "0.400 / 0.494 / 0.722", "中等偏强关联：两切法互为印证但不冗余（C3 高客单群是行为分群拆不出的增量信息）"]],
     [4.6*cm, 5.4*cm, 6.4*cm]),
 cap("表 4+ ｜ K-Means AI 质量指标（39.9 万意向用户，8 特征 log 变换 + 标准化；评估用 2 万随机子样，RandomState(42)）"),
 ps("<b>三层细分的策略含义</b>：S2 购物车挽回的主攻人群是 A 层 196,172 人（提醒/限时券即可激活）；B/C 层 91,347 人提醒无效，应降价、推替代款或放弃。数据支撑：A 层 89 天未动（遗忘特征），C 层移除率 93%（反悔特征），移除后回头仅 6.8%/7.3%（终局特征）。"),
 PageBreak()]

# ============ 6 第四幕 ============
story += [h1("6 ｜ 第四幕结果：钱该花在哪"),
 p("<b>思路</b>：每条策略必须挂可辩护的数字。假设全部写明（转化率、单价都来自实测），口径粗糙可以，没有数字不行。S5 用「每坑位 GMV」计价，不用转化率——bpw.style 转化率第一梯队但每坑位 $0.27 反而亏钱，是本项目的现成反面教材。"),
 img(f"{D}/data/act4_dashboard.png"),
 cap("图 4 ｜ 策略挽回空间（三情景）与人群 × 卡点 × 策略矩阵"),
 Spacer(1, 0.2*cm),
 tbl(["策略", "目标人群", "策略动作", "假设", "月挽回(中性)"],
     [["S1", "28.9万加购未买", "定向券+降价提醒+凑单", "首购转化5%×首购价值$37.66", "$10.9万"],
      ["S2", "8.8万单次购买", "30天回购触达", "唤醒10%×每购买日$45.70", "$8.0万"],
      ["S3", "$2–8 价格带加购用户（全站）", "批量优惠/订阅制", "该带移除率57%→45.8%", "$6.5万"],
      ["S4", "高价带浏览者", "比价工具/分期/评价前置", "加购→购买17.5%→22.9%", "$3.9万"],
      ["S5", "全站（结构性）", "kapous减坑位→strong/uno/cnd", "挪30%坑位，传导率50%", "$0.3万"],
      ["—", "15.8万C1流失用户", "不花钱（止损也是策略）", "—", "$0"]],
     [1.2*cm, 3.2*cm, 4.0*cm, 4.8*cm, 2.8*cm], red_cols=(4,)),
 cap("表 5 ｜ 策略矩阵与量化假设（保守 $13.6万 / 中性 $29.6万 / 乐观 $53.9万 每月；乐观口径不含 S5 为 $53.3万）"),
 Spacer(1, 0.2*cm),
 ps("<b>重叠声明（报告必写）</b>：S1 与 S3 目标人群部分重叠，合计是上限而非精确值。"),
 ps("<b>S5 备注</b>：金额小（S1 的 1/30），是零成本结构优化。strong 55% 的 GMV 来自 C3 高价值人群，流量平移换不来这群人，故传导率必须打折。"),
 PageBreak()]

# ============ 7 口径纪律 ============
story += [h1("7 ｜ 口径纪律（接手后必须遵守）"),
 h2("7.1 事件级 vs 用户级（最容易被问穿的点）"),
 tbl(["指标", "事件级口径", "用户级口径", "使用场景"],
     [["浏览→购买", "13.4%（购买事件/浏览事件）", "6.9%（购买用户/浏览用户）", "正文用用户级"],
      ["浏览→加购", "58.3%", "24.9%", "价格带分析用事件级"],
      ["加购→购买", "22.9%", "27.8%", "必须在表格注明口径"]],
     [2.8*cm, 4.6*cm, 4.6*cm, 4.0*cm]),
 cap("表 6 ｜ 指标×口径对照表：28.7%（<$2带，事件级）与 6.9%（全站，用户级）并存时必须注明"),
 ps("补充：<b>浏览→加购有三种算法并存</b>——24.94%（事件级行为口径）/ 22.42%（同用户）/ 17.57%（同商品先浏览后加购）。报告引用此转化率时必须写明用哪一种，不得混排。"),
 Spacer(1, 0.2*cm),
 h2("7.2 链路验证结论（决定漏斗能怎么讲）"),
 ps("91.9% 的购买事件前有同商品加购记录 → <b>加购→购买链路成立</b>，可用严格同商品口径。"),
 ps("仅 37.2% 的购买事件前有同商品浏览记录（同会话内仅 18.6%）→ <b>浏览→加购链路弱</b>（大量用户从站外直达商品页），漏斗只能按「用户 × 维度」的行为口径讲，不能讲成同一个人的完整路径。"),
 h2("7.3 数据局限（报告「局限性」章节直接可用）"),
 ps("① brand = unknown 覆盖 42% 事件，品牌结论只覆盖 58% 流量；"),
 ps("② category_code 在清洗时丢失，类目只剩数字 ID——若原始 CSV 还在，补回只要几分钟，强烈建议补；"),
 ps("③ 10 月漏斗结构突变（疑似埋点/页面改版），跨月对比用 11 月以后的口径；"),
 ps("④ 数据窗口仅 5 个月，早进入的用户复购机会更多，GMV 集中度略被高估；"),
 ps("⑤ RFM 与 K-Means 是同一批用户的两种切法，互相印证而非独立证据；k=4 是平台期后按业务可解释性选定，<b>不得写 k=4 最优</b>（k=2 轮廓系数 0.41 最高，k≥3 进入 0.23~0.28 平台期，证据在 act3_kselect.csv）。"),
 h2("7.4 已修复的坑（别踩第二次）"),
 ps("洛伦兹曲线：先 WHERE 抽样再算窗口累计会让曲线全期只有 0.2%——必须全量计算后抽样（见 act3_fix.py）。matplotlib 标题含 $ 会触发 mathtext 乱码——plt.rcParams['text.parse_math']=False 并手写对数轴刻度。"),
 PageBreak()]

# ============ 8 文件地图 ============
story += [h1("8 ｜ 文件地图与下一步"),
 h2("8.1 工作区文件"),
 tbl(["文件", "说明"],
     [["data/events.parquet", "事件底座（1,950 万行，299MB），一切分析从这读"],
      ["data/users.parquet", "用户宽表（163.8 万行），人群分析的底座"],
      ["data/act1~act4_dashboard.png", "四幕主图（本文档图 1–4）"],
      ["data/act1_*.csv ~ act5_*.csv", "全部明细数据表（月度/漏斗/价格带/品牌/分群/聚类/台账）"],
      ["data/act1.py ~ act5.py + *_chart.py", "可复跑脚本：计算与绘图分离"],
      ["data/audit.py", "审计脚本：53 项数字独立复算（含合计与分层校验），改分析后必跑"],
      ["data/act3_fix.py", "洛伦兹修复 + k 选型证据（轮廓系数扫描）"],
      ["工作记录.md", "全程工作日志（含每幕数字、假设、局限性和修复记录）"]],
     [5.6*cm, 10.4*cm]),
 Spacer(1, 0.2*cm),
 h2("8.2 建议的下一步"),
 ps("① 组装 10–15 页课程报告：按四幕结构，每页一个结论，图作证据；第 7 章内容进「数据质量与局限性」；"),
 ps("② 若原始 CSV 还在，补回 category_code，让类目分析可以点名（第二幕里 GMV 第二高的类目转化仅 1.38% 但客单约 $92，是个好故事）；"),
 ps("③ 三个数字记忆点（答辩/面试用）：1.4% 复购用户 = 47.9% GMV；$2–8 移除率 57% 是全场最高犹豫区；中性可挽回 $29.6 万/月 ≈ 月 GMV 的 23.3%。"),
 Spacer(1, 0.4*cm),
 Paragraph("—— 交接完毕。所有数字可复算，所有假设已写明，祝顺利。", NOTE)]

def deco(canvas, doc):
    canvas.saveState()
    w, h = A4
    if doc.page > 1:
        canvas.setFont('CJK', 8); canvas.setFillColor(GRAY)
        canvas.drawCentredString(w/2, h-1.2*cm, "化妆品电商转化诊断 · 工作交接文档 · 2026-11-25")
        canvas.setStrokeColor(HexColor('#cccccc')); canvas.setLineWidth(0.5)
        canvas.line(2.5*cm, h-1.4*cm, w-2.5*cm, h-1.4*cm)
        canvas.drawCentredString(w/2, 1.0*cm, f"第 {doc.page-1} 页")
    canvas.restoreState()

doc = SimpleDocTemplate(OUT, pagesize=A4, topMargin=2.2*cm, bottomMargin=2.0*cm,
                        leftMargin=2.5*cm, rightMargin=2.5*cm,
                        title="化妆品电商转化诊断项目交接文档", author="包云天")
doc.build(story, onFirstPage=deco, onLaterPages=deco)
print("PDF:", OUT)
