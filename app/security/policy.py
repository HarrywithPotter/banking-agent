# -*- coding: utf-8 -*-
"""权限分级：绿/黄/红。转账按【当日累计+本笔】动态升级。"""

GREEN_OPS = {
    "query_balance", "query_transactions", "bill_analysis", "anomaly_scan",
    "list_subscriptions", "list_cards", "list_products", "recommend_products",
    "compare_products", "get_holdings", "list_scheduled", "birthday_info",
    "list_contacts", "time_travel", "birthday_wealth_offer", "credit_card_benefit",
    "analyze_overspend", "compute_savings", "emergency_fund_check",
}
YELLOW_OPS = {
    "transfer", "scheduled_transfer_add", "scheduled_transfer_cancel", "aa_split",
    "subscription_cancel", "subscription_resume", "virtual_card_apply", "card_limit_adjust", "card_freeze",
    "wealth_redeem", "funds_lock", "place_order", "apply_card", "open_fixed_deposit",
    "allocate_to_goal",
}
RED_OPS = {
    "card_unlock", "report_loss", "cancel_loss", "wealth_purchase", "auto_wealth_purchase",
}

DAILY_LIMIT = 1000.0  # 日累计 >1000 即升级为红色


def risk_of(op, args, state):
    """唯一风险判定入口。state 含今日已累计转账额。"""
    if op in GREEN_OPS:
        return "green"
    if op == "transfer":
        cum = (state.get("daily_transfer_total", 0.0) or 0.0) + (args.get("amount") or 0.0)
        return "red" if cum > DAILY_LIMIT else "yellow"
    if op in RED_OPS:
        return "red"
    if op in YELLOW_OPS:
        return "yellow"
    return "yellow"  # 未登记默认黄色（保守）


def label(risk):
    return {"green": "绿色·自动执行", "yellow": "黄色·需用户确认", "red": "红色·需强验证"}[risk]
