# 個人理財 Streamlit Web UI

Tkinter desktop app 嘅 **web 版**，跨裝置 access。

## 📂 結構

```
streamlit_app/
├── Home.py                 ← Dashboard (entry point)
├── pages/                  ← 5 個 sub-pages
│   ├── 1_📤_提取單據.py
│   ├── 2_📋_單據紀錄.py
│   ├── 3_💰_個人記賬.py
│   ├── 4_🎯_Budget.py
│   └── 5_📈_Reports.py
├── .streamlit/config.toml  ← Catppuccin Latte theme
├── _common.py              ← Shared utilities
└── run_streamlit.bat       ← Windows launcher
```

## 🚀 本地 run

**雙擊 `run_streamlit.bat`**

或者手動：
```powershell
cd "C:\Users\xavie\Extract invoice"
venv\Scripts\python.exe -m streamlit run streamlit_app\Home.py
```

開咗之後 → browser 自動跳 http://localhost:8501

## 📱 手機 / iPad access（同 wifi）

電腦行緊 Streamlit 之後：
1. 揾你電腦嘅 local IP（cmd 打 `ipconfig`，IPv4 例：`192.168.1.50`）
2. 手機 browser 打 `http://192.168.1.50:8501`
3. 即時用得（同個 DB）

## ☁️ Deploy 上 Streamlit Cloud（免費 tier）

### 注意 ⚠️

Streamlit Community Cloud **filesystem 係 ephemeral** — 每次 restart 都會 reset，sqlite write 唔會保留。

3 個方法處理：

### 方法 A：只做 read-only dashboard（最簡單）
- DB 留喺本地，定期 commit 上 GitHub
- Cloud 跑嘅 app 只 read DB，唔寫
- 手機可以隨時睇 net worth，但加新 entry 要返本地

### 方法 B：用 external Postgres（Supabase 免費 tier）
- Sign up Supabase（[supabase.com](https://supabase.com)）
- Create project → 攞 connection string
- 修改 `personal_finance/db.py` 用 psycopg / SQLAlchemy 連 Postgres
- DB 永久 persist

### 方法 C：用 GitHub gist 做 backup
- 每次 close app 自動 dump DB 上 gist
- 啟動時 restore
- 麻煩但可以 work

### Deploy steps（方法 A）

1. Push 上 GitHub：
   ```powershell
   cd "C:\Users\xavie\Extract invoice"
   git init
   git add .
   # 注意：.gitignore 要 exclude .env / *.db
   git commit -m "Initial commit"
   git remote add origin https://github.com/你/personal-finance.git
   git push -u origin main
   ```

2. 去 [share.streamlit.io](https://share.streamlit.io)：
   - Sign in with GitHub
   - "New app" → 揀你個 repo
   - Main file path：`streamlit_app/Home.py`
   - Advanced → Secrets：加 `GEMINI_API_KEY="你個key"`
   - Deploy

3. ~ 2 分鐘自動 build → 攞到 URL

4. 用 GitHub Actions 定期 push DB（write 唔 work，read 用最新嘅）

## ⚙️ 配置

### 改 port
`run_streamlit.bat` 入面 `--server.port 8501` 改成 `8502` 之類

### 改 theme
`.streamlit/config.toml` 入面 `primaryColor` / `backgroundColor`

### 限制 access（加密碼）
加 `streamlit-authenticator` 或者用簡單 password gate：
```python
# Home.py 頂部
pw = st.text_input("Password", type="password")
if pw != st.secrets["app_password"]:
    st.stop()
```

## 🔒 Privacy 注意

- `invoices.db` / `personal_finance.db` 有你嘅 financial data
- **唔好** commit 入 public GitHub repo
- 用 **private** repo + `.gitignore` exclude `.env` 同 `*.db`
- Streamlit Cloud 免費 tier 默認 public，要付費 plan 先有 private app

## 🆚 Streamlit vs Tkinter

| | Tkinter (gui.py) | Streamlit |
|---|---|---|
| 安裝 | 開機自動有 | pip install streamlit |
| 啟動速度 | 1-2 秒 | 5-10 秒 |
| 跨裝置 | ❌ 淨係部 PC | ✅ 手機 / iPad / 公司電腦 |
| 拖檔上傳 | ✅ tkinterdnd2 | ⚠️ file uploader（要按 button）|
| 圖預覽 panel | ✅ 即時 | ⚠️ st.image |
| Modal dialog | ✅ Toplevel | ⚠️ st.dialog / sidebar |
| Auto-open Excel | ✅ `os.startfile` | ❌ 只可以 download |
| 自動 sync | ✅ 即時 update | ⚠️ 要按 refresh / st.rerun |

**兩個共存最好** — 桌面用 Tkinter，手機用 Streamlit。
