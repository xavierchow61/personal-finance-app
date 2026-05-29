"""程式設定 - Gemini API、路徑、類別清單"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Windows 中文 console UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

load_dotenv()

# === Gemini AI 設定 ===
# 優先順序：環境變數 (.env / OS) > Streamlit Cloud secrets
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    # 部署到 Streamlit Cloud 時，從 st.secrets 讀取
    try:
        import streamlit as st
        GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass
GEMINI_MODEL = "gemini-2.5-flash"  # 支援 Vision，速度快，免費 tier

# === 路徑 ===
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)
DB_PATH = BASE_DIR / "invoices.db"   # 預設路徑（沒登入時用）


def get_user_data_dir(user=None) -> Path:
    """取得指定用戶嘅 data 資料夾（僅 SQLite mode 用）。

    支援 user 為：
    - str：直接用作 folder name（舊版 secrets-based auth）
    - dict：抽 ["id"] 或 ["email"] 做 folder name（Supabase Auth）
    - None：自動從 Streamlit session 攞

    若已用 PostgreSQL（DATABASE_URL 設定咗），return BASE_DIR
    因為 PG 用單一共用 schema，無需 per-user folder。
    """
    # PostgreSQL 模式 → 共用 schema，唔需要 per-user folder
    if os.getenv("DATABASE_URL"):
        return BASE_DIR
    try:
        import streamlit as st
        if not os.getenv("DATABASE_URL"):
            db_url = st.secrets.get("DATABASE_URL", "")
            if db_url:
                return BASE_DIR
    except Exception:
        pass

    # SQLite 模式
    if user is None:
        try:
            import streamlit as st
            user = st.session_state.get("auth_user")
        except Exception:
            user = None

    # 抽 user folder name
    folder = None
    if isinstance(user, dict):
        # Supabase Auth dict format
        folder = user.get("id") or user.get("email")
        if folder and "@" in folder:
            # email 用 @ 前段做 folder
            folder = folder.split("@")[0]
    elif isinstance(user, str):
        folder = user

    if folder:
        d = BASE_DIR / "data" / folder
        d.mkdir(parents=True, exist_ok=True)
        return d
    return BASE_DIR


def get_invoices_db_path() -> Path:
    """目前用戶嘅 invoices.db 路徑"""
    return get_user_data_dir() / "invoices.db"


def get_personal_finance_db_path() -> Path:
    """目前用戶嘅 personal_finance.db 路徑"""
    return get_user_data_dir() / "personal_finance.db"

# === 類別預設清單（AI 會 reference 呢個 list，但可以加新類別）===
CATEGORIES = [
    "餐飲",       # 食肆、餐廳、外賣、咖啡
    "超市雜貨",   # 超市、便利店、街市
    "交通",       # 的士、巴士、地鐵、汽油、停車
    "服飾",       # 衫褲鞋襪
    "電子產品",   # 手機、電腦、家電
    "美容護理",   # 化妝品、護膚、剪髮
    "醫療藥物",   # 診所、藥房、醫院
    "娛樂",       # 戲院、KTV、遊戲
    "家居用品",   # 家具、廚具、清潔
    "教育學習",   # 書本、課程、文具
    "住宿旅遊",   # 酒店、機票、旅行社
    "通訊網絡",   # 電話費、上網費
    "水電煤",     # 水費、電費、煤氣
    "保險",       # 各類保險
    "其他",
]

# === 支援嘅圖片格式 ===
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"}
PDF_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | PDF_EXTENSIONS
