# -*- coding: utf-8 -*-
"""
银行核心业务沙箱。所有方法统一返回 (ok: bool, msg: str, data: dict|None)。
msg 即最终展示给用户的文案，避免二次生成导致数据失真（幻觉防护 L1/L3）。
"""
import random
from datetime import datetime, date
from ..sandbox import data_sandbox as ds

CUSTOMER_ID = 1  # 演示单用户


# ---------- 模拟时间 ----------
def get_sim_now():
    row = ds.query_one("SELECT value v FROM settings WHERE key='sim_now'")
    return row["v"] if row else date.today().strftime("%Y-%m-%d")


def set_sim_now(d):
    ds.execute("INSERT INTO settings(key,value) VALUES('sim_now',?) "
               "ON CONFLICT(key) DO UPDATE SET value=?", (d, d))


def _add_tx(direction, amount, category, cp, note, on_date):
    ts = f"{on_date} 09:00:00"
    ds.execute("INSERT INTO transactions(customer_id,direction,amount,category,counterparty,note,tx_time) VALUES(1,?,?,?,?,?,?)",
               (direction, amount, category, cp, note, ts))


def _random_monthly(cur, step_end, events):
    """为一个时间区间生成随机日常流水，数量按天数控制，每天最多3条。"""
    import random as _r
    from datetime import timedelta
    eateries = [("学校食堂", "午餐"), ("麦当劳", "汉堡"), ("海底捞", "聚餐"), ("瑞幸咖啡", "咖啡"),
                ("蜜雪冰城", "奶茶"), ("美团外卖", "晚餐"), ("沙县小吃", "快餐")]
    shops = [("京东", "日用品"), ("拼多多", "文具"), ("淘宝", "衣服"), ("天猫超市", "零食")]
    funs = [("B站", "大会员"), ("电影院", "周末观影"), ("Steam", "游戏"), ("网易云", "数字专辑")]
    transports = [("地铁", "通勤"), ("滴滴", "打车"), ("共享单车", "骑行")]
    # 区间天数：每天最多随机3条
    days_span = max((step_end - cur).days, 1)
    n = min(_r.randint(1, 3) * days_span, days_span * 3)
    for _ in range(n):
        day = cur + timedelta(days=_r.randint(1, days_span))
        day = min(day, step_end)
        cat = _r.choice(["餐饮", "购物", "娱乐", "交通"])
        if cat == "餐饮":
            cp, note = _r.choice(eateries); amt = round(_r.uniform(12, 80), 1)
        elif cat == "购物":
            cp, note = _r.choice(shops); amt = round(_r.uniform(15, 300), 1)
        elif cat == "娱乐":
            cp, note = _r.choice(funs); amt = round(_r.uniform(15, 68), 1)
        else:
            cp, note = _r.choice(transports); amt = round(_r.uniform(2, 25), 1)
        ds.execute("UPDATE customers SET balance=balance-? WHERE id=1", (amt,))
        _add_tx("支出", amt, cat, cp, note, day.strftime("%Y-%m-%d"))
    # 偶尔一笔小额收入（红包/AA）
    if _r.random() < 0.3 and days_span >= 5:
        day = cur + timedelta(days=_r.randint(1, days_span))
        day = min(day, step_end)
        cp = _r.choice(["李雷", "王磊", "张涛", "妈妈"])
        amt = round(_r.uniform(20, 200), 1)
        ds.execute("UPDATE customers SET balance=balance+? WHERE id=1", (amt,))
        _add_tx("收入", amt, "转账", cp, "AA/红包", day.strftime("%Y-%m-%d"))


def time_travel(months=0, days=0):
    """时间快进：从当前 sim_now 推进 months 个月 + days 天。
    每个跨过的月1号：扣订阅、付理财收益、付房租；月10号发工资。"""
    from calendar import monthrange
    start = datetime.strptime(get_sim_now(), "%Y-%m-%d").date()

    def add_months(d, n):
        y = d.year + (d.month - 1 + n) // 12
        m = (d.month - 1 + n) % 12 + 1
        day = min(d.day, monthrange(y, m)[1])
        return date(y, m, day)

    target = add_months(start, months)
    if days:
        from datetime import timedelta
        target = target + timedelta(days=days)
    cur = start
    events = []
    while cur < target:
        # 下一个月1号
        nm = add_months(cur.replace(day=1), 1)
        step_end = min(nm, target)
        # 1号事件
        if step_end == nm and nm > start:
            # 1月1日发年终奖（3-5万随机）
            if nm.month == 1:
                import random as _rnd
                bonus = _rnd.choice([30000, 35000, 40000, 45000, 50000])
                ds.execute("UPDATE customers SET balance=balance+? WHERE id=1", (bonus,))
                _add_tx("收入", bonus, "工资", "公司", "年终奖", nm.strftime("%Y-%m-%d"))
                events.append(f"{nm.strftime('%m-%d')} 年终奖到账 ¥{bonus:,.0f}")
            ds.execute("UPDATE customers SET balance=balance-3500 WHERE id=1")
            _add_tx("支出", 3500.0, "转账", "张建国", "房租", nm.strftime("%Y-%m-%d"))
            events.append(f"{nm.strftime('%m-%d')} 付房租 ¥3,500")
            subs = ds.query("SELECT service_name,amount FROM subscriptions WHERE customer_id=1 AND status='生效'")
            for s in subs:
                ds.execute("UPDATE customers SET balance=balance-? WHERE id=1", (s["amount"],))
                _add_tx("支出", s["amount"], "娱乐", s["service_name"], "自动续费", nm.strftime("%Y-%m-%d"))
            if subs:
                events.append(f"{nm.strftime('%m-%d')} 订阅扣费 ¥{sum(s['amount'] for s in subs):.0f}")
            holds = ds.query("SELECT product,principal,annual_yield FROM wealth_holdings WHERE customer_id=1 AND status='持有'")
            for h in holds:
                ret = round(h["principal"] * h["annual_yield"] / 100 / 12, 2)
                ds.execute("UPDATE customers SET balance=balance+? WHERE id=1", (ret,))
                _add_tx("收入", ret, "理财", h["product"], "月度收益", nm.strftime("%Y-%m-%d"))
            if holds:
                tot = round(sum(h["principal"] * h["annual_yield"] / 100 / 12 for h in holds), 2)
                events.append(f"{nm.strftime('%m-%d')} 理财收益到账 ¥{tot:,.2f}")
            # 执行定时转账（每月1号生效中的计划）
            scheds = ds.query("SELECT to_name,amount,note FROM scheduled_transfers WHERE customer_id=1 AND status='生效'")
            for sc in scheds:
                ds.execute("UPDATE customers SET balance=balance-? WHERE id=1", (sc["amount"],))
                _add_tx("支出", sc["amount"], "转账", sc["to_name"], sc["note"] or "定时转账", nm.strftime("%Y-%m-%d"))
            if scheds:
                tot_s = sum(sc["amount"] for sc in scheds)
                events.append(f"{nm.strftime('%m-%d')} 定时转账 ¥{tot_s:,.0f}（{len(scheds)}笔）")
        # 10号发工资
        sd = cur.replace(day=10)
        if sd > start and sd <= step_end:
            ds.execute("UPDATE customers SET balance=balance+5200 WHERE id=1")
            _add_tx("收入", 5200.0, "工资", "中央财经大学", "奖学金", sd.strftime("%Y-%m-%d"))
            events.append(f"{sd.strftime('%m-%d')} 工资到账 ¥5,200")
        # 每月随机日常流水（餐饮/交通/购物/娱乐/偶尔转账）
        _random_monthly(cur, step_end, events)
        cur = step_end
    set_sim_now(target.strftime("%Y-%m-%d"))
    bal = ds.query_one("SELECT balance b FROM customers WHERE id=1")["b"]
    head = f"⏩ 时间已快进到 {target.strftime('%Y-%m-%d')}（{target.year}年{target.month}月{target.day}日）\n本期发生："
    body = "\n".join("· " + e for e in events) if events else "· 本期无固定收支"
    return True, head + "\n" + body + f"\n当前余额 ¥{bal:,.2f}", {"new_date": target.strftime("%Y-%m-%d"), "events": len(events)}


def upcoming_reminders():
    """返回临近生日/纪念日提醒（仅父母+妻子+结婚纪念日；仅在7/3/1/0天提醒）。"""
    today = datetime.strptime(get_sim_now(), "%Y-%m-%d").date()
    me = ds.query_one("SELECT spouse_name,spouse_birthday,wedding_anniv FROM customers WHERE id=1")
    important = [
        (me["spouse_name"] or "爱人", me["spouse_birthday"], "生日"),
        ("结婚纪念日", me["wedding_anniv"], "纪念日"),
    ]
    # 只加父母
    for r in ds.query("SELECT name,birthday,relation_alias FROM customers WHERE id!=1"):
        if "妈" in r["relation_alias"] or "爸" in r["relation_alias"]:
            important.append((r["name"], r["birthday"], "生日"))
    out = []
    for name, md, kind in important:
        if not md:
            continue
        mm, dd = int(md.split("-")[0]), int(md.split("-")[1])
        try:
            this_year = today.replace(month=mm, day=dd)
        except ValueError:
            continue
        delta = (this_year - today).days
        if delta < 0:
            try:
                this_year = this_year.replace(year=today.year + 1)
            except ValueError:
                continue
            delta = (this_year - today).days
        # 只在 7/3/1/0 天提醒
        if delta in (7, 3, 1, 0):
            when = "就是今天！" if delta == 0 else f"还有 {delta} 天"
            out.append(f"🎂 {name}的{kind}（{md}）{when}，记得准备礼物")
    return out
def query_balance():
    c = ds.query_one("SELECT name,balance FROM customers WHERE id=?", (CUSTOMER_ID,))
    locks = ds.query("SELECT COALESCE(SUM(amount),0) s FROM funds_locks WHERE customer_id=? AND status='锁定中'", (CUSTOMER_ID,))
    locked = locks[0]["s"]
    avail = c["balance"] - locked
    msg = (f"您好 {c['name']}，您的活期账户余额为 ¥{c['balance']:,.2f}，"
           f"其中已锁定 ¥{locked:,.2f}，可用余额 ¥{avail:,.2f}。")
    return True, msg, {"balance": c["balance"], "locked": locked, "available": avail}


def query_transactions(days=None):
    from datetime import timedelta
    rows = ds.query(
        "SELECT direction,amount,category,counterparty,note,tx_time FROM transactions WHERE customer_id=? ORDER BY tx_time DESC",
        (CUSTOMER_ID,))
    # 按时间范围过滤（相对模拟当前日期）
    if days:
        sim = datetime.strptime(get_sim_now(), "%Y-%m-%d").date()
        cutoff = (sim - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = [r for r in rows if r["tx_time"][:10] >= cutoff]
    rng = f"近{days}天" if days else "全部"
    expense = [r for r in rows if r["direction"] == "支出"]
    income = [r for r in rows if r["direction"] == "收入"]
    total_out = sum(r["amount"] for r in expense)
    total_in = sum(r["amount"] for r in income)
    summary = (f"📊 {rng}共 {len(rows)} 笔交易：收入 ¥{total_in:,.2f}，支出 ¥{total_out:,.2f}，"
               f"净流入 ¥{total_in - total_out:,.2f}。\n明细：\n")
    if len(rows) > 15:
        out_rows = rows[:10]
        lines = [f"【{r['tx_time']}】{r['direction']} ¥{r['amount']:.2f}（{r['category']}）{r['counterparty']} {r['note'] or ''}" for r in out_rows]
        tail = f"\n…（已显示前10笔，共{len(rows)}笔）\n💡 要我按类别汇总一下吗？回复「汇总」。"
        return True, summary + "\n".join(lines) + tail, {"rows": rows, "in": total_in, "out": total_out}
    out_rows = rows
    lines = [f"【{r['tx_time']}】{r['direction']} ¥{r['amount']:.2f}（{r['category']}）{r['counterparty']} {r['note'] or ''}" for r in out_rows]
    return True, summary + ("\n".join(lines) if lines else "（该时间段内暂无交易）"), {"rows": rows, "in": total_in, "out": total_out}


def list_contacts():
    rows = ds.query(
        "SELECT name,phone,relation_alias,birthday FROM customers WHERE id!=? ORDER BY id", (CUSTOMER_ID,))
    # 主客户自己的重要日子
    me = ds.query_one("SELECT spouse_name,spouse_birthday,wedding_anniv FROM customers WHERE id=1")
    rel_label = {"妈妈":"母亲","爸爸":"父亲","老婆":"配偶","爱人":"配偶","老公":"配偶","儿子":"子女",
                 "女儿":"子女","哥哥":"兄弟","姐姐":"姐妹","弟弟":"兄弟","妹妹":"姐妹",
                 "表哥":"表亲","表姐":"表亲","舅舅":"舅","姑姑":"姑","奶奶":"祖父母","外婆":"外祖父母"}
    lines = []
    for r in rows:
        alias = r["relation_alias"] or ""
        # 识别关系标签
        rel = ""
        for k, v in rel_label.items():
            if k in alias:
                rel = v; break
        tag = f"【{rel}】" if rel else ""
        bd = f" 生日 {r['birthday']}" if r["birthday"] and rel else ""
        lines.append(f"· {tag}{r['name']}  {r['phone']}{bd}")
    head = f"您的通讯录共 {len(rows)} 位联系人：\n"
    head += f"（爱人 {me['spouse_name']} 生日 {me['spouse_birthday']}，结婚纪念日 {me['wedding_anniv']}）\n"
    return True, head + "\n".join(lines), {"rows": rows}


def bill_analysis(period="月"):
    rows = ds.query("SELECT direction,amount,category FROM transactions WHERE customer_id=?", (CUSTOMER_ID,))
    expense = [r for r in rows if r["direction"] == "支出"]
    income = [r for r in rows if r["direction"] == "收入"]
    total_out = sum(r["amount"] for r in expense)
    total_in = sum(r["amount"] for r in income)
    cat = {}
    for r in expense:
        cat[r["category"]] = cat.get(r["category"], 0) + r["amount"]
    top = sorted(cat.items(), key=lambda x: -x[1])[:3]
    top_txt = "、".join(f"{k} ¥{v:.0f}" for k, v in top)
    msg = (f"您本{period}账单：收入 ¥{total_in:,.2f}，支出 ¥{total_out:,.2f}。\n"
           f"支出主要集中在：{top_txt}。")
    return True, msg, {"in": total_in, "out": total_out, "categories": cat}


def anomaly_scan():
    rows = ds.query(
        "SELECT direction,amount,counterparty,note,tx_time FROM transactions WHERE customer_id=? ORDER BY amount DESC",
        (CUSTOMER_ID,))
    suspicious = [r for r in rows if r["amount"] >= 5000 and r["direction"] == "支出"]
    if suspicious:
        s = suspicious[0]
        msg = f"扫描到 1 笔较大支出：向 {s['counterparty']} 支出 ¥{s['amount']:.2f}（{s['tx_time']}）。如非本人操作，请立即挂失。"
    else:
        msg = "异常交易扫描完成：未发现可疑或异常大额交易。"
    return True, msg, {"suspicious": suspicious}


def list_subscriptions():
    rows = ds.query("SELECT service_name,amount,cycle,next_deduct,status FROM subscriptions WHERE customer_id=?", (CUSTOMER_ID,))
    active = [r for r in rows if r["status"] == "生效"]
    total = sum(r["amount"] for r in active)
    lines = [f"· {r['service_name']}：¥{r['amount']}/{r['cycle']}，下次扣费 {r['next_deduct']} [{r['status']}]" for r in rows]
    msg = f"当前生效订阅 {len(active)} 项，每月合计 ¥{total:.0f}：\n" + "\n".join(lines)
    return True, msg, {"rows": rows}


def list_cards():
    rows = ds.query("SELECT card_no,bank_name,card_type,daily_limit,status,expiry FROM cards WHERE customer_id=?", (CUSTOMER_ID,))
    lines = [f"· {r['card_type']} {r['card_no']}（{r['bank_name']}）日限 ¥{r['daily_limit']:,.0f}，状态：{r['status']}" for r in rows]
    return True, "您的银行卡：\n" + "\n".join(lines), {"rows": rows}


# ---------- 理财 ----------
PRODUCTS = [
    {"code": "安享货币A", "risk": "R1", "yield": 2.1, "min": 1.0},
    {"code": "稳健增利R2", "risk": "R2", "yield": 3.4, "min": 1000.0},
    {"code": "平衡配置R3", "risk": "R3", "yield": 4.8, "min": 1000.0},
    {"code": "成长优选R4", "risk": "R4", "yield": 6.5, "min": 5000.0},
    {"code": "进取股票R5", "risk": "R5", "yield": 9.2, "min": 10000.0},
]


def list_products():
    lines = [f"· {p['code']}（{p['risk']}）近一年收益 {p['yield']}%，起购 ¥{p['min']:.0f}" for p in PRODUCTS]
    return True, "在售理财产品：\n" + "\n".join(lines), {"products": PRODUCTS}


def product_info(code: str):
    """按产品代码查产品详情（走服务层，executor 不得直接读 PRODUCTS 常量）。"""
    for p in PRODUCTS:
        if p["code"] == code:
            return dict(p)
    return None


def recommend_products():
    c = ds.query_one("SELECT risk_level FROM customers WHERE id=?", (CUSTOMER_ID,))
    user_risk = c["risk_level"]
    order = ["R1", "R2", "R3", "R4", "R5"]
    ui = order.index(user_risk)
    # 风测匹配：推荐不超过用户风险等级的产品
    recs = [p for p in PRODUCTS if order.index(p["risk"]) <= ui]
    recs = sorted(recs, key=lambda p: -p["yield"])[:3]
    lines = [f"· {p['code']}（{p['risk']}）预期 {p['yield']}%" for p in recs]
    msg = (f"您的风测等级为 {user_risk}，为您匹配（不高于您风险等级）的产品：\n" + "\n".join(lines) +
           f"\n（已做适当性校验，不向您推荐高于 {user_risk} 的产品）")
    return True, msg, {"recommended": recs, "user_risk": user_risk}


def compare_products():
    lines = [f"· {p['code']}：风险 {p['risk']}，收益 {p['yield']}%，起购 ¥{p['min']:.0f}" for p in PRODUCTS[:4]]
    return True, "主要产品对比：\n" + "\n".join(lines), {"products": PRODUCTS[:4]}


def get_holdings():
    return True, "您当前持有「稳健增利R2」市值 ¥20,000.00，累计收益 ¥680.50。", {"market_value": 20000, "profit": 680.5}


# ---------- 转账 / 定时 / AA ----------
def transfer(to, amount, note=""):
    if not to:
        return False, "未指定收款人，转账已取消。", None
    if not amount or amount <= 0:
        return False, "转账金额无效，已取消。", None
    payee = ds.query_one("SELECT id,name,phone FROM customers WHERE name=?", (to,))
    c = ds.query_one("SELECT balance FROM customers WHERE id=?", (CUSTOMER_ID,))
    locked = ds.query_one("SELECT COALESCE(SUM(amount),0) s FROM funds_locks WHERE customer_id=? AND status='锁定中'", (CUSTOMER_ID,))
    avail = c["balance"] - locked["s"]
    if amount > avail:
        return False, f"余额不足：可用 ¥{avail:,.2f}，本次需 ¥{amount:,.2f}，转账失败。", None
    # 日限额校验
    card = ds.query_one("SELECT daily_limit FROM cards WHERE customer_id=? AND is_default=1", (CUSTOMER_ID,))
    if card and amount > card["daily_limit"]:
        return False, f"超过日限额：默认卡单日限额 ¥{card['daily_limit']:,.0f}，本次 ¥{amount:,.2f}。请先调高日限额或分笔转账。", None
    # 扣款
    ds.execute("UPDATE customers SET balance=balance-? WHERE id=?", (amount, CUSTOMER_ID))
    # 流水
    ds.execute(
        "INSERT INTO transactions(customer_id,direction,amount,category,counterparty,note,tx_time) VALUES(?,?,?,?,?,?,?)",
        (CUSTOMER_ID, "支出", amount, "转账", to, note or "转账", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    # 收款方虚拟入账
    if payee:
        ds.execute("UPDATE customers SET balance=balance+? WHERE id=?", (amount, payee["id"]))
    tid = random.randint(100000, 999999)
    return True, f"转账成功：向 {to}（{payee['phone'] if payee else '外部账户'}）支付 ¥{amount:,.2f}，回单号 {tid}。", {"tx_id": tid}


def scheduled_transfer_add(to, amount, schedule="每月1号", note=""):
    ds.execute(
        "INSERT INTO scheduled_transfers(customer_id,to_name,amount,schedule,next_run,note,status) VALUES(?,?,?,?,?,?,?)",
        (CUSTOMER_ID, to, amount, schedule, "2026-11-01", note, "生效"))
    return True, f"已设置定时转账：{schedule} 向 {to} 转 ¥{amount:,.0f}。", {}


def scheduled_transfer_cancel():
    ds.execute("UPDATE scheduled_transfers SET status='已取消' WHERE customer_id=? AND status='生效'", (CUSTOMER_ID,))
    return True, "已取消您最近一笔生效中的定时转账。", {}


def list_scheduled():
    rows = ds.query("SELECT to_name,amount,schedule,next_run,status FROM scheduled_transfers WHERE customer_id=?", (CUSTOMER_ID,))
    lines = [f"· {r['schedule']} 向 {r['to_name']} 转 ¥{r['amount']:,.0f}（下次 {r['next_run']}）[{r['status']}]" for r in rows]
    return True, "您的定时转账计划：\n" + "\n".join(lines), {"rows": rows}


def aa_split(total, n):
    if not total or not n:
        return False, "AA 收款需要总额和人数。", None
    per = round(total / n, 2)
    return True, f"已发起 AA 收款：总额 ¥{total:,.2f} / {n} 人，每人应付 ¥{per:,.2f}。", {"per": per}


# ---------- 卡片管理 ----------
def virtual_card_apply():
    card_no = "6259 " + "".join([str(random.randint(0, 9)) for _ in range(12)])
    ds.execute(
        "INSERT INTO cards(customer_id,card_no,bank_name,card_type,daily_limit,status,expiry,is_default) VALUES(?,?,?,?,?,?,?,0)",
        (CUSTOMER_ID, card_no, "招商银行", "虚拟卡", 5000.0, "正常", "2027-12"))
    return True, f"虚拟卡申请成功！卡号 {card_no}，日限额 ¥5,000。", {"card_no": card_no}


def apply_card(card_type="借记卡"):
    """开新卡：实体借记卡/信用卡。"""
    prefix = "6217" if card_type == "借记卡" else "4392"
    card_no = prefix + " " + " ".join(
        ["".join([str(random.randint(0, 9)) for _ in range(4)]) for _ in range(3)])
    limit = 50000.0 if card_type == "借记卡" else 15000.0
    ds.execute(
        "INSERT INTO cards(customer_id,card_no,bank_name,card_type,daily_limit,status,expiry,is_default) VALUES(?,?,?,?,?,?,?,0)",
        (CUSTOMER_ID, card_no, "招商银行", card_type, limit, "正常", "2029-12"))
    count = ds.query_one("SELECT COUNT(*) c FROM cards WHERE customer_id=?", (CUSTOMER_ID,))["c"]
    return True, (f"🎉 {card_type}开卡成功！新卡 {card_no}，日限额 ¥{limit:,.0f}。"
                  f"您名下现有 {count} 张银行卡。"), {"card_no": card_no, "total_cards": count}


def card_limit_adjust(limit):
    if not limit:
        return False, "请指定新的限额。", None
    ds.execute("UPDATE cards SET daily_limit=? WHERE customer_id=? AND is_default=1", (limit, CUSTOMER_ID))
    return True, f"默认卡日限额已调整为 ¥{limit:,.0f}。", {}


def card_freeze():
    ds.execute("UPDATE cards SET status='冻结' WHERE customer_id=? AND is_default=1", (CUSTOMER_ID,))
    return True, "已临时锁定默认卡片交易，可随时解锁。", {}


def card_unlock():
    ds.execute("UPDATE cards SET status='正常' WHERE customer_id=? AND status='冻结'", (CUSTOMER_ID,))
    return True, "卡片交易限制已解除，恢复正常。", {}


def report_loss(card_hint=""):
    # 根据用户提示定位具体卡：卡类型或卡号片段
    cards = ds.query("SELECT id,card_no,card_type,status FROM cards WHERE customer_id=?", (CUSTOMER_ID,))
    target = None
    if card_hint:
        for c in cards:
            if card_hint in (c["card_type"] or "") or card_hint.replace(" ", "") in (c["card_no"] or "").replace(" ", ""):
                target = c; break
    if target is None:
        # 默认卡
        for c in cards:
            if c["status"] == "正常":
                target = c; break
    if target is None:
        return False, "没有可挂失的正常卡片。", None
    ds.execute("UPDATE cards SET status='挂失' WHERE id=?", (target["id"],))
    return True, f"已挂失{target['card_type']} {target['card_no']}（其他卡片不受影响）。", {"card_no": target["card_no"]}


def cancel_loss():
    ds.execute("UPDATE cards SET status='正常' WHERE customer_id=? AND status='挂失'", (CUSTOMER_ID,))
    return True, "挂失已解除，卡片恢复正常使用。", {}


# ---------- 理财操作 ----------
def wealth_purchase(product, amount):
    c = ds.query_one("SELECT risk_level,balance FROM customers WHERE id=?", (CUSTOMER_ID,))
    p = next((x for x in PRODUCTS if x["code"] == product), None)
    if p:
        # 适当性校验：用户风测 < 产品风测 -> 拒绝
        order = ["R1", "R2", "R3", "R4", "R5"]
        if order.index(c["risk_level"]) < order.index(p["risk"]):
            return False, f"适当性拒绝：您的风测为 {c['risk_level']}，不能购买 {p['risk']} 产品 {product}。", None
    if not amount or amount <= 0:
        return False, "申购金额无效，请告诉我具体金额（如 一千元 / 5000）。", None
    if p and amount < p["min"]:
        return False, f"{p['code']} 起购金额为 ¥{p['min']:,.0f}，您输入的 ¥{amount:,.2f} 未达起购门槛，请提高金额。", None
    if amount > c["balance"]:
        return False, f"余额不足（可用 ¥{c['balance']:,.2f}），申购失败。", None
    ds.execute("UPDATE customers SET balance=balance-? WHERE id=?", (amount, CUSTOMER_ID))
    # 记录理财持仓（每月1号按年收益率派息）
    if p:
        ds.execute("INSERT INTO wealth_holdings(customer_id,product,principal,annual_yield,purchase_date,status) VALUES(1,?,?,?,?,'持有')",
                   (product, amount, p["yield"], get_sim_now()))
    return True, f"理财申购成功：{product or '推荐产品'} ¥{amount:,.2f}，已扣款。每月1号将按年化 {p['yield'] if p else '?'}% 派息。", {}


def wealth_redeem(amount):
    return True, f"理财赎回申请已提交（¥{amount or '全部'}），预计 T+1 到账活期。", {}


# ---------- 订阅 ----------
def subscription_cancel(service=None, services=None):
    targets = services or ([service] if service else [])
    if not targets:
        ok, rowcount = ds.execute("UPDATE subscriptions SET status='已取消' WHERE customer_id=? AND status='生效'",
                                  (CUSTOMER_ID,))
        return True, f"已取消全部生效中的订阅代扣（共 {rowcount} 项）。", {}
    names, total = [], 0
    for svc in targets:
        ok, rowcount = ds.execute("UPDATE subscriptions SET status='已取消' WHERE customer_id=? AND service_name LIKE ? AND status='生效'",
                                  (CUSTOMER_ID, f"%{svc}%"))
        if rowcount and rowcount > 0:
            names.append(svc)
            total += rowcount
    if not names:
        return False, "这些订阅当前均不在生效状态，无需取消。", None
    return True, f"已取消：{ '、'.join(names) }（共 {total} 项）。", {}


def subscription_resume(service=None, services=None):
    targets = services or ([service] if service else [])
    if not targets:
        return False, "请指定要恢复的订阅名称。", None
    names, total = [], 0
    for svc in targets:
        ok, rowcount = ds.execute("UPDATE subscriptions SET status='生效' WHERE customer_id=? AND service_name LIKE ? AND status='已取消'",
                                 (CUSTOMER_ID, f"%{svc}%"))
        if rowcount and rowcount > 0:
            names.append(svc)
            total += rowcount
    if not names:
        return False, "没有找到已取消的订阅，可能本就在生效或不存在。", None
    return True, f"已恢复：{ '、'.join(names) }（共 {total} 项）。", {}


# ---------- 资金锁定 / 订单 / 生日联动 ----------
def funds_lock(amount, reason="专项"):
    c = ds.query_one("SELECT balance FROM customers WHERE id=?", (CUSTOMER_ID,))
    if amount > c["balance"]:
        return False, f"余额不足，无法锁定 ¥{amount:,.2f}。", None
    ds.execute(
        "INSERT INTO funds_locks(customer_id,amount,reason,lock_until,status) VALUES(?,?,?,?, '锁定中')",
        (CUSTOMER_ID, amount, reason, "2026-12-31"))
    return True, f"已锁定 ¥{amount:,.2f}（{reason}），该部分暂不可用于普通转账。", {}


def place_order(order_type, days_ahead=2):
    addr = ds.query_one("SELECT address FROM customers WHERE id=?", (CUSTOMER_ID,))
    amount = {"鲜花": 199.0, "蛋糕": 268.0, "鲜花+蛋糕": 428.0}.get(order_type, 199.0)
    ds.execute(
        "INSERT INTO orders(customer_id,order_type,items,amount,address,status,created_at) VALUES(?,?,?,?,?,?,?)",
        (CUSTOMER_ID, order_type, order_type, amount, addr["address"], "已下单",
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    return True, f"已下单{order_type}，¥{amount:.0f}，将于纪念日前进 2 天送达：{addr['address']}。", {}


def birthday_info(relation="spouse"):
    c = ds.query_one("SELECT spouse_name,spouse_birthday FROM customers WHERE id=?", (CUSTOMER_ID,))
    rel_txt = {"spouse": "爱人", "mom": "妈妈", "dad": "爸爸"}.get(relation, "家人")
    bday = c["spouse_birthday"] if relation == "spouse" else "01-01"
    today_md = date.today().strftime("%m-%d")
    # 简单倒计时
    mm, dd = int(bday[:2]), int(bday[3:])
    this_year = date.today().year
    target = date(this_year, mm, dd)
    if target < date.today():
        target = date(this_year + 1, mm, dd)
    days = (target - date.today()).days
    return True, f"已为您标记{rel_txt}（{c['spouse_name'] if relation=='spouse' else ''}）生日 {bday}，距今约 {days} 天。", {"days": days}


def analyze_overspend(period="上月"):
    """分析上月不合理消费：餐饮/外卖/娱乐超支部分。"""
    rows = ds.query(
        "SELECT category, SUM(amount) s FROM transactions WHERE direction='支出' "
        "GROUP BY category")
    budget = {"餐饮": 800.0, "外卖": 400.0, "娱乐": 300.0, "购物": 1000.0, "交通": 300.0}
    findings = []
    for r in rows:
        cat = r["category"] or "其他"
        if cat == "转账":
            continue  # 转账是资金调度，不算消费超支
        expected = budget.get(cat, 500.0)
        if r["s"] > expected:
            findings.append((cat, r["s"], expected, r["s"] - expected))
    if not findings:
        return True, "✅ 上月消费结构合理，没有明显超支品类，无需强制储蓄。", {"overspend": 0}
    lines = [f"· {c}：花了 ¥{s:.0f}（建议 ¥{e:.0f}），超支 ¥{o:.0f}" for c, s, e, o in findings]
    total_over = sum(o for _, _, _, o in findings)
    msg = "📊 上月不合理消费分析：\n" + "\n".join(lines) + f"\n合计可削减 ¥{total_over:.0f}/月。"
    return True, msg, {"findings": findings, "overspend": total_over}


def compute_savings():
    """从 analyze_overspend 拿真实可省金额（分析结果收敛到 70% 作为建议强制储蓄额）。"""
    ok, msg, data = analyze_overspend()
    over = data.get("overspend", 0) if data else 0
    if over <= 0:
        return True, "💰 上月消费合理，暂无强制储蓄建议。", {"savings": 0.0}
    # 建议把超支部分的 70% 强制储蓄（留 30% 弹性）
    savings = round(over * 0.7, 2)
    return True, f"💰 上月超支 ¥{over:,.0f}，建议每月强制储蓄 ¥{savings:,.0f}（超支部分的70%收敛值）。", {"savings": savings}


def open_fixed_deposit(amount=None, portion=0.5):
    """一半存定期。"""
    base = amount or 1500.0
    half = round(base * portion, 2)
    return True, f"🏦 已开立 6 个月定期存款 ¥{half:,.2f}（年化 1.55%，到期自动转活期）。", {"amount": half}


def auto_wealth_purchase(product=None, amount=None, portion=0.5):
    """按可用金额自动选最划算的产品（起购门槛≤金额中收益率最高的）。"""
    base = amount or 1500.0
    money = round(base * portion, 2)
    candidates = [p for p in PRODUCTS if p["min"] <= money]
    if not candidates:
        return False, f"❌ ¥{money:,.0f} 不够任何理财起购门槛，先攒一攒再投。", {}
    best = max(candidates, key=lambda x: x["yield"])
    return True, (f"📈 按您可用 ¥{money:,.0f} 自动配置：{best['code']}（{best['risk']}，近一年 {best['yield']}%，"
                  f"起购¥{best['min']:.0f}）——在您能买的产品里收益率最高。"), {"amount": money, "product": best["code"]}


def emergency_fund_check(target_months=3):
    """应急金缺口：建议保留 target_months 个月生活费。"""
    monthly = ds.query_one(
        "SELECT COALESCE(SUM(amount),0) s FROM transactions WHERE direction='支出'")
    total_out = monthly["s"]
    months_have = 12  # 演示：按12个月流水算
    avg_month = total_out / max(months_have, 1)
    target = round(avg_month * target_months, 2)
    bal = ds.query_one("SELECT balance b FROM customers WHERE id=1")["b"]
    gap = max(0, round(target - bal, 2))
    return True, (f"💰 应急金检查：月均支出 ¥{avg_month:,.0f}，建议储备 {target_months} 个月生活费 = ¥{target:,.0f}；"
                  f"当前活期余额 ¥{bal:,.0f}，缺口 ¥{gap:,.0f}。"), {"target": target, "gap": gap}


def allocate_to_goal(amount=0, goal="家庭备用/旅行基金"):
    """年终奖20%分配给专项目标。"""
    return True, f"🎯 已拨备 ¥{amount:,.0f} 至「{goal}」专户口，可随时支取，不锁定期。", {"amount": amount, "goal": goal}


def birthday_wealth_offer(relation="spouse"):
    """生日专属理财推荐：让锁定的专项资金在等待期产生稳健收益。"""
    return True, ("🎁 为您的生日专款推荐稳健配置：\n"
                  "· 稳健增利R2（近一年 3.4%，起购 ¥1,000）—— 等待期闲钱增值\n"
                  "· 平衡配置R3（近一年 4.8%，起购 ¥1,000）—— 适度增值\n"
                  "💡 您的风测等级 R2，建议 R2 为主；生日过后可灵活赎回，不耽误用钱。"), {}


def credit_card_benefit(relation="spouse"):
    """信用卡生日月商圈权益匹配（先判断是否持有信用卡）。"""
    card = ds.query_one(
        "SELECT id FROM cards WHERE customer_id=? AND card_type LIKE '%信用%' AND status='正常'",
        (CUSTOMER_ID,))
    if not card:
        return True, "💳 您当前没有可用信用卡，生日月商圈权益暂不可用。可在「申请信用卡」后开通。", {}
    return True, ("💳 为您匹配到本月信用卡权益：\n"
                  "· 商圈餐饮：周三/周六指定餐厅 满300减100\n"
                  "· 生日月：双倍积分，兑换礼品/电影票\n"
                  "· 购物：商场百货单笔满5000享分期3期0手续费\n"
                  "📍 您附近的合作商圈：昌平永旺、合生汇、三里屯"), {}


# 白名单：op -> 函数。执行器只能通过此表调用，天然阻断代码注入。
DISPATCH = {
    "query_balance": lambda a: query_balance(),
    "query_transactions": lambda a: query_transactions(a.get("days")),
    "bill_analysis": lambda a: bill_analysis(a.get("period", "月")),
    "anomaly_scan": lambda a: anomaly_scan(),
    "list_subscriptions": lambda a: list_subscriptions(),
    "subscription_cancel": lambda a: subscription_cancel(a.get("service"), a.get("services")),
    "subscription_resume": lambda a: subscription_resume(a.get("service"), a.get("services")),
    "list_cards": lambda a: list_cards(),
    "list_contacts": lambda a: list_contacts(),
    "apply_card": lambda a: apply_card(a.get("card_type", "借记卡")),
    "list_products": lambda a: list_products(),
    "recommend_products": lambda a: recommend_products(),
    "compare_products": lambda a: compare_products(),
    "get_holdings": lambda a: get_holdings(),
    "list_scheduled": lambda a: list_scheduled(),
    "transfer": lambda a: transfer(a.get("to"), a.get("amount"), a.get("note", "")),
    "scheduled_transfer_add": lambda a: scheduled_transfer_add(a.get("to"), a.get("amount"), a.get("schedule", "每月1号"), a.get("note", "")),
    "scheduled_transfer_cancel": lambda a: scheduled_transfer_cancel(),
    "aa_split": lambda a: aa_split(a.get("total"), a.get("n")),
    "virtual_card_apply": lambda a: virtual_card_apply(),
    "card_limit_adjust": lambda a: card_limit_adjust(a.get("limit")),
    "card_freeze": lambda a: card_freeze(),
    "card_unlock": lambda a: card_unlock(),
    "report_loss": lambda a: report_loss(a.get("card_hint", "")),
    "cancel_loss": lambda a: cancel_loss(),
    "wealth_purchase": lambda a: wealth_purchase(a.get("product"), a.get("amount")),
    "wealth_redeem": lambda a: wealth_redeem(a.get("amount")),
    "funds_lock": lambda a: funds_lock(a.get("amount"), a.get("reason", "专项")),
    "place_order": lambda a: place_order(a.get("order_type"), a.get("days_ahead", 2)),
    "birthday_info": lambda a: birthday_info(a.get("relation", "spouse")),
    "birthday_wealth_offer": lambda a: birthday_wealth_offer(a.get("relation", "spouse")),
    "credit_card_benefit": lambda a: credit_card_benefit(a.get("relation", "spouse")),
    "analyze_overspend": lambda a: analyze_overspend(a.get("period", "上月")),
    "compute_savings": lambda a: compute_savings(),
    "emergency_fund_check": lambda a: emergency_fund_check(a.get("target_months", 3)),
    "allocate_to_goal": lambda a: allocate_to_goal(a.get("amount", 0), a.get("goal", "家庭备用/旅行基金")),
    "open_fixed_deposit": lambda a: open_fixed_deposit(a.get("amount"), a.get("portion", 0.5)),
    "auto_wealth_purchase": lambda a: auto_wealth_purchase(a.get("product", "稳健增利R2"), a.get("amount"), a.get("portion", 0.5)),
    "time_travel": lambda a: time_travel(a.get("months", 0), a.get("days", 0)),
}
