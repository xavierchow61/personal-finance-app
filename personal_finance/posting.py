"""Invoice → Journal Entry posting。

雙式記賬規則：
- 用 Cash / Bank 找數：     Dr Expense   /  Cr Asset
  （現金 / 銀行↓，expense ↑）
- 用 Credit Card 找數：     Dr Expense   /  Cr Liability
  （信用卡欠款↑，expense ↑）
- 收入：                     Dr Asset      /  Cr Income
"""
from datetime import date
from typing import Any

from . import db, seed


def post_invoice(invoice: dict,
                  account_code: str | None = None,
                  category_code: str | None = None,
                  project_id: int | None = None,
                  override_amount: float | None = None) -> int:
    """將一張 invoice post 成 journal entry。

    特殊處理：
    - 如果 invoice.expense_type == "公司報銷"
      → Dr Expense / Cr AR_REIMBURSE（公司應收款），而非 Cr 您的現金/卡
      → 之後等公司還款再呼叫 mark_reimbursement_received() 補一條 Dr Bank/Cr AR
    - 其他 (私人 / 可扣稅) → 正常 Dr Expense / Cr Asset|Liability
    """
    # 1. Category
    if not category_code:
        category_chinese = invoice.get("category") or "其他"
        category_code = seed.category_to_account_code(category_chinese)
    exp_acc = db.get_account(category_code)
    if not exp_acc:
        category_code = "OTHER"

    # 2. 金額 + 日期 + description
    amount = float(override_amount if override_amount is not None
                    else (invoice.get("total_amount") or 0))
    if amount <= 0:
        raise ValueError(f"Invoice 金額 ≤ 0：{amount}")
    entry_date = invoice.get("purchase_date") or date.today().isoformat()
    store = invoice.get("store_name") or "?"
    desc_base = f"{store} ({invoice.get('category') or '?'})"
    notes = invoice.get("notes")

    expense_type = (invoice.get("expense_type") or "").strip()

    # 找出付款 account（兩個 case 都用同一邏輯）
    if not account_code:
        pm = invoice.get("payment_method")
        account_code = db.lookup_payment_alias(pm)
        if not account_code:
            from . import settings as pf_settings
            fallback = pf_settings.get_default_account()
            account_code = seed.guess_account_from_payment(
                pm, fallback=fallback)
    pay_acc = db.get_account(account_code)
    if not pay_acc:
        raise ValueError(f"Account {account_code} 不存在")
    if pay_acc["account_type"] not in ("asset", "liability"):
        raise ValueError(
            f"{account_code} 是 {pay_acc['account_type']}，不可用於付款")

    # === Case A: 公司報銷 ===
    # 用自己的錢/卡 pay 公司開支 → 不是您的 expense → 入 AR
    # Dr AR_REIMBURSE / Cr Asset|Liability (Visa/Cash/Bank)
    if expense_type == "公司報銷":
        ar_acc = db.get_account("AR_REIMBURSE")
        if not ar_acc:
            db.upsert_account(
                code="AR_REIMBURSE", name="公司報銷應收",
                account_type="asset", icon="🏢",
                color="#bc7700", sort_order=40)
        desc = f"{desc_base} [公司報銷·{account_code} 墊支]"
        lines = [
            {"account_code": "AR_REIMBURSE", "debit": amount, "credit": 0},
            {"account_code": account_code, "debit": 0, "credit": amount},
        ]
    else:
        # === Case B: 私人 / 可扣稅 = 真實 expense ===
        desc = desc_base
        lines = [
            {"account_code": category_code, "debit": amount, "credit": 0},
            {"account_code": account_code, "debit": 0, "credit": amount},
        ]

    entry_id = db.create_entry(
        entry_date=entry_date,
        description=desc,
        lines=lines,
        invoice_id=invoice.get("id"),
        project_id=project_id,
        notes=notes,
    )
    return entry_id


def mark_reimbursement_received(invoice_id: int,
                                  received_account: str = "HSBC_BANK",
                                  received_date: str | None = None) -> int:
    """收到公司報銷款 → 補一條 Dr Bank / Cr AR 的 entry。

    Args:
        invoice_id: 原張公司報銷單
        received_account: 收款的 account (e.g. HSBC_BANK / CASH)

    Returns:
        新建的 receive entry_id
    """
    # 1. 找回原 AR entry
    entries = db.list_entries(invoice_id=invoice_id, limit=10)
    ar_entry = None
    for e in entries:
        full = db.get_entry(e["entry_id"])
        for line in full["lines"]:
            if line["account_code"] == "AR_REIMBURSE":
                ar_entry = full
                break
        if ar_entry:
            break

    if not ar_entry:
        raise ValueError(
            f"Invoice #{invoice_id} 找不到 AR_REIMBURSE entry，"
            f"可能未 post 成公司報銷")

    # 2. 取得 amount（AR 在 Dr side）
    amount = 0
    for line in ar_entry["lines"]:
        if line["account_code"] == "AR_REIMBURSE":
            # 新邏輯：AR 在 Dr 側
            amount = float(line["debit"] or line["credit"] or 0)
            break

    if amount <= 0:
        raise ValueError(f"AR amount 無效：{amount}")

    # 3. 收款 entry: Dr received_account / Cr AR_REIMBURSE
    if not received_date:
        received_date = date.today().isoformat()
    receive_entry_id = db.create_entry(
        entry_date=received_date,
        description=f"收到公司報銷 (invoice #{invoice_id})",
        lines=[
            {"account_code": received_account, "debit": amount, "credit": 0},
            {"account_code": "AR_REIMBURSE", "debit": 0, "credit": amount},
        ],
        invoice_id=invoice_id,
        notes=f"報銷收款，沖銷 AR entry #{ar_entry['entry_id']}",
    )
    return receive_entry_id


def record_income(amount: float,
                   account_code: str = "HSBC_BANK",
                   income_code: str = "SALARY",
                   entry_date: str | None = None,
                   description: str | None = None) -> int:
    """記一筆收入：Dr Asset / Cr Income"""
    if not entry_date:
        entry_date = date.today().isoformat()
    return db.create_entry(
        entry_date=entry_date,
        description=description or f"{income_code} income",
        lines=[
            {"account_code": account_code, "debit": amount, "credit": 0},
            {"account_code": income_code, "debit": 0, "credit": amount},
        ],
    )


def transfer_between_accounts(from_account: str, to_account: str,
                                amount: float,
                                entry_date: str | None = None,
                                description: str | None = None) -> int:
    """賬戶轉移：Dr To-Account / Cr From-Account
    例如：信用卡找數，由 HSBC Bank 還 HSBC Visa
         Dr HSBC_VISA $5000 / Cr HSBC_BANK $5000
    """
    if not entry_date:
        entry_date = date.today().isoformat()
    return db.create_entry(
        entry_date=entry_date,
        description=description or f"Transfer {from_account} → {to_account}",
        lines=[
            {"account_code": to_account, "debit": amount, "credit": 0},
            {"account_code": from_account, "debit": 0, "credit": amount},
        ],
    )


def unpost_invoice(invoice_id: int) -> int:
    """刪除由某 invoice post 出的 entry。回傳刪除的數目"""
    entries = db.list_entries(invoice_id=invoice_id, limit=100)
    n = 0
    for e in entries:
        db.delete_entry(e["entry_id"])
        n += 1
    return n
