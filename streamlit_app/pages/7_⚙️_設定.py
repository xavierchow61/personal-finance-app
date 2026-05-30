"""進階設定 — 匯率 / 付款方式對應 / 期間鎖定 / 專案管理"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
import pandas as pd

from streamlit_app._common import C, app_header, init_dbs

st.set_page_config(
    page_title="設定", page_icon="⚙️", layout="wide",
    initial_sidebar_state="expanded",
)
init_dbs()

app_header("進階設定", "⚙️",
           "帳戶 · 匯率 · 付款方式對應 · 期間鎖定 · 專案管理")

from personal_finance import db as pfdb, seed as pfseed

tab0, tab_acc, tab_cc, tab1, tab2, tab3, tab4 = st.tabs([
    "📖 使用教學",
    "🏦 帳戶管理",
    "💳 信用卡",
    "💱 外幣匯率",
    "🔗 付款方式對應",
    "🔒 期間鎖定",
    "🎯 專案管理",
])

# ============ Tab 0: 使用教學 ============
with tab0:
    # === 歡迎卡 ===
    st.markdown(
        """
        <div style="background:linear-gradient(135deg,
            rgba(0,166,224,0.15) 0%,
            rgba(255,199,0,0.12) 100%);
            border:2px solid rgba(0,166,224,0.3);
            border-radius:18px;padding:1.4rem 1.6rem;
            margin-bottom:1.2rem;
            box-shadow:0 6px 20px rgba(0,120,186,0.15);">
            <h2 style="color:#0078BA;margin:0 0 0.5rem 0;
                font-size:1.6rem;font-weight:700;">
                🎉 歡迎使用「哆啦理財」
            </h2>
            <p style="color:#1A1A2E;margin:0;line-height:1.6;
                font-size:0.95rem;">
                本系統整合 <b>AI 智能單據提取</b>、
                <b>雙式記賬</b>、<b>預算追蹤</b>、
                <b>公司報銷</b>等功能，
                讓您輕鬆管理個人財務。
                以下為各項主要功能的使用說明 ——
                建議首次使用時依序閱讀。
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # === Step-by-step 教學（用 expander）===
    with st.expander("📤 第一步：提取單據", expanded=True):
        st.markdown(
            """
            1. 進入左側「**提取單據**」頁面
            2. 將收據圖片或 PDF **拖曳**至上傳區，
               或按按鈕逐個選擇檔案
            3. 勾選「**自動寫入個人記賬**」可同步入賬
            4. 按「**🚀 開始提取**」按鈕

            ✨ 系統將自動辨識：
            - 商戶名稱、購買日期、總金額、幣別
            - 消費類別（餐飲、交通、超市等）
            - 付款方式（自動對應至您的帳戶）
            - 自動跳過重複的單據
            """
        )

    with st.expander("📋 第二步：核對與編輯單據"):
        st.markdown(
            """
            1. 進入「**單據紀錄**」頁面查閱所有單據
            2. 可依商戶名稱、類別、報銷狀態等**篩選**
            3. **點選任一單據**可進入編輯介面
            4. 右側會顯示原始單據**圖片預覽**
            5. 可修改商戶、金額、類別、付款方式、報銷狀態等
            6. 按「**💾 儲存修改**」會自動重新入賬

            ⚠️ 若修改了「類型」、金額、類別或付款方式，
            系統會自動刪除原分錄並重新建立。
            """
        )

    with st.expander("💰 第三步：管理帳目（個人記賬）"):
        st.markdown(
            """
            本系統採用**雙式記賬法**（Double-entry），
            每筆交易必有借方與貸方且金額相等。

            個人記賬頁面共三個分頁：

            **📜 交易紀錄**
            - 查閱最新 100 筆分錄
            - 可展開查看分錄詳情（借方/貸方）
            - 可刪除錯誤的分錄

            **🏦 帳戶總覽**
            - 查看所有帳戶當前餘額（已換算為 HKD）
            - 包含資產、負債、收入、支出四類帳戶

            **➕ 新增分錄**
            - 手動建立分錄
            - 適用於：薪金入賬、信用卡還款、帳戶轉移
            - 支援多幣別（自動套用最新匯率）
            """
        )

    with st.expander("🎯 第四步：設定預算"):
        st.markdown(
            """
            1. 進入「**預算與實績**」頁面
            2. 確認上方期間（預設為當月，YYYY-MM 格式）
            3. 展開下方「**➕ 設定或修改預算**」
            4. 為各消費類別輸入預算金額（留空表示不設定）
            5. 按「**💾 儲存全部預算**」

            📊 上方表格會即時顯示：
            - 各類別預算 vs 實績
            - 餘額（預算 − 實績）
            - 使用率進度條
            - **超支類別會以紅色警示**

            📈 頁面底部會顯示**過去 12 個月支出走勢圖**。
            """
        )

    with st.expander("📈 第五步：查看財務報表"):
        st.markdown(
            """
            「**財務報表**」頁面提供三類報表：

            **💰 收支表（P&L）**
            - 選擇期間（本月/上月/本年/上年/年初至今）
            - 顯示總收入、總支出、淨額
            - 收入與支出按類別細分

            **🏦 資產負債表**
            - 選擇截止日期
            - 顯示資產總額、負債總額、淨資產
            - 各帳戶餘額明細

            **⚖️ 期間對比**
            - 並排比較兩個期間
            - 顯示收入/支出/淨額的差異
            - 各類別細項對比與變化百分比
            """
        )

    with st.expander("🏢 第六步：公司報銷流程（重要）"):
        st.markdown(
            """
            若該筆消費是**為公司墊支**的款項，請依此流程：

            **A. 記錄報銷單據**
            1. 在提取單據時或之後，將「**類型**」改為「**公司報銷**」
            2. 系統會自動建立特殊分錄：
               - **Dr** AR_REIMBURSE（應收款）
               - **Cr** 您的付款帳戶（如 HSBC_VISA）
            3. **不會**計入您的個人開支

            **B. 收到公司還款後**
            1. 進入「**報銷追蹤**」頁面
            2. 上方可見 KPI：待報銷金額、已收款金額
            3. 在「**⏳ 待收款清單**」中選取單據
            4. 揀「**收款帳戶**」（如 HSBC_BANK）
            5. 按「**✅ 確認收款並入賬**」
            6. 系統自動建立沖銷分錄：
               - **Dr** HSBC_BANK
               - **Cr** AR_REIMBURSE

            ⏪ 如需撤銷已收款狀態，可至「**已收款歷史**」分頁。
            """
        )

    with st.expander("⚙️ 進階設定說明"):
        st.markdown(
            """
            **💱 外幣匯率**
            - 設定 USD、JPY、CNY 等對 HKD 的匯率
            - 影響多幣別記賬與財務報表的金額換算
            - 可同一幣別設定多個生效日期

            **🔗 付款方式對應**
            - 將 AI 識別的字眼對應至實際帳戶
            - 例：「PayMe」→ PAYME 帳戶
            - 可一鍵載入預設對應，或新增自訂規則

            **🔒 期間鎖定**
            - 月結後鎖定該月份，防止誤改舊資料
            - 鎖定後該月份的分錄不能新增/修改/刪除
            - 如需修改可隨時解鎖

            **🎯 專案管理**
            - 為旅行、裝修、副業等項目建立專案
            - 可設定專案預算、開始/結束日期
            - 將分錄關聯至專案，方便追蹤
            """
        )

    with st.expander("💡 實用小貼士"):
        st.markdown(
            """
            - 📑 **重複單據自動跳過** — 同檔案、同日期+商戶+金額會被識別
            - 📄 **PDF 多頁** 會全部讀取（最多 10 頁）
            - 🖼️ 支援格式：JPG、JPEG、PNG、BMP、WEBP、TIFF、PDF
            - 💾 所有資料儲存於本機 SQLite（雲端版用 Supabase）
            - ⚡ 介面卡片可滑鼠**懸停**查看微動畫
            - 🔍 單據紀錄頁可用搜尋框找特定商戶或備註
            - 📊 匯出 Excel 會含 Dashboard 圖表 + 報銷專屬分頁
            """
        )

    # === 底部：聯絡資訊卡 ===
    st.markdown(
        """
        <div style="background:rgba(255,255,255,0.92);
            border:2px solid rgba(255,199,0,0.4);
            border-radius:16px;padding:1.2rem 1.4rem;
            margin-top:1rem;text-align:center;
            box-shadow:0 6px 18px rgba(255,199,0,0.15);">
            <div style="color:#0078BA;font-size:1.1rem;
                font-weight:700;margin-bottom:0.4rem;">
                🌟 開始使用吧！
            </div>
            <p style="color:#1A1A2E;margin:0;
                font-size:0.9rem;line-height:1.6;">
                建議先從「<b>📤 提取單據</b>」上傳一張收據試試看，
                系統會在數秒內為您完成提取與分類，
                並自動寫入您的個人記賬。
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============ Tab 帳戶管理 ============
with tab_acc:
    st.caption(
        "管理所有帳戶：現金、銀行、信用卡、消費類別、收入來源。"
        "新增帳戶後，可在「個人記賬」或「提取單據」用到。"
    )

    ACCOUNT_TYPE_LABELS = {
        "asset": "💰 資產（現金/銀行/應收）",
        "liability": "💳 負債（信用卡/借款）",
        "expense": "🛒 支出類別",
        "income": "💼 收入類別",
    }

    # === 篩選 ===
    flt_col1, flt_col2, flt_col3 = st.columns(3)
    type_filter = flt_col1.selectbox(
        "篩選類型",
        ["（全部）"] + list(ACCOUNT_TYPE_LABELS.values()),
        key="acc_type_filter",
    )

    # 取資料（全部）
    all_accs_raw = pfdb.list_accounts(active_only=not False)  # 暫攞晒
    if type_filter != "（全部）":
        type_code = next(
            (k for k, v in ACCOUNT_TYPE_LABELS.items()
             if v == type_filter), None)
        if type_code:
            all_accs_raw = [a for a in all_accs_raw
                             if a["account_type"] == type_code]

    # === 父帳戶 dropdown（只列頂層、且有子嘅帳戶）===
    children_of = {}  # parent_code -> [child_acc, ...]
    for a in all_accs_raw:
        pc = a.get("parent_code")
        if pc:
            children_of.setdefault(pc, []).append(a)
    parents_with_children = [
        a for a in all_accs_raw
        if not a.get("parent_code") and a["code"] in children_of
    ]
    parent_opts = ["（全部）"] + [
        f"{a.get('icon') or ''} {a['name']} ({a['code']})"
        for a in parents_with_children
    ]
    parent_filter = flt_col2.selectbox(
        "🌳 父帳戶",
        parent_opts,
        key="acc_parent_filter",
        help="揀某父帳戶 → 只顯示佢同其子帳戶",
    )

    show_inactive = flt_col3.checkbox(
        "包含已停用的帳戶", value=False,
        key="acc_show_inactive",
    )

    # === 統一帳戶表單 dialog（新增 + 編輯共用同一彈窗）===
    CURRENCIES = ["HKD", "USD", "JPY", "CNY", "EUR",
                   "GBP", "AUD", "SGD", "TWD"]

    @st.dialog("帳戶資料", width="large")
    def _account_dialog(mode: str, acc: dict | None = None):
        """mode = 'new' or 'edit'"""
        is_edit = mode == "edit"
        st.caption("✏️ 修改現有帳戶" if is_edit else "➕ 建立新帳戶")

        c1, c2 = st.columns(2)
        with c1:
            if is_edit:
                st.text_input("帳戶代碼", value=acc["code"], disabled=True)
                code_val = acc["code"]
            else:
                code_val = st.text_input(
                    "帳戶代碼（英文 / 底線，建立後不能改）",
                    placeholder="例：ZA_BANK / CITI_VISA / FOOD",
                )
            name_val = st.text_input(
                "顯示名稱",
                value=acc["name"] if is_edit else "",
                placeholder="例：ZA Bank / Citi Visa / 餐飲",
            )
            if is_edit:
                type_code = acc["account_type"]
                st.text_input(
                    "帳戶類型（不能改）",
                    value=ACCOUNT_TYPE_LABELS.get(type_code, type_code),
                    disabled=True,
                )
            else:
                type_label = st.selectbox(
                    "帳戶類型", list(ACCOUNT_TYPE_LABELS.values()),
                )
                type_code = next(
                    (k for k, v in ACCOUNT_TYPE_LABELS.items()
                     if v == type_label), "asset")
        with c2:
            icon_val = st.text_input(
                "圖示 emoji（選填）",
                value=(acc.get("icon") or "") if is_edit else "",
                placeholder="例：🏦 💳 🛒",
            )
            opening_val = st.number_input(
                "期初餘額",
                value=(float(acc.get("opening_balance") or 0)
                       if is_edit else 0.0),
                format="%.2f",
            )
            cur_currency = (acc.get("currency") or "HKD") if is_edit else "HKD"
            curr_idx = (CURRENCIES.index(cur_currency)
                        if cur_currency in CURRENCIES else 0)
            currency_val = st.selectbox(
                "幣別", CURRENCIES, index=curr_idx,
            )

        # 父帳戶（用完整 active list，剔除自己）
        _all = pfdb.list_accounts(active_only=True)
        same_type = [
            a for a in _all
            if a["account_type"] == type_code
            and (not is_edit or a["code"] != code_val)
        ]
        parent_opts = ["（無 — 頂層帳戶）"] + [
            f"{a.get('icon') or ''} {a['name']} ({a['code']})"
            for a in same_type
        ]
        cur_parent_idx = 0
        if is_edit and acc.get("parent_code"):
            for i, a in enumerate(same_type, start=1):
                if a["code"] == acc["parent_code"]:
                    cur_parent_idx = i
                    break
        sel_parent = st.selectbox(
            "🌳 父帳戶（選填，將此帳戶歸類在某帳戶之下）",
            parent_opts, index=cur_parent_idx,
            help="例：Mox 信用卡 / Mox 保險 → 父帳戶 = Mox Bank",
        )
        parent_val = (
            same_type[parent_opts.index(sel_parent) - 1]["code"]
            if sel_parent != parent_opts[0] else None
        )

        # 編輯模式專用欄位
        if is_edit:
            sc1, sc2 = st.columns(2)
            sort_val = sc1.number_input(
                "排序（小→大）",
                value=int(acc.get("sort_order") or 0), step=1,
            )
            active_val = sc2.checkbox(
                "啟用此帳戶",
                value=bool(acc.get("is_active")),
            )
        else:
            sort_val = 0
            active_val = True

        notes_val = st.text_area(
            "備註",
            value=(acc.get("notes") or "") if is_edit else "",
        )

        st.divider()
        if is_edit:
            bc1, bc2 = st.columns(2)
            save_btn = bc1.button(
                "💾 儲存修改", type="primary",
                use_container_width=True, key="dlg_save_edit",
            )
            del_btn = bc2.button(
                "🗑️ 刪除帳戶", type="secondary",
                use_container_width=True, key="dlg_del",
            )
        else:
            save_btn = st.button(
                "✨ 建立帳戶", type="primary",
                use_container_width=True, key="dlg_create",
            )
            del_btn = False

        if save_btn:
            code_final = (code_val if is_edit
                          else code_val.strip().upper())
            if not code_final:
                st.error("代碼不能為空")
                return
            if not name_val.strip():
                st.error("名稱不能為空")
                return
            if (not is_edit) and pfdb.get_account(code_final):
                st.error(f"代碼「{code_final}」已存在")
                return
            try:
                pfdb.upsert_account(
                    code=code_final,
                    name=name_val.strip(),
                    account_type=type_code,
                    opening_balance=opening_val,
                    currency=currency_val,
                    sort_order=sort_val,
                    icon=icon_val or None,
                    notes=notes_val or None,
                    parent_code=parent_val,
                )
                if is_edit:
                    from personal_finance import db as _pfdb
                    with _pfdb._conn() as _c:
                        _c.execute(
                            "UPDATE accounts "
                            "SET is_active=? WHERE code=?",
                            (1 if active_val else 0, code_final),
                        )
                    # 用 toast（浮動通知，唔會阻擋 dialog 關閉）
                    st.toast(f"✅ 已更新 {code_final}", icon="✅")
                else:
                    st.toast(
                        f"✅ 建立：{name_val} ({code_final})",
                        icon="🎉",
                    )
                # 清快取，確保下次載入見到新資料
                try:
                    import cached_pfr
                    cached_pfr.invalidate_all()
                except Exception:
                    pass
                st.rerun()   # ← 關閉 dialog
            except Exception as ex:
                st.error(
                    f"{'更新' if is_edit else '建立'}失敗：{ex}"
                )

        if del_btn:
            try:
                pfdb.delete_account(code_val)
                st.toast(f"🗑️ 已刪除 {code_val}", icon="🗑️")
                try:
                    import cached_pfr
                    cached_pfr.invalidate_all()
                except Exception:
                    pass
                st.rerun()
            except Exception as ex:
                st.error(
                    f"❌ 刪除失敗（可能有分錄關聯）：\n\n"
                    f"{ex}\n\n"
                    f"💡 建議改為「停用」（取消勾選"
                    f"「啟用此帳戶」）。"
                )

    # === 按鈕區（placeholder：先佔位，render 表後填埋）===
    _action_bar = st.container()
    st.divider()

    # 應用 active filter
    all_accs = (all_accs_raw if show_inactive
                 else [a for a in all_accs_raw if a.get("is_active")])

    # 應用父帳戶 filter
    if parent_filter != "（全部）":
        idx = parent_opts.index(parent_filter) - 1
        parent_code = parents_with_children[idx]["code"]
        all_accs = [
            a for a in all_accs
            if a["code"] == parent_code or a.get("parent_code") == parent_code
        ]

    if all_accs:
        # === 樹狀分組排序：parent 在前，children 緊隨其後 ===
        _all_codes = {a["code"] for a in all_accs}
        # 頂層 = 無 parent_code OR parent_code 唔喺當前 list 入面
        top_level = [
            a for a in all_accs
            if not a.get("parent_code") or a["parent_code"] not in _all_codes
        ]
        children_by_parent = {}
        for a in all_accs:
            pc = a.get("parent_code")
            if pc and pc in _all_codes:
                children_by_parent.setdefault(pc, []).append(a)
        # sort top-level by (account_type, sort_order, name)
        top_level.sort(key=lambda x: (
            x["account_type"], x.get("sort_order") or 0, x["name"]))
        # 攤平：頂層 → 佢嘅子 → 下一個頂層
        ordered = []
        for top in top_level:
            ordered.append((top, 0))   # depth 0
            for child in sorted(children_by_parent.get(top["code"], []),
                                 key=lambda x: (x.get("sort_order") or 0,
                                                 x["name"])):
                ordered.append((child, 1))  # depth 1

        # 建 code → name 對照（包含完整 list，用於顯示父名稱）
        _name_by_code = {a["code"]: a["name"] for a in all_accs_raw}

        # === 批量編輯 toggle ===
        _bulk_edit = st.toggle(
            "📝 批量編輯模式（可一次過改多個帳戶，最後撳儲存）",
            key="acc_bulk_edit_toggle",
            help="開啟後可直接喺表入面改：圖示／名稱／幣別／"
                 "期初餘額／排序／啟用",
        )

        if _bulk_edit:
            # === 批量編輯模式 ===
            bulk_df = pd.DataFrame([
                {
                    "代碼": a["code"],
                    "圖示": a.get("icon") or "",
                    "名稱": a["name"],
                    "類型": ACCOUNT_TYPE_LABELS.get(
                        a["account_type"], a["account_type"]),
                    "幣別": a.get("currency") or "HKD",
                    "期初餘額": float(a.get("opening_balance") or 0),
                    "排序": int(a.get("sort_order") or 0),
                    "啟用": bool(a.get("is_active")),
                }
                for (a, depth) in ordered
            ])
            edited_df = st.data_editor(
                bulk_df,
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",   # 唔畀新增/刪除行（用 dialog 做）
                column_config={
                    "代碼": st.column_config.TextColumn(disabled=True),
                    "類型": st.column_config.TextColumn(disabled=True),
                    "幣別": st.column_config.SelectboxColumn(
                        options=CURRENCIES, required=True,
                    ),
                    "圖示": st.column_config.TextColumn(
                        help="emoji，例：🏦 💳",
                    ),
                    "名稱": st.column_config.TextColumn(required=True),
                    "期初餘額": st.column_config.NumberColumn(
                        format="$%.2f", step=0.01,
                    ),
                    "排序": st.column_config.NumberColumn(
                        step=1, format="%d",
                    ),
                    "啟用": st.column_config.CheckboxColumn(),
                },
                key="acc_data_editor",
            )

            # 填埋頂部按鈕區：儲存 + 取消
            with _action_bar:
                sa1, sa2, _sa_spacer = st.columns([1, 1, 4])
                with sa1:
                    if st.button("💾 儲存全部變更",
                                  type="primary",
                                  use_container_width=True,
                                  key="bulk_save"):
                        n_updated = 0
                        errors = []
                        for i in range(len(bulk_df)):
                            orig = bulk_df.iloc[i]
                            new = edited_df.iloc[i]
                            code = orig["代碼"]
                            # 比較有冇 diff
                            diff = (
                                (orig["圖示"] or "") != (new["圖示"] or "")
                                or orig["名稱"] != new["名稱"]
                                or orig["幣別"] != new["幣別"]
                                or float(orig["期初餘額"]) !=
                                   float(new["期初餘額"])
                                or int(orig["排序"]) != int(new["排序"])
                                or bool(orig["啟用"]) != bool(new["啟用"])
                            )
                            if not diff:
                                continue
                            try:
                                _acc = pfdb.get_account(code)
                                pfdb.upsert_account(
                                    code=code,
                                    name=new["名稱"].strip(),
                                    account_type=_acc["account_type"],
                                    opening_balance=float(new["期初餘額"]),
                                    currency=new["幣別"],
                                    sort_order=int(new["排序"]),
                                    icon=(new["圖示"] or None),
                                    notes=_acc.get("notes"),
                                    parent_code=_acc.get("parent_code"),
                                )
                                # is_active 要 raw SQL
                                from personal_finance import db as _pfdb
                                with _pfdb._conn() as _c:
                                    _c.execute(
                                        "UPDATE accounts "
                                        "SET is_active=? WHERE code=?",
                                        (1 if new["啟用"] else 0, code),
                                    )
                                n_updated += 1
                            except Exception as ex:
                                errors.append(f"{code}: {ex}")
                        if errors:
                            st.error(
                                f"⚠️ 部份失敗：\n\n" + "\n\n".join(errors)
                            )
                        if n_updated > 0:
                            st.toast(
                                f"✅ 已更新 {n_updated} 個帳戶",
                                icon="✅",
                            )
                            try:
                                import cached_pfr
                                cached_pfr.invalidate_all()
                            except Exception:
                                pass
                            # 關閉批量編輯模式
                            st.session_state[
                                "acc_bulk_edit_toggle"] = False
                            st.rerun()
                        else:
                            st.info("ℹ️ 沒有資料變動")
                with sa2:
                    if st.button("❌ 取消編輯",
                                  use_container_width=True,
                                  key="bulk_cancel"):
                        st.session_state[
                            "acc_bulk_edit_toggle"] = False
                        st.rerun()

            st.caption(
                "💡 想改父帳戶 / 類型 / 備註，或刪帳戶？"
                "請關閉批量編輯，揀行後撳「✏️ 編輯」開單筆 dialog。"
            )
        else:
            # === 一般檢視模式 ===
            df_acc = pd.DataFrame([
                {
                    "代碼": a["code"],
                    "圖示": a.get("icon") or "",
                    "名稱": (("　└─ " if depth > 0 else "") + a["name"]),
                    "父帳戶": (
                        _name_by_code.get(a.get("parent_code"), "—")
                        if a.get("parent_code") else "—"
                    ),
                    "類型": ACCOUNT_TYPE_LABELS.get(
                        a["account_type"], a["account_type"]),
                    "幣別": a.get("currency") or "HKD",
                    "期初餘額": a.get("opening_balance") or 0,
                    "排序": a.get("sort_order") or 0,
                    "啟用": "✅" if a.get("is_active") else "❌",
                }
                for (a, depth) in ordered
            ])
            sel_acc = st.dataframe(
                df_acc, hide_index=True, use_container_width=True,
                on_select="rerun", selection_mode="single-row",
                column_config={
                    "期初餘額": st.column_config.NumberColumn(
                        format="$%.2f"),
                },
            )

            # === 填埋頂部按鈕區（新增 + 編輯同一行）===
            _has_sel = bool(sel_acc.selection.rows)
            _sel_acc_obj = None
            if _has_sel:
                _sel_code = df_acc.iloc[
                    sel_acc.selection.rows[0]]["代碼"]
                _sel_acc_obj = pfdb.get_account(_sel_code)

            with _action_bar:
                ba1, ba2, _ba_spacer = st.columns([1, 1, 4])
                with ba1:
                    if st.button("➕ 新增帳戶",
                                  use_container_width=True,
                                  key="open_new_acc_dlg"):
                        _account_dialog("new")
                with ba2:
                    if _sel_acc_obj:
                        _btn_label = (
                            f"✏️ 編輯：{_sel_acc_obj.get('icon') or ''}"
                            f"{_sel_acc_obj['name']}"
                        )
                    else:
                        _btn_label = "✏️ 編輯（先揀一行）"
                    if st.button(
                        _btn_label,
                        use_container_width=True,
                        disabled=not _has_sel,
                        key="open_edit_dlg",
                    ):
                        if _sel_acc_obj:
                            _account_dialog("edit", _sel_acc_obj)
    else:
        # 表為空時填埋按鈕區（只新增）
        with _action_bar:
            ba1, _ba_spacer = st.columns([1, 5])
            with ba1:
                if st.button("➕ 新增帳戶",
                              use_container_width=True,
                              key="open_new_acc_dlg_empty"):
                    _account_dialog("new")
        st.info("尚無符合條件的帳戶。")


# ============ Tab 信用卡管理 ============
with tab_cc:
    st.caption(
        "管理信用卡額外資訊：信用額度、月結日、還款限期、利率、年費、回贈方式。"
        "新增前須先在「🏦 帳戶管理」建立負債類型帳戶。"
    )

    from personal_finance import reports as _pfr
    from datetime import date as _d, timedelta as _td

    def _next_due_date(due_day: int | None,
                        today: _d | None = None) -> _d | None:
        """計算今日之後最近嘅還款日"""
        if not due_day:
            return None
        today = today or _d.today()
        try:
            target = today.replace(day=due_day)
        except ValueError:
            # 如該月無呢一日（如 30/31）→ 用該月最後一日
            import calendar
            last = calendar.monthrange(today.year, today.month)[1]
            target = today.replace(day=min(due_day, last))
        if target <= today:
            # 已過 → 跳下個月
            month = today.month + 1
            year = today.year
            if month > 12:
                month = 1
                year += 1
            try:
                target = today.replace(year=year, month=month,
                                        day=due_day)
            except ValueError:
                import calendar
                last = calendar.monthrange(year, month)[1]
                target = today.replace(year=year, month=month,
                                        day=min(due_day, last))
        return target

    # 防呆：若 list_credit_cards 失敗（例如 migration 未跑），回空 list
    try:
        # 強制 init_db 確保新表存在
        pfdb.init_db()
        cards = pfdb.list_credit_cards()
    except Exception as ex:
        st.error(
            f"⚠️ 無法載入信用卡資料：{type(ex).__name__}: {ex}\n\n"
            "請嘗試重啟 Streamlit Cloud app（Manage app → Reboot）"
        )
        cards = []

    # === 💰 回贈統計 ===
    cards_with_rate = [c for c in cards
                        if c.get("rewards_rate")]
    if cards_with_rate:
        from datetime import date as _d2
        import database as _invdb2
        today_d2 = _d2.today()
        ytd_start = today_d2.replace(month=1, day=1).isoformat()
        mtd_start = today_d2.replace(day=1).isoformat()

        ytd_total = 0.0
        mtd_total = 0.0
        best_card = None
        best_card_ytd = 0.0
        all_inv = _invdb2.list_all()

        for c_meta in cards_with_rate:
            rate = c_meta.get("rewards_rate") or 0
            related_inv = []
            for inv in all_inv:
                pm = inv.get("payment_method") or ""
                # 用 last4 或 alias 對應
                if (c_meta.get("card_last4")
                        and c_meta["card_last4"] in pm):
                    related_inv.append(inv)
                elif pfdb.lookup_payment_alias(pm) == \
                        c_meta["account_code"]:
                    related_inv.append(inv)

            card_ytd = 0.0
            card_mtd = 0.0
            for inv in related_inv:
                d = inv.get("purchase_date") or ""
                amt = float(inv.get("total_amount") or 0)
                if d >= ytd_start:
                    card_ytd += amt * rate
                if d >= mtd_start:
                    card_mtd += amt * rate
            ytd_total += card_ytd
            mtd_total += card_mtd
            if card_ytd > best_card_ytd:
                best_card_ytd = card_ytd
                best_card = c_meta

        best_name = ((best_card.get("account_name") or "—")
                      if best_card else "—")
        st.markdown(
            f"""
            <div style="background:linear-gradient(135deg,
                rgba(255,199,0,0.18) 0%,
                rgba(0,166,224,0.10) 100%);
                border:2px solid rgba(255,199,0,0.5);
                border-radius:14px;padding:1rem 1.4rem;
                margin-bottom:1rem;">
                <div style="color:#0078BA;font-weight:700;
                            font-size:1.05rem;
                            margin-bottom:0.5rem;">
                    💰 回贈統計
                </div>
                <div style="display:flex;gap:1.5rem;
                            flex-wrap:wrap;color:#1A1A2E;">
                    <div>本月累計：<b>${mtd_total:,.2f}</b></div>
                    <div>本年累計：<b>${ytd_total:,.2f}</b></div>
                    <div>👑 賺最多：<b>{best_name}</b>
                        (${best_card_ytd:,.2f})</div>
                </div>
                <div style="color:#6B7BA0;font-size:0.78rem;
                            margin-top:0.4rem;">
                    💡 設定每張卡嘅回贈率（編輯信用卡），
                    系統會自動按已記錄嘅單據計算回贈
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if cards:
        # 計算每張卡嘅 utilization + 距離還款日
        rows_disp = []
        today = _d.today()
        for c_meta in cards:
            code = c_meta["account_code"]
            balance_hkd = abs(_pfr.account_balance(code, in_hkd=True))
            limit = c_meta.get("credit_limit") or 0
            util_pct = (balance_hkd / limit * 100) if limit > 0 else 0
            next_due = _next_due_date(c_meta.get("due_day"), today)
            days_left = (next_due - today).days if next_due else None

            # 狀態
            if util_pct > 80:
                util_emoji = "🔴"
            elif util_pct > 50:
                util_emoji = "🟡"
            else:
                util_emoji = "🟢"
            if days_left is not None and days_left <= 7:
                due_emoji = "⚠️"
            else:
                due_emoji = "✅"

            rows_disp.append({
                "代碼": code,
                "卡名": f"{c_meta.get('account_icon') or ''} "
                          f"{c_meta['account_name']}",
                "末 4 碼": c_meta.get("card_last4") or "—",
                "限額": limit,
                "已用": balance_hkd,
                "使用率": util_pct,
                "狀態": util_emoji,
                "月結日": c_meta.get("statement_day") or "—",
                "還款日": c_meta.get("due_day") or "—",
                "距還款": f"{due_emoji} {days_left} 日" if (
                    days_left is not None) else "—",
            })

        df_cc = pd.DataFrame(rows_disp)
        sel_cc = st.dataframe(
            df_cc, hide_index=True, use_container_width=True,
            on_select="rerun", selection_mode="single-row",
            column_config={
                "限額": st.column_config.NumberColumn(
                    format="$%.0f"),
                "已用": st.column_config.NumberColumn(
                    format="$%.0f"),
                "使用率": st.column_config.ProgressColumn(
                    format="%.0f%%", min_value=0, max_value=100),
            },
        )

        # === 編輯選定卡 ===
        if sel_cc.selection.rows:
            sel_code = df_cc.iloc[sel_cc.selection.rows[0]]["代碼"]
            card = pfdb.get_credit_card(sel_code)
            if card:
                st.divider()
                with st.expander(
                    f"✏️ 編輯：{sel_code} "
                    f"(末 4 碼 {card.get('card_last4') or '—'})",
                    expanded=True,
                ):
                    with st.form(f"edit_cc_{sel_code}"):
                        cc1, cc2 = st.columns(2)
                        with cc1:
                            ed_last4 = st.text_input(
                                "末 4 碼", card.get("card_last4") or "",
                                max_chars=4,
                            )
                            ed_limit = st.number_input(
                                "信用額度 (HKD)",
                                value=float(card.get(
                                    "credit_limit") or 0),
                                format="%.0f", min_value=0.0,
                            )
                            ed_stmt = st.number_input(
                                "月結日 (1-31)",
                                value=int(card.get(
                                    "statement_day") or 1),
                                min_value=1, max_value=31, step=1,
                            )
                            ed_due = st.number_input(
                                "還款限期日 (1-31)",
                                value=int(card.get("due_day") or 1),
                                min_value=1, max_value=31, step=1,
                            )
                        with cc2:
                            ed_rate = st.number_input(
                                "年利率（如 32 表示 32%）",
                                value=float(
                                    (card.get("interest_rate") or 0)
                                    * 100),
                                format="%.2f", min_value=0.0,
                            )
                            ed_fee = st.number_input(
                                "年費 (HKD)",
                                value=float(card.get(
                                    "annual_fee") or 0),
                                format="%.0f", min_value=0.0,
                            )
                            ed_rewards = st.text_input(
                                "回贈 / 里數 說明",
                                value=card.get("rewards") or "",
                                placeholder="例：1% 現金回贈 / 飛行里數",
                            )
                            ed_rewards_rate = st.number_input(
                                "回贈率 % (例 1 = 1% 現金回贈)",
                                value=float(
                                    (card.get("rewards_rate") or 0)
                                    * 100),
                                format="%.2f", min_value=0.0,
                            )
                            ed_rewards_type = st.selectbox(
                                "回贈類型",
                                ["cash 現金回贈", "miles 飛行里數",
                                 "points 積分"],
                                index=(
                                    ["cash", "miles",
                                      "points"].index(
                                        card.get("rewards_type")
                                        or "cash")
                                    if card.get("rewards_type")
                                       in ["cash", "miles",
                                            "points"]
                                    else 0
                                ),
                            )
                        ed_notes = st.text_area(
                            "備註", card.get("notes") or "",
                            placeholder="年費豁免條件、客服電話等",
                        )

                        b1, b2 = st.columns(2)
                        if b1.form_submit_button(
                                "💾 儲存", type="primary",
                                use_container_width=True):
                            try:
                                pfdb.upsert_credit_card(
                                    account_code=sel_code,
                                    card_last4=ed_last4 or None,
                                    credit_limit=ed_limit or None,
                                    statement_day=ed_stmt or None,
                                    due_day=ed_due or None,
                                    interest_rate=(ed_rate / 100
                                                    if ed_rate else None),
                                    annual_fee=ed_fee or None,
                                    rewards=ed_rewards or None,
                                    rewards_rate=(
                                        ed_rewards_rate / 100
                                        if ed_rewards_rate else None
                                    ),
                                    rewards_type=ed_rewards_type.split()[0],
                                    notes=ed_notes or None,
                                )
                                st.success(f"✅ 已更新 {sel_code}")
                                st.rerun()
                            except Exception as ex:
                                st.error(f"更新失敗：{ex}")
                        if b2.form_submit_button(
                                "🗑️ 移除信用卡資料",
                                type="secondary",
                                use_container_width=True):
                            try:
                                pfdb.delete_credit_card(sel_code)
                                st.success(
                                    f"已移除 {sel_code} 嘅信用卡資料"
                                    f"（原 account 不變）"
                                )
                                st.rerun()
                            except Exception as ex:
                                st.error(str(ex))
    else:
        st.info(
            "尚未設定任何信用卡。請於下方「➕ 新增信用卡」加入。"
        )

    # === 新增信用卡 ===
    st.divider()
    with st.expander("➕ 新增信用卡", expanded=not bool(cards)):
        # 找出可用嘅 liability accounts（未有 credit_card 紀錄嘅）
        liab_accs = pfdb.list_accounts(account_type="liability")
        existing_codes = {c["account_code"] for c in cards}
        available = [a for a in liab_accs
                     if a["code"] not in existing_codes]

        if not available:
            st.warning(
                "⚠️ 所有負債帳戶已有信用卡資料。"
                "若要加新卡，請先去「🏦 帳戶管理」建立新嘅"
                "「負債」帳戶（如 CITI_VISA、AMEX_PLATINUM）。"
            )
        else:
            with st.form("new_cc"):
                acc_opts = {
                    f"{a.get('icon') or '💳'} {a['name']} "
                    f"({a['code']})": a["code"]
                    for a in available
                }
                nc_acc_label = st.selectbox(
                    "選擇對應帳戶（負債類型）",
                    list(acc_opts.keys()),
                    help="必須先在「🏦 帳戶管理」建立負債帳戶",
                )

                n1, n2 = st.columns(2)
                with n1:
                    n_last4 = st.text_input(
                        "末 4 碼", max_chars=4,
                        placeholder="例：8989",
                    )
                    n_limit = st.number_input(
                        "信用額度 (HKD)",
                        value=0.0, format="%.0f", min_value=0.0,
                    )
                    n_stmt = st.number_input(
                        "月結日 (1-31)",
                        value=1, min_value=1, max_value=31, step=1,
                    )
                    n_due = st.number_input(
                        "還款限期日 (1-31)",
                        value=20, min_value=1, max_value=31, step=1,
                    )
                with n2:
                    n_rate = st.number_input(
                        "年利率（如 32 表示 32%）",
                        value=32.0, format="%.2f", min_value=0.0,
                    )
                    n_fee = st.number_input(
                        "年費 (HKD)",
                        value=0.0, format="%.0f", min_value=0.0,
                    )
                    n_rewards = st.text_input(
                        "回贈 / 里數 說明",
                        placeholder="例：1% 現金回贈",
                    )
                    n_rewards_rate = st.number_input(
                        "回贈率 % (例 1 = 1%)",
                        value=0.0, format="%.2f", min_value=0.0,
                    )
                    n_rewards_type = st.selectbox(
                        "回贈類型",
                        ["cash", "miles", "points"],
                    )
                n_notes = st.text_area(
                    "備註",
                    placeholder="年費豁免條件、客服電話等",
                )

                if st.form_submit_button(
                        "✨ 建立信用卡", type="primary",
                        use_container_width=True):
                    try:
                        pfdb.upsert_credit_card(
                            account_code=acc_opts[nc_acc_label],
                            card_last4=n_last4 or None,
                            credit_limit=n_limit or None,
                            statement_day=n_stmt or None,
                            due_day=n_due or None,
                            interest_rate=(n_rate / 100
                                            if n_rate else None),
                            annual_fee=n_fee or None,
                            rewards=n_rewards or None,
                            rewards_rate=(n_rewards_rate / 100
                                          if n_rewards_rate
                                          else None),
                            rewards_type=n_rewards_type,
                            notes=n_notes or None,
                        )
                        st.success(
                            f"✅ 已建立信用卡："
                            f"{acc_opts[nc_acc_label]}"
                        )
                        st.rerun()
                    except Exception as ex:
                        st.error(f"建立失敗：{ex}")


# ============ Tab 1: 外幣匯率 ============
with tab1:
    st.caption("設定各幣別對 HKD 的匯率（影響多幣別記賬報表）")

    rates = pfdb.list_fx_rates()
    if rates:
        df_fx = pd.DataFrame([
            {
                "ID": r["fx_id"],
                "幣別": r["currency"],
                "對 HKD 匯率": r["rate_to_hkd"],
                "生效日期": r.get("as_of_date") or "—",
                "備註": r.get("notes") or "",
            }
            for r in rates
        ])
        st.dataframe(df_fx, hide_index=True, use_container_width=True,
                      column_config={
                          "對 HKD 匯率": st.column_config.NumberColumn(
                              format="%.4f"),
                      })
    else:
        st.info("尚未設定任何匯率。HKD 預設 1.0")

    st.divider()
    with st.expander("➕ 新增 / 更新匯率"):
        with st.form("fx_form"):
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                curr = st.selectbox(
                    "幣別", ["USD", "JPY", "CNY", "EUR", "GBP",
                              "AUD", "CAD", "SGD", "TWD", "KRW"])
            with fc2:
                rate = st.number_input("對 HKD 匯率", value=1.0,
                                        format="%.4f", min_value=0.0001)
            with fc3:
                from datetime import date as _d
                as_of = st.date_input("生效日期", _d.today())
            notes = st.text_input("備註（選填）", "")

            if st.form_submit_button("💾 儲存匯率", type="primary"):
                try:
                    pfdb.set_fx_rate(curr, rate,
                                       as_of_date=as_of.isoformat(),
                                       notes=notes or None)
                    st.success(f"✅ 已設定 {curr} = {rate:.4f} HKD")
                    st.rerun()
                except Exception as ex:
                    st.error(str(ex))

# ============ Tab 2: 付款方式對應 ============
with tab2:
    st.caption(
        "設定 OCR 提取出來的「付款方式」字眼 → 對應到哪個帳戶。"
        "例如「PayMe」→ PAYME；「HSBC Visa」→ HSBC_VISA"
    )

    # === 🪄 智能對應精靈 ===
    import database as _invdb

    def _suggest_account(keyword: str, accounts: list[dict]) -> str | None:
        """為一個 OCR 字眼推薦最匹配嘅帳戶 code（partial match）"""
        kw_lower = keyword.lower().strip()
        if not kw_lower:
            return None
        # 1. 精確包含（雙向）
        for a in accounts:
            code_l = a["code"].lower()
            name_l = a["name"].lower()
            if code_l in kw_lower or name_l in kw_lower:
                return a["code"]
            if kw_lower in code_l or kw_lower in name_l:
                return a["code"]
        # 2. 模糊：字首匹配
        for a in accounts:
            if any(part in kw_lower
                    for part in a["code"].lower().split("_")):
                return a["code"]
        return None

    # 找出未對應嘅 OCR 字眼
    all_invoices = _invdb.list_all()
    payment_methods_seen = sorted({
        (i.get("payment_method") or "").strip()
        for i in all_invoices
        if i.get("payment_method")
        and i.get("payment_method").strip()
    })
    existing_aliases_lower = {
        a["keyword"].lower().strip()
        for a in pfdb.list_payment_aliases()
    }
    unmapped = [
        m for m in payment_methods_seen
        if m.lower() not in existing_aliases_lower
        and not pfdb.lookup_payment_alias(m)
    ]

    if unmapped:
        st.markdown(
            f"""
            <div style="background:linear-gradient(135deg,
                rgba(255,199,0,0.18) 0%,
                rgba(0,166,224,0.10) 100%);
                border:2px solid rgba(255,199,0,0.5);
                border-radius:16px;padding:1.1rem 1.4rem;
                margin-bottom:1rem;
                box-shadow:0 4px 16px rgba(0,120,186,0.15);">
                <div style="color:#0078BA;font-weight:700;
                            font-size:1.1rem;margin-bottom:0.4rem;">
                    🪄 智能對應精靈
                </div>
                <div style="color:#1A1A2E;font-size:0.92rem;
                            line-height:1.5;">
                    系統偵測到 <b>{len(unmapped)} 個</b>
                    已出現在單據但仍未對應到帳戶嘅付款方式字眼。
                    為佢哋指定對應帳戶，將來自動入賬會更準確。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 載入所有可選帳戶
        _accs = pfdb.list_accounts(account_type="asset") + \
                pfdb.list_accounts(account_type="liability")
        _acc_opts = {
            f"{a.get('icon') or ''} {a['name']} ({a['code']})":
                a["code"]
            for a in _accs
        }
        _opt_labels = ["（跳過）"] + list(_acc_opts.keys())

        with st.form("alias_wizard"):
            st.markdown(
                "**逐個揀對應帳戶（系統已預先建議）：**"
            )
            wizard_picks: dict[str, str] = {}
            for kw in unmapped:
                suggested_code = _suggest_account(kw, _accs)
                suggested_label = next(
                    (lbl for lbl, c in _acc_opts.items()
                     if c == suggested_code),
                    None,
                )
                default_idx = (
                    _opt_labels.index(suggested_label)
                    if suggested_label in _opt_labels
                    else 0
                )

                wc1, wc2 = st.columns([2, 3])
                badge = "✨ 已建議" if suggested_code else "❓ 未建議"
                wc1.markdown(
                    f"**{kw}**<br>"
                    f"<span style='color:#6B7BA0;font-size:0.78rem;'>"
                    f"{badge}</span>",
                    unsafe_allow_html=True,
                )
                with wc2:
                    sel = st.selectbox(
                        "對應到",
                        _opt_labels,
                        index=default_idx,
                        key=f"wiz_{kw}",
                        label_visibility="collapsed",
                    )
                wizard_picks[kw] = sel

            wb1, wb2 = st.columns(2)
            apply_all = wb1.form_submit_button(
                "✨ 一鍵儲存全部（跳過「（跳過）」項目）",
                type="primary", use_container_width=True,
            )
            apply_suggested = wb2.form_submit_button(
                "⚡ 只儲存已建議",
                use_container_width=True,
            )

            if apply_all or apply_suggested:
                n_saved = 0
                for kw, sel in wizard_picks.items():
                    # 「只儲存已建議」 → 跳過冇 suggestion 嘅
                    if apply_suggested:
                        if _suggest_account(kw, _accs) is None:
                            continue
                    if sel == "（跳過）":
                        continue
                    try:
                        pfdb.add_payment_alias(kw, _acc_opts[sel])
                        n_saved += 1
                    except Exception:
                        pass
                if n_saved > 0:
                    st.success(
                        f"✅ 對應精靈完成！已儲存 {n_saved} 條對應"
                    )
                    st.rerun()
                else:
                    st.warning("⚠️ 冇任何項目被儲存")
    else:
        # 全部對應 OK
        st.success(
            "🎉 所有已出現嘅付款方式都已對應到帳戶 — "
            "唔需要精靈協助！"
        )

    st.divider()

    # === 統一 dialog（新增 + 編輯共用）===
    @st.dialog("付款方式對應", width="large")
    def _alias_dialog(mode: str, alias: dict | None = None):
        is_edit = mode == "edit"
        st.caption("✏️ 修改現有對應" if is_edit
                   else "➕ 新增付款方式對應")

        _accs = pfdb.list_accounts(account_type="asset") + \
                pfdb.list_accounts(account_type="liability")
        _acc_opts = {
            f"{a.get('icon') or ''} {a['name']} ({a['code']})":
                a["code"]
            for a in _accs
        }
        _opt_list = list(_acc_opts.keys())

        cur_kw = alias["keyword"] if is_edit else ""
        cur_code = alias["account_code"] if is_edit else None
        cur_notes = (alias.get("notes") or "") if is_edit else ""
        cur_id = int(alias["alias_id"]) if is_edit else None

        new_kw = st.text_input(
            "關鍵字（會用 LIKE 模糊匹配）",
            value=cur_kw,
            placeholder="例：PayMe / HSBC / Visa",
        )
        cur_label = next(
            (lbl for lbl, c in _acc_opts.items() if c == cur_code),
            None,
        )
        cur_idx = (_opt_list.index(cur_label)
                   if cur_label in _opt_list else 0)
        new_acc_label = st.selectbox(
            "對應到帳戶", _opt_list, index=cur_idx,
        )
        new_notes_val = st.text_input(
            "備註（選填）", value=cur_notes,
        )

        st.divider()
        if is_edit:
            bc1, bc2 = st.columns(2)
            save_btn = bc1.button(
                "💾 儲存修改", type="primary",
                use_container_width=True, key="alias_dlg_save",
            )
            del_btn = bc2.button(
                "🗑️ 刪除", type="secondary",
                use_container_width=True, key="alias_dlg_del",
            )
        else:
            save_btn = st.button(
                "✨ 新增對應", type="primary",
                use_container_width=True, key="alias_dlg_create",
            )
            del_btn = False

        if save_btn:
            new_kw_s = new_kw.strip()
            if not new_kw_s:
                st.error("關鍵字不能為空")
                return
            try:
                # 編輯時如關鍵字有改 → 先刪舊嘅
                if is_edit and new_kw_s.lower() != cur_kw.lower():
                    pfdb.delete_payment_alias(cur_id)
                pfdb.add_payment_alias(
                    new_kw_s,
                    _acc_opts[new_acc_label],
                    new_notes_val or None,
                )
                if is_edit:
                    st.toast(
                        f"✅ 已更新：{new_kw_s} → "
                        f"{_acc_opts[new_acc_label]}",
                        icon="✅",
                    )
                else:
                    st.toast(
                        f"✨ 新增：{new_kw_s} → "
                        f"{_acc_opts[new_acc_label]}",
                        icon="🎉",
                    )
                try:
                    import cached_pfr
                    cached_pfr.invalidate_all()
                except Exception:
                    pass
                st.rerun()
            except Exception as ex:
                st.error(f"{'更新' if is_edit else '新增'}失敗：{ex}")

        if del_btn:
            try:
                pfdb.delete_payment_alias(cur_id)
                st.toast(f"🗑️ 已刪除 #{cur_id}", icon="🗑️")
                try:
                    import cached_pfr
                    cached_pfr.invalidate_all()
                except Exception:
                    pass
                st.rerun()
            except Exception as ex:
                st.error(str(ex))

    # === 按鈕區（placeholder：先佔位，render 表後填埋）===
    _alias_action_bar = st.container()
    st.divider()

    aliases = pfdb.list_payment_aliases()
    if aliases:
        df_al = pd.DataFrame([
            {
                "ID": a["alias_id"],
                "關鍵字（部份匹配）": a["keyword"],
                "對應帳戶": a["account_code"],
                "備註": a.get("notes") or "",
            }
            for a in aliases
        ])
        sel = st.dataframe(df_al, hide_index=True,
                            use_container_width=True,
                            on_select="rerun",
                            selection_mode="single-row")

        # 填埋頂部按鈕區（新增 + 編輯同一行）
        _has_sel_al = bool(sel.selection.rows)
        _sel_alias = None
        if _has_sel_al:
            _sel_alias = aliases[sel.selection.rows[0]]

        with _alias_action_bar:
            ab1, ab2, _ab_spacer = st.columns([1, 1, 4])
            with ab1:
                if st.button("➕ 新增對應",
                              use_container_width=True,
                              key="open_new_alias_dlg"):
                    _alias_dialog("new")
            with ab2:
                if _sel_alias:
                    _lbl = (
                        f"✏️ 編輯：{_sel_alias['keyword']} → "
                        f"{_sel_alias['account_code']}"
                    )
                else:
                    _lbl = "✏️ 編輯（先揀一行）"
                if st.button(
                    _lbl, use_container_width=True,
                    disabled=not _has_sel_al,
                    key="open_edit_alias_dlg",
                ):
                    if _sel_alias:
                        _alias_dialog("edit", _sel_alias)
    else:
        # 表為空時只填新增按鈕
        with _alias_action_bar:
            ab1, _ab_spacer = st.columns([1, 5])
            with ab1:
                if st.button("➕ 新增對應",
                              use_container_width=True,
                              key="open_new_alias_dlg_empty"):
                    _alias_dialog("new")
        st.info("尚未設定任何對應。系統會用 fallback 自動分類。")

    st.divider()
    al_c1, al_c2, al_c3 = st.columns(3)
    with al_c1:
        if st.button("📦 一鍵載入預設對應"):
            stats = pfseed.seed_payment_aliases(force=False)
            n = stats.get('inserted', stats.get('count', 0)) \
                if isinstance(stats, dict) else 0
            st.success(f"✅ 已載入預設對應（{n} 條）")
            st.rerun()
    with al_c2:
        if st.button("🔄 重設為預設值（會刪掉自訂）",
                     type="secondary"):
            stats = pfseed.reset_payment_aliases_to_defaults()
            if isinstance(stats, dict):
                st.warning(
                    f"⚠️ 已重設！刪 {stats.get('deleted', 0)} 條、"
                    f"新增 {stats.get('inserted', 0)} 條"
                )
            else:
                st.warning("⚠️ 已重設為預設值")
            st.rerun()
    with al_c3:
        # 全部刪除（兩步確認，防誤撳）
        if not st.session_state.get("confirm_del_all_aliases"):
            if st.button("🗑️ 全部刪除", type="secondary",
                          key="ask_del_all_aliases"):
                st.session_state["confirm_del_all_aliases"] = True
                st.rerun()
        else:
            st.warning("⚠️ 確認要刪除全部對應？")
            cc1, cc2 = st.columns(2)
            if cc1.button("✅ 確定刪除",
                          type="primary",
                          key="do_del_all_aliases",
                          use_container_width=True):
                try:
                    n = pfdb.delete_all_payment_aliases()
                    st.session_state["confirm_del_all_aliases"] = False
                    st.toast(f"🗑️ 已刪除 {n} 條對應", icon="🗑️")
                    st.rerun()
                except Exception as ex:
                    st.error(f"刪除失敗：{ex}")
            if cc2.button("取消",
                          key="cancel_del_all_aliases",
                          use_container_width=True):
                st.session_state["confirm_del_all_aliases"] = False
                st.rerun()

# ============ Tab 3: 期間鎖定 ============
with tab3:
    st.caption(
        "鎖定的月份不能新增 / 修改 / 刪除分錄，避免月結後資料變動。"
        "建議每月月結後鎖定上月。"
    )

    closed = pfdb.list_closed_periods()
    if closed:
        df_cl = pd.DataFrame([
            {
                "期間": cp["period"],
                "鎖定時間": cp.get("closed_at") or "—",
                "鎖定者": cp.get("closed_by") or "—",
                "備註": cp.get("notes") or "",
            }
            for cp in closed
        ])
        st.dataframe(df_cl, hide_index=True, use_container_width=True)
    else:
        st.info("尚未鎖定任何期間。所有月份均可自由編輯。")

    st.divider()
    pc1, pc2 = st.columns(2)

    with pc1:
        st.markdown("**🔒 鎖定一個期間**")
        with st.form("close_form"):
            from datetime import date as _d
            period_to_close = st.text_input(
                "期間 (YYYY-MM)",
                value=(_d.today().replace(day=1).strftime("%Y-%m"))
            )
            cl_notes = st.text_input("備註", "月結")
            if st.form_submit_button("🔒 確認鎖定", type="primary"):
                try:
                    pfdb.close_period(period_to_close,
                                        notes=cl_notes or None)
                    st.success(f"✅ 已鎖定 {period_to_close}")
                    st.rerun()
                except Exception as ex:
                    st.error(str(ex))

    with pc2:
        st.markdown("**🔓 重開（解鎖）期間**")
        if closed:
            periods = [cp["period"] for cp in closed]
            with st.form("reopen_form"):
                period_to_reopen = st.selectbox("選擇要解鎖的期間",
                                                  periods)
                if st.form_submit_button("🔓 確認解鎖",
                                          type="secondary"):
                    try:
                        pfdb.reopen_period(period_to_reopen)
                        st.warning(f"⚠️ 已解鎖 {period_to_reopen}")
                        st.rerun()
                    except Exception as ex:
                        st.error(str(ex))
        else:
            st.caption("（目前沒有鎖定的期間）")

# ============ Tab 4: 專案管理 ============
with tab4:
    st.caption("建立專案以追蹤特定開支（例如：旅行、裝修、副業）")

    projects = pfdb.list_projects()
    if projects:
        df_pj = pd.DataFrame([
            {
                "ID": p["project_id"],
                "圖示": p.get("icon") or "🎯",
                "名稱": p["name"],
                "狀態": p.get("status") or "active",
                "預算 (HKD)": p.get("total_budget") or 0,
                "開始日": p.get("start_date") or "—",
                "結束日": p.get("end_date") or "—",
                "說明": p.get("description") or "",
            }
            for p in projects
        ])
        sel_p = st.dataframe(df_pj, hide_index=True,
                              use_container_width=True,
                              on_select="rerun",
                              selection_mode="single-row",
                              column_config={
                                  "預算 (HKD)":
                                  st.column_config.NumberColumn(
                                      format="$%.2f"),
                              })
        if sel_p.selection.rows:
            pid = int(df_pj.iloc[sel_p.selection.rows[0]]["ID"])
            pcur = pfdb.get_project(pid)
            with st.expander(f"✏️ 編輯專案 #{pid}", expanded=True):
                with st.form(f"proj_edit_{pid}"):
                    p_name = st.text_input("名稱",
                                            pcur.get("name", ""))
                    p_status = st.selectbox(
                        "狀態", ["active", "completed", "archived"],
                        index=["active", "completed", "archived"].index(
                            pcur.get("status") or "active"))
                    p_budget = st.number_input(
                        "預算（HKD）",
                        value=float(pcur.get("total_budget") or 0),
                        format="%.2f", min_value=0.0)
                    p_icon = st.text_input("圖示 emoji",
                                            pcur.get("icon") or "🎯")
                    p_desc = st.text_area(
                        "說明",
                        pcur.get("description") or "")
                    ec1, ec2 = st.columns(2)
                    if ec1.form_submit_button("💾 儲存",
                                                type="primary"):
                        pfdb.update_project(
                            pid, name=p_name, status=p_status,
                            total_budget=p_budget, icon=p_icon,
                            description=p_desc)
                        st.success("✅ 已更新")
                        st.rerun()
                    if ec2.form_submit_button("🗑️ 刪除",
                                                type="secondary"):
                        pfdb.delete_project(pid)
                        st.success("已刪除")
                        st.rerun()
    else:
        st.info("尚未建立任何專案。")

    st.divider()
    with st.expander("➕ 新增專案"):
        with st.form("new_proj"):
            np_name = st.text_input("專案名稱",
                                      placeholder="例：京都旅行 2026")
            np_icon = st.text_input("圖示 emoji", "🎯")
            np_budget = st.number_input("預算（HKD，選填）",
                                          value=0.0, format="%.2f")
            np_desc = st.text_area("說明（選填）", "")
            if st.form_submit_button("✨ 建立專案", type="primary"):
                if np_name.strip():
                    pid = pfdb.create_project(
                        np_name.strip(),
                        description=np_desc or None,
                        total_budget=np_budget if np_budget > 0
                                     else None,
                        icon=np_icon or "🎯")
                    st.success(f"✅ 建立 #{pid}：{np_name}")
                    st.rerun()
                else:
                    st.error("名稱不能為空")
