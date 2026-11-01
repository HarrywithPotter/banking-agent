# -*- coding: utf-8 -*-
"""生成《智银·AI Banking Agent 技术文档》PDF（中文，全面版）。"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                PageBreak)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
CN = "STSong-Light"

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "智银AI银行助手-技术文档.pdf")
OUT = os.path.abspath(OUT)

def S(name, **kw):
    base = dict(fontName=CN, leading=16, fontSize=10.5)
    base.update(kw)
    return ParagraphStyle(name, **base)

H1 = S("H1", fontSize=19, leading=25, spaceBefore=10, spaceAfter=8, textColor=colors.HexColor("#1a2b4a"))
H2 = S("H2", fontSize=13.5, leading=19, spaceBefore=12, spaceAfter=5, textColor=colors.HexColor("#2a5db0"))
H3 = S("H3", fontSize=11.5, leading=16, spaceBefore=7, spaceAfter=3, textColor=colors.HexColor("#333"))
BODY = S("BODY", fontSize=10, leading=16, spaceAfter=4)
SMALL = S("SMALL", fontSize=9, leading=13, textColor=colors.HexColor("#555"))
CODE = S("CODE", fontSize=8.2, leading=11.5, textColor=colors.HexColor("#0a3d62"))
CELL = S("CELL", fontSize=8.5, leading=12)
CELLH = S("CELLH", fontSize=9, leading=12, textColor=colors.white)


def tbl(data, widths=None, header=True):
    t = Table(data, colWidths=widths, hAlign="LEFT")
    cmds = [
        ("FONTNAME", (0, 0), (-1, -1), CN),
        ("FONTSIZE", (0, 0), (-1, -1), 8.8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2a5db0"))]
    t.setStyle(TableStyle(cmds))
    return t


def P(t, st=CELL):
    return Paragraph(t, st)


story = []

# ============ 封面 ============
story.append(Spacer(1, 38 * mm))
story.append(Paragraph("智银 · AI Banking Agent", S("cover", fontSize=30, leading=40, alignment=1, textColor=colors.HexColor("#1a2b4a"))))
story.append(Spacer(1, 6 * mm))
story.append(Paragraph("自然语言驱动的银行业务智能体 —— 技术文档", S("sub", fontSize=14, alignment=1, textColor=colors.HexColor("#555"))))
story.append(Spacer(1, 18 * mm))
cover = [
    ["文档名称", "系统架构 · 核心算法 · 安全设计 · 功能清单"],
    ["版本", "v3.0（三栏暗色UI / SHA-256哈希链审计 / MFA批量确认 / 年终奖DAG）"],
    ["技术栈", "Python 3.15 · FastAPI · SQLite · 原生 HTML/JS 三栏暗色 Web UI"],
    ["覆盖场景", "8 大场景 / 40+ 操作 / 时间模拟引擎 / 63 条自动化测试"],
    ["权限分级", "绿色自动 / 黄色确认 / 红色强验证（动态升降，同批MFA一次通过）"],
    ["启动方式", "双击「启动智银银行AI助手.bat」"],
]
story.append(tbl(cover, [38 * mm, 122 * mm], header=False))
story.append(PageBreak())

# ============ 一、作品思路 ============
story.append(Paragraph("一、作品思路", H1))
story.append(Paragraph(
    "传统手机银行「功能入口深、操作路径长」，用户完成一笔转账平均需要 3 步以上操作。"
    "本作品构建一个可运行的银行 AI 智能体：用户只需用自然语言描述需求，系统自主完成"
    "<b>意图理解 → 任务规划 → 分级安全执行 → 结果反馈</b>的完整闭环。", BODY))
story.append(Paragraph("设计原则：", H3))
for p in [
    "<b>安全优先于智能</b>：任何操作都不得由模型直接决定资金动作，金额、账户、交易结果只来自受控工具的结构化返回。",
    "<b>规则可解释、链路可审计</b>：意图与规划采用确定性规则引擎，判定过程可写入审计日志，右侧面板以人话展示。",
    "<b>权限随风险动态变化</b>：不是给「转账」定死风险级别，而是按当日累计金额实时升降级；超日限额直接拦截。",
    "<b>可中断、可回退、可接管</b>：复杂任务在任意门禁点可由用户取消，资金不发生变动；异常时转人工。",
    "<b>双沙箱隔离</b>：代码沙箱执行受限代码，数据沙箱隔离银行核心库，不连接任何生产系统。",
    "<b>时间可模拟</b>：支持「一天后/一个月后」快进，自动结算房租、订阅、工资、理财派息与随机日常流水。",
]:
    story.append(Paragraph("• " + p, BODY))

# ============ 二、整体架构 ============
story.append(Paragraph("二、整体架构", H1))
story.append(Paragraph("系统分为五层：渠道层、Agent 层、安全框架层、银行核心沙箱、时间模拟引擎。安全框架以「横切」方式插入 Agent 与银行核心之间，业务代码无法绕过权限门直接调用资金接口。", BODY))
arch = [
    [P("层级", CELLH), P("组成", CELLH), P("职责", CELLH)],
    [P("渠道层"), P("暗色 Web 聊天界面"), P("对话输入、确认卡、MFA 验证卡、最近5条历史 chips、右侧人话审计日志、顶部日期/余额/日限")],
    [P("Agent 层"), P("intent.py / planner.py / executor.py"), P("意图识别、槽位抽取、同姓消歧、多意图 DAG 规划、执行状态机")],
    [P("安全框架"), P("policy.py / guard.py / mfa.py / audit.py"), P("绿黄红分级、注入防御、熔断、短信人脸强验证、全链路审计")],
    [P("银行核心沙箱"), P("db.py / service.py / data_sandbox.py"), P("账户转账、理财、卡片、订阅、订单、资金锁定、通讯录（SQLite）")],
    [P("时间模拟引擎"), P("service.time_travel"), P("虚拟时钟、月度事件结算、随机日常流水生成")],
    [P("代码沙箱"), P("code_sandbox.py"), P("受限子进程执行生成代码，超时强杀，禁危险模块")],
]
story.append(tbl(arch, [26*mm, 50*mm, 94*mm]))
story.append(Spacer(1, 3*mm))
story.append(Paragraph("请求处理链路：用户消息 → 注入/熔断检查 → 意图识别（含多意图拆分）→ DAG 规划 → 权限预检（理财起购/日限额）→ 用户确认 → 短信/人脸强验证 → 银行核心执行 → 人话审计留痕 → 追加生日/纪念日里程碑提醒。", SMALL))

story.append(PageBreak())

# ============ 三、核心算法 ============
story.append(Paragraph("三、核心算法", H1))

story.append(Paragraph("3.1 中文金额与称谓归一", H2))
story.append(Paragraph("用户常说「五百」「一千二」「两千五」「两千五」。算法按中文数位累加，并对省略尾数的口语补位：两千五 = (2×1000) + 5×100 = 2500。金额提取时自动跳过 R1-R5、A123 这类产品代码数字，避免把「R2」误识别为 2 元。称谓「我爱人/老婆/媳妇」映射到配偶，「妈妈/老妈」映射到母亲，从根上解决指代不唯一。", BODY))

story.append(Paragraph("3.2 意图识别与槽位补全", H2))
story.append(Paragraph("采用「有序规则 + 槽位抽取」的确定性方案，规则按高风险动作优先排序。关键槽位缺失时不臆测，进入 clarify 状态逐项追问。口语化表达广泛支持：", BODY))
for p in [
    "「购买一千元的R2」→ 产品=稳健增利R2，金额=1000；",
    "「取消爱奇艺和QQ音乐」→ 同时取消两项订阅；",
    "「取消爱奇艺，恢复QQ音乐」→ 按动作词与服务名位置远近拆成两步；",
    "「给老张转500」→ 同姓多人列出选择，同姓仅一人先确认；",
    "「我的银行卡丢了」→ 列出所有卡片让用户选哪张挂失；直接说「信用卡丢了」则跳过询问。",
]:
    story.append(Paragraph("• " + p, BODY))

story.append(Paragraph("3.3 多轮上下文记忆", H2))
story.append(Paragraph("会话对象记住上一笔转账的收款人与金额。用户先说「给妈妈转500」，确认后再说「再转200」，系统自动把收款人解析为韩梅梅，无需重复报名字。AA 拆分同理：「680四个人AA」自动算出每人170元。这把系统从「一问一答填表」升级为「能听懂上下文的对话」。", BODY))

story.append(Paragraph("3.4 动态预算 DAG（智能资金分配）", H2))
story.append(Paragraph("用户一句话：「帮我看看上个月哪些钱花得不合理，把省下来的钱一半存定期，一半买理财」，系统自动展开四步依赖链：", BODY))
budget = [
    [P("步骤", CELLH), P("操作", CELLH), P("风险", CELLH), P("说明", CELLH)],
    [P("s0"), P("分析不合理消费"), P("绿"), P("扫描上月餐饮/购物/娱乐超支品类，列出可削减金额")],
    [P("s1"), P("计算可省金额"), P("绿"), P("收敛建议每月强制储蓄额")],
    [P("s2"), P("一半存定期"), P("黄"), P("开立6个月定期存款（年化1.55%）")],
    [P("s3"), P("一半自动买理财"), P("红"), P("按可用金额自动选能买的产品里收益率最高的")],
]
story.append(tbl(budget, [14*mm, 36*mm, 16*mm, 98*mm]))
story.append(Paragraph("关键：理财产品不是写死R2，而是按可用金额动态选品——750元不够R2起购1000，自动降到R1货币基金；3000元能买R3就买R3。真正体现 Agent 的自主决策。", SMALL))

story.append(Paragraph("3.6 任务 DAG 规划", H2))
story.append(Paragraph("每个意图展开为带依赖的步骤节点。跨场景生日意图已金融化（非电商导购），展开为四步：", BODY))
dag = [
    [P("步骤", CELLH), P("操作", CELLH), P("风险", CELLH), P("说明", CELLH)],
    [P("s0"), P("birthday_info"), P("绿"), P("识别纪念日，提示倒计时")],
    [P("s1"), P("funds_lock"), P("黄"), P("预留¥2000生日专项资金（锁定活期，专款专用）")],
    [P("s2"), P("birthday_wealth_offer"), P("绿"), P("推荐生日专属稳健理财R2/R3，让闲钱在等待期增值")],
    [P("s3"), P("credit_card_benefit"), P("绿"), P("匹配信用卡生日月商圈餐饮/购物满减权益")],
]
story.append(tbl(dag, [14*mm, 40*mm, 14*mm, 98*mm]))

story.append(Paragraph("3.7 动态风险分级与预检", H2))
story.append(Paragraph("权限级别执行前实时计算：转账风险 = 当日累计 + 本笔，累计 >1000 元即升级红色。此外在进入 MFA 之前先做两道预检：(1) 理财申购金额是否达到起购门槛；(2) 转账金额是否超过默认卡日限额。未通过直接拒绝，不让用户走完人脸才被拒。", BODY))

story.append(Paragraph("3.8 时间模拟引擎", H2))
story.append(Paragraph("系统维护一个虚拟时钟（settings 表 sim_now）。用户说「一天后/三天后/一个月后」即推进时间，自动结算：", BODY))
tt = [
    [P("日期", CELLH), P("自动发生的事", CELLH)],
    [P("每月 1 号"), P("房租 ¥3,500 给房东；生效订阅全部扣费；理财按年化收益率月度派息")],
    [P("每月 10 号"), P("工资 ¥5,200 到账")],
    [P("区间内随机"), P("每天最多 3 笔日常流水：餐饮/交通/购物/娱乐，商户金额随机；约一半概率有 AA/红包收入")],
]
story.append(tbl(tt, [30*mm, 136*mm]))
story.append(Paragraph("所有事件写入 transactions 表，按 tx_time 降序展示；时间范围查询（近30天/近3个月）相对虚拟时钟计算。", SMALL))

story.append(Paragraph("3.6 执行状态机", H2))
story.append(Paragraph("会话状态由 plan / idx / awaiting / clarify / human 描述：绿色节点连续自动执行，遇黄/红节点暂停弹确认卡；红色确认后进入 MFA 门禁。门禁前零副作用——暂停态不产生任何资金变动。", BODY))

story.append(PageBreak())

# ============ 四、安全设计 ============
story.append(Paragraph("四、安全设计", H1))
story.append(Paragraph("4.1 权限分级矩阵", H2))
perm = [
    [P("级别", CELLH), P("策略", CELLH), P("典型操作", CELLH)],
    [P("绿色"), P("自动执行"), P("余额查询、流水查询、账单分析、异常扫描、通讯录/订阅/卡片查询、产品列表推荐、时间快进、生日提醒")],
    [P("黄色"), P("用户确认"), P("小额转账(日累计≤1000)、定时转账、AA、取消/恢复订阅、开卡、限额调整、卡片锁定、理财赎回、资金锁定、礼品下单")],
    [P("红色"), P("强验证"), P("大额转账(日累计>1000)、卡片挂失/解挂/解锁、理财申购")],
]
story.append(tbl(perm, [16*mm, 24*mm, 126*mm]))

story.append(Paragraph("4.2 五道防线", H2))
for p in [
    "第一道·输入侧注入防御：11 类中英双语正则，覆盖「忽略指令/绕过权限/伪造验证通过/提额至无限」等表达，命中即拒绝并审计。",
    "第二道·策略侧不可篡改：风险判定只接收 op 与结构化 args，不接收任何用户传入的「风险级别」。",
    "第三道·动作侧强验证：红色操作必须通过短信验证码或人脸（演示模拟），验证码与会话绑定；同一批次多笔红色操作只需验证一次，通过后批量执行。",
    "第四道·行为侧熔断：连续失败 3 次锁定 10 分钟，成功执行一次即清零。",
    "第五道·结果侧审计：每条消息产生完整事件链，右侧面板以人话展示（你说了什么/你确认了什么/结果如何）；审计日志采用 SHA-256 哈希链，每条记录包含 prev_hash 与自身 hash，任何篡改都会被 verify_chain() 检测到。",
]:
    story.append(Paragraph("• " + p, BODY))

story.append(Paragraph("4.3 双沙箱", H2))
story.append(Paragraph("<b>数据沙箱</b>：银行核心读写独立 SQLite 库，全部参数化查询防注入，可一键重置。<b>代码沙箱</b>：用户/Agent 生成的代码在隔离临时目录子进程中运行，5 秒超时强杀，静态扫描禁止 import os/subprocess/socket 等危险模块。", BODY))

# ============ 五、代码架构 ============
story.append(Paragraph("五、代码架构", H1))
code = """banking-agent/
├── run.py                  # 启动入口（启动服务并自动开浏览器）
├── gen_pdf.py              # 本文档生成脚本
├── 启动智银银行AI助手.bat   # 双击启动
├── app/
│   ├── main.py             # FastAPI 路由：/chat /mfa/* /audit /overview /reset /sandbox/run
│   ├── agent/
│   │   ├── nlp.py          # 中文数字归一、称谓解析、时间范围解析
│   │   ├── intent.py       # 30+ 有序意图规则、多意图拆分、同姓消歧
│   │   ├── planner.py      # 意图 → DAG 节点展开
│   │   └── executor.py     # 会话状态机 + 预检 + 人话审计
│   ├── security/
│   │   ├── policy.py       # 绿/黄/红 + 动态累计分级
│   │   ├── guard.py        # 注入正则 + 熔断器
│   │   ├── mfa.py          # 短信验证码 / 人脸（模拟）
│   │   └── audit.py        # 环形缓冲审计日志 + SHA-256 哈希链（防篡改）
│   ├── bank/
│   │   ├── db.py           # SQLite 建表 + 种子数据（34位联系人/双卡/4订阅）
│   │   └── service.py      # 银行核心白名单 DISPATCH + 时间快进引擎
│   └── sandbox/
│       ├── code_sandbox.py
│       └── data_sandbox.py
├── static/index.html       # 三栏暗色聊天 UI（左场景/中对话/右审计）
├── tests/test_all.py       # 63 条端到端测试（单意图/多意图/控制词/注入防御）
└── data/banking.db         # 可编辑数据库"""
story.append(Paragraph(code.replace(" ", "&nbsp;").replace("\n", "<br/>"), CODE))

story.append(PageBreak())

# ============ 六、系统功能 ============
story.append(Paragraph("六、系统功能覆盖", H1))
func = [
    [P("场景", CELLH), P("已实现能力", CELLH), P("示例语句", CELLH), P("风险", CELLH)],
    [P("智能转账"), P("人名/称谓/手机号、同姓消歧、日限额拦截、定时转账、AA"),
     P("给妈妈转500；给老张转500（列多人选择）；每月1号给房东转3500"), P("黄/红")],
    [P("账单分析"), P("分类统计、时间范围过滤、异常交易识别、按时间排序"),
     P("近一个月的流水；分析本月账单；有异常交易吗"), P("绿")],
    [P("理财操作"), P("产品列表、风测匹配推荐、对比、起购校验、申购记录持仓、月度派息"),
     P("推荐理财；购买1000元的R2；申购稳健增利 5000"), P("绿/红")],
    [P("卡片管理"), P("开卡、虚拟卡、限额调整并顶部同步、交易锁定、挂失选卡、解挂"),
     P("再办一张银行卡；把日限调到1000；我的信用卡丢了"), P("黄/红")],
    [P("订阅代扣"), P("一键查询、单个/多个同时取消、恢复、混合操作拆分"),
     P("取消爱奇艺和QQ音乐；取消爱奇艺恢复QQ音乐"), P("绿/黄")],
    [P("时间快进"), P("一天/三天/一周/一月/三月/半年/一年，自动结算收支与随机流水"),
     P("一天后；三个月后；半年后"), P("绿")],
    [P("跨场景联动"), P("生日金融方案：专项资金锁定、专属理财推荐、信用卡商圈权益匹配、里程碑提醒"),
     P("我爱人生日快到了"), P("绿/黄")],
    [P("智能预算"), P("分析不合理消费→计算可省金额→一半定期一半理财，按金额自动选最优产品"),
     P("上月哪些钱花得不合理，省下来一半定期一半理财"), P("绿/黄/红")],
    [P("年终奖规划"), P("年度维度五步DAG：消费诊断→应急金→50%定期→30%R2理财→20%专项目标；每年1月1日自动发3-5万年终奖"),
     P("我发了3万年终奖帮我规划"), P("绿/黄/红")],
    [P("多轮对话"), P("记住上次收款人，支持「再转200」跟随；AA拆分自动计算"),
     P("再转200；680四个人AA"), P("黄")],
    [P("通讯录"), P("34位联系人含同姓、关系标签、父母生日、配偶生日/结婚纪念日"),
     P("我的通讯录都有谁"), P("绿")],
]
story.append(tbl(func, [20*mm, 52*mm, 78*mm, 16*mm]))

story.append(Spacer(1, 4*mm))
story.append(Paragraph("数据库表设计（可编辑）", H3))
db_t = [
    [P("表", CELLH), P("关键字段", CELLH)],
    [P("customers"), P("人名、手机号、身份证、称谓别名、配偶、本人生日、配偶生日、结婚纪念日、风测等级、余额")],
    [P("cards"), P("卡号、银行、卡类型、日限额、状态(正常/挂失/冻结)、是否默认")],
    [P("transactions"), P("收支方向、金额、分类、交易对方、备注、tx_time（按时间排序）")],
    [P("subscriptions"), P("服务名、每期扣费、周期、下次扣费日、状态")],
    [P("wealth_holdings"), P("产品、本金、年化收益率、买入日、状态（每月1号派息）")],
    [P("scheduled_transfers"), P("收款人、金额、周期、下次执行")],
    [P("orders / funds_locks"), P("订单明细 / 锁定金额、原因、解冻日")],
    [P("settings"), P("key-value，存虚拟当前日期 sim_now")],
    [P("audit_logs"), P("时间、会话、事件类型、决策详情（右侧人话日志）")],
]
story.append(tbl(db_t, [38*mm, 128*mm]))

# ============ 七、UI 与交互 ============
story.append(Paragraph("七、界面与交互", H1))
story.append(Paragraph("采用三栏暗色 Web 布局（仿豆包/DeepSeek 风格）：", BODY))
for p in [
    "<b>左侧场景栏</b>：6 大场景分组（转账/账单/理财/卡片/订阅/跨场景），一键触发典型指令，降低演示门槛。",
    "<b>中间对话区</b>：渐变气泡、欢迎卡、风险图例（绿/黄/红）、黄色确认卡与红色强验证卡（带左侧色条高亮、金额大字号）。",
    "<b>右侧审计面板</b>：人话操作日志，按时间倒序，事件类型着色（user/execute/blocked），不显示任何代码或技术字段。",
    "<b>顶部信息栏</b>：渐变 Logo、用户名、📅当前模拟日期、活期余额、一键重置按钮，实时刷新。",
    "<b>历史记录 chips</b>：输入框上方显示最近5条问题，点击重发，超5条自动挤掉最旧。",
    "<b>MFA 批量确认</b>：多笔转账累计触发红色时，一次人脸验证通过后同批所有红色节点自动执行，无需重复验证。",
    "<b>生日里程碑提醒</b>：仅父母+配偶生日/结婚纪念日，在7天/3天/1天/当天各提醒一次，中间不打扰。",
]:
    story.append(Paragraph("• " + p, BODY))

# ============ 八、部署 ============
story.append(Paragraph("八、部署与运行", H1))
story.append(Paragraph("环境：Python 3.10+，无需 GPU、无需外部大模型密钥。双击「启动智银银行AI助手.bat」即可自动启动服务并打开浏览器（http://127.0.0.1:8000）。数据库文件位于 data/banking.db，可用 DB Browser for SQLite 直接打开编辑。", BODY))

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm)
doc.build(story)
print("PDF generated:", OUT)
