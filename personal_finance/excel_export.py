"""個人理財 Excel 匯出。

輸出多 sheet workbook：
- 📊 Overview      KPI + Top categories
- 🏦 Accounts      所有 accounts + balance
- 📜 Journal       全部 journal entries (date, desc, lines)
- 🎯 Budget        Budget vs Actual
- 🎯 Projects      Project tracking
- 💱 FX Rates      Currency rates
- 🔗 Aliases       Payment method aliases
"""
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import db, reports


# === Styles ===
HEADER_FILL = PatternFill(start_color="1E66F5", end_color="1E66F5", fill_type="solid")
ASSET_FILL = PatternFill(start_color="DDF1E2", end_color="DDF1E2", fill_type="solid")
LIAB_FILL = PatternFill(start_color="F8D9D9", end_color="F8D9D9", fill_type="solid")
ALT_FILL = PatternFill(start_color="F5F7FA", end_color="F5F7FA", fill_type="solid")
PENDING_FILL = PatternFill(start_color="FFF4E0", end_color="FFF4E0", fill_type="solid")
HEADER_FONT = Font(name="Microsoft JhengHei UI", size=11, bold=True, color="FFFFFF")
TITLE_FONT = Font(name="Microsoft JhengHei UI", size=16, bold=True, color="1E66F5")
SUBTITLE_FONT = Font(name="Microsoft JhengHei UI", size=11, bold=True, color="287D22")
NORMAL_FONT = Font(name="Microsoft JhengHei UI", size=10)
CENTER = Alignment(horizontal="center", vertical="center")
LEFT = Alignment(horizontal="left", vertical="center")
RIGHT = Alignment(horizontal="right", vertical="center")
THIN_BORDER = Border(
    left=Side(style="thin", color="DDDDDD"),
    right=Side(style="thin", color="DDDDDD"),
    top=Side(style="thin", color="DDDDDD"),
    bottom=Side(style="thin", color="DDDDDD"),
)


def export_all(out_path: str | Path, period: str | None = None) -> Path:
    """Export 個人理財 Excel。

    Args:
        period: 'YYYY-MM' 限定某月份。None = 全部
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    wb.remove(wb.active)

    _write_overview(wb, period=period)
    _write_accounts(wb, period=period)
    _write_journal(wb, period=period)
    _write_budget(wb, period=period)
    _write_projects(wb)
    _write_fx_rates(wb)
    _write_aliases(wb)

    wb.save(str(out_path))
    return out_path


def _write_overview(wb, period=None):
    ws = wb.create_sheet("📊 Overview")
    nw = reports.net_worth()
    spending = reports.category_spending()
    period = reports.current_period_month()

    ws["A1"] = "💰 個人理財 Overview"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:F1")
    ws["A2"] = f"生成時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}　當月：{period}"
    ws["A2"].font = Font(name="Microsoft JhengHei UI", size=9, color="888888")
    ws.merge_cells("A2:F2")

    # KPI
    r = 4
    kpis = [
        ("💰 總資產 (HKD)", nw["assets"], "1E66F5"),
        ("💳 總負債 (HKD)", nw["liabilities"], "BC1234"),
        ("📊 淨資產 (HKD)", nw["net_worth"], "287D22"),
        ("🛒 本月支出 (HKD)", sum(s["amount"] for s in spending), "BC7700"),
    ]
    for i, (label, val, color) in enumerate(kpis):
        col = 1 + i * 2
        ws.cell(row=r, column=col, value=label).font = Font(
            name="Microsoft JhengHei UI", size=10, color="5C5F77")
        ws.cell(row=r, column=col).alignment = CENTER
        vc = ws.cell(row=r + 1, column=col, value=val)
        vc.font = Font(name="Microsoft JhengHei UI", size=16, bold=True, color=color)
        vc.alignment = CENTER
        vc.number_format = "#,##0.00"
        ws.merge_cells(start_row=r, start_column=col, end_row=r, end_column=col + 1)
        ws.merge_cells(start_row=r + 1, start_column=col, end_row=r + 1, end_column=col + 1)
    ws.row_dimensions[r + 1].height = 30

    # Top categories
    r = 8
    ws.cell(row=r, column=1, value="🥇 本月各類別支出").font = SUBTITLE_FONT
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)

    headers = ["類別", "Icon", "金額 (HKD)", "Budget", "佔比", "%Used"]
    r += 1
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=r, column=c, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER

    total = sum(s["amount"] for s in spending) or 1
    for i, s in enumerate(spending):
        r += 1
        ws.cell(row=r, column=1, value=s["name"]).font = NORMAL_FONT
        ws.cell(row=r, column=2, value=s["icon"] or "").alignment = CENTER
        amt = ws.cell(row=r, column=3, value=s["amount"])
        amt.number_format = "#,##0.00"
        amt.alignment = RIGHT
        bud = ws.cell(row=r, column=4, value=s.get("budget"))
        if s.get("budget"):
            bud.number_format = "#,##0.00"
            bud.alignment = RIGHT
        ws.cell(row=r, column=5, value=s["amount"] / total).number_format = "0.00%"
        if s.get("pct_used") is not None:
            ws.cell(row=r, column=6, value=s["pct_used"] / 100).number_format = "0.00%"

    # Pie chart
    if spending:
        pie = PieChart()
        pie.title = "各類別佔比"
        labels = Reference(ws, min_col=1, min_row=10, max_row=9 + len(spending))
        data = Reference(ws, min_col=3, min_row=9, max_row=9 + len(spending))
        pie.add_data(data, titles_from_data=True)
        pie.set_categories(labels)
        pie.height = 10
        pie.width = 14
        pie.dataLabels = DataLabelList(showPercent=True, showCatName=True)
        ws.add_chart(pie, f"H{r - len(spending)}")

    for i, w in enumerate([18, 8, 14, 14, 10, 10], 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _write_accounts(wb, period=None):
    ws = wb.create_sheet("🏦 Accounts")
    ws["A1"] = "🏦 Accounts (含 balance, HKD)"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:G1")

    headers = ["Code", "Name", "Type", "Currency", "Opening", "Current (HKD)", "Active"]
    widths = [14, 22, 12, 10, 14, 16, 10]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=c, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    r = 3
    for a in db.list_accounts(active_only=False):
        r += 1
        ws.cell(row=r, column=1, value=a["code"]).font = NORMAL_FONT
        ws.cell(row=r, column=2, value=f"{a['icon'] or ''} {a['name']}").font = NORMAL_FONT
        ws.cell(row=r, column=3, value=a["account_type"]).alignment = CENTER
        ws.cell(row=r, column=4, value=a.get("currency") or "HKD").alignment = CENTER
        op = ws.cell(row=r, column=5, value=a["opening_balance"] or 0)
        op.number_format = "#,##0.00"
        op.alignment = RIGHT
        bal = reports.account_balance(a["code"], in_hkd=True)
        cur = ws.cell(row=r, column=6, value=bal)
        cur.number_format = "#,##0.00"
        cur.alignment = RIGHT
        ws.cell(row=r, column=7, value="✅" if a["is_active"] else "❌").alignment = CENTER

        # Color by type
        if a["account_type"] == "asset":
            for c in range(1, 8):
                ws.cell(row=r, column=c).fill = ASSET_FILL
        elif a["account_type"] == "liability":
            for c in range(1, 8):
                ws.cell(row=r, column=c).fill = LIAB_FILL

    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:{get_column_letter(len(headers))}{r}"


def _write_journal(wb, period=None):
    ws = wb.create_sheet("📜 Journal")
    if period:
        ws["A1"] = f"📜 Journal Entries — {period}"
    else:
        ws["A1"] = "📜 All Journal Entries"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:H1")

    headers = ["Entry ID", "Date", "Description", "Currency", "FX Rate", "Account", "Debit", "Credit"]
    widths = [10, 12, 35, 10, 10, 18, 14, 14]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=c, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    r = 3
    # Filter entries by period if specified
    if period and len(period) == 7:
        start = f"{period}-01"
        # End of month
        year, month = int(period[:4]), int(period[5:7])
        if month == 12:
            end_year, end_month = year + 1, 1
        else:
            end_year, end_month = year, month + 1
        from datetime import date as _d, timedelta
        end = (_d(end_year, end_month, 1) - timedelta(days=1)).isoformat()
        entries = db.list_entries(start_date=start, end_date=end, limit=10000)
    else:
        entries = db.list_entries(limit=10000)

    for entry in entries:
        full = db.get_entry(entry["entry_id"])
        first = True
        for line in full["lines"]:
            r += 1
            if first:
                ws.cell(row=r, column=1, value=full["entry_id"]).alignment = CENTER
                ws.cell(row=r, column=2, value=full["entry_date"]).alignment = CENTER
                ws.cell(row=r, column=3, value=full["description"] or "")
                ws.cell(row=r, column=4, value=full.get("currency") or "HKD").alignment = CENTER
                fx = full.get("fx_rate") or 1.0
                fxc = ws.cell(row=r, column=5, value=fx)
                fxc.number_format = "0.0000"
                fxc.alignment = RIGHT
                first = False
            ws.cell(row=r, column=6, value=line["account_code"])
            if line["debit"]:
                dc = ws.cell(row=r, column=7, value=line["debit"])
                dc.number_format = "#,##0.00"
                dc.alignment = RIGHT
            if line["credit"]:
                cc = ws.cell(row=r, column=8, value=line["credit"])
                cc.number_format = "#,##0.00"
                cc.alignment = RIGHT
        # Light separator
        if r > 4:
            for c in range(1, 9):
                ws.cell(row=r, column=c).border = Border(
                    bottom=Side(style="thin", color="EEEEEE"))

    ws.freeze_panes = "A4"


def _write_budget(wb, period=None):
    ws = wb.create_sheet("🎯 Budget vs Actual")
    period = reports.current_period_month()
    ws["A1"] = f"🎯 Budget vs Actual ({period})"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:F1")

    headers = ["Category", "Budget", "Actual", "Remaining", "%Used", "Status"]
    widths = [22, 14, 14, 14, 10, 14]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=c, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    r = 3
    for row in reports.budget_vs_actual(period):
        r += 1
        budget = row.get("budget") or 0
        actual = row["amount"]
        remain = budget - actual if budget else None
        pct = row.get("pct_used")
        status = "—"
        if pct is not None:
            if pct > 100:
                status = "⚠️ 超支"
            elif pct > 80:
                status = "🟡 接近"
            else:
                status = "🟢 OK"
        ws.cell(row=r, column=1, value=f"{row['icon'] or ''} {row['name']}")
        if budget:
            bc = ws.cell(row=r, column=2, value=budget)
            bc.number_format = "#,##0.00"
            bc.alignment = RIGHT
        ac = ws.cell(row=r, column=3, value=actual)
        ac.number_format = "#,##0.00"
        ac.alignment = RIGHT
        if remain is not None:
            rc = ws.cell(row=r, column=4, value=remain)
            rc.number_format = "#,##0.00;[Red](#,##0.00)"
            rc.alignment = RIGHT
        if pct is not None:
            pc = ws.cell(row=r, column=5, value=pct / 100)
            pc.number_format = "0.00%"
            pc.alignment = RIGHT
            if pct > 100:
                for c in range(1, 7):
                    ws.cell(row=r, column=c).fill = LIAB_FILL
        ws.cell(row=r, column=6, value=status).alignment = CENTER

    ws.freeze_panes = "A4"


def _write_projects(wb):
    ws = wb.create_sheet("🎯 Projects")
    ws["A1"] = "🎯 Projects"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:H1")

    headers = ["Project", "Status", "Start", "End", "Budget", "Spent", "Remaining", "%Used"]
    widths = [25, 12, 12, 12, 14, 14, 14, 10]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=c, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    r = 3
    for p in db.list_projects():
        data = reports.project_spending(p["project_id"])
        r += 1
        spent = data.get("total_spent", 0)
        budget = data.get("budget", 0) or 0
        remain = budget - spent if budget else None
        pct = data.get("pct_used")
        ws.cell(row=r, column=1, value=f"{p['icon'] or '🎯'} {p['name']}")
        ws.cell(row=r, column=2, value=p["status"] or "active").alignment = CENTER
        ws.cell(row=r, column=3, value=p.get("start_date") or "")
        ws.cell(row=r, column=4, value=p.get("end_date") or "")
        if budget:
            bc = ws.cell(row=r, column=5, value=budget)
            bc.number_format = "#,##0.00"
            bc.alignment = RIGHT
        sc = ws.cell(row=r, column=6, value=spent)
        sc.number_format = "#,##0.00"
        sc.alignment = RIGHT
        if remain is not None:
            rc = ws.cell(row=r, column=7, value=remain)
            rc.number_format = "#,##0.00;[Red](#,##0.00)"
            rc.alignment = RIGHT
        if pct is not None:
            pc = ws.cell(row=r, column=8, value=pct / 100)
            pc.number_format = "0.00%"
            pc.alignment = RIGHT


def _write_fx_rates(wb):
    ws = wb.create_sheet("💱 FX Rates")
    ws["A1"] = "💱 Exchange Rates to HKD"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:D1")

    headers = ["Currency", "Rate (1 unit = ? HKD)", "As-of Date", "Notes"]
    widths = [12, 22, 14, 30]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=c, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    r = 3
    for fx in db.list_fx_rates():
        r += 1
        ws.cell(row=r, column=1, value=fx["currency"]).alignment = CENTER
        rc = ws.cell(row=r, column=2, value=fx["rate_to_hkd"])
        rc.number_format = "0.0000"
        rc.alignment = RIGHT
        ws.cell(row=r, column=3, value=fx["as_of_date"]).alignment = CENTER
        ws.cell(row=r, column=4, value=fx.get("notes") or "")


def _write_aliases(wb):
    ws = wb.create_sheet("🔗 Payment Aliases")
    ws["A1"] = "🔗 自訂 Payment Method Aliases"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:D1")

    headers = ["Keyword", "→ Account Code", "Notes", "Created"]
    widths = [25, 16, 30, 16]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=c, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    r = 3
    for a in db.list_payment_aliases():
        r += 1
        ws.cell(row=r, column=1, value=a["keyword"])
        ws.cell(row=r, column=2, value=a["account_code"]).alignment = CENTER
        ws.cell(row=r, column=3, value=a.get("notes") or "")
        ws.cell(row=r, column=4, value=a.get("created_at") or "").alignment = CENTER


if __name__ == "__main__":
    out = export_all("outputs/personal_finance_export.xlsx")
    print(f"✅ Exported: {out}")
