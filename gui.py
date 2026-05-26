"""單據提取 GUI - Tkinter（Catppuccin Latte 淺色主題）

新功能：
- 單據圖預覽（揀一行 → 右邊顯示原張單）
- Drag & Drop 上傳（拖檔入 window 即時加入）
- 公司報銷 / 可扣稅標記
- 重複偵測
"""
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from PIL import Image, ImageTk

import config
import database
import excel_exporter
from config import (CATEGORIES, IMAGE_EXTENSIONS, OUTPUT_DIR, PDF_EXTENSIONS,
                    SUPPORTED_EXTENSIONS)
from database import EXPENSE_TYPES
from extractor import extract_receipt

# === 嘗試載入 tkinterdnd2（drag & drop）===
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False


# === Catppuccin Latte 樣式 ===
BG = "#eff1f5"
FG = "#1e293b"
ACCENT = "#1e66f5"
SUCCESS = "#287d22"
WARNING = "#bc7700"
ERROR = "#bc1234"
MUTED = "#5c5f77"
CARD = "#ffffff"

# === 報銷類型 emoji ===
EXPENSE_ICONS = {
    "私人": "👤",
    "公司報銷": "🏢",
    "可扣稅": "🧾",
}


class InvoiceExtractApp:
    def __init__(self, root):
        self.root = root
        self.root.title("📃 商店單據 AI 提取 + Excel Dashboard")
        self.root.geometry("1280x860")
        self.root.configure(bg=BG)

        self.is_processing = False
        self.msg_queue: queue.Queue = queue.Queue()
        self.selected_files: list[Path] = []
        self.preview_image: ImageTk.PhotoImage | None = None  # keep ref
        self.filter_expense_type: str = "全部"

        database.init_db()
        # Personal finance: init + seed (silent)
        try:
            from personal_finance import db as pfdb
            from personal_finance import seed as pfseed
            pfdb.init_db()
            if not pfdb.list_accounts(active_only=False):
                pfseed.seed_all()
        except Exception:
            pass

        self._setup_style()
        self._build_ui()
        self._poll_queue()
        self._refresh_table()
        self._setup_drag_drop()
        # 首次 refresh PF tab
        try:
            self._pf_refresh_all()
        except Exception:
            pass

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=FG, fieldbackground=CARD)
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=FG, font=("Microsoft JhengHei UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=ACCENT,
                        font=("Microsoft JhengHei UI", 18, "bold"))
        style.configure("Subtitle.TLabel", background=BG, foreground=MUTED,
                        font=("Microsoft JhengHei UI", 9))
        style.configure("Status.TLabel", background=BG, foreground=SUCCESS,
                        font=("Microsoft JhengHei UI", 10, "bold"))
        style.configure("Section.TLabel", background=BG, foreground=ACCENT,
                        font=("Microsoft JhengHei UI", 11, "bold"))
        style.configure("Preview.TLabel", background=CARD, foreground=MUTED,
                        font=("Microsoft JhengHei UI", 10))
        style.configure("TButton", background=CARD, foreground=FG, borderwidth=0,
                        focuscolor=CARD, font=("Microsoft JhengHei UI", 10), padding=(12, 8))
        style.map("TButton", background=[("active", ACCENT)],
                  foreground=[("active", BG)])
        style.configure("Accent.TButton", background=ACCENT, foreground=BG,
                        font=("Microsoft JhengHei UI", 11, "bold"), padding=(20, 12))
        style.map("Accent.TButton", background=[("active", SUCCESS), ("disabled", MUTED)])
        style.configure("Success.TButton", background=SUCCESS, foreground=BG,
                        font=("Microsoft JhengHei UI", 10, "bold"), padding=(15, 10))
        style.map("Success.TButton", background=[("active", ACCENT)])
        style.configure("TCombobox", fieldbackground=CARD, background=CARD,
                        foreground=FG, arrowcolor=FG)
        style.configure("TEntry", fieldbackground=CARD, foreground=FG,
                        insertcolor=FG, borderwidth=0)
        style.configure("TCheckbutton", background=BG, foreground=FG)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=CARD, foreground=FG,
                        padding=(20, 8), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", ACCENT)],
                  foreground=[("selected", BG)])
        style.configure("TProgressbar", background=ACCENT, troughcolor=CARD,
                        borderwidth=0, lightcolor=ACCENT, darkcolor=ACCENT)
        style.configure("Treeview", background=CARD, foreground=FG,
                        fieldbackground=CARD, rowheight=26,
                        font=("Microsoft JhengHei UI", 9), borderwidth=0)
        style.configure("Treeview.Heading", background=ACCENT, foreground=BG,
                        font=("Microsoft JhengHei UI", 10, "bold"), borderwidth=0)
        style.map("Treeview", background=[("selected", ACCENT)],
                  foreground=[("selected", BG)])

    def _build_ui(self):
        # === Header ===
        header = ttk.Frame(self.root, padding=(20, 15, 20, 5))
        header.pack(fill=tk.X)
        title_row = ttk.Frame(header)
        title_row.pack(fill=tk.X)
        ttk.Label(title_row, text="📃 個人理財 — 單據 + 記賬",
                  style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Button(title_row, text="📊 開 Excel Dashboard",
                   style="Success.TButton",
                   command=self.export_and_open).pack(side=tk.RIGHT, padx=(6, 0))

        subtitle_text = "Gemini Vision · 自動分類 · 圖預覽 · 報銷追蹤"
        if DND_AVAILABLE:
            subtitle_text += " · 拖拉上傳 ✅"
        else:
            subtitle_text += " · (tkinterdnd2 未裝，拖拉停用)"
        ttk.Label(header, text=subtitle_text,
                  style="Subtitle.TLabel").pack(anchor=tk.W, pady=(2, 0))

        # === 檔案揀選 ===
        pick_frame = ttk.Frame(self.root, padding=(20, 10))
        pick_frame.pack(fill=tk.X)
        ttk.Button(pick_frame, text="📁 揀單據檔（可多選）",
                   command=self.pick_files).pack(side=tk.LEFT)
        ttk.Button(pick_frame, text="📂 揀整個資料夾",
                   command=self.pick_folder).pack(side=tk.LEFT, padx=(8, 0))

        if DND_AVAILABLE:
            ttk.Label(pick_frame, text="💡 提示：可以直接拖檔入呢個 window",
                      style="Subtitle.TLabel").pack(side=tk.LEFT, padx=(15, 0))

        self.file_label_var = tk.StringVar(value="(未選擇檔案)")
        ttk.Label(pick_frame, textvariable=self.file_label_var,
                  style="Subtitle.TLabel").pack(side=tk.RIGHT)

        # === Action ===
        action_frame = ttk.Frame(self.root, padding=(20, 5))
        action_frame.pack(fill=tk.X)
        self.start_btn = ttk.Button(action_frame, text="🚀 開始提取",
                                    style="Accent.TButton",
                                    command=self.start_extract)
        self.start_btn.pack(side=tk.LEFT)
        ttk.Button(action_frame, text="🗑️ 清空待處理",
                   command=self.clear_pending).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(action_frame, text="📊 匯出 Excel",
                   command=self.export_excel).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(action_frame, text="📂 Outputs 資料夾",
                   command=self.open_outputs).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(action_frame, text="🔄 重新整理",
                   command=self._refresh_table).pack(side=tk.LEFT, padx=(6, 0))

        # === Default payment account selector ===
        ttk.Label(action_frame, text="  💰 預設付款 account：",
                  style="Subtitle.TLabel").pack(side=tk.LEFT, padx=(15, 4))
        # Load from settings + populate options
        try:
            from personal_finance import db as pfdb
            from personal_finance import settings as pf_settings
            pfdb.init_db()
            assets_liab = [a for a in pfdb.list_accounts(active_only=True)
                            if a["account_type"] in ("asset", "liability")]
            opts = [f"{a['icon'] or ''} {a['code']} ({a['name']})"
                    for a in assets_liab]
            self._pf_account_opt_map = {opt: a["code"]
                                         for opt, a in zip(opts, assets_liab)}
            current_code = pf_settings.get_default_account()
            current_opt = next((o for o in opts
                                 if self._pf_account_opt_map[o] == current_code),
                                opts[0] if opts else "")
            self.default_account_var = tk.StringVar(value=current_opt)
            cb = ttk.Combobox(action_frame, textvariable=self.default_account_var,
                              values=opts, state="readonly", width=22)
            cb.pack(side=tk.LEFT)
            cb.bind("<<ComboboxSelected>>",
                    lambda e: self._on_default_account_change())
        except Exception as e:
            self.default_account_var = tk.StringVar(value="")
            self._pf_account_opt_map = {}

        # === Progress ===
        progress_frame = ttk.Frame(self.root, padding=(20, 8))
        progress_frame.pack(fill=tk.X)
        self.status_var = tk.StringVar(value="✅ 準備就緒，請揀單據檔開始")
        ttk.Label(progress_frame, textvariable=self.status_var,
                  style="Status.TLabel").pack(anchor=tk.W)
        self.progress = ttk.Progressbar(progress_frame, mode="determinate", length=400)
        self.progress.pack(fill=tk.X, pady=(5, 0))

        # === Tabs ===
        notebook_frame = ttk.Frame(self.root, padding=(20, 5, 20, 10))
        notebook_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook = ttk.Notebook(notebook_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        records_tab = ttk.Frame(self.notebook)
        self.notebook.add(records_tab, text="📋 單據紀錄")
        self._build_records_tab(records_tab)

        dash_tab = ttk.Frame(self.notebook)
        self.notebook.add(dash_tab, text="📊 Dashboard")
        self._build_dashboard_tab(dash_tab)

        reimb_tab = ttk.Frame(self.notebook)
        self.notebook.add(reimb_tab, text="🏢 報銷追蹤")
        self._build_reimbursement_tab(reimb_tab)

        pf_tab = ttk.Frame(self.notebook)
        self.notebook.add(pf_tab, text="💰 個人記賬")
        self._build_pf_tab(pf_tab)

        log_tab = ttk.Frame(self.notebook)
        self.notebook.add(log_tab, text="🔍 Log")
        self.log_widget = scrolledtext.ScrolledText(
            log_tab, wrap=tk.WORD, bg=CARD, fg=MUTED,
            insertbackground=FG, font=("Consolas", 9),
            relief=tk.FLAT, padx=15, pady=15)
        self.log_widget.pack(fill=tk.BOTH, expand=True)

        # === Footer ===
        footer = ttk.Frame(self.root, padding=(20, 0, 20, 10))
        footer.pack(fill=tk.X)
        ttk.Label(footer, text=f"輸出：{OUTPUT_DIR}",
                  style="Subtitle.TLabel").pack(side=tk.LEFT)
        ttk.Label(footer, text=f"資料庫：{Path(database.DB_PATH).name}",
                  style="Subtitle.TLabel").pack(side=tk.RIGHT)

    def _build_records_tab(self, parent):
        # === Filter bar ===
        toolbar = ttk.Frame(parent, padding=(0, 0, 0, 8))
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="✏️ 編輯", command=self.edit_selected).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="✅ 標記已報銷",
                   command=self.toggle_reimbursed_selected).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(toolbar, text="🗑️ 刪除", command=self.delete_selected).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(toolbar, text="  類型篩選：",
                  style="Subtitle.TLabel").pack(side=tk.LEFT, padx=(15, 4))
        self.filter_var = tk.StringVar(value="全部")
        filter_combo = ttk.Combobox(toolbar, textvariable=self.filter_var,
                                    values=["全部"] + EXPENSE_TYPES,
                                    state="readonly", width=12)
        filter_combo.pack(side=tk.LEFT)
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_table())

        ttk.Label(toolbar, text="（雙擊一行去編輯，揀一行右邊預覽圖）",
                  style="Subtitle.TLabel").pack(side=tk.LEFT, padx=(15, 0))

        # === Paned: Tree (left) + Preview (right) ===
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # ----- Left: Tree -----
        left_frame = ttk.Frame(paned)
        cols = ("id", "type", "purchase_date", "store_name", "category",
                "total_amount", "currency", "reimbursed")
        col_labels = {
            "id": "ID", "type": "類型", "purchase_date": "日期",
            "store_name": "商店", "category": "類別",
            "total_amount": "金額", "currency": "幣",
            "reimbursed": "已報銷",
        }
        col_widths = {
            "id": 40, "type": 50, "purchase_date": 85, "store_name": 140,
            "category": 75, "total_amount": 80, "currency": 40, "reimbursed": 55,
        }
        anchors = {
            "store_name": tk.W,
            "id": tk.CENTER, "type": tk.CENTER, "purchase_date": tk.CENTER,
            "category": tk.CENTER, "currency": tk.CENTER, "reimbursed": tk.CENTER,
            "total_amount": tk.E,
        }

        tree_inner = ttk.Frame(left_frame)
        tree_inner.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_inner, columns=cols, show="headings",
                                 selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=col_labels[c])
            self.tree.column(c, width=col_widths[c], anchor=anchors.get(c, tk.W))

        vsb = ttk.Scrollbar(tree_inner, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        paned.add(left_frame, weight=3)

        # ----- Right: Image preview -----
        right_frame = tk.Frame(paned, bg=CARD)
        right_inner = tk.Frame(right_frame, bg=CARD, padx=10, pady=10)
        right_inner.pack(fill=tk.BOTH, expand=True)

        self.preview_title_var = tk.StringVar(value="📷 單據預覽")
        tk.Label(right_inner, textvariable=self.preview_title_var,
                 bg=CARD, fg=ACCENT,
                 font=("Microsoft JhengHei UI", 11, "bold")).pack(anchor=tk.W)
        self.preview_info_var = tk.StringVar(value="揀一行睇原張單")
        tk.Label(right_inner, textvariable=self.preview_info_var,
                 bg=CARD, fg=MUTED, justify=tk.LEFT,
                 font=("Microsoft JhengHei UI", 9)).pack(anchor=tk.W, pady=(2, 8))

        self.preview_label = tk.Label(right_inner, bg=CARD,
                                       text="(冇預覽)", fg=MUTED,
                                       font=("Microsoft JhengHei UI", 10))
        self.preview_label.pack(fill=tk.BOTH, expand=True)
        # 視窗 size 變 → 重新縮放
        self.preview_label.bind("<Configure>", self._on_preview_resize)
        self._current_preview_path: Path | None = None

        paned.add(right_frame, weight=2)

    def _build_dashboard_tab(self, parent):
        # Scrollable container
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        wrap = ttk.Frame(canvas, padding=(10, 10))
        wrap.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        cw = canvas.create_window((0, 0), window=wrap, anchor="nw")
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(cw, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mw(e): canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mw))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        kpi_frame = ttk.Frame(wrap)
        kpi_frame.pack(fill=tk.X)
        self.kpi_count_var = tk.StringVar(value="0")
        self.kpi_total_var = tk.StringVar(value="0.00")
        self.kpi_avg_var = tk.StringVar(value="0.00")
        self._make_kpi_card(kpi_frame, "總單據數", self.kpi_count_var).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
        self._make_kpi_card(kpi_frame, "總支出", self.kpi_total_var).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=6)
        self._make_kpi_card(kpi_frame, "平均每單", self.kpi_avg_var).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(6, 0))

        ttk.Label(wrap, text="🏆 Top 5 最貴單據", style="Section.TLabel").pack(anchor=tk.W, pady=(15, 5))
        self.top_expenses_widget = scrolledtext.ScrolledText(
            wrap, wrap=tk.WORD, bg=CARD, fg=FG, height=8,
            font=("Microsoft JhengHei UI", 10), relief=tk.FLAT, padx=15, pady=10)
        self.top_expenses_widget.pack(fill=tk.X)
        self.top_expenses_widget.config(state=tk.DISABLED)

        ttk.Label(wrap, text="💰 Top 5 類別支出", style="Section.TLabel").pack(anchor=tk.W, pady=(15, 5))
        self.top_cats_widget = scrolledtext.ScrolledText(
            wrap, wrap=tk.WORD, bg=CARD, fg=FG, height=8,
            font=("Microsoft JhengHei UI", 10), relief=tk.FLAT, padx=15, pady=10)
        self.top_cats_widget.pack(fill=tk.X)
        self.top_cats_widget.config(state=tk.DISABLED)

        ttk.Label(wrap, text="💡 完整圓餅圖喺匯出 Excel 入面睇 →",
                  style="Subtitle.TLabel").pack(anchor=tk.W, pady=(10, 0))

    def _build_reimbursement_tab(self, parent):
        wrap = ttk.Frame(parent, padding=(10, 10))
        wrap.pack(fill=tk.BOTH, expand=True)

        # KPI cards
        kpi_frame = ttk.Frame(wrap)
        kpi_frame.pack(fill=tk.X)
        self.reimb_pending_var = tk.StringVar(value="0.00")
        self.reimb_done_var = tk.StringVar(value="0.00")
        self.reimb_tax_var = tk.StringVar(value="0.00")
        self.reimb_personal_var = tk.StringVar(value="0.00")
        self._make_kpi_card(kpi_frame, "🏢 未報銷", self.reimb_pending_var,
                            color=WARNING).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        self._make_kpi_card(kpi_frame, "✅ 已報銷", self.reimb_done_var,
                            color=SUCCESS).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        self._make_kpi_card(kpi_frame, "🧾 可扣稅", self.reimb_tax_var,
                            color=ACCENT).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        self._make_kpi_card(kpi_frame, "👤 私人", self.reimb_personal_var,
                            color=MUTED).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 0))

        ttk.Label(wrap, text="🏢 待報銷清單", style="Section.TLabel").pack(anchor=tk.W, pady=(15, 5))
        self.pending_reimb_widget = scrolledtext.ScrolledText(
            wrap, wrap=tk.WORD, bg=CARD, fg=FG,
            font=("Microsoft JhengHei UI", 10), relief=tk.FLAT, padx=15, pady=10)
        self.pending_reimb_widget.pack(fill=tk.BOTH, expand=True)
        self.pending_reimb_widget.config(state=tk.DISABLED)

        ttk.Label(wrap, text="💡 詳細報銷單會喺匯出 Excel 入面有專屬 sheet",
                  style="Subtitle.TLabel").pack(anchor=tk.W, pady=(5, 0))

    def _build_pf_tab(self, parent):
        """個人記賬 tab - sub-tabs for Accounts / Budget / Projects / Transactions"""
        # 先 ensure DB + seed
        try:
            from personal_finance import db as pfdb
            from personal_finance import seed as pfseed
            pfdb.init_db()
            # 第一次自動 seed
            if not pfdb.list_accounts(active_only=False):
                pfseed.seed_all()
        except Exception as e:
            ttk.Label(parent,
                      text=f"❌ Personal Finance 初始化失敗：{e}",
                      style="Status.TLabel",
                      foreground=ERROR).pack(padx=20, pady=20)
            return

        # 精簡 toolbar - 只有 refresh + 設定 menu
        top = ttk.Frame(parent)
        top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(8, 4))

        ttk.Button(top, text="🔄 重新整理全部",
                   command=self._pf_refresh_all).pack(side=tk.LEFT)

        # ⚙️ 設定 menu button
        settings_mb = ttk.Menubutton(top, text="⚙️ 設定 ▾")
        settings_menu = tk.Menu(settings_mb, tearoff=0,
                                 font=("Microsoft JhengHei UI", 10))
        settings_menu.add_command(label="📥 將 invoice 入賬",
                                    command=self._pf_post_invoices)
        settings_menu.add_separator()
        settings_menu.add_command(label="🔗 Payment alias（管理付款方式對應）",
                                    command=self._pf_open_aliases)
        settings_menu.add_command(label="💱 FX rates（外幣匯率）",
                                    command=self._pf_open_fx)
        settings_menu.add_command(label="🔒 期間管理（鎖定 / 重開月份）",
                                    command=self._pf_open_periods)
        settings_menu.add_separator()
        settings_menu.add_command(label="📊 匯出 Excel（全部）",
                                    command=self._pf_export_excel)
        settings_menu.add_command(label="📊 匯出 Excel（指定 period）",
                                    command=self._pf_export_excel_period)
        settings_mb["menu"] = settings_menu
        settings_mb.pack(side=tk.LEFT, padx=(8, 0))

        # 再加 sub-notebook 填剩低空間
        inner_nb = ttk.Notebook(parent)
        inner_nb.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        overview_tab = ttk.Frame(inner_nb)
        inner_nb.add(overview_tab, text="📊 Overview")
        self._build_pf_overview(overview_tab)

        budget_tab = ttk.Frame(inner_nb)
        inner_nb.add(budget_tab, text="🎯 Budget")
        self._build_pf_budget(budget_tab)

        accounts_tab = ttk.Frame(inner_nb)
        inner_nb.add(accounts_tab, text="🏦 Accounts")
        self._build_pf_accounts(accounts_tab)

        projects_tab = ttk.Frame(inner_nb)
        inner_nb.add(projects_tab, text="🎯 Projects")
        self._build_pf_projects(projects_tab)

        reports_tab = ttk.Frame(inner_nb)
        inner_nb.add(reports_tab, text="📈 Reports")
        self._build_pf_reports(reports_tab)

        transactions_tab = ttk.Frame(inner_nb)
        inner_nb.add(transactions_tab, text="📜 Transactions")
        self._build_pf_transactions(transactions_tab)

    def _make_scrollable_wrap(self, parent, padding=15):
        """Helper：將個 frame 包入 scrollable canvas，return inner wrap frame"""
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        wrap = ttk.Frame(canvas, padding=padding)
        wrap.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        cw = canvas.create_window((0, 0), window=wrap, anchor="nw")
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(cw, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mw(e): canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mw))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        return wrap

    def _build_pf_overview(self, parent):
        wrap = self._make_scrollable_wrap(parent)

        # === Period selector ===
        period_row = ttk.Frame(wrap)
        period_row.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(period_row, text="📅 Period：",
                  style="Section.TLabel").pack(side=tk.LEFT)
        self.pf_overview_period_var = tk.StringVar(value="this_month")
        for label, val in [("本月", "this_month"), ("上月", "last_month"),
                            ("本年", "this_year"), ("上年", "last_year"),
                            ("全部", "all")]:
            ttk.Radiobutton(period_row, text=label, value=val,
                            variable=self.pf_overview_period_var,
                            command=self._pf_refresh_overview).pack(
                                side=tk.LEFT, padx=(8, 0))

        # KPI cards
        kpi_frame = ttk.Frame(wrap)
        kpi_frame.pack(fill=tk.X, pady=(0, 12))
        self.pf_assets_var = tk.StringVar(value="0.00")
        self.pf_liab_var = tk.StringVar(value="0.00")
        self.pf_net_var = tk.StringVar(value="0.00")
        self.pf_month_spend_var = tk.StringVar(value="0.00")
        self._make_kpi_card(kpi_frame, "💰 總資產", self.pf_assets_var,
                            color=SUCCESS).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        self._make_kpi_card(kpi_frame, "💳 總負債", self.pf_liab_var,
                            color=ERROR).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        self._make_kpi_card(kpi_frame, "📊 淨資產", self.pf_net_var,
                            color=ACCENT).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        self._make_kpi_card(kpi_frame, "🛒 本月支出", self.pf_month_spend_var,
                            color=WARNING).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 0))

        # Account balances
        ttk.Label(wrap, text="🏦 Account 餘額",
                  style="Section.TLabel").pack(anchor=tk.W, pady=(10, 4))
        self.pf_balances_widget = scrolledtext.ScrolledText(
            wrap, height=10, bg=CARD, fg=FG,
            font=("Microsoft JhengHei UI", 10),
            relief=tk.FLAT, padx=15, pady=10)
        self.pf_balances_widget.pack(fill=tk.X)
        self.pf_balances_widget.config(state=tk.DISABLED)

        # This month spending
        ttk.Label(wrap, text="🛒 本月各類別支出",
                  style="Section.TLabel").pack(anchor=tk.W, pady=(15, 4))
        self.pf_month_widget = scrolledtext.ScrolledText(
            wrap, height=12, bg=CARD, fg=FG,
            font=("Microsoft JhengHei UI", 10),
            relief=tk.FLAT, padx=15, pady=10)
        self.pf_month_widget.pack(fill=tk.BOTH, expand=True)
        self.pf_month_widget.config(state=tk.DISABLED)

    def _build_pf_budget(self, parent):
        wrap = self._make_scrollable_wrap(parent)

        # Period picker
        top = ttk.Frame(wrap)
        top.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(top, text="期間：").pack(side=tk.LEFT)
        from datetime import date
        self.pf_budget_period_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
        ttk.Entry(top, textvariable=self.pf_budget_period_var, width=12).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(top, text="📂 載入",
                   command=self._pf_refresh_budget).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(top, text="➕ 設 / 改 budget",
                   command=self._pf_open_budget_dialog).pack(side=tk.LEFT, padx=(6, 0))

        # Budget vs Actual table
        cols = ("icon", "name", "budget", "actual", "remain", "pct")
        col_labels = {
            "icon": "", "name": "類別", "budget": "Budget",
            "actual": "Actual", "remain": "Remaining", "pct": "%",
        }
        col_widths = {"icon": 40, "name": 130, "budget": 100,
                       "actual": 100, "remain": 100, "pct": 80}
        col_anchors = {"icon": tk.CENTER, "name": tk.W,
                        "budget": tk.E, "actual": tk.E, "remain": tk.E,
                        "pct": tk.CENTER}

        tree_frame = ttk.Frame(wrap)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.pf_budget_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                            selectmode="browse")
        for c in cols:
            self.pf_budget_tree.heading(c, text=col_labels[c])
            self.pf_budget_tree.column(c, width=col_widths[c],
                                        anchor=col_anchors[c])
        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=self.pf_budget_tree.yview)
        self.pf_budget_tree.configure(yscrollcommand=vsb.set)
        self.pf_budget_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Trend section
        ttk.Label(wrap, text="📈 過去 12 個月開支 trend",
                  style="Section.TLabel").pack(anchor=tk.W, pady=(15, 4))
        self.pf_trend_widget = scrolledtext.ScrolledText(
            wrap, height=8, bg=CARD, fg=FG,
            font=("Consolas", 9),
            relief=tk.FLAT, padx=15, pady=10)
        self.pf_trend_widget.pack(fill=tk.X)
        self.pf_trend_widget.config(state=tk.DISABLED)

    def _build_pf_accounts(self, parent):
        wrap = self._make_scrollable_wrap(parent)

        top = ttk.Frame(wrap)
        top.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(top, text="➕ 加 account",
                   command=lambda: self._pf_account_dialog(None)).pack(side=tk.LEFT)
        ttk.Button(top, text="✏️ 改",
                   command=self._pf_edit_selected_account).pack(side=tk.LEFT, padx=(6, 0))

        cols = ("icon", "code", "name", "type", "balance", "active")
        col_labels = {"icon": "", "code": "Code", "name": "Name",
                       "type": "Type", "balance": "Balance", "active": "Active"}
        widths = {"icon": 40, "code": 100, "name": 200,
                   "type": 80, "balance": 120, "active": 60}
        anchors = {"icon": tk.CENTER, "code": tk.W, "name": tk.W,
                    "type": tk.CENTER, "balance": tk.E, "active": tk.CENTER}

        tree_frame = ttk.Frame(wrap)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.pf_account_tree = ttk.Treeview(tree_frame, columns=cols,
                                              show="headings", selectmode="browse")
        for c in cols:
            self.pf_account_tree.heading(c, text=col_labels[c])
            self.pf_account_tree.column(c, width=widths[c], anchor=anchors[c])
        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=self.pf_account_tree.yview)
        self.pf_account_tree.configure(yscrollcommand=vsb.set)
        self.pf_account_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.pf_account_tree.bind("<Double-1>",
                                    lambda e: self._pf_edit_selected_account())

    def _build_pf_projects(self, parent):
        wrap = self._make_scrollable_wrap(parent)

        top = ttk.Frame(wrap)
        top.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(top, text="➕ 新 project",
                   command=lambda: self._pf_project_dialog(None)).pack(side=tk.LEFT)
        ttk.Button(top, text="✏️ 改",
                   command=self._pf_edit_selected_project).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(top, text="🗑️ 刪",
                   command=self._pf_delete_selected_project).pack(side=tk.LEFT, padx=(6, 0))

        cols = ("icon", "name", "status", "budget", "spent", "remain", "pct")
        col_labels = {"icon": "", "name": "Project", "status": "Status",
                       "budget": "Budget", "spent": "Spent",
                       "remain": "Remaining", "pct": "%"}
        widths = {"icon": 40, "name": 200, "status": 80, "budget": 100,
                   "spent": 100, "remain": 100, "pct": 70}
        anchors = {"icon": tk.CENTER, "name": tk.W, "status": tk.CENTER,
                    "budget": tk.E, "spent": tk.E, "remain": tk.E, "pct": tk.CENTER}

        tree_frame = ttk.Frame(wrap)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.pf_project_tree = ttk.Treeview(tree_frame, columns=cols,
                                              show="headings", selectmode="browse")
        for c in cols:
            self.pf_project_tree.heading(c, text=col_labels[c])
            self.pf_project_tree.column(c, width=widths[c], anchor=anchors[c])
        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=self.pf_project_tree.yview)
        self.pf_project_tree.configure(yscrollcommand=vsb.set)
        self.pf_project_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.pf_project_tree.bind("<Double-1>",
                                    lambda e: self._pf_edit_selected_project())

    def _build_pf_reports(self, parent):
        wrap = self._make_scrollable_wrap(parent)

        ttk.Label(wrap, text="📈 Financial Reports",
                  style="Section.TLabel").pack(anchor=tk.W, pady=(0, 4))
        ttk.Label(wrap,
                  text="揀期間 → 即時生成 P&L / Balance Sheet / Period Compare",
                  style="Subtitle.TLabel").pack(anchor=tk.W, pady=(0, 12))

        # Period selector
        period_row = ttk.Frame(wrap)
        period_row.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(period_row, text="📅 期間：").pack(side=tk.LEFT)
        self.pf_reports_period_var = tk.StringVar(value="this_month")
        for label, val in [("本月", "this_month"), ("上月", "last_month"),
                            ("本年", "this_year"), ("上年", "last_year"),
                            ("全部", "all")]:
            ttk.Radiobutton(period_row, text=label, value=val,
                            variable=self.pf_reports_period_var,
                            command=self._pf_refresh_reports).pack(
                                side=tk.LEFT, padx=(8, 0))
        ttk.Button(period_row, text="🔄 Refresh",
                   command=self._pf_refresh_reports).pack(side=tk.RIGHT)

        # === 3 報表並排 ===
        # 1. Income Statement (P&L)
        ttk.Label(wrap, text="💰 Income Statement (P&L)",
                  style="Section.TLabel").pack(anchor=tk.W, pady=(10, 4))
        self.pf_pl_widget = scrolledtext.ScrolledText(
            wrap, height=10, bg=CARD, fg=FG,
            font=("Microsoft JhengHei UI", 10), relief=tk.FLAT,
            padx=15, pady=10)
        self.pf_pl_widget.pack(fill=tk.X)
        self.pf_pl_widget.config(state=tk.DISABLED)

        # 2. Balance Sheet
        ttk.Label(wrap, text="🏦 Balance Sheet（截至 period 結束日）",
                  style="Section.TLabel").pack(anchor=tk.W, pady=(15, 4))
        self.pf_bs_widget = scrolledtext.ScrolledText(
            wrap, height=10, bg=CARD, fg=FG,
            font=("Microsoft JhengHei UI", 10), relief=tk.FLAT,
            padx=15, pady=10)
        self.pf_bs_widget.pack(fill=tk.X)
        self.pf_bs_widget.config(state=tk.DISABLED)

        # 3. Period Compare
        ttk.Label(wrap, text="⚖️ Period Compare（vs 上月）",
                  style="Section.TLabel").pack(anchor=tk.W, pady=(15, 4))
        self.pf_cmp_widget = scrolledtext.ScrolledText(
            wrap, height=12, bg=CARD, fg=FG,
            font=("Microsoft JhengHei UI", 10), relief=tk.FLAT,
            padx=15, pady=10)
        self.pf_cmp_widget.pack(fill=tk.BOTH, expand=True)
        self.pf_cmp_widget.config(state=tk.DISABLED)

    def _pf_refresh_reports(self):
        from personal_finance import reports as pfr
        period_type = self.pf_reports_period_var.get()
        start, end = pfr.period_dates(period_type)
        label = pfr.period_label(period_type)

        # === P&L ===
        pl = pfr.income_statement(start, end)
        self.pf_pl_widget.config(state=tk.NORMAL)
        self.pf_pl_widget.delete("1.0", tk.END)
        self.pf_pl_widget.insert(tk.END, f"📅 {label} ({start} ~ {end})\n\n")
        if pl["income"]:
            self.pf_pl_widget.insert(tk.END, "  收入:\n")
            for it in pl["income"]:
                self.pf_pl_widget.insert(
                    tk.END,
                    f"    {it['icon'] or ' '} {it['name']:<14} "
                    f"${it['amount']:>10,.2f}\n")
            self.pf_pl_widget.insert(
                tk.END,
                f"  ─────────────────────────────\n"
                f"  總收入                ${pl['total_income']:>10,.2f}\n\n")
        if pl["expense"]:
            self.pf_pl_widget.insert(tk.END, "  支出:\n")
            for it in pl["expense"]:
                self.pf_pl_widget.insert(
                    tk.END,
                    f"    {it['icon'] or ' '} {it['name']:<14} "
                    f"${it['amount']:>10,.2f}\n")
            self.pf_pl_widget.insert(
                tk.END,
                f"  ─────────────────────────────\n"
                f"  總支出                ${pl['total_expense']:>10,.2f}\n")
        self.pf_pl_widget.insert(
            tk.END,
            f"\n  📊 Net (收入 - 支出): ${pl['net']:>10,.2f}\n"
            f"  {'✅ 盈餘' if pl['net'] >= 0 else '⚠️ 赤字'}\n")
        self.pf_pl_widget.config(state=tk.DISABLED)

        # === Balance Sheet ===
        bs = pfr.balance_sheet(as_of_date=end)
        self.pf_bs_widget.config(state=tk.NORMAL)
        self.pf_bs_widget.delete("1.0", tk.END)
        self.pf_bs_widget.insert(tk.END, f"📅 截至 {end}\n\n")
        if bs["assets"]:
            self.pf_bs_widget.insert(tk.END, "  💰 資產:\n")
            for a in bs["assets"]:
                self.pf_bs_widget.insert(
                    tk.END,
                    f"    {a['icon'] or ' '} {a['name']:<18} "
                    f"${a['balance']:>12,.2f}\n")
            self.pf_bs_widget.insert(
                tk.END,
                f"  ───────────────────────────────────\n"
                f"  總資產                  ${bs['total_assets']:>12,.2f}\n\n")
        if bs["liabilities"]:
            self.pf_bs_widget.insert(tk.END, "  💳 負債:\n")
            for l in bs["liabilities"]:
                self.pf_bs_widget.insert(
                    tk.END,
                    f"    {l['icon'] or ' '} {l['name']:<18} "
                    f"${l['balance']:>12,.2f}\n")
            self.pf_bs_widget.insert(
                tk.END,
                f"  ───────────────────────────────────\n"
                f"  總負債                  ${bs['total_liabilities']:>12,.2f}\n")
        self.pf_bs_widget.insert(
            tk.END,
            f"\n  📊 淨資產 (Net Worth):    ${bs['net_worth']:>12,.2f}\n")
        self.pf_bs_widget.config(state=tk.DISABLED)

        # === Period Compare ===
        cmp_period_b = "last_month" if period_type == "this_month" else (
            "last_year" if period_type == "this_year" else "last_month")
        cmp = pfr.period_compare(period_type, cmp_period_b)
        self.pf_cmp_widget.config(state=tk.NORMAL)
        self.pf_cmp_widget.delete("1.0", tk.END)
        self.pf_cmp_widget.insert(
            tk.END,
            f"  比較：{cmp['period_a_label']} vs {cmp['period_b_label']}\n\n")
        self.pf_cmp_widget.insert(
            tk.END,
            f"  {'項目':<14} {cmp['period_a_label']:>12} "
            f"{cmp['period_b_label']:>12} {'差異':>12}\n")
        self.pf_cmp_widget.insert(
            tk.END,
            f"  {'─'*54}\n"
            f"  {'收入':<14} ${cmp['income_a']:>10,.2f}  "
            f"${cmp['income_b']:>10,.2f}  ${cmp['income_diff']:>+10,.2f}\n"
            f"  {'支出':<14} ${cmp['expense_a']:>10,.2f}  "
            f"${cmp['expense_b']:>10,.2f}  ${cmp['expense_diff']:>+10,.2f}\n"
            f"  {'淨':<14} ${cmp['net_a']:>10,.2f}  "
            f"${cmp['net_b']:>10,.2f}  ${cmp['net_diff']:>+10,.2f}\n\n")
        if cmp["categories"]:
            self.pf_cmp_widget.insert(tk.END, "  📋 各類別支出比較:\n")
            for c in cmp["categories"][:15]:
                pct = (f"{c['pct_change']:+.0f}%"
                        if c["pct_change"] is not None and
                           c["pct_change"] != float("inf") else "  NEW")
                self.pf_cmp_widget.insert(
                    tk.END,
                    f"    {c['icon'] or ' '} {c['name']:<10} "
                    f"${c['amount_a']:>8,.2f}  vs  ${c['amount_b']:>8,.2f}  "
                    f"({pct})\n")
        self.pf_cmp_widget.config(state=tk.DISABLED)

    def _build_pf_transactions(self, parent):
        wrap = self._make_scrollable_wrap(parent)

        top = ttk.Frame(wrap)
        top.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(top, text="最近 100 個 transactions：",
                  style="Subtitle.TLabel").pack(side=tk.LEFT)
        ttk.Button(top, text="➕ 加手動 entry",
                   command=self._pf_manual_entry_dialog).pack(side=tk.RIGHT)
        ttk.Button(top, text="🔄 Refresh",
                   command=self._pf_refresh_transactions).pack(side=tk.RIGHT, padx=(0, 6))
        ttk.Button(top, text="🔁 重 post (改 account)",
                   command=self._pf_repost_selected).pack(side=tk.RIGHT, padx=(0, 6))
        ttk.Button(top, text="🗑️ 刪",
                   command=self._pf_delete_selected_entry).pack(side=tk.RIGHT, padx=(0, 6))

        cols = ("date", "desc", "amount", "lines")
        col_labels = {"date": "Date", "desc": "Description",
                       "amount": "Amount", "lines": "Lines (Dr/Cr)"}
        widths = {"date": 90, "desc": 220, "amount": 100, "lines": 400}
        anchors = {"date": tk.CENTER, "desc": tk.W,
                    "amount": tk.E, "lines": tk.W}

        tree_frame = ttk.Frame(wrap)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.pf_txn_tree = ttk.Treeview(tree_frame, columns=cols,
                                          show="headings", selectmode="browse")
        for c in cols:
            self.pf_txn_tree.heading(c, text=col_labels[c])
            self.pf_txn_tree.column(c, width=widths[c], anchor=anchors[c])
        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=self.pf_txn_tree.yview)
        self.pf_txn_tree.configure(yscrollcommand=vsb.set)
        self.pf_txn_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    def _make_kpi_card(self, parent, label, value_var, color=ACCENT):
        card = tk.Frame(parent, bg=CARD, padx=15, pady=12, highlightthickness=0)
        tk.Label(card, text=label, bg=CARD, fg=MUTED,
                 font=("Microsoft JhengHei UI", 10)).pack(anchor=tk.W)
        tk.Label(card, textvariable=value_var, bg=CARD, fg=color,
                 font=("Microsoft JhengHei UI", 20, "bold")).pack(anchor=tk.W, pady=(2, 0))
        return card

    # ------------------------------ Drag & Drop ------------------------------
    def _setup_drag_drop(self):
        if not DND_AVAILABLE:
            return
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event):
        # Tk 嘅 dnd data 係 space-separated paths，含空格嘅 path 會用 {} 包住
        paths = self._parse_dnd_paths(event.data)
        added = []
        for p in paths:
            path = Path(p)
            if path.is_dir():
                for f in path.iterdir():
                    if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                        added.append(f)
            elif path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                added.append(path)

        if not added:
            messagebox.showinfo("冇支援嘅檔案",
                f"拖入嘅檔唔係支援格式。\n支援：{', '.join(SUPPORTED_EXTENSIONS)}")
            return

        self.selected_files = added
        self.file_label_var.set(f"📥 拖入 {len(added)} 個檔")
        self.log(f"📥 Drag-drop 加入 {len(added)} 個檔")

    @staticmethod
    def _parse_dnd_paths(data: str) -> list[str]:
        """解析 Tk DND 傳嚟嘅 path string（含空格嘅用 {} 包住）"""
        paths = []
        buf = ""
        in_brace = False
        for ch in data:
            if ch == "{":
                in_brace = True
                buf = ""
            elif ch == "}":
                in_brace = False
                if buf:
                    paths.append(buf)
                buf = ""
            elif ch == " " and not in_brace:
                if buf:
                    paths.append(buf)
                buf = ""
            else:
                buf += ch
        if buf:
            paths.append(buf)
        return paths

    # ------------------------------ File picking ------------------------------
    def pick_files(self):
        paths = filedialog.askopenfilenames(
            title="揀單據檔（可 Ctrl/Shift 多選）",
            filetypes=[
                ("單據檔案", "*.jpg *.jpeg *.png *.bmp *.webp *.tiff *.pdf"),
                ("圖片", "*.jpg *.jpeg *.png *.bmp *.webp *.tiff"),
                ("PDF", "*.pdf"),
                ("所有檔案", "*.*"),
            ],
        )
        if paths:
            self.selected_files = [Path(p) for p in paths]
            self.file_label_var.set(f"已選 {len(self.selected_files)} 個檔")
            self.log(f"📁 已選擇 {len(self.selected_files)} 個檔")

    def pick_folder(self):
        folder = filedialog.askdirectory(title="揀一個資料夾")
        if folder:
            folder = Path(folder)
            files = sorted([
                p for p in folder.iterdir()
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
            ])
            if not files:
                messagebox.showinfo("冇單據檔",
                    f"資料夾入面冇支援嘅檔案格式。\n支援：{', '.join(SUPPORTED_EXTENSIONS)}")
                return
            self.selected_files = files
            self.file_label_var.set(f"📂 {folder.name}（{len(files)} 個檔）")
            self.log(f"📂 已選擇資料夾 {folder} → {len(files)} 個檔")

    def clear_pending(self):
        self.selected_files = []
        self.file_label_var.set("(未選擇檔案)")
        self.log("🗑️ 已清空待處理")

    # ------------------------------ Extract ------------------------------
    def start_extract(self):
        if self.is_processing:
            return
        if not self.selected_files:
            messagebox.showwarning("未選擇檔案", "請先揀單據檔或者拖入 window。")
            return
        if not config.GEMINI_API_KEY:
            messagebox.showerror("缺 API Key",
                "未設定 GEMINI_API_KEY。\n\n"
                "去 https://aistudio.google.com/apikey 攞免費 key，\n"
                "然後喺資料夾入面整個 .env 檔，內容：\n\n"
                "GEMINI_API_KEY=你個key")
            return

        self.is_processing = True
        self.start_btn.config(state=tk.DISABLED)
        self.progress["value"] = 0
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        total = len(self.selected_files)
        saved = 0
        failed = 0
        skipped = 0
        try:
            for i, f in enumerate(self.selected_files, 1):
                pct = (i - 1) / total * 100
                self.q("progress", pct)
                self.q("status", f"🤖 提取中 [{i}/{total}]：{f.name}")
                self.q("log", f"🔍 處理：{f.name}")
                try:
                    data = extract_receipt(f)
                    # 重複偵測
                    dup = database.is_duplicate(data)
                    if dup:
                        self.q("log",
                               f"⚠️ 重複！同 #{dup['id']} 一樣 "
                               f"({dup.get('store_name')}, ${dup.get('total_amount')}) → 跳過")
                        skipped += 1
                        continue
                    inv_id = database.save_invoice(data)
                    saved += 1
                    self.q("log",
                           f"✅ #{inv_id} | {data.get('store_name', '?')} | "
                           f"{data.get('category', '?')} | "
                           f"${data.get('total_amount', 0):.2f}")
                    # 自動 post 入個人理財 ledger
                    try:
                        from personal_finance import posting as pfpost
                        data_with_id = {**data, "id": inv_id}
                        entry_id = pfpost.post_invoice(data_with_id)
                        self.q("log",
                               f"   💰 已入個人記賬 (entry #{entry_id})")
                    except Exception as e:
                        self.q("log",
                               f"   ⚠️ 個人記賬入唔到：{e}")
                except Exception as e:
                    failed += 1
                    self.q("log", f"❌ {f.name} → {e}")

            self.q("progress", 100)
            msg = f"✅ 完成！成功 {saved}/{total}"
            if skipped:
                msg += f"，跳過 {skipped}（重複）"
            if failed:
                msg += f"，失敗 {failed}"
            self.q("status", msg)
            # 提取完清空待處理 list
            self.selected_files = []
            self.q("file_label", "(未選擇檔案)")
            self.q("done", True)
        except Exception as e:
            self.q("log", f"❌ 嚴重錯誤：{e}")
            self.q("status", f"❌ 處理失敗")
            self.q("error", str(e))

    # ------------------------------ Excel ------------------------------
    def export_excel(self):
        if database.count() == 0:
            messagebox.showwarning("冇資料", "資料庫入面冇單據，請先提取至少一張。")
            return
        try:
            path = excel_exporter.export_excel()
            self.log(f"📊 已匯出：{path.name}")
            if messagebox.askyesno("匯出成功",
                                    f"Excel 已存：\n{path}\n\n要而家開個檔嗎？"):
                self._open_file(path)
        except Exception as e:
            self.log(f"❌ 匯出失敗：{e}")
            messagebox.showerror("匯出失敗", str(e))

    def export_and_open(self):
        if database.count() == 0:
            messagebox.showwarning("冇資料", "資料庫入面冇單據，請先提取至少一張。")
            return
        try:
            path = excel_exporter.export_excel()
            self.log(f"📊 已匯出並開檔：{path.name}")
            self._open_file(path)
        except Exception as e:
            self.log(f"❌ 匯出失敗：{e}")
            messagebox.showerror("匯出失敗", str(e))

    def _open_file(self, path: Path):
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)])
            else:
                subprocess.run(["xdg-open", str(path)])
        except Exception as e:
            self.log(f"⚠️ 無法自動開檔：{e}")

    def open_outputs(self):
        OUTPUT_DIR.mkdir(exist_ok=True)
        self._open_file(OUTPUT_DIR)

    def _on_default_account_change(self):
        """User 揀新 default account → 存入 settings"""
        opt = self.default_account_var.get()
        code = self._pf_account_opt_map.get(opt)
        if code:
            try:
                from personal_finance import settings as pf_settings
                pf_settings.set_default_account(code)
                self.log(f"💰 預設付款 account 改為：{code}")
            except Exception as e:
                self.log(f"⚠️ 設定失敗：{e}")

    # ------------------------------ Personal Finance ------------------------------
    def _pf_refresh_all(self):
        try:
            self._pf_refresh_overview()
            self._pf_refresh_budget()
            self._pf_refresh_accounts()
            self._pf_refresh_projects()
            self._pf_refresh_transactions()
            try:
                self._pf_refresh_reports()
            except (AttributeError, Exception):
                pass  # reports tab 可能未 init
        except Exception as e:
            self.log(f"❌ PF refresh 失敗：{e}")

    def _pf_refresh_overview(self):
        from personal_finance import reports as pfr
        # Period
        period_type = getattr(self, "pf_overview_period_var",
                                None) and self.pf_overview_period_var.get() or "this_month"

        # 用 period 對應嘅 end date 計 Balance Sheet
        if period_type == "all":
            as_of = None  # 用今日
        else:
            _, as_of = pfr.period_dates(period_type)
        nw = pfr.net_worth(as_of)
        self.pf_assets_var.set(f"{nw['assets']:,.2f}")
        self.pf_liab_var.set(f"{nw['liabilities']:,.2f}")
        self.pf_net_var.set(f"{nw['net_worth']:,.2f}")

        # P&L for period
        if period_type == "all":
            # All-time: sum monthly spending for last 24 months
            month_spend = sum(m["amount"]
                              for m in pfr.monthly_spending(months=24))
        else:
            start, end = pfr.period_dates(period_type)
            pl = pfr.income_statement(start, end)
            month_spend = pl["total_expense"]
        self.pf_month_spend_var.set(f"{month_spend:,.2f}")

        # Balances widget
        self.pf_balances_widget.config(state=tk.NORMAL)
        self.pf_balances_widget.delete("1.0", tk.END)
        from personal_finance import db as pfdb
        for atype, label in [("asset", "💰 資產"), ("liability", "💳 負債")]:
            self.pf_balances_widget.insert(tk.END, f"{label}\n")
            for b in pfr.all_account_balances():
                if b["account_type"] == atype:
                    icon = b["icon"] or "  "
                    bar = ("█" * min(int(abs(b["balance"]) / 1000), 30)) or ""
                    self.pf_balances_widget.insert(
                        tk.END,
                        f"  {icon} {b['name']:<18} "
                        f"${b['balance']:>12,.2f}  {bar}\n")
            self.pf_balances_widget.insert(tk.END, "\n")
        self.pf_balances_widget.config(state=tk.DISABLED)

        # Category spending widget — 用 period selector 嘅範圍
        self.pf_month_widget.config(state=tk.NORMAL)
        self.pf_month_widget.delete("1.0", tk.END)
        start_p, end_p = pfr.period_dates(period_type)
        # 月度先有 budget；年/全部冇
        period_arg = (start_p[:7]
                       if period_type in ("this_month", "last_month") else None)
        cat_list = pfr.spending_by_category(start_p, end_p, period=period_arg)
        label = pfr.period_label(period_type)
        self.pf_month_widget.insert(tk.END, f"  📅 {label}\n\n")
        if cat_list:
            for s in cat_list:
                bar = "█" * min(int(s["amount"] / 100), 30)
                bud = (f"  (budget ${s['budget']:,.0f}, {s['pct_used']:.0f}%)"
                        if s["budget"] else "")
                self.pf_month_widget.insert(
                    tk.END,
                    f"  {s['icon'] or '  '} {s['name']:<10} "
                    f"${s['amount']:>9,.2f}  {bar}{bud}\n")
        else:
            self.pf_month_widget.insert(tk.END, "  (呢個 period 冇支出記錄)")
        self.pf_month_widget.config(state=tk.DISABLED)

    def _pf_refresh_budget(self):
        from personal_finance import reports as pfr
        period = self.pf_budget_period_var.get().strip()
        for item in self.pf_budget_tree.get_children():
            self.pf_budget_tree.delete(item)
        for r in pfr.budget_vs_actual(period):
            budget = r.get("budget") or 0
            actual = r["amount"]
            remain = budget - actual if budget else None
            pct = r.get("pct_used")
            pct_str = f"{pct:.0f}%" if pct is not None else "—"
            if pct is not None and pct > 100:
                pct_str = f"⚠️ {pct_str}"
            self.pf_budget_tree.insert("", tk.END, iid=r["code"], values=(
                r["icon"] or "",
                r["name"],
                f"{budget:,.2f}" if budget else "—",
                f"{actual:,.2f}",
                f"{remain:,.2f}" if remain is not None else "—",
                pct_str,
            ))
        # Trend
        self.pf_trend_widget.config(state=tk.NORMAL)
        self.pf_trend_widget.delete("1.0", tk.END)
        for m in pfr.monthly_spending(12):
            bar = "█" * min(int(m["amount"] / 500), 40)
            self.pf_trend_widget.insert(
                tk.END, f"  {m['month']}  ${m['amount']:>10,.2f}  {bar}\n")
        self.pf_trend_widget.config(state=tk.DISABLED)

    def _pf_refresh_accounts(self):
        from personal_finance import db as pfdb
        from personal_finance import reports as pfr
        for item in self.pf_account_tree.get_children():
            self.pf_account_tree.delete(item)
        for acc in pfdb.list_accounts(active_only=False):
            bal = pfr.account_balance(acc["code"])
            self.pf_account_tree.insert("", tk.END, iid=acc["code"], values=(
                acc["icon"] or "",
                acc["code"],
                acc["name"],
                acc["account_type"],
                f"{bal:,.2f}",
                "✅" if acc["is_active"] else "❌",
            ))

    def _pf_refresh_projects(self):
        from personal_finance import db as pfdb
        from personal_finance import reports as pfr
        for item in self.pf_project_tree.get_children():
            self.pf_project_tree.delete(item)
        for p in pfdb.list_projects():
            data = pfr.project_spending(p["project_id"])
            spent = data.get("total_spent", 0)
            budget = data.get("budget", 0) or 0
            remain = budget - spent if budget else None
            pct = data.get("pct_used")
            pct_str = f"{pct:.0f}%" if pct is not None else "—"
            if pct is not None and pct > 100:
                pct_str = f"⚠️ {pct_str}"
            self.pf_project_tree.insert("", tk.END, iid=str(p["project_id"]),
                                          values=(
                p["icon"] or "🎯",
                p["name"],
                p["status"] or "active",
                f"{budget:,.2f}" if budget else "—",
                f"{spent:,.2f}",
                f"{remain:,.2f}" if remain is not None else "—",
                pct_str,
            ))

    def _pf_refresh_transactions(self):
        from personal_finance import db as pfdb
        for item in self.pf_txn_tree.get_children():
            self.pf_txn_tree.delete(item)
        for e in pfdb.list_entries(limit=100):
            self.pf_txn_tree.insert("", tk.END, iid=str(e["entry_id"]),
                                      values=(
                e["entry_date"],
                e["description"] or "",
                f"{e.get('amount', 0):,.2f}",
                e.get("lines_summary") or "",
            ))

    def _pf_post_invoices(self):
        """將 invoice DB 入面未 post 嘅 invoices 入賬"""
        from personal_finance import db as pfdb
        from personal_finance import posting as pfpost
        import database as invdb

        invoices = invdb.list_all()
        posted_ids = set()
        # 揾已 post 過嘅 invoice_id
        for e in pfdb.list_entries(limit=10000):
            if e.get("invoice_id"):
                posted_ids.add(e["invoice_id"])

        to_post = [inv for inv in invoices if inv["id"] not in posted_ids]
        if not to_post:
            messagebox.showinfo("冇新單",
                "所有 invoice 已經入賬。")
            return

        if not messagebox.askyesno(
            "確認入賬",
            f"有 {len(to_post)} 張未入賬嘅 invoice，現在自動 post？\n"
            f"（按 invoice 嘅 payment_method 估 account）"):
            return

        ok = 0
        fail = 0
        for inv in to_post:
            try:
                pfpost.post_invoice(inv)
                ok += 1
            except Exception as e:
                fail += 1
                self.log(f"⚠️ Post invoice #{inv['id']} 失敗：{e}")
        self._pf_refresh_all()
        messagebox.showinfo("完成",
            f"✅ 入賬 {ok} 張" + (f"，失敗 {fail} 張" if fail else ""))

    # ============ PF Dialogs ============
    def _pf_open_budget_dialog(self):
        period = self.pf_budget_period_var.get().strip()
        PFBudgetDialog(self.root, self, period)

    def _pf_account_dialog(self, account_code: str | None):
        PFAccountDialog(self.root, self, account_code)

    def _pf_edit_selected_account(self):
        sel = self.pf_account_tree.selection()
        if not sel:
            messagebox.showinfo("揀一個", "請先揀一個 account。")
            return
        self._pf_account_dialog(sel[0])

    def _pf_project_dialog(self, project_id):
        PFProjectDialog(self.root, self, project_id)

    def _pf_edit_selected_project(self):
        sel = self.pf_project_tree.selection()
        if not sel:
            messagebox.showinfo("揀一個", "請先揀一個 project。")
            return
        self._pf_project_dialog(int(sel[0]))

    def _pf_delete_selected_project(self):
        sel = self.pf_project_tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("確認", "刪呢個 project？（相關 entry 嘅 project link 會 unset）"):
            return
        from personal_finance import db as pfdb
        pfdb.delete_project(int(sel[0]))
        self._pf_refresh_projects()

    def _pf_manual_entry_dialog(self):
        PFManualEntryDialog(self.root, self)

    def _pf_open_aliases(self):
        PFAliasDialog(self.root, self)

    def _pf_open_fx(self):
        PFFxDialog(self.root, self)

    def _pf_open_periods(self):
        PFPeriodDialog(self.root, self)

    def _pf_export_excel_period(self):
        # 簡單 dialog: 揀 period
        from tkinter import simpledialog
        from datetime import date
        period = simpledialog.askstring(
            "匯出指定 period",
            "輸入 period (YYYY-MM)：\n例：2026-05",
            initialvalue=date.today().strftime("%Y-%m"),
            parent=self.root)
        if not period:
            return
        if len(period) != 7 or period[4] != "-":
            messagebox.showwarning("格式錯", "用 YYYY-MM 格式（例：2026-05）")
            return
        from personal_finance import excel_export
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = OUTPUT_DIR / f"個人理財_{period}_{ts}.xlsx"
        try:
            result = excel_export.export_all(out, period=period)
            self.log(f"📊 已匯出 {period}：{result.name}")
            if messagebox.askyesno("成功",
                f"已匯出 {period} period：\n{result}\n而家開？"):
                self._open_file(result)
        except Exception as e:
            messagebox.showerror("失敗", str(e))

    def _pf_export_excel(self):
        from personal_finance import excel_export
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = OUTPUT_DIR / f"個人理財_{ts}.xlsx"
        try:
            result = excel_export.export_all(out)
            self.log(f"📊 個人理財已匯出：{result.name}")
            if messagebox.askyesno("成功",
                f"已匯出：\n{result}\n而家開？"):
                self._open_file(result)
        except Exception as e:
            messagebox.showerror("失敗", str(e))

    def _pf_delete_selected_entry(self):
        sel = self.pf_txn_tree.selection()
        if not sel:
            messagebox.showinfo("揀一個", "請揀一個 entry")
            return
        if not messagebox.askyesno("確認", "刪呢個 journal entry？"):
            return
        from personal_finance import db as pfdb
        for s in sel:
            try:
                pfdb.delete_entry(int(s))
            except Exception as e:
                self.log(f"⚠️ 刪失敗：{e}")
        self._pf_refresh_all()

    def _pf_repost_selected(self):
        """揀一個由 invoice post 出嚟嘅 entry → 刪走 → 用而家 default account 重 post"""
        sel = self.pf_txn_tree.selection()
        if not sel:
            messagebox.showinfo("揀一個", "請揀一個 entry")
            return
        from personal_finance import db as pfdb
        from personal_finance import posting as pfpost
        import database as invdb

        ok = 0
        skipped = 0
        for entry_id_str in sel:
            entry_id = int(entry_id_str)
            entry = pfdb.get_entry(entry_id)
            if not entry:
                continue
            invoice_id = entry.get("invoice_id")
            if not invoice_id:
                skipped += 1
                continue
            # 攞原 invoice
            inv = invdb.get_invoice(invoice_id)
            if not inv:
                skipped += 1
                continue
            # 刪舊 entry，重 post
            pfdb.delete_entry(entry_id)
            try:
                new_id = pfpost.post_invoice(inv)
                self.log(f"🔁 Repost invoice #{invoice_id} → entry #{new_id}")
                ok += 1
            except Exception as e:
                self.log(f"⚠️ Repost 失敗 #{invoice_id}：{e}")
        self._pf_refresh_all()
        if skipped:
            messagebox.showinfo("完成",
                f"✅ Repost {ok} 個\n⚠️ Skip {skipped}（manual entry 唔可以 repost）")
        else:
            messagebox.showinfo("完成", f"✅ Repost {ok} 個 entries")

    # ------------------------------ Accounting App ------------------------------
    def _refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        invoices = database.list_all()
        filter_type = self.filter_var.get() if hasattr(self, "filter_var") else "全部"
        if filter_type != "全部":
            invoices = [i for i in invoices if i.get("expense_type") == filter_type]

        for inv in invoices:
            etype = inv.get("expense_type") or "私人"
            icon = EXPENSE_ICONS.get(etype, "👤")
            reimbursed_str = "✅" if inv.get("reimbursed") else ("⏳" if etype == "公司報銷" else "—")
            self.tree.insert("", tk.END, iid=str(inv["id"]), values=(
                inv["id"],
                icon,
                inv.get("purchase_date") or "—",
                inv.get("store_name") or "—",
                inv.get("category") or "—",
                f"{inv.get('total_amount') or 0:.2f}",
                inv.get("currency") or "—",
                reimbursed_str,
            ))

        # === Dashboard KPI ===
        self.kpi_count_var.set(str(database.count()))
        total = database.grand_total()
        cnt = database.count()
        self.kpi_total_var.set(f"{total:,.2f}")
        self.kpi_avg_var.set(f"{(total/cnt if cnt else 0):,.2f}")

        # Top 5 expenses
        self.top_expenses_widget.config(state=tk.NORMAL)
        self.top_expenses_widget.delete("1.0", tk.END)
        top5 = database.top_n_by_amount(5)
        if top5:
            for i, inv in enumerate(top5, 1):
                self.top_expenses_widget.insert(
                    tk.END,
                    f"{i}. {inv.get('purchase_date') or '—'}  "
                    f"{inv.get('store_name') or '—'}  "
                    f"［{inv.get('category') or '—'}］  "
                    f"${inv.get('total_amount') or 0:,.2f} {inv.get('currency') or ''}\n"
                )
        else:
            self.top_expenses_widget.insert(tk.END, "(暫無資料)")
        self.top_expenses_widget.config(state=tk.DISABLED)

        # Top 5 categories
        self.top_cats_widget.config(state=tk.NORMAL)
        self.top_cats_widget.delete("1.0", tk.END)
        top_cats = database.top_n_categories(5)
        total_all = sum(t for _, t in database.category_totals()) or 1
        if top_cats:
            for i, (cat, amt) in enumerate(top_cats, 1):
                pct = amt / total_all * 100
                self.top_cats_widget.insert(
                    tk.END,
                    f"{i}. {cat:<10}  ${amt:>12,.2f}   ({pct:5.1f}%)\n"
                )
        else:
            self.top_cats_widget.insert(tk.END, "(暫無資料)")
        self.top_cats_widget.config(state=tk.DISABLED)

        # === 報銷 Tab ===
        summary = database.reimbursement_summary()
        self.reimb_pending_var.set(f"{summary['company_pending']:,.2f}")
        self.reimb_done_var.set(f"{summary['company_reimbursed']:,.2f}")
        self.reimb_tax_var.set(f"{summary['tax_deductible_total']:,.2f}")
        self.reimb_personal_var.set(f"{summary['personal_total']:,.2f}")

        # Pending list
        self.pending_reimb_widget.config(state=tk.NORMAL)
        self.pending_reimb_widget.delete("1.0", tk.END)
        all_company = database.by_expense_type("公司報銷")
        pending = [i for i in all_company if not i.get("reimbursed")]
        if pending:
            for inv in pending:
                self.pending_reimb_widget.insert(
                    tk.END,
                    f"⏳ #{inv['id']:>3}  {inv.get('purchase_date') or '?':<12} "
                    f"{inv.get('store_name') or '?':<22}  "
                    f"[{inv.get('category') or '?'}]  "
                    f"${inv.get('total_amount') or 0:>10,.2f} {inv.get('currency') or ''}\n"
                )
        else:
            self.pending_reimb_widget.insert(tk.END, "🎉 冇待報銷單據！")
        self.pending_reimb_widget.config(state=tk.DISABLED)

    def _on_tree_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        try:
            invoice_id = int(sel[0])
        except ValueError:
            return
        inv = database.get_invoice(invoice_id)
        if not inv:
            return
        self._show_preview(inv)

    def _show_preview(self, inv: dict):
        """喺右邊顯示張單嘅原圖"""
        src = inv.get("source_file")
        self.preview_title_var.set(f"📷 單據 #{inv['id']} 預覽")
        store = inv.get("store_name") or "?"
        date = inv.get("purchase_date") or "?"
        amt = inv.get("total_amount") or 0
        etype = inv.get("expense_type") or "私人"
        info = (f"{EXPENSE_ICONS.get(etype, '')} {etype}  |  "
                f"{date}  |  {store}  |  ${amt:,.2f}")
        self.preview_info_var.set(info)

        if not src or not Path(src).exists():
            self.preview_label.config(image="", text="(找唔到原檔)", fg=MUTED)
            self.preview_image = None
            self._current_preview_path = None
            return

        self._current_preview_path = Path(src)
        self._load_preview_image()

    def _load_preview_image(self):
        """根據 preview_label 嘅當前 size 縮圖"""
        path = self._current_preview_path
        if not path or not path.exists():
            return
        ext = path.suffix.lower()
        try:
            if ext in IMAGE_EXTENSIONS:
                img = Image.open(path)
                try:
                    from PIL import ImageOps
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass
            elif ext in PDF_EXTENSIONS:
                try:
                    from pdf_utils import pdf_first_page_to_image
                    img = pdf_first_page_to_image(path, dpi=120)
                except Exception as e:
                    self.preview_label.config(
                        image="", fg=WARNING,
                        text=f"PDF 預覽失敗\n{e}")
                    self.preview_image = None
                    return
            else:
                self.preview_label.config(image="", text=f"唔識預覽 {ext}", fg=MUTED)
                return

            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")

            # 縮放至 fit preview_label
            w = max(self.preview_label.winfo_width() - 20, 200)
            h = max(self.preview_label.winfo_height() - 20, 200)
            img.thumbnail((w, h), Image.LANCZOS)

            self.preview_image = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self.preview_image, text="")
        except Exception as e:
            self.preview_label.config(image="", text=f"預覽失敗：{e}", fg=ERROR)
            self.preview_image = None

    def _on_preview_resize(self, _event):
        # 拖大個 pane 就 reload
        if self._current_preview_path:
            self._load_preview_image()

    def edit_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("揀一個", "請先喺表入面揀一行。")
            return
        invoice_id = int(sel[0])
        inv = database.get_invoice(invoice_id)
        if not inv:
            return
        EditDialog(self.root, self, inv)

    def toggle_reimbursed_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("揀一個", "請先喺表入面揀一行。")
            return
        invoice_id = int(sel[0])
        inv = database.get_invoice(invoice_id)
        new_state = database.toggle_reimbursed(invoice_id)
        self._refresh_table()
        self.log(f"{'✅' if new_state else '⏳'} #{invoice_id} "
                 f"{'已標記報銷' if new_state else '取消報銷標記'}")

        # AR workflow: 由 ⏳ → ✅ 時，trigger 收款 dialog
        if (new_state and inv and inv.get("expense_type") == "公司報銷"):
            self._trigger_ar_receive_if_needed(invoice_id)
        try:
            self._pf_refresh_all()
        except Exception:
            pass

    def _trigger_ar_receive_if_needed(self, invoice_id: int):
        """揀張單 → check AR entry → 彈收款 dialog。

        如果 AR entry 仲未 post（用咗舊邏輯 / 未 post），
        自動 post AR entry 先，然後彈收款 dialog。
        """
        from personal_finance import db as pfdb
        from personal_finance import posting as pfpost

        inv = database.get_invoice(invoice_id)
        if not inv:
            return

        # 揾 AR entry
        entries = pfdb.list_entries(invoice_id=invoice_id, limit=10)
        ar_entry = None
        for e in entries:
            full = pfdb.get_entry(e["entry_id"])
            for line in full["lines"]:
                if line["account_code"] == "AR_REIMBURSE":
                    ar_entry = full
                    break
            if ar_entry:
                break

        if not ar_entry:
            # 冇 AR entry — 提供自動 fix
            if messagebox.askyesno(
                "未 post 入 AR ledger",
                f"張單 #{invoice_id} 仲未 post 做 AR entry。\n"
                f"（可能用咗舊邏輯 / 未入賬）\n\n"
                f"自動重 post + 彈收款 dialog？"):
                # 清舊 entries (if any with old logic)
                for e in entries:
                    pfdb.delete_entry(e["entry_id"])
                # Post fresh AR entry
                try:
                    new_entry_id = pfpost.post_invoice(inv)
                    self.log(f"💼 重 post 公司報銷 → entry #{new_entry_id}")
                except Exception as e:
                    messagebox.showerror("Post 失敗", str(e))
                    return

        # 而家肯定有 AR entry，彈收款 dialog
        ARReceiveDialog(self.root, self, invoice_id)

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("揀一個", "請先喺表入面揀一行。")
            return
        invoice_id = int(sel[0])
        if messagebox.askyesno("確認", f"確定刪除單據 #{invoice_id}？（檔案唔會刪）"):
            database.delete_invoice(invoice_id)
            self._refresh_table()
            self.preview_label.config(image="", text="(冇預覽)", fg=MUTED)
            self.preview_image = None
            self._current_preview_path = None
            self.log(f"🗑️ 已刪除 #{invoice_id}")

    # ------------------------------ Queue ------------------------------
    def q(self, kind: str, payload):
        self.msg_queue.put((kind, payload))

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                self._handle(kind, payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _handle(self, kind: str, payload):
        if kind == "status":
            self.status_var.set(payload)
        elif kind == "progress":
            self.progress["value"] = payload
        elif kind == "log":
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_widget.insert(tk.END, f"[{ts}] {payload}\n")
            self.log_widget.see(tk.END)
        elif kind == "file_label":
            self.file_label_var.set(payload)
        elif kind == "done":
            self.is_processing = False
            self.start_btn.config(state=tk.NORMAL)
            self._refresh_table()
            # 提取完亦 refresh 個人記賬 tab（auto-posted entries 即時顯示）
            try:
                self._pf_refresh_all()
            except Exception:
                pass
        elif kind == "error":
            self.is_processing = False
            self.start_btn.config(state=tk.NORMAL)
            self._refresh_table()
            try:
                self._pf_refresh_all()
            except Exception:
                pass
            messagebox.showerror("處理失敗", str(payload))

    def log(self, msg: str):
        self.q("log", msg)


# ========================= Edit Dialog =========================

class EditDialog(tk.Toplevel):
    def __init__(self, parent, app: InvoiceExtractApp, invoice: dict):
        super().__init__(parent)
        self.app = app
        self.invoice = invoice
        self.title(f"✏️ 編輯單據 #{invoice['id']}")
        self.geometry("560x620")
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text=f"✏️ 編輯單據 #{invoice['id']}",
                  style="Title.TLabel").pack(pady=(15, 10), padx=20, anchor=tk.W)

        form = ttk.Frame(self, padding=(20, 5))
        form.pack(fill=tk.BOTH, expand=True)

        self.fields = {}

        def add_field(row, label, key, widget_kind="entry", values=None):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky=tk.W, pady=4)
            var = tk.StringVar(value=str(invoice.get(key) or ""))
            if widget_kind == "combo":
                w = ttk.Combobox(form, textvariable=var, values=values, width=35, state="readonly")
            else:
                w = ttk.Entry(form, textvariable=var, width=38)
            w.grid(row=row, column=1, sticky=tk.EW, pady=4, padx=(8, 0))
            self.fields[key] = var

        add_field(0, "購買日期 (YYYY-MM-DD)", "purchase_date")
        add_field(1, "商店名稱", "store_name")
        add_field(2, "類別", "category", "combo", CATEGORIES)
        add_field(3, "總金額", "total_amount")
        add_field(4, "幣值", "currency")
        add_field(5, "付款方式", "payment_method")
        add_field(6, "稅項", "tax")
        add_field(7, "單號", "receipt_number")
        add_field(8, "備註", "notes")

        # === 報銷標記 section ===
        ttk.Label(form, text="").grid(row=9, column=0, pady=(8, 0))  # spacer
        ttk.Label(form, text="🏷️ 支出類型：",
                  style="Section.TLabel").grid(row=10, column=0, sticky=tk.W, pady=(8, 4))

        self.expense_type_var = tk.StringVar(value=invoice.get("expense_type") or "私人")
        ttk.Combobox(form, textvariable=self.expense_type_var, values=EXPENSE_TYPES,
                     state="readonly", width=35).grid(row=10, column=1, sticky=tk.EW,
                                                       pady=(8, 4), padx=(8, 0))

        self.reimbursed_var = tk.BooleanVar(value=bool(invoice.get("reimbursed")))
        ttk.Checkbutton(form, text="✅ 已報銷 / 已收到報銷",
                        variable=self.reimbursed_var).grid(row=11, column=1,
                                                            sticky=tk.W, pady=4, padx=(8, 0))

        form.columnconfigure(1, weight=1)

        # Items preview
        ttk.Label(form, text="產品清單：").grid(row=12, column=0, sticky=tk.NW, pady=(10, 4))
        items_txt = scrolledtext.ScrolledText(form, height=6, bg=CARD, fg=FG,
                                              font=("Microsoft JhengHei UI", 9),
                                              relief=tk.FLAT, padx=8, pady=6)
        items_txt.grid(row=12, column=1, sticky=tk.EW, pady=(10, 4), padx=(8, 0))
        items = invoice.get("items") or []
        if items:
            for it in items:
                items_txt.insert(tk.END,
                    f"• {it.get('name', '?')}  "
                    f"x{it.get('quantity', '?')}  "
                    f"${it.get('price', '?')}\n")
        else:
            items_txt.insert(tk.END, "(冇)")
        items_txt.config(state=tk.DISABLED)

        btn_frame = ttk.Frame(self, padding=(20, 15))
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="💾 儲存",
                   style="Accent.TButton", command=self.do_save).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=(8, 0))

    def do_save(self):
        data = dict(self.invoice)
        for key, var in self.fields.items():
            val = var.get().strip()
            if key in ("total_amount", "tax"):
                try:
                    val = float(val) if val else None
                except ValueError:
                    messagebox.showerror("格式錯誤", f"{key} 必須係數字", parent=self)
                    return
            data[key] = val if val else None
        data["expense_type"] = self.expense_type_var.get()
        data["reimbursed"] = self.reimbursed_var.get()

        was_reimbursed = bool(self.invoice.get("reimbursed"))
        now_reimbursed = bool(data["reimbursed"])
        is_company = data["expense_type"] == "公司報銷"

        try:
            database.update_invoice(self.invoice["id"], data)
            self.app.log(f"✏️ 已更新 #{self.invoice['id']}")
            self.app._refresh_table()
            self.destroy()

            # AR receive flow：⏳ → ✅ + 公司報銷 + 有 AR entry
            if (not was_reimbursed and now_reimbursed and is_company):
                self.app._trigger_ar_receive_if_needed(self.invoice["id"])
            try:
                self.app._pf_refresh_all()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("儲存失敗", str(e), parent=self)


def main():
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = InvoiceExtractApp(root)

    def _on_close():
        # 關 GUI 嗰陣埋葬 sub-app
        try:
            from accounting_launcher import get_launcher
            launcher = get_launcher()
            if launcher.is_running:
                launcher.stop()
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)
    root.mainloop()


# ========================= Personal Finance Dialogs =========================

class PFBudgetDialog(tk.Toplevel):
    """設 / 改 budget"""
    def __init__(self, parent, app, period):
        super().__init__(parent)
        self.app = app
        self.period = period
        self.title(f"🎯 設 Budget – {period}")
        self.geometry("500x500")
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text=f"🎯 Budget for {period}",
                  style="Title.TLabel").pack(pady=(15, 5), padx=20, anchor=tk.W)

        from personal_finance import db as pfdb
        existing = {b["account_code"]: b["amount"]
                     for b in pfdb.list_budgets(period=period)}
        cats = pfdb.list_accounts(account_type="expense")

        form = ttk.Frame(self, padding=(20, 10))
        form.pack(fill=tk.BOTH, expand=True)

        # Scrollable
        canvas = tk.Canvas(form, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(form, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.vars = {}
        for i, c in enumerate(cats):
            ttk.Label(inner, text=f"{c['icon'] or ''} {c['name']}",
                      width=14).grid(row=i, column=0, sticky=tk.W, pady=2, padx=(5, 0))
            v = tk.StringVar(value=str(existing.get(c["code"], "")))
            ttk.Entry(inner, textvariable=v, width=15).grid(
                row=i, column=1, padx=(8, 5), pady=2)
            self.vars[c["code"]] = v

        btn = ttk.Frame(self, padding=(20, 10))
        btn.pack(fill=tk.X)
        ttk.Button(btn, text="💾 儲存", style="Accent.TButton",
                   command=self._save).pack(side=tk.LEFT)
        ttk.Button(btn, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=(8, 0))

    def _save(self):
        from personal_finance import db as pfdb
        n = 0
        for code, var in self.vars.items():
            val = var.get().strip()
            if val:
                try:
                    amount = float(val)
                    pfdb.set_budget(code, self.period, amount)
                    n += 1
                except ValueError:
                    continue
        self.app._pf_refresh_all()
        self.destroy()
        messagebox.showinfo("已存", f"已設 {n} 個 budget")


class PFAccountDialog(tk.Toplevel):
    def __init__(self, parent, app, account_code: str | None):
        super().__init__(parent)
        self.app = app
        self.account_code = account_code
        self.title("✏️ Account" if account_code else "➕ 新 Account")
        self.geometry("450x420")
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        from personal_finance import db as pfdb
        existing = pfdb.get_account(account_code) if account_code else None

        ttk.Label(self, text=("✏️ 編輯" if existing else "➕ 新增"),
                  style="Title.TLabel").pack(pady=(15, 5), padx=20, anchor=tk.W)

        form = ttk.Frame(self, padding=(20, 10))
        form.pack(fill=tk.BOTH, expand=True)

        def add(row, label, key, default="", widget="entry", values=None):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky=tk.W, pady=4)
            var = tk.StringVar(value=str(existing[key] if existing and existing.get(key) is not None else default))
            if widget == "combo":
                w = ttk.Combobox(form, textvariable=var, values=values,
                                  state="readonly", width=28)
            else:
                w = ttk.Entry(form, textvariable=var, width=30)
                if existing and key == "code":
                    w.config(state="disabled")
            w.grid(row=row, column=1, sticky=tk.EW, padx=(8, 0), pady=4)
            return var

        self.code_var = add(0, "Code (英文/數字)", "code")
        self.name_var = add(1, "Name", "name")
        from personal_finance.db import ACCOUNT_TYPES
        self.type_var = add(2, "Type", "account_type", "asset",
                             "combo", list(ACCOUNT_TYPES.keys()))
        self.ob_var = add(3, "Opening Balance", "opening_balance", "0")
        self.curr_var = add(4, "Currency", "currency", "HKD")
        self.icon_var = add(5, "Icon (emoji)", "icon", "")
        self.color_var = add(6, "Color (hex)", "color", "")
        self.sort_var = add(7, "Sort Order", "sort_order", "0")

        self.active_var = tk.BooleanVar(value=bool(existing["is_active"]) if existing else True)
        ttk.Checkbutton(form, text="Active",
                         variable=self.active_var).grid(row=8, column=1,
                                                         sticky=tk.W, pady=4, padx=(8, 0))

        form.columnconfigure(1, weight=1)

        btn = ttk.Frame(self, padding=(20, 10))
        btn.pack(fill=tk.X)
        ttk.Button(btn, text="💾 儲存", style="Accent.TButton",
                   command=self._save).pack(side=tk.LEFT)
        if existing and self.account_code != "CASH":
            ttk.Button(btn, text="🗑️ 刪",
                       command=self._delete).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(btn, text="取消",
                   command=self.destroy).pack(side=tk.RIGHT)

    def _save(self):
        from personal_finance import db as pfdb
        try:
            pfdb.upsert_account(
                code=self.code_var.get().strip().upper(),
                name=self.name_var.get().strip(),
                account_type=self.type_var.get(),
                opening_balance=float(self.ob_var.get() or 0),
                currency=self.curr_var.get().strip() or "HKD",
                is_active=self.active_var.get(),
                sort_order=int(self.sort_var.get() or 0),
                icon=self.icon_var.get().strip() or None,
                color=self.color_var.get().strip() or None,
            )
            self.app._pf_refresh_all()
            self.destroy()
        except Exception as e:
            messagebox.showerror("失敗", str(e), parent=self)

    def _delete(self):
        if not messagebox.askyesno("確認", f"刪 account {self.account_code}？",
                                     parent=self):
            return
        from personal_finance import db as pfdb
        try:
            pfdb.delete_account(self.account_code)
            self.app._pf_refresh_all()
            self.destroy()
        except Exception as e:
            messagebox.showerror("失敗", str(e), parent=self)


class PFProjectDialog(tk.Toplevel):
    def __init__(self, parent, app, project_id):
        super().__init__(parent)
        self.app = app
        self.project_id = project_id
        self.title("✏️ Project" if project_id else "➕ 新 Project")
        self.geometry("450x380")
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        from personal_finance import db as pfdb
        existing = pfdb.get_project(project_id) if project_id else None

        ttk.Label(self, text=("✏️ 編輯" if existing else "➕ 新 Project"),
                  style="Title.TLabel").pack(pady=(15, 5), padx=20, anchor=tk.W)

        form = ttk.Frame(self, padding=(20, 10))
        form.pack(fill=tk.BOTH, expand=True)

        def add(row, label, key, default=""):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky=tk.W, pady=4)
            var = tk.StringVar(value=str(existing[key] if existing and existing.get(key) is not None else default))
            ttk.Entry(form, textvariable=var, width=30).grid(
                row=row, column=1, sticky=tk.EW, padx=(8, 0), pady=4)
            return var

        self.name_var = add(0, "Name", "name", "")
        self.desc_var = add(1, "Description", "description", "")
        self.start_var = add(2, "Start Date (YYYY-MM-DD)", "start_date", "")
        self.end_var = add(3, "End Date (YYYY-MM-DD)", "end_date", "")
        self.budget_var = add(4, "Total Budget", "total_budget", "")
        self.icon_var = add(5, "Icon (emoji)", "icon", "🎯")

        from personal_finance.db import PROJECT_STATUSES
        ttk.Label(form, text="Status").grid(row=6, column=0, sticky=tk.W, pady=4)
        self.status_var = tk.StringVar(
            value=(existing["status"] if existing else "active"))
        ttk.Combobox(form, textvariable=self.status_var, values=PROJECT_STATUSES,
                     state="readonly", width=28).grid(
                         row=6, column=1, sticky=tk.EW, padx=(8, 0), pady=4)

        form.columnconfigure(1, weight=1)

        btn = ttk.Frame(self, padding=(20, 10))
        btn.pack(fill=tk.X)
        ttk.Button(btn, text="💾 儲存", style="Accent.TButton",
                   command=self._save).pack(side=tk.LEFT)
        ttk.Button(btn, text="取消",
                   command=self.destroy).pack(side=tk.RIGHT)

    def _save(self):
        from personal_finance import db as pfdb
        try:
            data = {
                "name": self.name_var.get().strip(),
                "description": self.desc_var.get().strip() or None,
                "start_date": self.start_var.get().strip() or None,
                "end_date": self.end_var.get().strip() or None,
                "total_budget": float(self.budget_var.get()) if self.budget_var.get().strip() else None,
                "icon": self.icon_var.get().strip() or None,
                "status": self.status_var.get(),
            }
            if not data["name"]:
                messagebox.showwarning("缺", "Name 一定要填", parent=self)
                return
            if self.project_id:
                pfdb.update_project(self.project_id, **data)
            else:
                pfdb.create_project(**data)
            self.app._pf_refresh_all()
            self.destroy()
        except Exception as e:
            messagebox.showerror("失敗", str(e), parent=self)


class PFManualEntryDialog(tk.Toplevel):
    """加 manual journal entry（例如：salary、賬戶轉移、現金提款）"""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("➕ Manual Entry")
        self.geometry("520x420")
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="➕ Manual Journal Entry",
                  style="Title.TLabel").pack(pady=(15, 5), padx=20, anchor=tk.W)
        ttk.Label(self,
                  text="預設模板：揀類型 → 自動 fill",
                  style="Subtitle.TLabel").pack(padx=20, anchor=tk.W)

        form = ttk.Frame(self, padding=(20, 10))
        form.pack(fill=tk.BOTH, expand=True)

        from personal_finance import db as pfdb
        accs = pfdb.list_accounts(active_only=True)
        asset_opts = [f"{a['code']} ({a['name']})"
                       for a in accs if a["account_type"] == "asset"]
        liab_opts = [f"{a['code']} ({a['name']})"
                      for a in accs if a["account_type"] == "liability"]
        income_opts = [f"{a['code']} ({a['name']})"
                        for a in accs if a["account_type"] == "income"]
        all_opts = [f"{a['code']} ({a['name']})" for a in accs]

        # Template
        ttk.Label(form, text="類型：").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.template_var = tk.StringVar(value="收入 (e.g. salary)")
        templates = ["收入 (e.g. salary)", "賬戶轉移", "信用卡找數", "其他"]
        ttk.Combobox(form, textvariable=self.template_var, values=templates,
                     state="readonly", width=30).grid(
                         row=0, column=1, sticky=tk.EW, pady=4, padx=(8, 0))

        from datetime import date
        ttk.Label(form, text="日期：").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.date_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(form, textvariable=self.date_var, width=32).grid(
            row=1, column=1, sticky=tk.EW, pady=4, padx=(8, 0))

        ttk.Label(form, text="金額：").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.amount_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.amount_var, width=32).grid(
            row=2, column=1, sticky=tk.EW, pady=4, padx=(8, 0))

        ttk.Label(form, text="From / Dr：").grid(row=3, column=0, sticky=tk.W, pady=4)
        self.from_var = tk.StringVar()
        ttk.Combobox(form, textvariable=self.from_var, values=all_opts,
                     width=30).grid(row=3, column=1, sticky=tk.EW, pady=4, padx=(8, 0))

        ttk.Label(form, text="To / Cr：").grid(row=4, column=0, sticky=tk.W, pady=4)
        self.to_var = tk.StringVar()
        ttk.Combobox(form, textvariable=self.to_var, values=all_opts,
                     width=30).grid(row=4, column=1, sticky=tk.EW, pady=4, padx=(8, 0))

        ttk.Label(form, text="說明：").grid(row=5, column=0, sticky=tk.W, pady=4)
        self.desc_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.desc_var, width=32).grid(
            row=5, column=1, sticky=tk.EW, pady=4, padx=(8, 0))

        form.columnconfigure(1, weight=1)

        btn = ttk.Frame(self, padding=(20, 10))
        btn.pack(fill=tk.X)
        ttk.Button(btn, text="💾 儲存", style="Accent.TButton",
                   command=self._save).pack(side=tk.LEFT)
        ttk.Button(btn, text="取消",
                   command=self.destroy).pack(side=tk.RIGHT)

    def _save(self):
        from personal_finance import db as pfdb
        try:
            amount = float(self.amount_var.get())
            from_code = self.from_var.get().split(" ")[0].strip()
            to_code = self.to_var.get().split(" ")[0].strip()
            if not from_code or not to_code:
                messagebox.showwarning("缺", "From 同 To 都要揀", parent=self)
                return
            pfdb.create_entry(
                entry_date=self.date_var.get(),
                description=self.desc_var.get() or self.template_var.get(),
                lines=[
                    {"account_code": from_code, "debit": amount, "credit": 0},
                    {"account_code": to_code, "debit": 0, "credit": amount},
                ],
            )
            self.app._pf_refresh_all()
            self.destroy()
        except Exception as e:
            messagebox.showerror("失敗", str(e), parent=self)


class PFAliasDialog(tk.Toplevel):
    """管理 payment_method → account 嘅自訂 alias"""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("🔗 Payment Method Aliases")
        self.geometry("700x500")
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="🔗 Payment Method 對應 Account",
                  style="Title.TLabel").pack(pady=(15, 5), padx=20, anchor=tk.W)
        ttk.Label(self,
                  text="設定 keyword → account：當 invoice 有 payment_method "
                       "match keyword（不分大小寫）時自動 post 入呢個 account。\n"
                       "（內置 25+ keyword 已 work，呢度淨係加你嘅自訂）",
                  style="Subtitle.TLabel", wraplength=650).pack(
                      padx=20, anchor=tk.W, pady=(0, 10))

        # Add new
        addf = ttk.LabelFrame(self, text=" 加新 alias ", padding=10)
        addf.pack(fill=tk.X, padx=20, pady=4)
        ttk.Label(addf, text="Keyword：").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.kw_var = tk.StringVar()
        ttk.Entry(addf, textvariable=self.kw_var, width=25).grid(
            row=0, column=1, sticky=tk.EW, padx=(8, 0), pady=2)

        ttk.Label(addf, text="→ Account：").grid(row=1, column=0, sticky=tk.W, pady=2)
        from personal_finance import db as pfdb
        accs = [a for a in pfdb.list_accounts()
                if a["account_type"] in ("asset", "liability")]
        opts = [f"{a['code']} ({a['name']})" for a in accs]
        self._opt_map = {opt: a["code"] for opt, a in zip(opts, accs)}
        self.acc_var = tk.StringVar(value=opts[0] if opts else "")
        ttk.Combobox(addf, textvariable=self.acc_var, values=opts,
                     state="readonly", width=24).grid(
                         row=1, column=1, sticky=tk.EW, padx=(8, 0), pady=2)

        ttk.Label(addf, text="Notes：").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.notes_var = tk.StringVar()
        ttk.Entry(addf, textvariable=self.notes_var, width=25).grid(
            row=2, column=1, sticky=tk.EW, padx=(8, 0), pady=2)

        ttk.Button(addf, text="➕ 加", style="Accent.TButton",
                   command=self._add).grid(row=3, column=1,
                                            sticky=tk.W, padx=(8, 0), pady=(8, 0))
        addf.columnconfigure(1, weight=1)

        # Existing list
        listf = ttk.LabelFrame(self, text=" 已有 aliases ", padding=10)
        listf.pack(fill=tk.BOTH, expand=True, padx=20, pady=4)

        cols = ("kw", "acc", "notes")
        col_labels = {"kw": "Keyword", "acc": "Account", "notes": "Notes"}
        widths = {"kw": 200, "acc": 130, "notes": 250}
        tree_frame = ttk.Frame(listf)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=col_labels[c])
            self.tree.column(c, width=widths[c])
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        # 雙擊 row → 載入入 edit 區
        self.tree.bind("<Double-1>", lambda e: self._edit_selected())

        # 底部 button row
        btnrow = ttk.Frame(listf)
        btnrow.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btnrow, text="🗑️ 刪揀選",
                   command=self._del).pack(side=tk.LEFT)
        ttk.Button(btnrow, text="🔄 載入內置 25 個",
                   command=self._seed_defaults).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(btnrow, text="⚠️ Reset 全部做 default",
                   command=self._reset_defaults).pack(side=tk.RIGHT)

        self._refresh()

    def _refresh(self):
        from personal_finance import db as pfdb
        for item in self.tree.get_children():
            self.tree.delete(item)
        for a in pfdb.list_payment_aliases():
            self.tree.insert("", tk.END, iid=str(a["alias_id"]),
                              values=(a["keyword"], a["account_code"],
                                       a.get("notes") or ""))

    def _edit_selected(self):
        """雙擊 row → 載入入上面 form，按「加」就 update"""
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        keyword, account_code, notes = vals[0], vals[1], vals[2]
        self.kw_var.set(keyword)
        self.notes_var.set(notes)
        # 揾返 dropdown option
        for opt, code in self._opt_map.items():
            if code == account_code:
                self.acc_var.set(opt)
                break

    def _add(self):
        kw = self.kw_var.get().strip()
        acc = self._opt_map.get(self.acc_var.get())
        if not kw or not acc:
            messagebox.showwarning("缺", "Keyword 同 Account 都要填", parent=self)
            return
        from personal_finance import db as pfdb
        pfdb.add_payment_alias(kw, acc, self.notes_var.get() or None)
        self.kw_var.set("")
        self.notes_var.set("")
        self._refresh()
        self.app.log(f"🔗 加 alias：{kw} → {acc}")

    def _del(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("揀一個", "揀至少一個 alias", parent=self)
            return
        if not messagebox.askyesno("確認", f"刪 {len(sel)} 個 alias？",
                                     parent=self):
            return
        from personal_finance import db as pfdb
        for s in sel:
            pfdb.delete_payment_alias(int(s))
        self._refresh()

    def _seed_defaults(self):
        """載入內置 25 個 default（保留現有 user-added，唔覆寫）"""
        from personal_finance import seed as pfseed
        stats = pfseed.seed_payment_aliases(force=False)
        self._refresh()
        messagebox.showinfo(
            "完成",
            f"加咗 {stats['created']} 個 default alias"
            f"\n（跳過 {stats['skipped']} 個已存在嘅）",
            parent=self)

    def _reset_defaults(self):
        """完全刪曬 + 重 seed default（會 lose user-added）"""
        if not messagebox.askyesno(
            "⚠️ 確認 reset",
            "會刪曬全部 alias（包括你自訂嘅），重 seed 內置 25 個 default。\n"
            "確定？",
            parent=self):
            return
        from personal_finance import seed as pfseed
        stats = pfseed.reset_payment_aliases_to_defaults()
        self._refresh()
        messagebox.showinfo("Reset 完成",
            f"已 reset，加 {stats['created']} 個 default alias",
            parent=self)


class PFFxDialog(tk.Toplevel):
    """設 / 改匯率"""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("💱 Exchange Rates")
        self.geometry("600x450")
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="💱 設定匯率到 HKD",
                  style="Title.TLabel").pack(pady=(15, 5), padx=20, anchor=tk.W)
        ttk.Label(self,
                  text="設定外幣 → HKD 匯率。Multi-currency entries 會自動 convert "
                       "用最新 rate。",
                  style="Subtitle.TLabel", wraplength=550).pack(
                      padx=20, anchor=tk.W, pady=(0, 10))

        # Add new
        addf = ttk.LabelFrame(self, text=" 加 / 改匯率 ", padding=10)
        addf.pack(fill=tk.X, padx=20, pady=4)
        ttk.Label(addf, text="Currency：").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.cur_var = tk.StringVar()
        ttk.Combobox(addf, textvariable=self.cur_var,
                     values=["USD", "JPY", "CNY", "EUR", "GBP", "TWD",
                              "KRW", "SGD", "AUD", "THB"],
                     width=10).grid(row=0, column=1, sticky=tk.W, padx=(8, 0), pady=2)

        ttk.Label(addf, text="1 unit = ? HKD：").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.rate_var = tk.StringVar()
        ttk.Entry(addf, textvariable=self.rate_var, width=12).grid(
            row=1, column=1, sticky=tk.W, padx=(8, 0), pady=2)

        from datetime import date as _date
        ttk.Label(addf, text="As-of date：").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.date_var = tk.StringVar(value=_date.today().isoformat())
        ttk.Entry(addf, textvariable=self.date_var, width=12).grid(
            row=2, column=1, sticky=tk.W, padx=(8, 0), pady=2)

        ttk.Button(addf, text="💾 儲存", style="Accent.TButton",
                   command=self._save).grid(row=3, column=1,
                                              sticky=tk.W, padx=(8, 0), pady=(8, 0))

        # Existing list
        listf = ttk.LabelFrame(self, text=" 最新匯率 ", padding=10)
        listf.pack(fill=tk.BOTH, expand=True, padx=20, pady=4)

        cols = ("cur", "rate", "date", "notes")
        col_labels = {"cur": "Currency", "rate": "Rate (→ HKD)",
                       "date": "As-of", "notes": "Notes"}
        widths = {"cur": 80, "rate": 130, "date": 100, "notes": 180}
        tree_frame = ttk.Frame(listf)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=col_labels[c])
            self.tree.column(c, width=widths[c], anchor=tk.CENTER)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._refresh()

    def _refresh(self):
        from personal_finance import db as pfdb
        for item in self.tree.get_children():
            self.tree.delete(item)
        for fx in pfdb.list_fx_rates():
            self.tree.insert("", tk.END, iid=str(fx["fx_id"]), values=(
                fx["currency"],
                f"{fx['rate_to_hkd']:.4f}",
                fx["as_of_date"],
                fx.get("notes") or ""))

    def _save(self):
        cur = self.cur_var.get().strip().upper()
        if not cur:
            return
        try:
            rate = float(self.rate_var.get())
        except ValueError:
            messagebox.showwarning("缺", "Rate 必須係數字", parent=self)
            return
        from personal_finance import db as pfdb
        pfdb.set_fx_rate(cur, rate, self.date_var.get())
        self._refresh()
        self.app.log(f"💱 {cur} → {rate} HKD")


class PFPeriodDialog(tk.Toplevel):
    """期間管理：鎖定 / 重開月份"""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("🔒 期間管理")
        self.geometry("550x500")
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="🔒 期間管理",
                  style="Title.TLabel").pack(pady=(15, 5), padx=20, anchor=tk.W)
        ttk.Label(self,
                  text="鎖定後該月份嘅 journal entries 唔可以新增 / 刪 / 改。\n"
                       "用喺月底 close book 之後，防誤改舊 data。",
                  style="Subtitle.TLabel", wraplength=500).pack(
                      padx=20, anchor=tk.W, pady=(0, 10))

        # Add new
        addf = ttk.LabelFrame(self, text=" 鎖定新月份 ", padding=10)
        addf.pack(fill=tk.X, padx=20, pady=4)

        from datetime import date as _d
        ttk.Label(addf, text="月份 (YYYY-MM)：").grid(row=0, column=0, sticky=tk.W, pady=2)
        # 預設上個月
        today = _d.today()
        last_m = today.replace(day=1) - __import__("datetime").timedelta(days=1)
        self.period_var = tk.StringVar(value=last_m.strftime("%Y-%m"))
        ttk.Entry(addf, textvariable=self.period_var, width=12).grid(
            row=0, column=1, sticky=tk.W, padx=(8, 0), pady=2)

        ttk.Label(addf, text="Notes：").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.notes_var = tk.StringVar()
        ttk.Entry(addf, textvariable=self.notes_var, width=30).grid(
            row=1, column=1, sticky=tk.EW, padx=(8, 0), pady=2)

        ttk.Button(addf, text="🔒 鎖定", style="Accent.TButton",
                   command=self._close).grid(row=2, column=1,
                                              sticky=tk.W, padx=(8, 0), pady=(8, 0))

        # List
        listf = ttk.LabelFrame(self, text=" 已鎖定月份 ", padding=10)
        listf.pack(fill=tk.BOTH, expand=True, padx=20, pady=4)

        cols = ("period", "date", "notes")
        col_labels = {"period": "月份", "date": "鎖定時間", "notes": "Notes"}
        widths = {"period": 100, "date": 150, "notes": 230}
        tree_frame = ttk.Frame(listf)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=col_labels[c])
            self.tree.column(c, width=widths[c])
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Button(listf, text="🔓 重開揀選月份",
                   command=self._reopen).pack(anchor=tk.E, pady=(8, 0))

        self._refresh()

    def _refresh(self):
        from personal_finance import db as pfdb
        for item in self.tree.get_children():
            self.tree.delete(item)
        for p in pfdb.list_closed_periods():
            self.tree.insert("", tk.END, iid=p["period"], values=(
                p["period"], p.get("closed_at") or "", p.get("notes") or ""))

    def _close(self):
        period = self.period_var.get().strip()
        if len(period) != 7 or period[4] != "-":
            messagebox.showwarning("格式錯", "用 YYYY-MM (例: 2026-05)", parent=self)
            return
        from personal_finance import db as pfdb
        pfdb.close_period(period, self.notes_var.get() or None)
        self._refresh()
        self.app.log(f"🔒 鎖定 period {period}")

    def _reopen(self):
        sel = self.tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("確認", f"重開 {sel[0]}？",
                                     parent=self):
            return
        from personal_finance import db as pfdb
        pfdb.reopen_period(sel[0])
        self._refresh()
        self.app.log(f"🔓 重開 period {sel[0]}")


class ARReceiveDialog(tk.Toplevel):
    """收到公司報銷款 → 揀收入邊個 account → post Dr Bank / Cr AR"""
    def __init__(self, parent, app, invoice_id):
        super().__init__(parent)
        self.app = app
        self.invoice_id = invoice_id
        self.title(f"💵 收公司報銷款 (invoice #{invoice_id})")
        self.geometry("450x280")
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text=f"💵 收公司報銷款",
                  style="Title.TLabel").pack(pady=(15, 5), padx=20, anchor=tk.W)
        ttk.Label(self,
                  text=f"Invoice #{invoice_id} 公司報銷已收款？\n"
                       f"系統會 post 收款 entry：Dr [收款 account] / Cr 公司報銷應收",
                  style="Subtitle.TLabel", wraplength=400).pack(
                      padx=20, anchor=tk.W, pady=(0, 10))

        form = ttk.Frame(self, padding=(20, 10))
        form.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form, text="收入邊個 account：").grid(row=0, column=0,
                                                       sticky=tk.W, pady=4)
        from personal_finance import db as pfdb
        assets = [a for a in pfdb.list_accounts()
                  if a["account_type"] == "asset" and a["code"] != "AR_REIMBURSE"]
        opts = [f"{a['icon'] or ''} {a['code']} ({a['name']})" for a in assets]
        self._opt_map = {opt: a["code"] for opt, a in zip(opts, assets)}
        # 默認 HSBC_BANK
        default = next((o for o in opts if "HSBC_BANK" in o), opts[0] if opts else "")
        self.acc_var = tk.StringVar(value=default)
        ttk.Combobox(form, textvariable=self.acc_var, values=opts,
                     state="readonly", width=30).grid(
                         row=0, column=1, sticky=tk.EW, padx=(8, 0), pady=4)

        from datetime import date as _d
        ttk.Label(form, text="收款日期：").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.date_var = tk.StringVar(value=_d.today().isoformat())
        ttk.Entry(form, textvariable=self.date_var, width=32).grid(
            row=1, column=1, sticky=tk.EW, padx=(8, 0), pady=4)

        form.columnconfigure(1, weight=1)

        btn = ttk.Frame(self, padding=(20, 10))
        btn.pack(fill=tk.X)
        ttk.Button(btn, text="💾 確認收款", style="Accent.TButton",
                   command=self._save).pack(side=tk.LEFT)
        ttk.Button(btn, text="稍後處理",
                   command=self.destroy).pack(side=tk.LEFT, padx=(8, 0))

    def _save(self):
        acc = self._opt_map.get(self.acc_var.get())
        if not acc:
            messagebox.showwarning("缺", "揀收款 account", parent=self)
            return
        from personal_finance import posting as pfpost
        try:
            entry_id = pfpost.mark_reimbursement_received(
                self.invoice_id,
                received_account=acc,
                received_date=self.date_var.get())
            self.app.log(f"💵 收公司報銷款 #{self.invoice_id} → entry #{entry_id}")
            self.app._pf_refresh_all()
            self.destroy()
        except Exception as e:
            messagebox.showerror("失敗", str(e), parent=self)


if __name__ == "__main__":
    main()
