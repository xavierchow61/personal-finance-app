"""使用者認證 — 多用戶 + 各自 database

用戶設定方式：
1. Streamlit Cloud：secrets.toml 加入
   [auth.users]
   xavier = "password123"
   mary   = "anotherpwd"

2. 本機：在 .streamlit/secrets.toml 加同樣內容

3. 若完全沒設定 → 不要求登入（向後兼容，本地開發用）

Session：
- 登入後 st.session_state["auth_user"] = username
- 所有 DB 操作會用 data/{username}/*.db
"""
from __future__ import annotations

import hashlib
import streamlit as st


# ============================================================
# 用戶設定 / 密碼驗證
# ============================================================

def _get_users() -> dict[str, str]:
    """讀取所有用戶設定 — {username: password_or_hash}

    支援格式：
    - 純文字密碼："password123"
    - SHA256 雜湊：以 "sha256:" 開頭，例如 "sha256:abc123..."
    """
    try:
        # Streamlit secrets（[auth.users] section）
        auth_section = st.secrets.get("auth", {})
        users = auth_section.get("users", {}) if hasattr(
            auth_section, "get") else dict(auth_section).get("users", {})
        return dict(users) if users else {}
    except Exception:
        return {}


def _verify_password(plain: str, stored: str) -> bool:
    """驗證密碼。支援純文字或 sha256: 開頭嘅雜湊"""
    if not stored:
        return False
    if stored.startswith("sha256:"):
        expected = stored[7:]
        actual = hashlib.sha256(plain.encode("utf-8")).hexdigest()
        return actual == expected
    # 純文字（簡單但夠用）
    return plain == stored


def hash_password(plain: str) -> str:
    """產生可貼入 secrets 的雜湊字串（如需更安全）"""
    return "sha256:" + hashlib.sha256(plain.encode("utf-8")).hexdigest()


# ============================================================
# Session 狀態
# ============================================================

def get_current_user() -> str | None:
    """取得目前登入用戶名。未登入則回 None"""
    return st.session_state.get("auth_user")


def is_authenticated() -> bool:
    return bool(get_current_user())


def login(username: str, password: str) -> bool:
    """嘗試登入。成功 → set session + 回 True；失敗 → 回 False"""
    users = _get_users()
    if username in users and _verify_password(password, users[username]):
        st.session_state["auth_user"] = username
        return True
    return False


def logout():
    """登出 — 清除 session"""
    for key in list(st.session_state.keys()):
        if key.startswith("auth_") or key in ("user_db_path",):
            del st.session_state[key]


# ============================================================
# 登入閘門
# ============================================================

def require_login():
    """喺每個頁面開頭呼叫。

    - 若 secrets 沒有設用戶 → 跳過（本地開發向後兼容）
    - 若未登入 → 渲染登入畫面 + st.stop()
    - 若已登入 → 繼續
    - 處理 ?logout=1 query param（用 HTML link 登出）
    """
    # 偵測登出 query param（由側欄登出 link 觸發）
    try:
        if st.query_params.get("logout") == "1":
            logout()
            st.query_params.clear()
            st.rerun()
    except Exception:
        pass

    users = _get_users()
    if not users:
        # 沒設定用戶 = 不要求登入（本地 / demo 模式）
        return
    if is_authenticated():
        return
    _render_login_page()
    st.stop()


def _render_login_page():
    """全屏登入畫面 — 哆啦藍漸層 + 玻璃卡"""
    from style import inject_glass_style, PALETTE
    inject_glass_style()

    # 隱藏側欄
    st.markdown(
        '<style>[data-testid="stSidebar"]{display:none !important;}'
        '[data-testid="stSidebarCollapseButton"]{display:none !important;}'
        '</style>',
        unsafe_allow_html=True,
    )

    # 中央卡片
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown(
            f"""
            <div style="
                background: white;
                border: 2px solid rgba(0,166,224,0.3);
                border-radius: 24px;
                padding: 2.5rem 2rem 1.5rem 2rem;
                margin-top: 3rem;
                box-shadow: 0 20px 60px rgba(0,120,186,0.25),
                            inset 0 1px 0 rgba(255,255,255,0.8);
                text-align: center;
            ">
                <div style="font-size:3rem;line-height:1;
                            margin-bottom:0.5rem;">
                    🔔 🐱
                </div>
                <h1 style="
                    background: linear-gradient(135deg,
                        {PALETTE['accent_dark']} 0%,
                        {PALETTE['accent']} 50%,
                        {PALETTE['red']} 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                    font-size: 2rem;font-weight: 800;
                    margin: 0;letter-spacing: -0.01em;
                ">哆啦理財</h1>
                <p style="color:{PALETTE['muted']};
                          margin: 0.3rem 0 0 0;
                          font-size: 0.85rem;
                          letter-spacing: 0.15em;">
                    PERSONAL FINANCE
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form", border=False):
            username = st.text_input(
                "👤 用戶名",
                placeholder="輸入您的用戶名",
                key="login_username",
            )
            password = st.text_input(
                "🔑 密碼",
                type="password",
                placeholder="輸入密碼",
                key="login_password",
            )
            submitted = st.form_submit_button(
                "🚪 登入",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            if not username or not password:
                st.error("⚠️ 請輸入用戶名同密碼")
            elif login(username, password):
                st.success(f"✅ 歡迎回來，{username}！正在載入...")
                st.rerun()
            else:
                st.error("❌ 用戶名或密碼錯誤")

        # 提示
        st.markdown(
            """
            <div style="text-align:center;color:#6B7BA0;
                        font-size:0.8rem;margin-top:1.5rem;
                        line-height:1.6;">
                <div>💡 仍未有帳號？請聯絡管理員開設</div>
                <div style="margin-top:0.3rem;">
                    🔒 每位用戶有獨立資料庫，互不干擾
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_logout_section():
    """於側欄顯示目前用戶 + 登出按鈕（純 HTML，避開 Streamlit button CSS 鬥爭）"""
    user = get_current_user()
    if not user:
        return
    with st.sidebar:
        st.markdown(
            f"""
            <div style="background:rgba(255,255,255,0.12);
                        border:1px solid rgba(255,255,255,0.25);
                        border-radius:10px;
                        padding:8px 12px;
                        margin-top:0.5rem;
                        font-size:0.85rem;
                        color:white;">
                <span style="opacity:0.7;">👤 已登入</span><br>
                <span style="font-weight:700;font-size:1rem;">{user}</span>
            </div>

            <a href="?logout=1" target="_self"
               style="display:block;
                      background:white;
                      color:#1A1A2E !important;
                      text-decoration:none !important;
                      text-align:center;
                      padding:10px 16px;
                      border-radius:10px;
                      margin-top:8px;
                      font-weight:700;
                      font-size:0.95rem;
                      border:1px solid rgba(255,255,255,0.4);
                      box-shadow:0 2px 8px rgba(0,0,0,0.18);
                      transition:all 0.2s ease;">
                🚪 登出
            </a>
            """,
            unsafe_allow_html=True,
        )
