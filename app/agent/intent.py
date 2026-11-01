# -*- coding: utf-8 -*-
"""
意图识别：有序规则 + 槽位抽取 + 多意图拆分。
按"高风险动作优先"排序，避免误判。
返回 (control, [(intent, slots)])，保序，后续由 planner 展开为 DAG。
"""
import re
from . import nlp


# 控制词（fullmatch + 尾部标点容错）
CONTROL_PATTERNS = [
    ("confirm", re.compile(
        r"^(确认|确认执行|确定|好的?|好|可以|行|嗯+|对|是的?|没问题|ok|okay|yes|y|"
        r"执行|同意|继续|下一步|就这么办|办吧|开始|搞定|就这样)[!。,.，~～\s]*$", re.I)),
    ("cancel", re.compile(
        r"^(取消|算了|不要了?|不用了?|停|停止|终止|撤回|放弃|不了|别办了?|先不办|先别|等等)"
        r"(\s*(转账|操作|这笔|这个|交易|订单|挂失|办卡))?[!。,.，~～\s]*$", re.I)),
    ("human", re.compile(r"(转人工|人工客服|人工服务|找人工|我要人工|叫人工|真人|接人工|人工)")),
    ("ai_back", re.compile(r"(恢复\s*ai|回到\s*ai|继续\s*ai|切回\s*ai|ai\s*继续)", re.I)),
]


# 多意图连接词（无逗号也能拆）
_SPLIT_RE = re.compile(r"[，,。；;]\s*|然后|接着|再帮|并且|以及|顺便|之后(?!的)|再给|又给|也给|另外|再转|又转")


def _slots_from_amounts(text):
    """从文本中抓所有金额候选（屏蔽卡号/手机号附近数字）。"""
    # 屏蔽区域：卡号/尾号/手机号/账号 后20字符
    mask = [False] * len(text)
    for kw in ("卡号", "尾号", "手机号", "身份证", "账号", "号码", "后四位", "有效期"):
        for m in re.finditer(kw, text):
            for i in range(m.start(), min(m.end() + 20, len(text))):
                mask[i] = True
    out = []
    for m in re.finditer(r"(?<![RrAa])\d+(?:\.\d+)?\s*(?:万|亿|块|元)?", text):
        if any(mask[i] for i in range(m.start(), m.end())):
            continue
        v = nlp.parse_amount(m.group(0))
        v = nlp.convert_if_foreign(text, v)
        if v:
            out.append(v)
    for m in re.finditer(r"[零一二两三四五六七八九十百千万]+(?:块|块钱|元)?", text):
        if any(mask[i] for i in range(m.start(), m.end())):
            continue
        v = nlp.parse_amount(m.group(0))
        v = nlp.convert_if_foreign(text, v)
        if v and v not in out:
            out.append(v)
    return out


def _extract_payee(text, contacts):
    """根据联系人列表解析收款人。contacts: {name: customer_row}。"""
    rel = nlp.resolve_alias(text)
    if rel == "spouse":
        for c in contacts.values():
            if c.get("spouse_name"):
                return c["spouse_name"], "配偶"
    if rel == "mom":
        for c in contacts.values():
            aliases = (c.get("relation_alias") or "").split(",")
            if "妈妈" in aliases or "老妈" in aliases or "我妈" in aliases:
                return c["name"], "母亲"
    if rel == "dad":
        for c in contacts.values():
            aliases = (c.get("relation_alias") or "").split(",")
            if "爸爸" in aliases or "老爸" in aliases:
                return c["name"], "父亲"
    phone = nlp.extract_phone(text)
    if phone:
        for c in contacts.values():
            if c.get("phone") == phone:
                return c["name"], "手机号"
    names = sorted(contacts.keys(), key=len, reverse=True)
    for nm in names:
        if nm and nm in text:
            return nm, "姓名"
    return None, None


def _note_extract(text):
    m = re.search(r"备注[:：]?([\u4e00-\u9fa5]{2,12})", text)
    if m:
        return m.group(1)
    for kw in ["生活费", "房租", "还款", "借款", "零花钱", "孝敬", "AA", "聚会"]:
        if kw in text:
            return kw
    return ""


def _parse_single(text, contacts):
    """单段文本 -> [(intent, slots)]。"""
    found = []
    def add(i, s): found.append((i, s))
    SVC_LIST = ["爱奇艺", "腾讯视频", "网易云音乐", "QQ音乐", "百度网盘", "B站"]

    # ---- 订阅混合动作预处理 ----
    _cancel_words = re.compile(r"(取消|关闭|退订|停掉|关掉|停了)")
    _resume_words = re.compile(r"(重新订阅|恢复|重新开通|再续|续订|开通)")
    cancel_pos = [(m.start(), m.group(0)) for m in _cancel_words.finditer(text)]
    resume_pos = [(m.start(), m.group(0)) for m in _resume_words.finditer(text)]
    cancel_svcs, resume_svcs = [], []
    for svc in SVC_LIST:
        for m in re.finditer(re.escape(svc), text):
            spos = m.start()
            nc = min([abs(spos - p) for p, _ in cancel_pos], default=9999)
            nr = min([abs(spos - p) for p, _ in resume_pos], default=9999)
            (cancel_svcs if nc < nr else resume_svcs).append(svc)
    cancel_svcs = list(dict.fromkeys(cancel_svcs))
    resume_svcs = list(dict.fromkeys(resume_svcs))
    if cancel_svcs and resume_svcs and cancel_pos and resume_pos:
        add("subscription_cancel", {"services": cancel_svcs, "service": cancel_svcs[0]})
        add("subscription_resume", {"services": resume_svcs, "service": resume_svcs[0]})
        return found

    # ---- 时间快进（修：去掉裸"过"，要求时间词+后/以后/之后/到了/快进/跳）----
    if re.search(r"(天|周|星期|个月|月|半年|年).{0,4}(后|以后|之后|到了|快进|跳|过去)", text) or \
       re.search(r"(时间快进|快进|跳几天|跳几个月)", text) or \
       re.search(r"^(明天|后天|大后天)$", text):
        months, days = 0, 0
        if re.search(r"(一年|12个月|1年)", text): months = 12
        elif re.search(r"(半年|6个月)", text): months = 6
        elif re.search(r"(三个月|3个月)", text): months = 3
        elif re.search(r"(两个月|2个月)", text): months = 2
        elif re.search(r"(一个月|一月|个月后|月后|下个月|月以后|月之后)", text): months = 1
        if re.search(r"明天", text): days = 1
        elif re.search(r"后天", text): days = 2
        elif re.search(r"(一周|一星期|7天|七天)", text): days = 7
        elif re.search(r"三天|3天", text): days = 3
        else:
            dm = re.search(r"([一二两三四五六七八九十\d]+)\s*天", text)
            if dm:
                cn = dm.group(1)
                if cn.isdigit(): days = int(cn)
                else:
                    cm = {"一":1,"两":2,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
                    if cn == "十": days = 10
                    elif cn.startswith("十"): days = 10 + cm.get(cn[1], 0)
                    elif cn.endswith("十"): days = cm.get(cn[0], 1) * 10
                    else: days = cm.get(cn, 1)
            else: days = 1
        add("time_travel", {"months": months, "days": days})
        return found

    # 智能预算
    if re.search(r"(不合理|浪费|不该花|省下来|节约|砍掉|超支).*(定期|存款).*(理财|R\d)|(不合理|浪费|省下来).*(一半|一半一半|拆分).*(存|买|投)", text):
        add("smart_budget", {"period": "上月"})
        return found
    # 年终奖
    if re.search(r"(年终奖|发奖金|年终|年底奖金)", text):
        m = re.search(r"(\d+(?:\.\d+)?)\s*万", text)
        if m: bonus = float(m.group(1)) * 10000
        else:
            m2 = re.search(r"([一二三四五六七八九十两\d]+)\s*万", text)
            if m2:
                cn = {"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
                bonus = cn.get(m2.group(1), 1) * 10000
            else: bonus = nlp.parse_amount(text) or 20000.0
        add("annual_bonus_plan", {"amount": float(bonus)})
        return found
    # 汇总
    if re.search(r"^(汇总|总结|按类别|分类汇总|分类总结)$", text) or re.search(r"汇总一下|分类总结|按类别汇总", text):
        add("bill_analysis", {"period": "全部"})
        return found

    # 理财赎回（先于申购）
    if re.search(r"(赎回|卖出|取回).{0,4}(理财|基金|持仓)?", text) and "申购" not in text and "买" not in text[:2]:
        amts = _slots_from_amounts(text)
        add("wealth_redeem", {"amount": amts[0] if amts else None})
        return found
    # 理财申购
    _buy = re.search(r"(申购|买入|购买|买点|投点|买|投)", text)
    _prod_id = re.search(r"(安享\s?货币?\s?A?|稳健\s?增利?|平衡\s?配置?|成长\s?优选?|进取\s?股票?|货币\s?A?|R\s?[1-5])", text)
    if _buy and _prod_id and not re.search(r"(赎回|卖出|我要买什么|推荐)", text):
        amts = _slots_from_amounts(text)
        prod = _prod_id.group(0).replace(" ", "")
        if "货币" in prod: prod = "安享货币A"
        elif "稳健" in prod or prod == "R2": prod = "稳健增利R2"
        elif "平衡" in prod or prod == "R3": prod = "平衡配置R3"
        elif "成长" in prod or prod == "R4": prod = "成长优选R4"
        elif "进取" in prod or prod == "R5": prod = "进取股票R5"
        elif prod == "R1": prod = "安享货币A"
        add("wealth_purchase", {"product": prod, "amount": amts[0] if amts else None})
        return found

    # 卡片：挂失 -> 解挂 -> 额度 -> 冻结 -> 虚拟卡 -> 开卡
    if re.search(r"(挂失|卡.{0,4}(丢|不见|找不到|没了)|卡被盗|丢失|丢了)", text) and not re.search(r"(解挂|解冻|取消挂)", text):
        card_hint = ""
        if "信用卡" in text: card_hint = "信用卡"
        elif "虚拟卡" in text: card_hint = "虚拟卡"
        elif "借记卡" in text or "储蓄卡" in text: card_hint = "借记卡"
        add("report_loss", {"card_hint": card_hint})
        return found
    if re.search(r"(解挂|解除挂失|取消挂失|解冻|解锁|恢复.{0,2}卡)", text):
        add("cancel_loss" if re.search(r"解挂|解除挂失|取消挂失", text) else "card_unlock", {})
        return found
    if re.search(r"(额度|限额|日限|单日限额|日转账限额|每天限额|支付限额|取款限额|提款限额|取现限额).{0,8}(调|改|提高|降|提到|调到|调高|调低|改成|升到|压到|设为|设到|是多少|多少|查询|看看|知道|提高|加大)|(调高|调低|提高|降低|改|调一下?|上调|下调|放宽|收紧|提升|增加|减少|放大|加大).{0,6}(额度|限额|日限|单日限额|支付限额|取款限额|提款限额)", text):
        amts = _slots_from_amounts(text)
        add("card_limit_adjust", {"limit": amts[0] if amts else None})
        return found
    if re.search(r"(锁|冻结|封锁).{0,4}(卡|卡片|交易)|(把|将|请).{0,4}(卡|卡片).{0,4}(锁|冻结|封锁|锁死|停|停用)", text):
        add("card_freeze", {})
        return found
    if "虚拟卡" in text:
        add("virtual_card_apply", {})
        return found
    if re.search(r"(办|开|申请|要).{0,4}(一?张|个)?\s*(借记卡|信用卡|储蓄卡|银行卡|卡)", text) or \
       re.search(r"^(再办|新开|新办|再开|再申请).{0,3}(张|个)?$", text):
        ctype = "信用卡" if "信用卡" in text else "借记卡"
        add("apply_card", {"card_type": ctype})
        return found

    # 订阅：恢复先于取消
    if (re.search(r"(重新订阅|恢复|重新开通|开通|续订|再续|开回来|续上|重新用)", text) and
        re.search(r"(爱奇艺|腾讯视频|网易云音乐|网易云|QQ音乐|百度网盘|B站)", text)):
        services = [s for s in SVC_LIST if s in text or (s == "网易云音乐" and "网易云" in text)]
        add("subscription_resume", {"services": services, "service": services[0] if services else ""})
        return found
    if (re.search(r"(取消|关闭|退订|停掉|关掉|不用了|不想用|别再扣|别扣|不要续|停了|关了|取消自动|关掉自动).{0,12}(订阅|自动续费|续费|包月|会员|扣费|全部|服务|代扣)", text) or
        re.search(r"(取消|退订|关掉|停掉|别扣|别再扣|停了|关了).{0,3}(爱奇艺|腾讯|网易云|QQ音乐|视频|音乐|网盘|B站)", text) or
        re.search(r"(爱奇艺|腾讯|网易云|QQ音乐|视频|音乐|网盘|B站).{0,6}(都|全)?(取消|退订|关掉|停掉|不要|别续)", text)):
        services = [s for s in SVC_LIST if s in text or (s == "网易云音乐" and "网易云" in text)]
        add("subscription_cancel", {"services": services, "service": services[0] if services else ""})
        return found

    # 定时转账：list 先于 add，再于 cancel
    if re.search(r"(查看|列表|有哪些|查询|我的|看看).{0,6}(定时|自动转|每月转|自动扣款计划)|^(定时|自动转)", text):
        add("list_scheduled", {})
        return found
    if (re.search(r"每\s*个?\s*(月|周|天|星期)", text) or re.search(r"(设|建|加|新增).{0,3}定时", text)) and \
       re.search(r"(转|打|汇)", text):
        payee, how = _extract_payee(text, contacts)
        amts = _slots_from_amounts(text)
        schedule = "每月1号"
        sm = re.search(r"(每月|每周|每天)(\d{1,2})?[号日]?", text)
        if sm:
            if sm.group(1) == "每周": schedule = "每周" + ("一" if "一" in text else "五")
            elif sm.group(2): schedule = f"每月{sm.group(2)}号"
        add("scheduled_transfer_add", {"to": payee, "amount": amts[0] if amts else None,
                                       "schedule": schedule, "note": _note_extract(text)})
        return found
    if re.search(r"(取消定时|取消自动转|取消每月|停掉定时)", text):
        add("scheduled_transfer_cancel", {})
        return found

    # AA
    if re.search(r"AA|拼单|均摊|平摊", text) or (re.search(r"(聚餐|吃饭).{0,6}几个人", text)):
        amts = _slots_from_amounts(text)
        pm = re.search(r"(\d+)\s*人", text)
        n = int(pm.group(1)) if pm else None
        add("aa_split", {"total": amts[0] if amts else None, "n": n})
        return found
    # 资金锁定
    if re.search(r"(锁定|冻结|预留|存一部分|留点|存点|攒点|存\d+|存\s*[一二两三四五六七八九十百千万]+).{0,10}(钱|资金|活期|应急)", text) and "卡" not in text:
        amts = _slots_from_amounts(text)
        reason = "生日专项" if "生日" in text else "专项预留"
        add("funds_lock", {"amount": amts[0] if amts else None, "reason": reason})
        return found
    # 下单
    if re.search(r"(买|订|订购|下单|送|要).{0,6}(鲜花|蛋糕|花|玫瑰|礼物|礼品)", text):
        item = "鲜花" if re.search(r"(花|玫瑰)", text) else "蛋糕"
        add("place_order", {"order_type": item})
        return found

    # 转账（必须有金额或明确收款人，避免"我能转给谁"被误判）
    _has_amt = bool(_slots_from_amounts(text))
    _has_payee = bool(_extract_payee(text, contacts)[0])
    if ((re.search(r"(转|打|汇|划|转账|汇款|转给|打给|汇给|划给|转过去|打过去|汇过去|转一笔|打一笔|转点钱|打点钱).{0,15}(钱|款)?", text) and (_has_amt or _has_payee)) or
       re.search(r"给.{2,6}(转|打|汇|划|转过去|打过去)", text) or
       re.search(r"给.{2,6}\s*[\d一二两三四五六七八九十百千万]+\s*(块|元|钱)?$", text)):
        payee, how = _extract_payee(text, contacts)
        amts = _slots_from_amounts(text)
        slots = {"to": payee, "amount": amts[0] if amts else None,
                 "note": _note_extract(text), "candidates": []}
        if not payee:
            surname = nlp.parse_nickname(text)
            if surname:
                matches = [(n, contacts[n].get("phone", "")) for n in contacts if n.startswith(surname)]
                if matches:
                    slots["candidates"] = matches
        add("transfer", slots)
        return found

    # 查询类：holdings 必须在 list_products 前
    if re.search(r"(余额|剩多少|卡里有多少|有钱吗|可用|还有多少钱|账户.{0,4}多少|卡里还剩|我有多少存款|资产多少|活期多少|还剩多少|我还有多少|钱够吗|账户余额|账上.{0,4}多少|里面有多少)", text):
        add("query_balance", {})
        return found
    if re.search(r"(持仓|收益.{0,4}(多少|明细|查询|情况)|赚了多少|理财.{0,4}(盈亏|收益|赚))", text):
        add("get_holdings", {})
        return found
    if re.search(r"(异常|可疑|不正常|风控|被骗|乱扣|被拒|拒绝|无效|拒绝付款|付款失败|交易失败|被盗|盗刷)", text):
        add("anomaly_scan", {})
        return found
    if re.search(r"(账单分析|账单报告|消费.{0,4}(分析|统计|报告)|月度报告|年度报告|分类统计|分析.{0,8}账单|账单.{0,4}分析|信用卡账单|账单到期|出一个账单)", text):
        add("bill_analysis", {"period": "年" if re.search(r"年|年度", text) else "月"})
        return found
    if re.search(r"(流水|交易记录|交易明细|交易情况|交易信息|最新交易|最新.{0,4}交易|明细|消费记录|花了?多少|开销|支出|账单|交易|交易列表|付款记录)", text):
        days = nlp.parse_time_range(text)
        add("query_transactions", {"days": days})
        return found
    if re.search(r"(订阅|自动续费|扣费|会员|代扣|哪些.{0,4}扣|开.{0,2}了哪些会员)", text):
        add("list_subscriptions", {})
        return found
    if re.search(r"(通讯录|联系人|好友|朋友|能转给谁)", text):
        add("list_contacts", {})
        return found
    if re.search(r"(几张卡|多少张卡|银行卡数量|我有.*卡|银行卡|我的卡|卡片|卡列表)", text):
        add("list_cards", {})
        return found
    if re.search(r"(推荐|适合|帮我选).{0,6}(理财|产品|基金)", text) or re.search(r"买什么理财", text):
        add("recommend_products", {})
        return found
    if re.search(r"(对比|比较|哪个好).{0,6}(理财|产品)", text):
        add("compare_products", {})
        return found
    if re.search(r"(理财|产品|基金)", text):
        add("list_products", {})
        return found
    # 生日
    if re.search(r"(生日|纪念日|节日快乐)", text):
        add("cross_scene_birthday", {"relation": nlp.resolve_alias(text) or "spouse"})
        return found

    # 模糊兜底
    KEYWORDS = [
        ("query_balance", ["余额", "剩", "多少钱", "存款", "资产"]),
        ("query_transactions", ["流水", "交易", "明细", "账单", "消费", "花", "记录", "支出"]),
        ("list_cards", ["银行卡", "卡片"]),
        ("list_contacts", ["通讯录", "联系人", "好友"]),
        ("list_subscriptions", ["订阅", "会员", "续费", "扣费"]),
        ("recommend_products", ["理财", "推荐", "产品"]),
        ("report_loss", ["挂失", "丢了", "被盗"]),
        ("transfer", ["转", "打钱", "汇", "给"]),
    ]
    best, best_score = None, 0
    for it, kws in KEYWORDS:
        score = sum(1 for k in kws if re.search(k, text))
        if score > best_score:
            best, best_score = it, score
    if best and best_score >= 1:
        days = nlp.parse_time_range(text) if best == "query_transactions" else None
        add(best, {"days": days} if days else {})
    return found


def parse_intent(text, contacts):
    """
    返回 (control, found_list)
    control: None | 'confirm'/'cancel'/'human'/'ai_back'
    found_list: [(intent, slots)] 有序，多意图时按连接词拆分
    """
    text = (text or "").strip()
    for name, pat in CONTROL_PATTERNS:
        if pat.search(text):
            return name, []
    # 多意图拆分
    parts = [p.strip() for p in _SPLIT_RE.split(text) if p.strip()]
    if not parts:
        parts = [text]
    found = []
    for part in parts:
        found.extend(_parse_single(part, contacts))
    return None, found


if __name__ == "__main__":
    contacts = {
        "王芳": {"spouse_name": "王芳", "phone": "13800000001", "relation_alias": ""},
        "韩梅梅": {"name": "韩梅梅", "phone": "13912345678", "relation_alias": "妈妈,老妈"},
        "李雷": {"name": "李雷", "phone": "13798765432"},
    }
    for t in ["给我爱人转两千五", "查一下余额然后给妈妈转200", "我的理财收益",
              "取消爱奇艺恢复QQ音乐", "我爱人生日快到了"]:
        print(t, "=>", parse_intent(t, contacts))
