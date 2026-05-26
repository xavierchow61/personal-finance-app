"""Package Personal Finance app 做 share ZIP。

EXCLUDE 私隱：
  - .env (你個 Gemini key)
  - *.db (你嘅單據 / 帳戶 data)
  - venv/, __pycache__/
  - outputs/ (你嘅 Excel exports)
  - testing/ (你嘅 sample invoices)

INCLUDE：
  - 全部 .py source
  - requirements.txt
  - run.bat / 啟動.bat
  - .env.example (template)
  - 新 setup README

用法：python make_share_zip.py
產出：個人理財_share.zip (~50 KB)
"""
import os
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

# Windows console UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

BASE = Path(__file__).parent
OUT_NAME = f"個人理財_share_{datetime.now().strftime('%Y%m%d')}.zip"
OUT_PATH = BASE / OUT_NAME

# Files / folders to EXCLUDE (relative paths or patterns)
EXCLUDE_DIRS = {"venv", "__pycache__", "outputs", "testing",
                  ".git", ".vscode", ".idea", "node_modules"}
EXCLUDE_FILES = {".env", "make_share_zip.py", OUT_NAME, "README.md"}
# README.md 由 SHARE_README 取代
EXCLUDE_EXT = {".db", ".db-journal", ".pyc"}


def should_include(rel_path: Path) -> bool:
    """Check if file should be in the share zip"""
    # Skip if any parent dir is excluded
    for part in rel_path.parts:
        if part in EXCLUDE_DIRS:
            return False
    # Skip excluded files
    if rel_path.name in EXCLUDE_FILES:
        return False
    # Skip excluded extensions
    if rel_path.suffix.lower() in EXCLUDE_EXT:
        return False
    # Skip any .zip files
    if rel_path.suffix.lower() == ".zip":
        return False
    return True


# === Setup README for recipient ===
SHARE_README = """# 個人理財 App — Setup 指南

歡迎使用呢個 app！跟住做就用得。

## 📦 你會收到啲咩

```
個人理財/
├── personal_finance/         (記賬 module)
├── extractor.py              (AI 提取)
├── gui.py                    (主 GUI)
├── ... 其他 .py source
├── run.bat                   ← 雙擊呢個啟動
├── requirements.txt
├── .env.example              ← Copy 做 .env，填你個 Gemini API key
└── README.md (呢個檔)
```

## 🚀 點 setup（一次性，5 分鐘）

### Step 1：裝 Python（如果未裝）

去 https://www.python.org/downloads/ 下載最新版 Python 3.10+
**安裝時記得剔「Add Python to PATH」** ← 好重要！

驗證：開 cmd 打 `python --version` → 應該見到 `Python 3.13.x`

### Step 2：攞免費 Gemini API key

去 https://aistudio.google.com/apikey
- 用 Google account 登入
- 按「Create API key」
- 複製個 key（似 `AIzaSy...` 開頭）

### Step 3：填入 .env 檔

1. 將 `.env.example` 複製成 `.env`（直接 rename 都可以）
2. 用 Notepad 打開
3. 將個 key 填入：
   ```
   GEMINI_API_KEY=AIzaSy...你個key
   ```
4. 儲存

### Step 4：雙擊 `run.bat`

- 第一次會自動建 virtual environment + 裝套件（**2-3 分鐘**）
- 之後每次開都係幾秒
- GUI 彈出 → 開始用

## 🎯 點用

### 提取單據
1. 「📋 單據紀錄」tab
2. 「📁 揀單據檔」（可多選）或者**直接拖檔入 window**
3. 「🚀 開始提取」
4. AI 自動 extract 入 invoices.db **同時自動入賬**到個人記賬 ledger

### 睇 dashboard
- 「📊 Dashboard」：Top 5 + 圓餅圖
- 「💰 個人記賬」→「📊 Overview」：總資產 / 負債 / 淨資產 + 月度支出
- 「💰 個人記賬」→「🎯 Budget」：設預算 + 超支警告
- 「💰 個人記賬」→「📈 Reports」：P&L / Balance Sheet

### 公司報銷
1. 揀張單 → 雙擊 Edit → expense_type 改「公司報銷」→ Save
2. 公司還咗錢之後：揀返張單 → 「✅ 標記已報銷」→ 彈窗揀收款 account

## ⚠️ 你嘅資料

- **全部本地**：`invoices.db` 同 `personal_finance.db` 留喺 app folder
- 第一次開會自動建空 DB
- 唔會 upload 去任何 cloud
- Backup 自己做（copy 嗰 2 個 .db 檔就得）

## ❓ 出 error 點算

| Error | 解決 |
|---|---|
| `Python not found` | Step 1 漏咗剔「Add to PATH」。重 install Python |
| `GEMINI_API_KEY not set` | Step 3 漏咗。 `.env` 一定要喺同一個 folder |
| `503 UNAVAILABLE` | Gemini 暫時忙，會自動 retry 5 次 |
| `429 RESOURCE_EXHAUSTED` | 免費 quota 用完。等下個月 / 升級 paid tier |

## 🆘 仲係用唔到

問返 send 你個 app 嗰個朋友。

---
*個人理財 App · 由 Xavier Chow 開發 · 100% 本地處理*
"""

# === Main ===
def main():
    print(f"📦 Building share ZIP: {OUT_NAME}")
    print(f"   Source: {BASE}")
    print()

    included = []
    excluded = []

    with zipfile.ZipFile(OUT_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        # Walk all files
        for root, dirs, files in os.walk(BASE):
            # Filter dirs in-place（防 walk 入去）
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                full = Path(root) / f
                rel = full.relative_to(BASE)
                if should_include(rel):
                    # Write 入 zip，inside top-level folder "個人理財/"
                    zf.write(full, arcname=Path("個人理財") / rel)
                    included.append(str(rel))
                else:
                    excluded.append(str(rel))

        # Add SHARE_README (replace existing README.md if any)
        readme_arcname = "個人理財/README.md"
        if "README.md" not in included:
            zf.writestr(readme_arcname, SHARE_README)
        # else: skip - 已經 included 原 README，唔加 dup

    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"✅ ZIP 整好：{OUT_PATH}")
    print(f"   📏 Size: {size_kb:.1f} KB")
    print(f"   📁 Included: {len(included)} files")
    print(f"   🚫 Excluded: {len(excluded)} files (隱私 / 不需要)")
    print()
    print("📋 Included files:")
    for f in sorted(included)[:30]:
        print(f"   ✓ {f}")
    if len(included) > 30:
        print(f"   ... 仲有 {len(included) - 30} 個")
    print()
    print("📋 Top excluded (確認冇 leak 私隱):")
    private_excl = [e for e in excluded
                     if any(x in e for x in [".env", ".db", "venv",
                                              "outputs", "testing"])]
    for f in sorted(private_excl)[:15]:
        print(f"   ✗ {f}")
    print()
    print(f"📤 而家可以 send {OUT_NAME} 俾朋友")
    print(f"   解壓後雙擊「個人理財/run.bat」即可")


if __name__ == "__main__":
    main()
