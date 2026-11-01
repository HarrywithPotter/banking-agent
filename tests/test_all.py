# -*- coding: utf-8 -*-
"""
智银·AI Banking Agent 测试套件 v4.0
运行：python tests/test_all.py
60+ 用例：NLP / 控制词 / 查询 / 操作 / DAG / 多意图(22条) / 沙箱 / 端到端
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.bank import db
from app.agent import nlp, intent
from app.agent.executor import Engine
from app.sandbox import code_sandbox, data_sandbox as ds
from app.bank.service import (upcoming_reminders, product_info, get_sim_now,
                              set_sim_now, list_contacts, list_cards,
                              query_balance, query_transactions)


def new_engine():
    db.init_db(force=True)
    return Engine()


# ============ A. NLP 基础（6条） ============
class TestNLP(unittest.TestCase):
    def test_amount_cn(self):
        self.assertEqual(nlp.parse_amount("五百"), 500.0)
        self.assertEqual(nlp.parse_amount("两千五"), 2500.0)
        self.assertEqual(nlp.parse_amount("一万二"), 12000.0)

    def test_amount_cn2(self):
        self.assertEqual(nlp.parse_amount("三千八"), 3800.0)
        self.assertEqual(nlp.parse_amount("八千"), 8000.0)
        self.assertEqual(nlp.parse_amount("十万"), 100000.0)

    def test_amount_ar(self):
        self.assertEqual(nlp.parse_amount("500"), 500.0)
        self.assertEqual(nlp.parse_amount("1.5万"), 15000.0)
        self.assertEqual(nlp.parse_amount("5000元"), 5000.0)

    def test_amount_no(self):
        self.assertIsNone(nlp.parse_amount("你好"))
        self.assertIsNone(nlp.parse_amount("查余额"))

    def test_alias(self):
        self.assertEqual(nlp.resolve_alias("给我爱人转钱"), "spouse")
        self.assertEqual(nlp.resolve_alias("给妈妈"), "mom")
        self.assertEqual(nlp.resolve_alias("给老爸"), "dad")

    def test_time_range(self):
        self.assertEqual(nlp.parse_time_range("近一个月"), 30)


# ============ B. 控制词（4条） ============
class TestControl(unittest.TestCase):
    def test_confirm1(self):
        e = new_engine()
        for t in ["确认", "好的", "OK", "嗯", "行"]:
            ctrl, _ = intent.parse_intent(t, e._contacts())
            self.assertEqual(ctrl, "confirm", f"{t}")

    def test_confirm2(self):
        e = new_engine()
        for t in ["就这么办", "没问题", "可以", "对", "是的"]:
            ctrl, _ = intent.parse_intent(t, e._contacts())
            self.assertEqual(ctrl, "confirm", f"{t}")

    def test_cancel(self):
        e = new_engine()
        for t in ["取消", "算了", "不要了", "别办了", "先不办", "停止"]:
            ctrl, _ = intent.parse_intent(t, e._contacts())
            self.assertEqual(ctrl, "cancel", f"{t}")

    def test_human(self):
        e = new_engine()
        ctrl, _ = intent.parse_intent("我要人工", e._contacts())
        self.assertEqual(ctrl, "human")


# ============ C. 查询类（10条，每功能2-3种说法） ============
class TestQuery(unittest.TestCase):
    def test_balance(self):
        e = new_engine()
        for t in ["查余额", "我卡里有多少钱", "还剩多少"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "query_balance", f"{t}")

    def test_balance2(self):
        e = new_engine()
        for t in ["还有多少钱", "账户余额", "可用余额"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "query_balance", f"{t}")

    def test_transactions(self):
        e = new_engine()
        for t in ["查流水", "最近交易记录", "近一个月的开销"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "query_transactions", f"{t}")

    def test_transactions2(self):
        e = new_engine()
        for t in ["交易明细", "消费记录", "花了多少钱"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "query_transactions", f"{t}")

    def test_holdings(self):
        e = new_engine()
        for t in ["我的理财收益", "持仓怎么样", "理财赚了多少"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "get_holdings", f"{t}")

    def test_subscriptions(self):
        e = new_engine()
        for t in ["我有哪些订阅", "自动续费列表", "开了哪些会员"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "list_subscriptions", f"{t}")

    def test_contacts(self):
        e = new_engine()
        for t in ["我的通讯录", "联系人都有谁", "我能转给谁"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "list_contacts", f"{t}")

    def test_cards(self):
        e = new_engine()
        for t in ["我有几张银行卡", "我的卡片", "卡列表"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "list_cards", f"{t}")

    def test_scheduled_list(self):
        e = new_engine()
        for t in ["查看我的定时转账", "有哪些自动转", "定时转账列表"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "list_scheduled", f"{t}")

    def test_recommend(self):
        e = new_engine()
        for t in ["推荐理财", "帮我选个产品", "买什么理财好"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "recommend_products", f"{t}")


# ============ D. 操作类（10条） ============
class TestActions(unittest.TestCase):
    def test_transfer(self):
        e = new_engine()
        for t in ["给妈妈转500", "给王芳打1000", "转两千五给我爱人"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "transfer", f"{t}")

    def test_transfer2(self):
        e = new_engine()
        for t in ["给老爸汇300", "转钱给老婆", "给李雷200"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "transfer", f"{t}")

    def test_wealth_buy(self):
        e = new_engine()
        for t in ["买1000元的R2", "申购稳健增利5000", "买R3理财三千"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "wealth_purchase", f"{t}")

    def test_wealth_redeem(self):
        e = new_engine()
        for t in ["赎回理财", "卖出持仓", "取回基金"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "wealth_redeem", f"{t}")

    def test_loss(self):
        e = new_engine()
        for t in ["卡丢了", "我银行卡找不到了", "挂失"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "report_loss", f"{t}")

    def test_apply_card(self):
        e = new_engine()
        for t in ["再办一张卡", "新开一张借记卡", "申请信用卡"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "apply_card", f"{t}")

    def test_sub_cancel(self):
        e = new_engine()
        for t in ["取消爱奇艺", "关掉腾讯视频自动续费", "退订B站会员"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "subscription_cancel", f"{t}")

    def test_sub_resume(self):
        e = new_engine()
        for t in ["恢复QQ音乐", "重新订阅网易云", "开通百度网盘"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "subscription_resume", f"{t}")

    def test_scheduled_add(self):
        e = new_engine()
        for t in ["每个月给房东转3500", "每周给妈妈打钱", "每月1号自动转"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "scheduled_transfer_add", f"{t}")

    def test_time_travel(self):
        e = new_engine()
        for t in ["一天后", "一个月后", "三天后"]:
            _, f = intent.parse_intent(t, e._contacts())
            self.assertEqual(f[0][0], "time_travel", f"{t}")


# ============ E. 智能DAG（3条） ============
class TestDAG(unittest.TestCase):
    def test_smart_budget(self):
        e = new_engine()
        _, f = intent.parse_intent("帮我看看上个月哪些钱花得不合理，省下来的一半存定期一半买理财", e._contacts())
        self.assertIn("smart_budget", [i for i, _ in f])

    def test_bonus(self):
        e = new_engine()
        _, f = intent.parse_intent("我发了3万年终奖，帮我规划一下", e._contacts())
        self.assertEqual(f[0][0], "annual_bonus_plan")
        self.assertEqual(f[0][1]["amount"], 30000.0)

    def test_birthday(self):
        e = new_engine()
        _, f = intent.parse_intent("我爱人生日快到了", e._contacts())
        self.assertEqual(f[0][0], "cross_scene_birthday")


# ============ F. 多意图（22条，拆4个方法） ============
class TestMultiIntent(unittest.TestCase):
    def _check(self, cases):
        e = new_engine()
        for text, expected in cases:
            _, f = intent.parse_intent(text, e._contacts())
            got = [i for i, _ in f]
            self.assertEqual(got, expected, f"{text}: 期望{expected}, 实际{got}")

    def test_multi_1(self):
        self._check([
            ("查一下余额然后给妈妈转200", ["query_balance", "transfer"]),
            ("查余额，顺便看一下我的理财持仓", ["query_balance", "get_holdings"]),
            ("查完流水然后推荐个理财", ["query_transactions", "recommend_products"]),
            ("看看我的卡然后再办一张", ["list_cards", "apply_card"]),
            ("查下订阅，然后取消爱奇艺", ["list_subscriptions", "subscription_cancel"]),
            ("查一下通讯录，顺便给王芳转500", ["list_contacts", "transfer"]),
        ])

    def test_multi_2(self):
        self._check([
            ("取消爱奇艺恢复QQ音乐", ["subscription_cancel", "subscription_resume"]),
            ("查余额然后买1000元R2", ["query_balance", "wealth_purchase"]),
            ("看看持仓然后赎回一半", ["get_holdings", "wealth_redeem"]),
            ("查一下近一个月流水，然后分析下账单", ["query_transactions", "bill_analysis"]),
            ("帮我看看余额，再给老婆转500", ["query_balance", "transfer"]),
        ])

    def test_multi_3(self):
        self._check([
            ("我发了3万年终奖，先查下余额再规划", ["annual_bonus_plan", "query_balance"]),
            ("查下我的卡，然后挂失", ["list_cards", "report_loss"]),
            ("查订阅，把爱奇艺和腾讯视频都取消", ["list_subscriptions", "subscription_cancel"]),
            ("看看理财持仓，再推荐个新产品", ["get_holdings", "recommend_products"]),
            ("查一下余额然后设个定时转账", ["query_balance", "scheduled_transfer_add"]),
        ])

    def test_multi_4(self):
        self._check([
            ("给妈妈转500，再给爸爸转300", ["transfer", "transfer"]),
            ("查一下我的定时转账，然后取消", ["list_scheduled"]),
            ("帮我存2000块钱应急", ["funds_lock"]),
            ("查余额然后看看通讯录", ["query_balance", "list_contacts"]),
            ("挂失然后查一下我的卡", ["report_loss", "list_cards"]),
            ("推荐理财然后买5000的R2", ["recommend_products", "wealth_purchase"]),
        ])


# ============ G. 沙箱安全（4条） ============
class TestSandbox(unittest.TestCase):
    def test_code_block_import(self):
        ok, _, _ = code_sandbox.run_code("import os; os.system('echo hi')")
        self.assertFalse(ok)

    def test_code_block_builtins(self):
        ok, _, _ = code_sandbox.run_code("f = getattr(__builtins__, 'eval')")
        self.assertFalse(ok)

    def test_code_block_eval(self):
        ok, _, _ = code_sandbox.run_code("eval('1+1')")
        self.assertFalse(ok)

    def test_data_block_ddl(self):
        ok, _ = ds.execute("DROP TABLE customers")
        self.assertFalse(ok)


# ============ H. 业务端到端（4条） ============
class TestE2E(unittest.TestCase):
    def test_contacts_count(self):
        new_engine()
        ok, msg, _ = list_contacts()
        self.assertGreaterEqual(msg.count("·"), 30)

    def test_cards_count(self):
        new_engine()
        ok, msg, _ = list_cards()
        self.assertIn("卡", msg)

    def test_time_travel_bonus(self):
        new_engine()
        set_sim_now("2026-10-24")
        from app.bank.service import time_travel
        ok, msg, _ = time_travel(months=3)
        self.assertIn("年终奖", msg)

    def test_birthday_reminder(self):
        new_engine()
        set_sim_now("2026-11-02")
        reminders = upcoming_reminders()
        self.assertTrue(any("生日" in r for r in reminders))


# ============ I. 误判防护（3条） ============
class TestAntiFalse(unittest.TestCase):
    def test_birthday_not_timetravel(self):
        e = new_engine()
        _, f = intent.parse_intent("我上个月过了生日", e._contacts())
        self.assertEqual(f[0][0], "cross_scene_birthday")

    def test_holdings_not_products(self):
        e = new_engine()
        _, f = intent.parse_intent("我的理财收益", e._contacts())
        self.assertEqual(f[0][0], "get_holdings")

    def test_scheduled_not_transfer(self):
        e = new_engine()
        _, f = intent.parse_intent("查看我的定时转账", e._contacts())
        self.assertEqual(f[0][0], "list_scheduled")


# ============ J. 补充场景（15条） ============
class TestExtra(unittest.TestCase):
    def test_anomaly(self):
        e = new_engine()
        _, f = intent.parse_intent("查一下异常交易", e._contacts())
        self.assertEqual(f[0][0], "anomaly_scan")

    def test_bill_analysis(self):
        e = new_engine()
        _, f = intent.parse_intent("分析一下这个月的账单", e._contacts())
        self.assertIn("bill_analysis", [i for i, _ in f])

    def test_card_limit(self):
        e = new_engine()
        _, f = intent.parse_intent("把日限调到1万", e._contacts())
        self.assertEqual(f[0][0], "card_limit_adjust")

    def test_card_freeze(self):
        e = new_engine()
        _, f = intent.parse_intent("锁卡", e._contacts())
        self.assertEqual(f[0][0], "card_freeze")

    def test_card_unfreeze(self):
        e = new_engine()
        _, f = intent.parse_intent("解冻卡片", e._contacts())
        self.assertEqual(f[0][0], "card_unlock")

    def test_aa(self):
        e = new_engine()
        _, f = intent.parse_intent("聚餐680我们4个人AA", e._contacts())
        self.assertEqual(f[0][0], "aa_split")

    def test_order_flower(self):
        e = new_engine()
        _, f = intent.parse_intent("买束鲜花", e._contacts())
        self.assertEqual(f[0][0], "place_order")

    def test_order_cake(self):
        e = new_engine()
        _, f = intent.parse_intent("订个蛋糕", e._contacts())
        self.assertEqual(f[0][0], "place_order")

    def test_virtual_card(self):
        e = new_engine()
        _, f = intent.parse_intent("申请虚拟卡", e._contacts())
        self.assertEqual(f[0][0], "virtual_card_apply")

    def test_compare(self):
        e = new_engine()
        _, f = intent.parse_intent("对比一下哪个理财好", e._contacts())
        self.assertEqual(f[0][0], "compare_products")

    def test_contact_same_surname(self):
        e = new_engine()
        _, f = intent.parse_intent("给老张转500", e._contacts())
        self.assertEqual(f[0][0], "transfer")
        self.assertTrue(len(f[0][1].get("candidates", [])) >= 1)

    def test_balance_value(self):
        new_engine()
        ok, msg, data = query_balance()
        self.assertTrue(ok)
        self.assertIn("余额", msg)

    def test_transactions_e2e(self):
        new_engine()
        ok, msg, data = query_transactions()
        self.assertTrue(ok)

    def test_product_list(self):
        new_engine()
        from app.bank.service import PRODUCTS
        self.assertGreaterEqual(len(PRODUCTS), 4)

    def test_sim_date(self):
        new_engine()
        d = get_sim_now()
        self.assertRegex(d, r"\d{4}-\d{2}-\d{2}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
