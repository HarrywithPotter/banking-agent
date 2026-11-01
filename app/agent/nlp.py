# -*- coding: utf-8 -*-
"""
NLP 工具：中文金额数字归一、称谓/关系解析。
支持口语化表达：'两千五'=2500、'一千二'=1200、'五百块'=500、'一万'=10000、'88.5'=88.5。
"""
import re

_CN_DIGIT = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000}


def parse_amount(text):
    """把一段金额文字解析为 float。解析失败返回 None。"""
    if text is None:
        return None
    s = str(text).strip().replace(",", "").replace("，", "")
    s = re.sub(r"(元|块|块钱|块人民币|人民币|块整|整)", "", s)
    # 纯数字（可带小数点、可带 万/亿 后缀）
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(万|亿)?", s)
    if m:
        v = float(m.group(1))
        if m.group(2) == "万":
            v *= 10000
        elif m.group(2) == "亿":
            v *= 100000000
        return round(v, 2)
    # 中文数字：逐字符累加 + 口语补位（两千五 = 2500）
    total, num, last_unit = 0.0, 0.0, 1
    has_cn = False
    for ch in s:
        if ch in _CN_DIGIT:
            num = _CN_DIGIT[ch]
            has_cn = True
        elif ch in _CN_UNIT:
            u = _CN_UNIT[ch]
            if num == 0:
                num = 1  # 处理 '十块' = 10
            total += num * u
            last_unit = u
            num = 0
            has_cn = True
        elif ch == "万":
            total = (total + num) * 10000
            last_unit = 10000
            num = 0
            has_cn = True
    if has_cn:
        # 口语补位：'两千五' 末尾的 5 实际是 5 百
        if num != 0 and last_unit >= 10:
            total += num * (last_unit // 10)
        else:
            total += num
        return round(total, 2)
    return None


# 关系称谓 -> 标准化关系
ALIAS_GROUPS = {
    "spouse": ["我爱人", "爱人", "我老婆", "老婆", "我媳妇", "媳妇", "我老公", "老公", "对象", "我对象", "另一半"],
    "mom":    ["妈妈", "老妈", "咱妈", "我妈", "母亲", "咱妈", "我妈妈"],
    "dad":    ["爸爸", "老爸", "咱爸", "我爸", "父亲"],
    "child":  ["儿子", "女儿", "我儿子", "我女儿", "孩子"],
}


def resolve_alias(text):
    """把 '我爱人/老婆' 这类称谓映射到关系 key；无则返回 None。"""
    for key, aliases in ALIAS_GROUPS.items():
        for a in sorted(aliases, key=len, reverse=True):
            if a in text:
                return key
    return None


# 常见称呼后缀
NAME_PATTERNS = [
    r"给([\u4e00-\u9fa5]{2,4})", r"转给([\u4e00-\u9fa5]{2,4})", r"([\u4e00-\u9fa5]{2,4})(?:转|打|汇)",
    r"([\u4e00-\u9fa5]{2,4}家)",
]

# 手机号
PHONE_RE = re.compile(r"1[3-9]\d{9}")
# 卡号（13-19位数字，允许空格）
CARD_RE = re.compile(r"\d{4}[\s]?\d{4}[\s]?\d{4}[\s]?\d{3,7}")

# 昵称/姓氏：老张、小李、阿强
NICKNAME_RE = re.compile(r"(?:^|[\s给转打是叫])(老|小|阿)([\u4e00-\u9fa5])")


def parse_nickname(text):
    """'老张' -> '张'，'小李' -> '李'。返回姓氏首字或 None。"""
    m = NICKNAME_RE.search(text or "")
    return m.group(2) if m else None


_CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def parse_time_range(text):
    """
    解析时间范围 -> 天数（int）。无法识别返回 None（表示全部）。
    支持：近一个月/最近3个月/近半年/近一年/近7天/上周/半个月。
    """
    t = text or ""
    # 半年
    if re.search(r"(近|最近|过去)?半\s*年", t):
        return 180
    # N 天/周
    m = re.search(r"(\d+)\s*(天|日|周)", t)
    if m and re.search(r"(近|最近|过去|这)", t):
        n = int(m.group(1))
        return n * 7 if m.group(2) == "周" else n
    # N 个月/年（阿拉伯数字）
    m = re.search(r"(\d+)\s*(个)?\s*(月|年)", t)
    if m and re.search(r"(近|最近|过去|这)", t):
        n = int(m.group(1))
        return n * 365 if m.group(2) == "年" else n * 30
    # 中文数字 N 个月/年
    m = re.search(r"([一两三四五六七八九十]+)\s*(个)?\s*(月|年)", t)
    if m and re.search(r"(近|最近|过去|这)", t):
        cn = m.group(1)
        n = _CN_NUM.get(cn, 1)
        return n * 365 if m.group(3) == "年" else n * 30
    # 单独的"近一个月/最近一个月/这一个月"
    if re.search(r"(近|最近|这)\s*一?\s*个?\s*月", t):
        return 30
    if re.search(r"(近|最近)\s*一\s*年", t):
        return 365
    if "上个月" in t:
        return 60
    if "上周" in t:
        return 7
    if "近三天" in t or "最近三天" in t:
        return 3
    return None


def extract_phone(text):
    m = PHONE_RE.search(text)
    return m.group(0) if m else None


# 常见汇率（兑人民币，演示用固定值）
CURRENCY_RATES = {
    "美元": 7.20, "美金": 7.20, "刀": 7.20, "USD": 7.20, "$": 7.20,
    "港币": 0.92, "HKD": 0.92,
    "欧元": 7.80, "EUR": 7.80, "€": 7.80,
    "日元": 0.05, "日币": 0.05, "JPY": 0.05,
    "英镑": 9.10, "GBP": 9.10, "£": 9.10,
}


def convert_if_foreign(text, amount):
    """如果文本里含外币关键词，把金额按汇率折成人民币。否则原样返回。"""
    if amount is None:
        return None
    t = text or ""
    for cur, rate in CURRENCY_RATES.items():
        if cur in t:
            return round(amount * rate, 2)
    return round(amount, 2)


if __name__ == "__main__":
    tests = ["五百", "一千二", "两千五", "一万", "88.5", "给妈妈转五百块", "3500", "一千", "2万", "三百二"]
    for t in tests:
        print(t, "->", parse_amount(t))
