# -*- coding: utf-8 -*-
"""
任务规划：把意图列表展开为带依赖的 DAG 节点。
跨场景生日展开为三步子图；其余按语句顺序串成线性链。
"""


def _node(nid, op, args, risk, desc, depends_on=None):
    return {
        "id": nid, "op": op, "args": args, "risk": risk,
        "risk_label": {"green": "绿色·自动", "yellow": "黄色·需确认", "red": "红色·强验证"}[risk],
        "description": desc, "depends_on": depends_on or [], "status": "pending",
    }


def plan(intents, state):
    """
    intents: [(intent, slots)]
    state: 会话状态（含今日已累计转账额等，由 policy 实时算风险）
    返回: [nodes]  有序
    """
    nodes = []
    idx = 0
    prev = []
    for intent, slots in intents:
        if intent == "annual_bonus_plan":
            bonus = slots.get("amount", 20000.0)
            s0 = f"s{idx}"; idx += 1
            s1 = f"s{idx}"; idx += 1
            s2 = f"s{idx}"; idx += 1
            s3 = f"s{idx}"; idx += 1
            s4 = f"s{idx}"; idx += 1
            nodes.append(_node(s0, "analyze_overspend", {"period": "全年"}, "green",
                               f"评估全年消费结构与超支品类", prev))
            nodes.append(_node(s1, "emergency_fund_check", {"target_months": 3}, "green",
                               f"计算应急金缺口（建议3个月生活费）", [s0]))
            nodes.append(_node(s2, "open_fixed_deposit", {"amount": round(bonus*0.5,2)}, "yellow",
                               f"年终奖50% → 存定期 ¥{bonus*0.5:,.0f}（稳健底仓）", [s1]))
            nodes.append(_node(s3, "auto_wealth_purchase", {"amount": round(bonus*0.3,2)}, "red",
                               f"年终奖30% → 自动配置理财 ¥{bonus*0.3:,.0f}", [s2]))
            nodes.append(_node(s4, "allocate_to_goal", {"amount": round(bonus*0.2,2)}, "yellow",
                               f"年终奖20% → 专项目标（旅行/礼物/家庭备用）¥{bonus*0.2:,.0f}", [s3]))
            prev = [s4]
            continue

        if intent == "smart_budget":
            # 动态规划四步：分析不合理消费 -> 算出可省金额 -> 一半定期 -> 一半R2
            s0 = f"s{idx}"; idx += 1
            s1 = f"s{idx}"; idx += 1
            s2 = f"s{idx}"; idx += 1
            s3 = f"s{idx}"; idx += 1
            nodes.append(_node(s0, "analyze_overspend", {"period": "上月"}, "green",
                               "分析上月消费，识别不合理/超支品类", prev))
            nodes.append(_node(s1, "compute_savings", {}, "green",
                               "计算建议削减金额（可省下来的钱）", [s0]))
            nodes.append(_node(s2, "open_fixed_deposit", {"portion": 0.5}, "yellow",
                               "省下来的钱一半 → 存定期（锁定稳健）", [s1]))
            nodes.append(_node(s3, "auto_wealth_purchase", {"product": "稳健增利R2", "portion": 0.5}, "red",
                               "省下来的钱另一半 → 自动申购 R2 稳健理财", [s2]))
            prev = [s3]
            continue

        if intent == "cross_scene_birthday":
            # 金融化四步 DAG：识别纪念日 -> 专款锁定 -> 生日专属理财推荐 -> 信用卡商圈权益匹配
            s0 = f"s{idx}"; idx += 1
            s1 = f"s{idx}"; idx += 1
            s2 = f"s{idx}"; idx += 1
            s3 = f"s{idx}"; idx += 1
            rel = slots.get("relation", "spouse")
            rel_txt = {"spouse": "爱人", "mom": "妈妈", "dad": "爸爸"}.get(rel, "家人")
            nodes.append(_node(s0, "birthday_info", {"relation": rel}, "green",
                               f"识别到{rel_txt}生日/纪念日，查询倒计时与资金安排", prev))
            nodes.append(_node(s1, "funds_lock", {"amount": 2000, "reason": f"{rel_txt}生日专款"}, "yellow",
                               f"预留 ¥2,000 生日专项资金（锁定活期，专款专用）", [s0]))
            nodes.append(_node(s2, "birthday_wealth_offer", {"relation": rel}, "green",
                               f"推荐生日专属稳健理财（R2/R3），让专款在等待期产生收益", [s1]))
            nodes.append(_node(s3, "credit_card_benefit", {"relation": rel}, "green",
                               f"匹配信用卡生日月商圈餐饮/购物满减权益", [s2]))
            prev = [s3]
            continue

        # 单意图 -> 单节点
        if intent == "transfer":
            to = slots.get("to") or "（待确认收款人）"
            amt = slots.get("amount")
            amt_txt = f"¥{amt:,.2f}" if amt else "（待补金额）"
            note = slots.get("note") or ""
            note_txt = f"，备注：{note}" if note else ""
            cands = slots.get("candidates") or []
            desc = f"向 {to} 转账 {amt_txt}{note_txt}"
            if cands and not slots.get("to"):
                desc = f"转账 {amt_txt}（{len(cands)}位同姓联系人待选择）{note_txt}"
            nodes.append(_node(f"s{idx}", "transfer", dict(slots), "yellow", desc, prev))
        elif intent == "query_balance":
            nodes.append(_node(f"s{idx}", "query_balance", {}, "green", "查询活期账户余额", prev))
        elif intent == "query_transactions":
            days = slots.get("days")
            rng = f"近{days}天" if days else "全部"
            nodes.append(_node(f"s{idx}", "query_transactions", {"days": days}, "green",
                               f"查询{rng}交易流水明细", prev))
        elif intent == "bill_analysis":
            period = slots.get("period", "月")
            nodes.append(_node(f"s{idx}", "bill_analysis", {"period": period}, "green",
                               f"生成{period}度账单分类统计报告", prev))
        elif intent == "anomaly_scan":
            nodes.append(_node(f"s{idx}", "anomaly_scan", {}, "green", "扫描异常/可疑交易", prev))
        elif intent == "list_subscriptions":
            nodes.append(_node(f"s{idx}", "list_subscriptions", {}, "green", "查询当前订阅代扣列表", prev))
        elif intent == "subscription_cancel":
            svcs = slots.get("services") or ([slots.get("service")] if slots.get("service") else [])
            label = "、".join(svcs) if svcs else "全部订阅"
            nodes.append(_node(f"s{idx}", "subscription_cancel", dict(slots), "yellow",
                               f"取消订阅：{label}", prev))
        elif intent == "subscription_resume":
            svcs = slots.get("services") or ([slots.get("service")] if slots.get("service") else [])
            label = "、".join(svcs) if svcs else ""
            nodes.append(_node(f"s{idx}", "subscription_resume", dict(slots), "yellow",
                               f"恢复订阅：{label}", prev))
        elif intent == "list_cards":
            nodes.append(_node(f"s{idx}", "list_cards", {}, "green", "查询我的银行卡列表与数量", prev))
        elif intent == "list_contacts":
            nodes.append(_node(f"s{idx}", "list_contacts", {}, "green", "查询通讯录联系人", prev))
        elif intent == "apply_card":
            nodes.append(_node(f"s{idx}", "apply_card", dict(slots), "yellow",
                               f"申请新{slots.get('card_type','借记卡')}", prev))
        elif intent == "list_products":
            nodes.append(_node(f"s{idx}", "list_products", {}, "green", "查询在售理财产品列表", prev))
        elif intent == "recommend_products":
            nodes.append(_node(f"s{idx}", "recommend_products", {}, "green", "按我的风测等级推荐理财产品", prev))
        elif intent == "compare_products":
            nodes.append(_node(f"s{idx}", "compare_products", {}, "green", "对比理财产品收益与风险", prev))
        elif intent == "get_holdings":
            nodes.append(_node(f"s{idx}", "get_holdings", {}, "green", "查询理财持仓与累计收益", prev))
        elif intent == "scheduled_transfer_add":
            to = slots.get("to") or "（待补收款人）"
            amt = slots.get("amount")
            nodes.append(_node(f"s{idx}", "scheduled_transfer_add", dict(slots), "yellow",
                               f"设置定时转账：{slots.get('schedule','每月1号')} 向 {to} 转 ¥{amt or 0:,.0f}", prev))
        elif intent == "scheduled_transfer_cancel":
            nodes.append(_node(f"s{idx}", "scheduled_transfer_cancel", {}, "yellow", "取消最近一笔定时转账", prev))
        elif intent == "aa_split":
            nodes.append(_node(f"s{idx}", "aa_split", dict(slots), "yellow",
                               f"发起 AA 收款：总额 ¥{slots.get('total') or 0:,.0f} / {slots.get('n') or '?'}人", prev))
        elif intent == "virtual_card_apply":
            nodes.append(_node(f"s{idx}", "virtual_card_apply", {}, "yellow", "申请一张虚拟信用卡", prev))
        elif intent == "card_limit_adjust":
            nodes.append(_node(f"s{idx}", "card_limit_adjust", dict(slots), "yellow",
                               f"调整银行卡日限额至 ¥{slots.get('limit') or 0:,.0f}", prev))
        elif intent == "card_freeze":
            nodes.append(_node(f"s{idx}", "card_freeze", {}, "yellow", "临时锁定卡片交易", prev))
        elif intent == "wealth_purchase":
            nodes.append(_node(f"s{idx}", "wealth_purchase", dict(slots), "red",
                               f"申购理财产品 {slots.get('product') or ''} ¥{slots.get('amount') or 0:,.0f}", prev))
        elif intent == "wealth_redeem":
            nodes.append(_node(f"s{idx}", "wealth_redeem", dict(slots), "yellow",
                               f"赎回理财 ¥{slots.get('amount') or '全部'}", prev))
        elif intent == "report_loss":
            hint = slots.get("card_hint") or ""
            desc = f"银行卡挂失（{hint}）" if hint else "银行卡挂失"
            nodes.append(_node(f"s{idx}", "report_loss", dict(slots), "red", desc, prev))
        elif intent == "cancel_loss":
            nodes.append(_node(f"s{idx}", "cancel_loss", {}, "red", "解除挂失（恢复卡片）", prev))
        elif intent == "card_unlock":
            nodes.append(_node(f"s{idx}", "card_unlock", {}, "red", "解锁交易限制", prev))
        elif intent == "funds_lock":
            nodes.append(_node(f"s{idx}", "funds_lock", dict(slots), "yellow",
                               f"锁定资金 ¥{slots.get('amount') or 0:,.0f}（{slots.get('reason','')}）", prev))
        elif intent == "place_order":
            nodes.append(_node(f"s{idx}", "place_order", dict(slots), "yellow",
                               f"下单订购：{slots.get('order_type','礼品')}", prev))
        elif intent == "list_scheduled":
            nodes.append(_node(f"s{idx}", "list_scheduled", {}, "green", "查询我的定时转账计划", prev))
        elif intent == "time_travel":
            m = slots.get("months", 0); d = slots.get("days", 0)
            label = (f"{m}个月" if m else "") + (f"{d}天" if d else "")
            nodes.append(_node(f"s{idx}", "time_travel", dict(slots), "green", f"时间快进 {label}", prev))
        else:
            nodes.append(_node(f"s{idx}", "unknown", {"raw": str(intent)}, "green", f"未识别：{intent}", prev))
        prev = [f"s{idx}"]
        idx += 1
    return nodes
