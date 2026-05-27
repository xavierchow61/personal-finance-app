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
    flt_col1, flt_col2 = st.columns(2)
    type_filter = flt_col1.selectbox(
        "篩選類型",
        ["（全部）"] + list(ACCOUNT_TYPE_LABELS.values()),
        key="acc_type_filter",
    )
    show_inactive = flt_col2.checkbox(
        "包含已停用的帳戶", value=False,
        key="acc_show_inactive",
    )

    # 取資料
    all_accs = pfdb.list_accounts(active_only=not show_inactive)
    if type_filter != "（全部）":
        # 反查 type code
        type_code = next(
            (k for k, v in ACCOUNT_TYPE_LABELS.items()
             if v == type_filter), None)
        if type_code:
            all_accs = [a for a in all_accs
                         if a["account_type"] == type_code]

    if all_accs:
        df_acc = pd.DataFrame([
            {
                "代碼": a["code"],
                "圖示": a.get("icon") or "",
                "名稱": a["name"],
                "類型": ACCOUNT_TYPE_LABELS.get(
                    a["account_type"], a["account_type"]),
                "幣別": a.get("currency") or "HKD",
                "期初餘額": a.get("opening_balance") or 0,
                "排序": a.get("sort_order") or 0,
                "啟用": "✅" if a.get("is_active") else "❌",
            }
            for a in all_accs
        ])
        sel_acc = st.dataframe(
            df_acc, hide_index=True, use_container_width=True,
            on_select="rerun", selection_mode="single-row",
            column_config={
                "期初餘額": st.column_config.NumberColumn(
                    format="$%.2f"),
            },
        )

        # === 編輯選定帳戶 ===
        if sel_acc.selection.rows:
            sel_code = df_acc.iloc[sel_acc.selection.rows[0]]["代碼"]
            acc = pfdb.get_account(sel_code)
            if acc:
                st.divider()
                with st.expander(
                    f"✏️ 編輯帳戶：{acc.get('icon') or ''} "
                    f"{acc['name']} ({acc['code']})",
                    expanded=True,
                ):
                    with st.form(f"edit_acc_{sel_code}"):
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            new_name = st.text_input(
                                "顯示名稱", acc.get("name", ""))
                            new_icon = st.text_input(
                                "圖示 emoji（選填）",
                                acc.get("icon") or "",
                                placeholder="例：🏦 💳 🛒")
                            new_currency = st.selectbox(
                                "幣別",
                                ["HKD", "USD", "JPY", "CNY", "EUR",
                                  "GBP", "AUD", "SGD", "TWD"],
                                index=(["HKD", "USD", "JPY", "CNY",
                                        "EUR", "GBP", "AUD", "SGD",
                                        "TWD"].index(
                                    acc.get("currency") or "HKD")
                                    if (acc.get("currency") or "HKD")
                                       in ["HKD", "USD", "JPY", "CNY",
                                           "EUR", "GBP", "AUD", "SGD",
                                           "TWD"] else 0),
                            )
                        with ec2:
                            new_opening = st.number_input(
                                "期初餘額",
                                value=float(acc.get(
                                    "opening_balance") or 0),
                                format="%.2f",
                            )
                            new_sort = st.number_input(
                                "排序（小→大）",
                                value=int(acc.get("sort_order") or 0),
                                step=1,
                            )
                            new_active = st.checkbox(
                                "啟用此帳戶",
                                value=bool(acc.get("is_active")),
                            )
                        new_notes = st.text_area(
                            "備註", acc.get("notes") or "")

                        bcol1, bcol2 = st.columns(2)
                        if bcol1.form_submit_button(
                                "💾 儲存", type="primary",
                                use_container_width=True):
                            try:
                                pfdb.upsert_account(
                                    code=sel_code,
                                    name=new_name,
                                    account_type=acc["account_type"],
                                    opening_balance=new_opening,
                                    currency=new_currency,
                                    sort_order=new_sort,
                                    icon=new_icon or None,
                                    notes=new_notes or None,
                                )
                                # 處理 is_active（upsert 無此欄位，
                                # 直接 raw SQL）
                                from personal_finance import db as _pfdb
                                with _pfdb._conn() as _c:
                                    _c.execute(
                                        "UPDATE accounts "
                                        "SET is_active=? WHERE code=?",
                                        (1 if new_active else 0,
                                         sel_code),
                                    )
                                st.success(f"✅ 已更新 {sel_code}")
                                st.rerun()
                            except Exception as ex:
                                st.error(f"更新失敗：{ex}")

                        if bcol2.form_submit_button(
                                "🗑️ 刪除", type="secondary",
                                use_container_width=True):
                            try:
                                pfdb.delete_account(sel_code)
                                st.success(f"已刪除 {sel_code}")
                                st.rerun()
                            except Exception as ex:
                                st.error(
                                    f"❌ 刪除失敗（可能有分錄關聯）：\n\n"
                                    f"{ex}\n\n"
                                    f"💡 建議改為「停用」（取消勾選"
                                    f"「啟用此帳戶」）。"
                                )
    else:
        st.info("尚無符合條件的帳戶。")

    # === 新增帳戶 ===
    st.divider()
    with st.expander("➕ 新增帳戶", expanded=False):
        with st.form("new_acc"):
            nc1, nc2 = st.columns(2)
            with nc1:
                na_code = st.text_input(
                    "帳戶代碼（英文 / 底線，建立後不能改）",
                    placeholder="例：ZA_BANK / CITI_VISA / FOOD",
                )
                na_name = st.text_input(
                    "顯示名稱",
                    placeholder="例：ZA Bank / Citi Visa / 餐飲",
                )
                na_type_label = st.selectbox(
                    "帳戶類型",
                    list(ACCOUNT_TYPE_LABELS.values()),
                )
                na_type = next(
                    (k for k, v in ACCOUNT_TYPE_LABELS.items()
                     if v == na_type_label), "asset")
            with nc2:
                na_icon = st.text_input(
                    "圖示 emoji（選填）",
                    placeholder="例：🏦 💳 🛒",
                )
                na_opening = st.number_input(
                    "期初餘額", value=0.0, format="%.2f",
                )
                na_currency = st.selectbox(
                    "幣別",
                    ["HKD", "USD", "JPY", "CNY", "EUR",
                      "GBP", "AUD", "SGD", "TWD"],
                )
            na_notes = st.text_input("備註（選填）", "")

            if st.form_submit_button(
                    "✨ 建立帳戶", type="primary",
                    use_container_width=True):
                # 驗證
                if not na_code.strip():
                    st.error("代碼不能為空")
                elif not na_name.strip():
                    st.error("名稱不能為空")
                elif pfdb.get_account(na_code.strip().upper()):
                    st.error(f"代碼「{na_code}」已存在")
                else:
                    try:
                        pfdb.upsert_account(
                            code=na_code.strip().upper(),
                            name=na_name.strip(),
                            account_type=na_type,
                            opening_balance=na_opening,
                            currency=na_currency,
                            icon=na_icon or None,
                            notes=na_notes or None,
                        )
                        st.success(
                            f"✅ 建立成功：{na_icon or ''} {na_name} "
                            f"({na_code.upper()})"
                        )
                        st.rerun()
                    except Exception as ex:
                        st.error(f"建立失敗：{ex}")


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

    cards = pfdb.list_credit_cards()

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
                                "回贈 / 里數",
                                value=card.get("rewards") or "",
                                placeholder="例：1% 現金回贈 / 飛行里數",
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
                        "回贈 / 里數",
                        placeholder="例：1% 現金回贈",
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

        # === 編輯選定對應（含預設值都可改）===
        if sel.selection.rows:
            sel_row = df_al.iloc[sel.selection.rows[0]]
            sel_id = int(sel_row["ID"])
            sel_kw = sel_row["關鍵字（部份匹配）"]
            sel_acc_code = sel_row["對應帳戶"]
            sel_notes_val = sel_row["備註"]

            st.divider()
            with st.expander(
                f"✏️ 編輯對應 #{sel_id}：{sel_kw} → {sel_acc_code}",
                expanded=True,
            ):
                _accs_edit = pfdb.list_accounts(
                    account_type="asset") + \
                    pfdb.list_accounts(account_type="liability")
                _acc_opts_edit = {
                    f"{a['code']} - {a['name']}": a["code"]
                    for a in _accs_edit
                }
                _opt_list = list(_acc_opts_edit.keys())
                # 揾返現時 account 嘅 label
                cur_label = next(
                    (lbl for lbl, c in _acc_opts_edit.items()
                     if c == sel_acc_code),
                    None,
                )

                with st.form(f"edit_alias_{sel_id}"):
                    new_kw = st.text_input(
                        "關鍵字（會用 LIKE 模糊匹配）",
                        value=sel_kw,
                    )
                    new_acc_label = st.selectbox(
                        "對應到帳戶",
                        _opt_list,
                        index=(_opt_list.index(cur_label)
                                if cur_label in _opt_list else 0),
                    )
                    new_notes = st.text_input(
                        "備註（選填）", value=sel_notes_val or "",
                    )

                    eb1, eb2 = st.columns(2)
                    save_clicked = eb1.form_submit_button(
                        "💾 儲存修改", type="primary",
                        use_container_width=True,
                    )
                    del_clicked = eb2.form_submit_button(
                        "🗑️ 刪除", type="secondary",
                        use_container_width=True,
                    )

                    if save_clicked:
                        new_kw_s = new_kw.strip()
                        if not new_kw_s:
                            st.error("關鍵字不能為空")
                        else:
                            try:
                                # 如關鍵字有改 → 先刪舊嘅
                                # （因 add_payment_alias 用 lower
                                # 比較，會 conflict）
                                if (new_kw_s.lower() !=
                                        sel_kw.lower()):
                                    pfdb.delete_payment_alias(sel_id)
                                # 寫入（會 ON CONFLICT update）
                                pfdb.add_payment_alias(
                                    new_kw_s,
                                    _acc_opts_edit[new_acc_label],
                                    new_notes or None,
                                )
                                st.success(
                                    f"✅ 已更新：{new_kw_s} → "
                                    f"{_acc_opts_edit[new_acc_label]}"
                                )
                                st.rerun()
                            except Exception as ex:
                                st.error(f"更新失敗：{ex}")

                    if del_clicked:
                        try:
                            pfdb.delete_payment_alias(sel_id)
                            st.success(f"已刪除 #{sel_id}")
                            st.rerun()
                        except Exception as ex:
                            st.error(str(ex))
    else:
        st.info("尚未設定任何對應。系統會用 fallback 自動分類。")

    st.divider()
    al_c1, al_c2 = st.columns(2)
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

    with st.expander("➕ 新增對應"):
        with st.form("alias_form"):
            accs = pfdb.list_accounts(account_type="asset") + \
                   pfdb.list_accounts(account_type="liability")
            acc_opts = {f"{a['code']} - {a['name']}": a["code"]
                        for a in accs}
            kw = st.text_input("關鍵字（會用 LIKE 模糊匹配）",
                                placeholder="例：PayMe / HSBC / Visa")
            acc_label = st.selectbox("對應到帳戶",
                                      list(acc_opts.keys()))
            al_notes = st.text_input("備註（選填）", "")
            if st.form_submit_button("💾 新增對應", type="primary"):
                if kw.strip():
                    try:
                        pfdb.add_payment_alias(
                            kw.strip(), acc_opts[acc_label],
                            al_notes or None)
                        st.success(
                            f"✅ {kw} → {acc_opts[acc_label]}")
                        st.rerun()
                    except Exception as ex:
                        st.error(str(ex))

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
