"""Seed default accounts (14 expense categories + 常用 HK 個人 accounts)。

第一次跑會 setup 全部 default。已 exist 嘅 account 唔會被 overwrite。
"""
from . import db
from config import CATEGORIES


# === 14 Expense Categories（同 Extract Invoice 嘅 CATEGORIES 一致）===
# Category 中文名 → (code, icon, sort)
EXPENSE_CATEGORIES = {
    "餐飲":     ("FOOD",          "🍱", 10),
    "超市雜貨": ("GROCERY",       "🛒", 20),
    "交通":     ("TRANSPORT",     "🚇", 30),
    "服飾":     ("CLOTHING",      "👔", 40),
    "電子產品": ("ELECTRONICS",   "💻", 50),
    "美容護理": ("BEAUTY",        "💄", 60),
    "醫療藥物": ("MEDICAL",       "🏥", 70),
    "娛樂":     ("ENTERTAINMENT", "🎬", 80),
    "家居用品": ("HOUSEWARE",     "🏠", 90),
    "教育學習": ("EDUCATION",     "📚", 100),
    "住宿旅遊": ("TRAVEL",        "✈️", 110),
    "通訊網絡": ("COMM",          "📱", 120),
    "水電煤":   ("UTILITY",       "💡", 130),
    "保險":     ("INSURANCE",     "🛡️", 140),
    "其他":     ("OTHER",         "📦", 999),
}

# Reverse lookup
CATEGORY_TO_CODE = {chi: tup[0] for chi, tup in EXPENSE_CATEGORIES.items()}
CODE_TO_CATEGORY = {tup[0]: chi for chi, tup in EXPENSE_CATEGORIES.items()}


# === Default Accounts ===
DEFAULT_ASSETS = [
    # code, name, opening_balance, icon, color
    ("CASH",         "現金",            0, "💵", "#16a34a"),
    ("OCTOPUS",      "八達通",          0, "🚇", "#dc2626"),
    ("HSBC_BANK",    "HSBC 戶口",       0, "🏦", "#dc2626"),
    # 公司報銷應收款（asset = 公司欠你錢，等收款）
    ("AR_REIMBURSE", "公司報銷應收",    0, "🏢", "#bc7700"),
]

DEFAULT_LIABILITIES = [
    ("HSBC_VISA",  "HSBC Visa",  0, "💳", "#dc2626"),
    ("CITI_MC",    "Citi MasterCard", 0, "💳", "#1d4ed8"),
]

DEFAULT_INCOME = [
    ("SALARY",     "人工",       0, "💼", "#287d22"),
    ("BONUS",      "紅利",       0, "🎁", "#fbbf24"),
    ("INVESTMENT", "投資回報",   0, "📈", "#1e66f5"),
    ("OTHER_IN",   "其他收入",   0, "💰", "#5c5f77"),
]


# === Payment method → Account code 自動映射（更全面）===
PAYMENT_METHOD_MAP = {
    # Cash
    "現金":           "CASH", "cash": "CASH", "現金支付": "CASH",
    # Octopus
    "八達通":         "OCTOPUS", "octopus": "OCTOPUS",
    # Visa
    "visa":           "HSBC_VISA", "信用卡": "HSBC_VISA",
    "credit card":    "HSBC_VISA", "credit": "HSBC_VISA",
    "hsbc visa":      "HSBC_VISA", "hsbc credit": "HSBC_VISA",
    # MasterCard
    "mastercard":     "CITI_MC", "master": "CITI_MC",
    "mc":             "CITI_MC", "citi": "CITI_MC",
    "citi mastercard": "CITI_MC",
    # AlipayHK / 支付寶
    "alipay":         "HSBC_BANK", "支付寶": "HSBC_BANK",
    "alipayhk":       "HSBC_BANK",
    # PayMe / FPS / 轉數快
    "payme":          "HSBC_BANK", "fps": "HSBC_BANK",
    "轉數快":         "HSBC_BANK", "faster payment": "HSBC_BANK",
    # WeChat
    "wechat":         "HSBC_BANK", "微信": "HSBC_BANK",
    "wechat pay":     "HSBC_BANK",
    # Bank
    "銀行轉賬":       "HSBC_BANK", "bank transfer": "HSBC_BANK",
    "atm":            "HSBC_BANK", "eps": "HSBC_BANK",
    "debit card":     "HSBC_BANK", "debit": "HSBC_BANK",
}


# === Default account fallback（用戶可改）===
# 由 .env 個 DEFAULT_PAYMENT_ACCOUNT 或者 personal_finance 嘅 settings 揀
import os as _os
DEFAULT_FALLBACK_ACCOUNT = _os.getenv("DEFAULT_PAYMENT_ACCOUNT", "CASH")


def guess_account_from_payment(payment_method: str | None,
                                  fallback: str | None = None) -> str:
    """估 invoice 嘅 payment_method 對應邊個 account code。

    Args:
        payment_method: extractor 攞嘅 payment_method 字串
        fallback: 如果估唔到，用呢個。None = 用 DEFAULT_FALLBACK_ACCOUNT
    """
    if payment_method:
        s = payment_method.lower().strip()
        # Exact match
        if s in PAYMENT_METHOD_MAP:
            return PAYMENT_METHOD_MAP[s]
        # Substring
        for k, v in PAYMENT_METHOD_MAP.items():
            if k.lower() in s or s in k.lower():
                return v
    return fallback or DEFAULT_FALLBACK_ACCOUNT


def category_to_account_code(category_chinese: str) -> str:
    """Extract Invoice 嘅 category 中文 → expense account code"""
    return CATEGORY_TO_CODE.get(category_chinese, "OTHER")


def seed_payment_aliases(force: bool = False) -> dict:
    """將 PAYMENT_METHOD_MAP 內置 alias 寫入 DB（變可編輯 row）。

    force=True 會覆寫（即係 reset 返做 default）。
    """
    db.init_db()
    existing = {a["keyword"] for a in db.list_payment_aliases()}
    created = 0
    skipped = 0
    for keyword, account_code in PAYMENT_METHOD_MAP.items():
        if keyword in existing and not force:
            skipped += 1
            continue
        try:
            db.add_payment_alias(keyword, account_code, "built-in default")
            created += 1
        except Exception:
            skipped += 1
    return {"created": created, "skipped": skipped}


def reset_payment_aliases_to_defaults() -> dict:
    """完全 reset：刪曬現有 + 重 seed default"""
    db.init_db()
    from .db import _conn
    with _conn() as c:
        c.execute("DELETE FROM payment_aliases")
    return seed_payment_aliases(force=True)


def seed_all(force: bool = False) -> dict:
    """Seed default accounts + payment aliases。
    Returns {accounts_created, aliases_created, ...}"""
    db.init_db()
    existing = {a["code"] for a in db.list_accounts(active_only=False)}
    accounts_created = 0
    accounts_skipped = 0

    def _add(code, name, account_type, opening_balance=0, sort_order=0,
              icon=None, color=None):
        nonlocal accounts_created, accounts_skipped
        if code in existing and not force:
            accounts_skipped += 1
            return
        db.upsert_account(
            code=code, name=name, account_type=account_type,
            opening_balance=opening_balance,
            sort_order=sort_order, icon=icon, color=color,
        )
        accounts_created += 1

    # Expense categories
    for chinese, (code, icon, sort_order) in EXPENSE_CATEGORIES.items():
        _add(code, chinese, "expense", sort_order=sort_order, icon=icon)

    # Assets
    for code, name, ob, icon, color in DEFAULT_ASSETS:
        _add(code, name, "asset", opening_balance=ob,
              sort_order=10 + len(name), icon=icon, color=color)

    # Liabilities
    for code, name, ob, icon, color in DEFAULT_LIABILITIES:
        _add(code, name, "liability", opening_balance=ob,
              sort_order=10 + len(name), icon=icon, color=color)

    # Income
    for code, name, ob, icon, color in DEFAULT_INCOME:
        _add(code, name, "income", opening_balance=ob,
              sort_order=10 + len(name), icon=icon, color=color)

    # Payment aliases
    alias_stats = seed_payment_aliases(force=force)

    return {
        "created": accounts_created,
        "skipped": accounts_skipped,
        "aliases_created": alias_stats["created"],
        "aliases_skipped": alias_stats["skipped"],
    }


if __name__ == "__main__":
    stats = seed_all()
    print(f"✅ Created {stats['created']} accounts, skipped {stats['skipped']}")
    for acc in db.list_accounts():
        print(f"  {acc['icon'] or ''} {acc['code']:15} {acc['name']:20} "
              f"({acc['account_type']})")
