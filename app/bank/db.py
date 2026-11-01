# -*- coding: utf-8 -*-
"""
银行核心数据库层（SQLite，可被 DB Browser for SQLite 直接打开编辑）。
所有表结构对应赛题要求的客户资料：人名/手机号/卡号/存款/年流水/订阅/限额/挂失等。
"""
import os
import sqlite3
from datetime import datetime, date

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "banking.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                 -- 人名
    phone TEXT UNIQUE,                  -- 手机号
    id_card TEXT,                       -- 身份证号
    relation_alias TEXT DEFAULT '',      -- 常用称谓别名(逗号分隔, 如 爱人,老婆)
    spouse_name TEXT DEFAULT '',         -- 配偶/爱人姓名
    birthday TEXT DEFAULT '',            -- 本人生日 MM-DD
    spouse_birthday TEXT DEFAULT '',     -- 爱人生日 MM-DD
    wedding_anniv TEXT DEFAULT '',        -- 结婚纪念日 MM-DD
    risk_level TEXT DEFAULT 'R2',        -- 风测等级 R1保守/R2稳健/R3平衡/R4成长/R5进取
    balance REAL DEFAULT 0,              -- 活期存款余额
    annual_flow REAL DEFAULT 0,          -- 一年流水(收支合计)
    address TEXT DEFAULT '',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS cards(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    card_no TEXT UNIQUE,                 -- 银行卡号
    bank_name TEXT,
    card_type TEXT DEFAULT '借记卡',      -- 借记卡/信用卡/虚拟卡
    daily_limit REAL DEFAULT 50000,      -- 银行卡日限额
    status TEXT DEFAULT '正常',           -- 正常/挂失/冻结/已解锁
    expiry TEXT DEFAULT '',
    is_default INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS transactions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    direction TEXT,                      -- 收入/支出
    amount REAL,
    category TEXT,                       -- 餐饮/交通/购物/转账/工资/理财/娱乐...
    counterparty TEXT,                   -- 交易对方
    note TEXT,                           -- 备注
    tx_time TEXT,
    status TEXT DEFAULT '成功'
);
CREATE TABLE IF NOT EXISTS subscriptions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    service_name TEXT,                   -- 爱奇艺/腾讯视频/QQ音乐...
    amount REAL,                         -- 每期扣费
    cycle TEXT DEFAULT '月',             -- 月/年
    next_deduct TEXT,                    -- 下次扣费日 MM-DD
    status TEXT DEFAULT '生效'            -- 生效/已取消
);
CREATE TABLE IF NOT EXISTS scheduled_transfers(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    to_name TEXT,
    amount REAL,
    schedule TEXT,                       -- 如 每月1号
    next_run TEXT,
    note TEXT DEFAULT '',
    status TEXT DEFAULT '生效'            -- 生效/已取消
);
CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    order_type TEXT,                     -- 鲜花/蛋糕/礼品
    items TEXT,
    amount REAL,
    address TEXT DEFAULT '',
    status TEXT DEFAULT '已下单',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS funds_locks(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    amount REAL,
    reason TEXT,
    lock_until TEXT,
    status TEXT DEFAULT '锁定中'          -- 锁定中/已解冻
);
CREATE TABLE IF NOT EXISTS audit_logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT,
    session_id TEXT,
    event_type TEXT,
    detail TEXT
);
CREATE TABLE IF NOT EXISTS settings(
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS wealth_holdings(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    product TEXT,
    principal REAL,
    annual_yield REAL,
    purchase_date TEXT,
    status TEXT DEFAULT '持有'
);
"""


def get_conn():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(force=False):
    """建表并写入种子数据。force=True 时重置。"""
    if force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = get_conn()
    conn.executescript(SCHEMA)
    cur = conn.execute("SELECT COUNT(*) c FROM customers")
    if cur.fetchone()["c"] == 0:
        _seed(conn)
    conn.commit()
    conn.close()


def _seed(conn):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = date.today().strftime("%m-%d")
    # 主客户：我（dzx），配偶 王芳
    conn.execute(
        "INSERT INTO customers(name,phone,id_card,relation_alias,spouse_name,birthday,spouse_birthday,wedding_anniv,risk_level,balance,annual_flow,address,created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("dzx", "13800138000", "6401**********1234", "爱人,老婆,媳妇,我爱人", "王芳",
         today, "11-05", "05-20", "R2", 52800.50, 356000.00, "北京中央财经大学沙河校区", now),
    )
    # ---- 通讯录联系人（30+，含同姓，便于测试按姓名/同姓识别）----
    contacts = [
        # name, phone, id_card_tail, alias, birthday, risk, balance, annual_flow
        ("韩梅梅", "13912345678", "5678", "妈妈,老妈,咱妈", "03-12", "R1", 120000.0, 80000.0),
        ("韩刚", "13987654321", "5679", "爸爸,老爸,咱爸", "04-05", "R1", 150000.0, 90000.0),
        ("李雷", "13798765432", "9012", "", "07-22", "R3", 8600.0, 42000.0),
        ("张建国", "13655556666", "3456", "房东", "01-30", "R2", 300000.0, 120000.0),
        ("王强", "13511112222", "1111", "表哥", "05-18", "R3", 45000.0, 60000.0),
        ("王秀英", "13522223333", "2222", "姑姑", "09-02", "R1", 210000.0, 90000.0),
        ("王磊", "13533334444", "3333", "", "11-11", "R4", 12000.0, 30000.0),
        ("王海燕", "13544445555", "4444", "表姐", "06-25", "R2", 56000.0, 48000.0),
        ("李伟", "13611113333", "5555", "同学", "08-08", "R3", 9800.0, 25000.0),
        ("李娜", "13622224444", "6666", "闺蜜", "04-14", "R2", 33000.0, 40000.0),
        ("李军", "13633335555", "7777", "舅舅", "12-20", "R1", 150000.0, 70000.0),
        ("李静", "13644446666", "8888", "", "02-17", "R2", 21000.0, 18000.0),
        ("张伟", "13711114444", "9999", "同事", "10-01", "R3", 15000.0, 35000.0),
        ("张敏", "13722225555", "1010", "", "03-30", "R2", 28000.0, 22000.0),
        ("张涛", "13733336666", "2020", "室友", "07-07", "R3", 7600.0, 15000.0),
        ("张晓燕", "13744447777", "3030", "学姐", "05-05", "R2", 41000.0, 38000.0),
        ("刘洋", "13811115555", "4040", "室友", "09-15", "R3", 6800.0, 12000.0),
        ("刘娟", "13822226666", "5050", "", "01-25", "R1", 88000.0, 55000.0),
        ("刘志强", "13833337777", "6060", "导师", "11-11", "R2", 76000.0, 49000.0),
        ("陈杰", "13911116666", "7070", "学长", "06-06", "R3", 11000.0, 20000.0),
        ("陈丽华", "13922227777", "8080", "班主任", "08-18", "R1", 130000.0, 62000.0),
        ("陈伟", "13933338888", "9090", "", "12-12", "R4", 22000.0, 41000.0),
        ("杨帆", "13011117777", "1212", "球友", "04-04", "R3", 5400.0, 9000.0),
        ("杨丽", "13022228888", "1313", "", "10-10", "R2", 19000.0, 17000.0),
        ("赵磊", "13111118888", "1414", "同学", "02-28", "R3", 8800.0, 14000.0),
        ("赵倩", "13122229999", "1515", "", "07-07", "R2", 24000.0, 21000.0),
        ("黄志强", "13211119999", "1616", "老板", "03-03", "R2", 260000.0, 150000.0),
        ("黄敏", "13222220000", "1717", "", "09-09", "R1", 95000.0, 48000.0),
        ("周杰", "13311110000", "1818", "球友", "05-21", "R3", 7300.0, 11000.0),
        ("周秀英", "13322221111", "1919", "奶奶", "01-01", "R1", 180000.0, 76000.0),
        ("吴昊", "13555550000", "2121", "学长", "11-11", "R4", 15000.0, 28000.0),
        ("吴桂芳", "13566661111", "2222", "外婆", "12-25", "R1", 220000.0, 88000.0),
        ("郑凯", "15012340000", "2323", "同事", "06-16", "R3", 12000.0, 22000.0),
        ("孙悦", "15023451111", "2424", "", "08-08", "R2", 31000.0, 26000.0),
    ]
    for i, (name, phone, tail, alias, bday, risk, bal, flow) in enumerate(contacts, start=2):
        conn.execute(
            "INSERT INTO customers(name,phone,id_card,relation_alias,birthday,risk_level,balance,annual_flow,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (name, phone, f"1101**********{tail}", alias, bday, risk, bal, flow, now),
        )
    # 银行卡：主客户两张卡
    conn.execute(
        "INSERT INTO cards(customer_id,card_no,bank_name,card_type,daily_limit,status,expiry,is_default) "
        "VALUES(1,'6217001234567890','招商银行','借记卡',50000,'正常','2029-10',1)"
    )
    conn.execute(
        "INSERT INTO cards(customer_id,card_no,bank_name,card_type,daily_limit,status,expiry,is_default) "
        "VALUES(1,'4392 2600 1111 2222','招商银行','信用卡',20000,'正常','2028-06',0)"
    )
    # 交易流水种子：近12个月，每月若干笔
    year = datetime.now().year
    tx_seed = [
        # (month, direction, amount, category, counterparty, note)
        (1, "收入", 5200.0, "工资", "中央财经大学", "奖学金"),
        (1, "支出", 3500.0, "转账", "张建国", "房租"),
        (1, "支出", 320.0, "购物", "京东", " winter衣"),
        (2, "支出", 45.0, "餐饮", "学校食堂", "聚餐"),
        (2, "收入", 500.0, "转账", "李雷", "AA回款"),
        (3, "支出", 500.0, "转账", "韩梅梅", "生活费"),
        (3, "支出", 1200.0, "购物", "苹果官网", "耳机"),
        (4, "支出", 38.5, "餐饮", "麦当劳", "午餐"),
        (4, "支出", 15.0, "娱乐", "爱奇艺", "自动续费"),
        (5, "收入", 5200.0, "工资", "中央财经大学", "奖学金"),
        (5, "支出", 3500.0, "转账", "张建国", "房租"),
        (5, "支出", 299.0, "购物", "京东", "机械键盘"),
        (6, "支出", 450.0, "餐饮", "海底捞", "毕业聚餐"),
        (6, "支出", 9.0, "娱乐", "QQ音乐", "绿钻"),
        (7, "收入", 8000.0, "工资", "实习公司", "实习工资"),
        (7, "支出", 2000.0, "转账", "王强", "借款"),
        (8, "支出", 66.0, "购物", "拼多多", "文具"),
        (8, "支出", 18.0, "娱乐", "网易云音乐", "黑胶"),
        (9, "支出", 38.5, "餐饮", "麦当劳", "午餐"),
        (9, "支出", 12.0, "交通", "地铁", "通勤"),
        (9, "支出", 299.0, "购物", "京东", "键盘"),
        (9, "收入", 5200.0, "工资", "中央财经大学", "奖学金"),
        (10, "支出", 45.0, "餐饮", "学校食堂", "晚餐"),
        (10, "支出", 9.0, "娱乐", "QQ音乐", "绿钻续费"),
        (10, "收入", 200.0, "转账", "李雷", "AA餐费"),
        (10, "支出", 66.0, "购物", "拼多多", "文具"),
    ]
    for m, direction, amt, cat, cp, note in tx_seed:
        mm = f"-{m:02d}-{ (m*7)%27 +1:02d} "
        ts = f"{year}{mm}{(m%12)+8:02d}:{(m*13)%60:02d}"
        conn.execute(
            "INSERT INTO transactions(customer_id,direction,amount,category,counterparty,note,tx_time) VALUES(1,?,?,?,?,?,?)",
            (direction, amt, cat, cp, note, ts),
        )
    # 订阅代扣
    subs = [
        ("爱奇艺黄金VIP", 15.0, "月", "10-05", "生效"),
        ("QQ音乐绿钻", 9.0, "月", "10-08", "生效"),
        ("网易云音乐黑胶", 18.0, "月", "10-11", "生效"),
        ("腾讯视频会员", 25.0, "月", "10-20", "已取消"),
    ]
    for name, amt, cyc, nxt, st in subs:
        conn.execute(
            "INSERT INTO subscriptions(customer_id,service_name,amount,cycle,next_deduct,status) VALUES(1,?,?,?,?,?)",
            (name, amt, cyc, nxt, st),
        )
    # 定时转账种子
    conn.execute(
        "INSERT INTO scheduled_transfers(customer_id,to_name,amount,schedule,next_run,note,status) VALUES(1,'张建国',3500,'每月1号','2026-11-01','房租','生效')"
    )
    # 模拟当前日期（可被"时间快进"修改）
    conn.execute("INSERT INTO settings(key,value) VALUES('sim_now',?)", (date.today().strftime("%Y-%m-%d"),))


if __name__ == "__main__":
    init_db(force=True)
    print("数据库已初始化:", DB_PATH)
