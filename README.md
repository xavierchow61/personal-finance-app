# 📃 商店單據 AI 提取器

用 Gemini Vision 由商店單據（相片 / PDF）自動提取資料，存入 Excel 同 dashboard。

## 功能

- 🤖 **AI 自動辨識** - Gemini 2.5 Flash Vision 識別購買日期、商店、類別、金額、產品
- 📁 **多格式支援** - JPG / PNG / BMP / WebP / TIFF / PDF
- 🖱️ **Drag & Drop** - 直接拖檔入 window 自動加入待處理
- 📷 **單據預覽** - 揀一行 → 右邊顯示原張單，方便對住資料 verify
- 📦 **批量處理** - 一次過處理整個資料夾
- 🚫 **重複偵測** - 同一張單 import 兩次自動跳過
- 🏷️ **自動分類** - 餐飲、超市、交通、醫療等 15 個常用類別
- ✏️ **可編輯** - GUI 入面雙擊任何一行直接改
- 🏢 **報銷追蹤** - 標記「私人 / 公司報銷 / 可扣稅」、追蹤待報銷金額
- 📊 **Excel Dashboard** - 圓餅圖、Top 5、KPI、未報銷總額
- 📑 **報銷單 sheet** - 按月份分組嘅公司報銷單，方便交俾 HR
- 💾 **SQLite 儲存** - 所有資料本地留底
- 📄 **PDF → Word 轉換** - 額外功能：自動偵測文字 PDF / 掃描 PDF，分別用 pdf2docx（秒級）或 Gemini AI 轉做 .docx

## 安裝

### 1. Python 環境
需要 Python 3.10+。雙擊 `啟動.bat` 會自動建立 venv 同安裝套件。

或者手動：
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Gemini API Key

1. 去 https://aistudio.google.com/apikey 攞免費 key
2. 將 `.env.example` 複製成 `.env`
3. 填入：
   ```
   GEMINI_API_KEY=你個key
   ```

### 3. PDF 支援

✅ PDF 已內建支援，**唔需要安裝任何外部軟件**（用 `pypdfium2` 純 Python wheel）。

## 點用

### GUI（推薦）
雙擊 `啟動.bat`，或者：
```powershell
python gui.py
```

步驟：
1. 按 **📁 揀單據檔** 或 **📂 揀整個資料夾**
2. 按 **🚀 開始提取**
3. 喺「📋 單據紀錄」tab 睇結果，雙擊改錯
4. 按 **📊 開 Excel Dashboard** 自動匯出 + 開檔

### 命令列
```powershell
# 單張
python main.py receipt.jpg

# 整個資料夾
python main.py receipts_folder/

# 提取後即時匯出 Excel
python main.py receipts_folder/ --export

# 只匯出（用 DB 已有資料）
python main.py --export-only
```

## Excel Dashboard 內容

匯出嘅 `.xlsx` 包含 2 個 sheet：

**📊 Dashboard**
- KPI cards：總單據數 / 總支出 / 平均每單
- 🏆 Top 5 最貴單據
- 💰 Top 5 類別支出
- 🥧 各類別佔比圓餅圖
- 📊 Top 5 類別 bar chart

**📋 單據明細**
- 全部單據完整資料，可篩選 / 排序

## 📄 PDF → Word 轉換

呢個 app 仲有額外功能：將任何 PDF 轉成 Word 檔。GUI 開咗之後揀「📄 PDF → Word」tab。

### 哲學：內容準確 > 視覺漂亮

優先用 **pdf2docx** 直接 extract PDF 原文（100% 保留），然後 **post-process** 自動修常見格式問題：
- 重複嘅 page header / footer / disclaimer → 剩第一個
- 太緊嘅 line spacing 導致文字重疊 → 強制 ≥ 1.15
- Text box 內部 spacing 放鬆

AI mode 只係 fallback 俾真.掃描 PDF（冇 text layer），**唔建議用喺正常文字 PDF**，
因為 Gemini 會 reinterpret 內容，可能 over-summarize / 漏 data / hallucinate。

| Mode | 點 work | 速度 | 內容準確度 |
|------|---------|------|---------|
| 🤖 自動（推薦）| 文字 PDF → pdf2docx + post-process；掃描 PDF → AI | 秒級（文字）/ 10-30s/頁（掃描） | **100%（文字 PDF）** |
| ⚡ 快速 + 修格式 | 強制 pdf2docx + post-process | 秒級 | **100%** |
| 🧠 AI（小心用）| 強制 Gemini AI 重讀 | 10-30s/頁 | 70-90%（可能漏 / 改）|

**命令列用法：**
```powershell
python pdf_to_word.py input.pdf                   # 自動 mode，輸出 input.docx
python pdf_to_word.py input.pdf -o out.docx       # 指定輸出
python pdf_to_word.py scanned.pdf --mode ai       # 真.掃描件先用 AI
```

### Post-process 修咗咩

`docx_postprocess.py` 對 pdf2docx 輸出做：
1. **`remove_repeated_boilerplate`** — 出現 ≥ 3 次嘅長段落（≥ 30 字）剩第一個
2. **`fix_line_spacing`** — 全部段落 line spacing ≥ 1.15，space-after ≥ 2pt
3. **`relax_textbox_positioning`** — text box 入面段落都加 spacing

可以單獨用：
```powershell
python docx_postprocess.py any_file.docx
```

## 💰 個人記賬 / Personal Finance

GUI 入面有「💰 個人記賬」tab，係**雙式記賬 (double-entry) ledger** 嘅 personal finance system：

### Sub-tabs
1. **📊 Overview** — 總資產 / 總負債 / 淨資產 / 本月支出 KPI cards + 各 account 餘額 + 本月分類支出 bar chart
2. **🎯 Budget** — Budget vs Actual table（超支標 ⚠️）+ 過去 12 個月 trend
3. **🏦 Accounts** — 管理 14 個 expense categories + 現金/Visa/MC/HSBC/八達通 等 accounts
4. **🎯 Projects** — 自定 project（例「日本旅行 2026」）+ project budget tracking
5. **📜 Transactions** — 最近 100 個 journal entries

### 自動入賬
- Extract Invoice 提取一張單 → **自動 post journal entry 入 ledger**
- 按 `payment_method` 智能估 account（PayMe → HSBC、Visa → HSBC_VISA、現金 → CASH 等）
- 雙式記賬：`Dr 餐飲 $100 / Cr HSBC_VISA $100`
- 信用卡 spending 會自動增加 liability balance（你欠卡幾錢）

### 預設 setup
第一次開 GUI 自動 seed：
- 14 個 expense category：餐飲 🍱 / 超市雜貨 🛒 / 交通 🚇 / 服飾 👔 / 電子產品 💻 / 美容護理 💄 / 醫療藥物 🏥 / 娛樂 🎬 / 家居用品 🏠 / 教育學習 📚 / 住宿旅遊 ✈️ / 通訊網絡 📱 / 水電煤 💡 / 保險 🛡️ / 其他 📦
- Sample assets：現金 💵 / 八達通 🚇 / HSBC 戶口 🏦
- Sample liabilities：HSBC Visa 💳 / Citi MasterCard 💳
- Sample income：人工 💼 / 紅利 🎁 / 投資回報 📈

### Storage
- 獨立 SQLite DB：`personal_finance.db`（同 `invoices.db` 分開）
- Schema：accounts / journal_entries / journal_lines / budgets / projects

### Manual entry
「📜 Transactions」tab 入面按「➕ 加手動 entry」可以記：
- 人工 (Dr HSBC_BANK / Cr SALARY)
- 信用卡找數 (Dr HSBC_VISA / Cr HSBC_BANK)
- 賬戶轉移 (Dr Account A / Cr Account B)

## 💰 Accounting App (Sub-app)

完整嘅 ERP 系統喺 [`accounting_app/`](accounting_app/) 入面，包含：
- **Finance**：General Ledger、AR、AP、Expense Reports、Budget
- **HR / Sourcing / Inventory / Admin** 等 module

啟動方法：
1. **由 GUI launch（推薦）**：GUI 右上角按 **「💰 開 Accounting App」**
   - 開**桌面 window**（無 browser bar），用 pywebview 包 Streamlit
   - 睇起嚟同普通桌面 app 一樣
   - 關 Extract Invoice GUI 時自動殺埋 sub-app
2. **獨立 CLI**（browser mode）：
   ```powershell
   python accounting_launcher.py start
   ```
3. **原裝 batch 檔**：直接行 `accounting_app/run.bat`

URL：http://localhost:8502（如果要喺 browser 開）

⚠️ 第一次啟動要 10-30 秒（streamlit 初始化），之後 reload 快。
⚠️ 桌面 window mode 需要 **Edge WebView2 Runtime**（Windows 10 1809+ 預裝；如果未裝去 https://developer.microsoft.com/microsoft-edge/webview2/ 攞 free runtime）

## 📒 Trial Balance Auto-Updater

GUI 入面有「📒 TB 更新」tab。每月由會計軟件 export 出嘅 TB → 1 click 更新你嘅 master TB 檔。

**workflow：**
1. 揀 TB Master Excel
2. 揀 source（會計軟件 export）
3. 「🔍 自動偵測 + 確認」→ Dialog 揀 account col + amount cols → OK
4. 「💾 儲存呢個 mapping」→ 存 `.json`
5. 按「🚀 1-click 更新 TB」→ 出 updated TB 入 outputs/

**之後每月**：
- 揀新 source → 「📂 載入過往 mapping」→ 按「🚀 更新」（30 秒搞掂）

**特點：**
- ✅ **保留原 TB formula**（subtotal、grand total 唔會壞）
- ✅ **保留 formatting**（標題、底色、字體）
- ✅ **變動 cell 標黃色**，肉眼即時見到改咗咩
- ✅ 第一個 sheet 自動加「📋 Update Report」：總結 + 詳細變動 + missing/new accounts
- ✅ Mapping JSON 可重用，無限 update

**命令列：**
```powershell
python tb_updater.py update master_tb.xlsx new_source.csv --mapping tb_mapping.json
```

### 📝 提取 Cell 附注（額外功能）

GUI TB tab 入面底部有「📝 提取附注 → Excel」section。

掃描任何 Excel 入面所有有 cell comment / note 嘅 cell，輸出 Excel 報告：

| Sheet | Cell | Account Code | Account Name | Column | Value | Comment | Author |
|-------|------|--------------|--------------|--------|-------|---------|--------|
| TB    | C2   | 1001         | Cash         | Debit  | 55,000.00 | Year-end adj: +$5k cash count diff | Auditor Wong |
| TB    | C3   | 1100         | AR           | Debit  | 35,000.00 | Includes $2k from ABC Co... | Xavier |

**用法：**
- 自動估 account code / name column
- 可揀「掃全部 sheets」
- 命令列：
  ```powershell
  python tb_updater.py extract-comments your_tb.xlsx --all-sheets
  ```

## 📊 PDF → Excel（表格提取）

GUI 入面有「📊 PDF → Excel」tab，由 PDF 提取 table 出 Excel。每個 table 一個 sheet。

| Mode | 適合 | 速度 |
|---|---|---|
| 🤖 自動（推薦）| 先試 pdfplumber，攞唔到就轉 AI | 秒級 / 10-30s/頁 |
| ⚡ Fast (pdfplumber) | 電子發票、有真.文字 table 嘅 PDF | 秒級 |
| 🧠 AI (Gemini) | 銀行 statement、scan 件（table 係圖片渲染）| 10-30s/頁 |

**例**：滙豐 / 恆生銀行 statement 啲交易表通常係圖片渲染，必須用 AI mode。

```powershell
python pdf_to_excel.py statement.pdf
python pdf_to_excel.py statement.pdf --mode ai
```

## 🖼️ 圖片 → Word / PDF / Markdown

GUI 入面有「🖼️ 圖片 → 文件」tab，可以將圖片（JPG/PNG/BMP/WebP/TIFF）OCR + 格式還原成 Word、PDF 或 Markdown。

**功能：**
- 多張圖片自動合併成一個檔案（每張之間 page break）
- 識別中/英文、手寫字、表格、bullet list、標題、星級
- 🆕 **公式 → Word equation**：v=S/t 之類嘅公式會由 Gemini extract 成 LaTeX，再經 MS Word 嘅 MML2OMML.xsl 轉做 Word 原生 equation（可以喺 Word 編輯）
- 🆕 **圖 / Diagram 嵌入**：手繪嘅示意圖會由 Gemini 標 bbox 坐標，自動由原圖裁出嚟嵌入 docx
- 用緊 Gemini 2.5 Flash Vision（同 Chandra/Qwen3-VL 同類技術，但唔需要 GPU）

**輸出格式（可多選）：**
- 📄 **Word (.docx)** — 100% 可編輯
- 📕 **PDF** — 需要安裝 MS Word（程式自動 call MS Word COM 轉換）
- 📝 **Markdown (.md)** — 適合 ChatGPT / Obsidian / GitHub

**命令列用法：**
```powershell
# 單張圖片 → Word
python image_to_doc.py photo.jpg

# 多張 → 合併 PDF
python image_to_doc.py page1.jpg page2.jpg page3.jpg --format pdf

# 整個資料夾 → 三種格式都出
python image_to_doc.py photos_folder/ --format all
```

## 檔案結構

```
Extract invoice/
├─ config.py           # Gemini API、類別清單
├─ extractor.py        # Gemini Vision 提取
├─ database.py         # SQLite 儲存
├─ excel_exporter.py   # Excel + Dashboard + 圓餅圖
├─ gui.py              # Tkinter GUI
├─ main.py             # CLI 入口
├─ 啟動.bat            # Windows 快捷啟動
├─ requirements.txt
├─ .env.example
├─ outputs/            # 匯出嘅 Excel
└─ invoices.db         # SQLite DB
```

## 自定類別

改 `config.py` 入面個 `CATEGORIES` list 就得。
