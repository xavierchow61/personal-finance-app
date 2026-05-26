# 🚀 部署到 GitHub + Streamlit Cloud

## ⚠️ 重要警告

| 檔案 | 為何不能上傳 |
|------|------------|
| `.env` | 含 Gemini API key |
| `*.db` | 含**個人財務資料**（單據金額、商戶名、消費紀錄）|
| `.streamlit/secrets.toml` | 含部署用 API key |
| `outputs/`、`testing/` | 含個人 Excel 報表 |

✅ 上述檔案已加入 `.gitignore`，請**勿手動取消**。

> **強烈建議使用 Private repo**，即使資料沒有上傳，部署過程中如果失誤被推上去，至少不會被全世界看到。

---

## 📋 Part 1：上傳到 GitHub

### Step 1：建立 GitHub repo

1. 上 https://github.com/new
2. Repository name：`personal-finance-app`（或自取）
3. **務必選「Private」**（不要選 Public！）
4. **不要勾**「Add README / .gitignore / license」（我們本地已有）
5. 按 **Create repository**

### Step 2：本地 git 設定（首次）

開 PowerShell（在 `C:\Users\xavie\Extract invoice`）：

```powershell
# 進入專案資料夾
cd "C:\Users\xavie\Extract invoice"

# 設定 git 身份（首次而已）
git config --global user.name "你的名字"
git config --global user.email "xavierchow63@gmail.com"

# 初始化 git
git init
git branch -M main

# 先測試一次 — 確認沒有不該上傳的檔案
git status
```

⚠️ **檢查 `git status` 輸出**：
- ✅ 應該看到：`config.py`、`streamlit_app/`、`personal_finance/`、`requirements.txt`、`.gitignore`、`README.md` 等
- ❌ **絕對不可看到**：`.env`、`invoices.db`、`personal_finance.db`、`venv/`、`outputs/`

如果看到禁止項目 → **立即停止**，告訴我。

### Step 3：首次 commit + push

```powershell
# 加入所有被追蹤的檔案（.gitignore 會自動排除機密檔）
git add .

# 再次確認沒有 .env 或 .db
git status

# Commit
git commit -m "Initial commit - Personal Finance with Doraemon theme"

# 連結到 GitHub（換成你的 username + repo 名）
git remote add origin https://github.com/你的username/personal-finance-app.git

# 推上去
git push -u origin main
```

第一次推時，GitHub 會要你授權登入。

---

## ☁️ Part 2：部署到 Streamlit Cloud

### Step 1：登入 Streamlit Cloud

1. 上 https://share.streamlit.io/
2. 用你的 **GitHub 帳號** 登入並授權
3. 授權時記得**勾選你的 private repo 存取權**

### Step 2：建立新 App

1. 按 **New app** → **Deploy a public app from GitHub**
2. 填寫：
   | 欄位 | 填什麼 |
   |------|--------|
   | Repository | `你的username/personal-finance-app` |
   | Branch | `main` |
   | Main file path | **`streamlit_app/Home.py`** |
   | App URL | 自訂（例如 `xavier-finance`）|

### Step 3：設定 Secrets（API key）

部署前在 **Advanced settings → Secrets** 貼入：

```toml
GEMINI_API_KEY = "你的_gemini_api_key"
```

從 https://aistudio.google.com/apikey 拿 key（**重新生一個新的**，不要用你本機 `.env` 那條，避免共用）。

### Step 4：按 Deploy

第一次部署需要 3~5 分鐘安裝 dependencies。完成後會給你一個 URL：

```
https://xavier-finance.streamlit.app
```

---

## ⚠️ Part 3：Streamlit Cloud 限制（請務必了解）

### 🔴 SQLite 資料**不會永久保存**

Streamlit Cloud 使用**短暫磁碟（ephemeral disk）**，意思係：
- 每次 app **重啟（每幾天 / 大概一週一次）** 都會清空所有 `*.db`
- 你上傳的單據、設定的預算、入賬紀錄全部會消失

### 🟢 解決方案

#### 選項 A：純展示用（推薦先試）
- 雲端版只用來「demo 給朋友 / 同事」
- 真正的數據仍在本機（雙擊 `run_streamlit.bat`）
- 雲端版每次重啟「乾淨開始」

#### 選項 B：用雲端資料庫（要改 code）
把 SQLite 換成：
- **Turso**（SQLite 雲端版，免費 1GB）— 改動最少
- **Supabase PostgreSQL**（免費 500MB）
- **Neon Postgres**（免費）

需要的話告訴我，我幫你改 `db.py` 抽象層。

#### 選項 C：手動同步 DB
- 本機 export 為 JSON
- 上雲時 import
- 但這違背「線上同步」的初衷

---

## 🛡️ Part 4：常見錯誤排除

### ❌ `ModuleNotFoundError: No module named 'streamlit_app'`

**原因**：Streamlit Cloud 預設 working directory 是 repo root，但你的 imports 用了 `streamlit_app._common`。

**解法**：已經在 `_common.py` 處理了 `sys.path`，應該不會發生。如果發生，告訴我。

### ❌ `GEMINI_API_KEY 未設定`

**原因**：忘了在 Streamlit Cloud Secrets 設定。

**解法**：上 Streamlit Cloud → 你的 app → **Manage app → Secrets** → 貼上：
```toml
GEMINI_API_KEY = "..."
```
按 Save，app 會自動重啟。

### ❌ Push 時 `.env` 被擋

**原因**：之前不小心 commit 過 `.env`。

**解法**：
```powershell
git rm --cached .env
git commit -m "Remove .env from tracking"
git push
```
**然後立即去 Google AI Studio 把該 API key 撤銷重新生成！**

### ❌ 字體不支援中文

Streamlit Cloud 沒裝中文字體。
**解法**：通常瀏覽器本身有中文字體，會自動 fallback。如果你發現亂碼，告訴我。

---

## 📦 Part 5：更新部署（之後改 code 後）

```powershell
cd "C:\Users\xavie\Extract invoice"
git add .
git commit -m "Update: 改了 XXX"
git push
```

推上去後 Streamlit Cloud 會**自動偵測到 commit** 並重新部署（約 1-2 分鐘）。

---

## ✅ 完成檢查清單

部署前確認：

- [ ] `.gitignore` 包含 `.env`、`*.db`、`.streamlit/secrets.toml`
- [ ] `git status` 沒看到任何 `.env` 或 `.db` 檔案
- [ ] `requirements.txt` 內容正確（不是亂碼）
- [ ] GitHub repo 是 **Private**
- [ ] Streamlit Cloud 已設定 `GEMINI_API_KEY` Secret
- [ ] Streamlit Cloud Main file path = `streamlit_app/Home.py`

---

有問題歡迎截圖問！
