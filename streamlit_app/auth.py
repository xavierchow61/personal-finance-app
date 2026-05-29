"""使用者認證 — Supabase Auth（Email + Magic Link + 忘記密碼）

設定方式（Streamlit secrets / .env）：
    SUPABASE_URL = "https://xxxx.supabase.co"
    SUPABASE_ANON_KEY = "eyJ..."

可選 fallback：保留舊嘅 [auth.users] 做本地 demo 模式
（無 SUPABASE_URL 設定 → 自動 fallback）
"""
from __future__ import annotations

import os
from typing import Optional

import streamlit as st


# ============================================================
# Supabase Client（lazy init）
# ============================================================

@st.cache_resource
def _get_supabase_client():
    """取得 Supabase client（cached for performance）"""
    url = (os.getenv("SUPABASE_URL", "")
           or _safe_secret("SUPABASE_URL"))
    key = (os.getenv("SUPABASE_ANON_KEY", "")
           or _safe_secret("SUPABASE_ANON_KEY"))
    if not (url and key):
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


def _safe_secret(name: str) -> str:
    """從 Streamlit secrets 安全讀（無就回 ''）"""
    try:
        return st.secrets.get(name, "") or ""
    except Exception:
        return ""


def _is_enabled() -> bool:
    """Supabase Auth 係咪可用"""
    return _get_supabase_client() is not None


# ============================================================
# Session 狀態
# ============================================================

def get_current_user() -> Optional[dict]:
    """取得目前登入用戶（dict with email, id, etc.），未登入 = None"""
    return st.session_state.get("auth_user")


def get_current_email() -> Optional[str]:
    u = get_current_user()
    return u.get("email") if u else None


def get_current_user_id() -> Optional[str]:
    """目前用戶 UUID（用於 per-user 資料隔離）"""
    u = get_current_user()
    return u.get("id") if u else None


def is_authenticated() -> bool:
    return bool(get_current_user())


def logout():
    """登出 — 清除 session + 通知 Supabase"""
    client = _get_supabase_client()
    if client:
        try:
            client.auth.sign_out()
        except Exception:
            pass
    for key in list(st.session_state.keys()):
        if key.startswith("auth_"):
            del st.session_state[key]


# ============================================================
# 認證行為
# ============================================================

def sign_in_with_password(email: str, password: str) -> tuple[bool, str]:
    """Email + password 登入。回 (success, message)"""
    client = _get_supabase_client()
    if not client:
        return False, "Supabase 未設定"
    try:
        resp = client.auth.sign_in_with_password({
            "email": email.strip().lower(),
            "password": password,
        })
        user = resp.user
        if user:
            st.session_state["auth_user"] = {
                "id": user.id,
                "email": user.email,
            }
            return True, "登入成功"
        return False, "登入失敗"
    except Exception as ex:
        return False, _friendly_error(str(ex))


def sign_up_with_password(email: str, password: str) -> tuple[bool, str]:
    """註冊新帳戶。需要 email 驗證才生效。"""
    client = _get_supabase_client()
    if not client:
        return False, "Supabase 未設定"
    try:
        resp = client.auth.sign_up({
            "email": email.strip().lower(),
            "password": password,
        })
        if resp.user:
            # 視乎 Supabase 設定，可能需要 email 確認
            if resp.session:
                # 已自動登入
                st.session_state["auth_user"] = {
                    "id": resp.user.id,
                    "email": resp.user.email,
                }
                return True, "✅ 註冊成功並已登入"
            return True, (
                "✅ 註冊成功！請查 email 點擊驗證連結後再登入。"
            )
        return False, "註冊失敗"
    except Exception as ex:
        return False, _friendly_error(str(ex))


def send_magic_link(email: str) -> tuple[bool, str]:
    """發送 Magic Link 到 email — 點 link 即登入"""
    client = _get_supabase_client()
    if not client:
        return False, "Supabase 未設定"
    try:
        client.auth.sign_in_with_otp({
            "email": email.strip().lower(),
            "options": {
                "should_create_user": True,
                # email_redirect_to 預設用 Supabase site URL
            },
        })
        return True, (
            "✨ Magic Link 已發送！查你嘅 email，"
            "點擊連結即可登入。"
        )
    except Exception as ex:
        return False, _friendly_error(str(ex))


def send_password_reset(email: str) -> tuple[bool, str]:
    """發送密碼重設 email"""
    client = _get_supabase_client()
    if not client:
        return False, "Supabase 未設定"
    try:
        client.auth.reset_password_for_email(email.strip().lower())
        return True, (
            "📧 密碼重設 email 已發送！"
            "查 email 點擊連結設定新密碼。"
        )
    except Exception as ex:
        return False, _friendly_error(str(ex))


def _friendly_error(err: str) -> str:
    """將 Supabase 錯誤訊息轉成中文"""
    err_lower = err.lower()
    if "invalid login" in err_lower or "invalid credentials" in err_lower:
        return "❌ 電郵或密碼錯誤"
    if "user already registered" in err_lower:
        return "⚠️ 此電郵已註冊，請改用登入"
    if "email not confirmed" in err_lower:
        return "📧 請先到 email 點擊驗證連結"
    if "password" in err_lower and "weak" in err_lower:
        return "⚠️ 密碼太弱，至少 6 個字元"
    if "rate limit" in err_lower:
        return "⏱️ 嘗試次數過多，請稍後再試"
    if "network" in err_lower:
        return "🌐 網絡錯誤，請檢查連線"
    return f"❌ {err[:120]}"


# ============================================================
# 登入閘門（喺 app_header 自動 call）
# ============================================================

def require_login():
    """喺每個頁面開頭 call。
    - 若 Supabase 未設定 → 顯示警告 banner 並跳過
    - 若已登入 → 繼續
    - 若未登入 → 渲染登入畫面 + st.stop()
    """
    if not _is_enabled():
        # 顯示診斷資訊（方便排查）
        _render_auth_disabled_banner()
        return
    if is_authenticated():
        return
    _render_login_page()
    st.stop()


def _render_auth_disabled_banner():
    """當 Supabase Auth 未配置 → 顯示一個診斷 banner"""
    url_set = bool(os.getenv("SUPABASE_URL") or _safe_secret("SUPABASE_URL"))
    key_set = bool(os.getenv("SUPABASE_ANON_KEY")
                    or _safe_secret("SUPABASE_ANON_KEY"))

    # 嘗試 import supabase 看是否安裝
    pkg_installed = False
    try:
        import supabase as _sb  # noqa
        pkg_installed = True
    except ImportError:
        pass

    status = (
        f"📦 supabase package: {'✅ 已安裝' if pkg_installed else '❌ 未安裝'}<br>"
        f"🌐 SUPABASE_URL: {'✅ 已設定' if url_set else '❌ 未設定'}<br>"
        f"🔑 SUPABASE_ANON_KEY: {'✅ 已設定' if key_set else '❌ 未設定'}"
    )

    st.markdown(
        f"""
        <div style="background:rgba(255,199,0,0.18);
                    border:2px solid rgba(230,0,18,0.5);
                    border-radius:12px;padding:0.9rem 1.2rem;
                    margin-bottom:1rem;color:#1A1A2E;font-size:0.9rem;">
            <b>⚠️ Supabase Auth 未啟用</b><br>
            <small>{status}</small><br>
            <small style="color:#6B7BA0;margin-top:0.4rem;display:block;">
                請在 Streamlit Cloud → Settings → Secrets 設定
                SUPABASE_URL + SUPABASE_ANON_KEY，
                然後等部署完成（約 2 分鐘安裝 supabase 套件）。
            </small>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# 登入畫面
# ============================================================

def _render_login_page():
    """全屏登入畫面 — 哆啦藍漸層 + 玻璃卡 + 3 tabs"""
    from style import inject_glass_style, PALETTE
    inject_glass_style()

    # 隱藏側欄
    st.markdown(
        '<style>[data-testid="stSidebar"]{display:none !important;}'
        '[data-testid="stSidebarCollapseButton"]{display:none !important;}'
        '</style>',
        unsafe_allow_html=True,
    )

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        # 品牌 banner
        st.markdown(
            f"""
            <div style="
                background: white;
                border: 2px solid rgba(0,166,224,0.3);
                border-radius: 24px;
                padding: 2rem 2rem 1rem 2rem;
                margin-top: 2rem;
                margin-bottom: 1rem;
                box-shadow: 0 20px 60px rgba(0,120,186,0.25),
                            inset 0 1px 0 rgba(255,255,255,0.8);
                text-align: center;
            ">
                <div style="font-size:2.6rem;line-height:1;
                            margin-bottom:0.4rem;">🔔 🐱</div>
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
                          margin: 0.2rem 0 0 0;
                          font-size: 0.82rem;
                          letter-spacing: 0.15em;">
                    PERSONAL FINANCE
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 3 個 tabs
        tab_login, tab_signup, tab_reset = st.tabs([
            "🚪 登入", "✨ 註冊", "🔑 忘記密碼"
        ])

        # === Tab 1: 登入 ===
        with tab_login:
            with st.form("login_form", border=False):
                email = st.text_input(
                    "📧 電郵",
                    placeholder="your@email.com",
                    key="login_email",
                )
                password = st.text_input(
                    "🔑 密碼",
                    type="password",
                    placeholder="密碼",
                    key="login_password",
                )
                col1, col2 = st.columns(2)
                login_clicked = col1.form_submit_button(
                    "🚪 登入", type="primary",
                    use_container_width=True,
                )
                magic_clicked = col2.form_submit_button(
                    "✨ Magic Link",
                    help="收 email 一鍵登入，唔需要密碼",
                    use_container_width=True,
                )

            if login_clicked:
                if not email or not password:
                    st.error("⚠️ 請輸入電郵同密碼")
                else:
                    ok, msg = sign_in_with_password(email, password)
                    if ok:
                        st.success(f"✅ {msg}，正在載入...")
                        st.rerun()
                    else:
                        st.error(msg)

            if magic_clicked:
                if not email:
                    st.error("⚠️ 請輸入電郵")
                else:
                    ok, msg = send_magic_link(email)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

        # === Tab 2: 註冊 ===
        with tab_signup:
            with st.form("signup_form", border=False):
                su_email = st.text_input(
                    "📧 電郵",
                    placeholder="your@email.com",
                    key="signup_email",
                )
                su_pwd = st.text_input(
                    "🔑 設定密碼（至少 6 個字元）",
                    type="password",
                    key="signup_password",
                )
                su_pwd2 = st.text_input(
                    "🔑 再次輸入密碼",
                    type="password",
                    key="signup_password2",
                )
                su_submit = st.form_submit_button(
                    "✨ 建立帳戶", type="primary",
                    use_container_width=True,
                )

            if su_submit:
                if not su_email or not su_pwd:
                    st.error("⚠️ 請填寫電郵同密碼")
                elif len(su_pwd) < 6:
                    st.error("⚠️ 密碼至少 6 個字元")
                elif su_pwd != su_pwd2:
                    st.error("⚠️ 兩次密碼不一致")
                else:
                    ok, msg = sign_up_with_password(su_email, su_pwd)
                    if ok:
                        st.success(msg)
                        # 如果 session 已建立 → rerun
                        if is_authenticated():
                            st.rerun()
                    else:
                        st.error(msg)

        # === Tab 3: 忘記密碼 ===
        with tab_reset:
            with st.form("reset_form", border=False):
                r_email = st.text_input(
                    "📧 註冊時用嘅電郵",
                    placeholder="your@email.com",
                    key="reset_email",
                )
                r_submit = st.form_submit_button(
                    "📧 發送重設連結", type="primary",
                    use_container_width=True,
                )

            if r_submit:
                if not r_email:
                    st.error("⚠️ 請輸入電郵")
                else:
                    ok, msg = send_password_reset(r_email)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

        # 底部提示
        st.markdown(
            """
            <div style="text-align:center;color:#6B7BA0;
                        font-size:0.8rem;margin-top:1.5rem;
                        line-height:1.6;">
                <div>💡 第一次用？揀「✨ 註冊」建立帳戶</div>
                <div style="margin-top:0.3rem;">
                    🔒 用 Supabase 安全認證 · 密碼加密儲存
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# 側欄顯示用戶資訊 + 登出
# ============================================================

def render_logout_section():
    """喺側欄顯示用戶 + 登出 link"""
    user = get_current_user()
    if not user:
        return
    email = user.get("email", "")
    # 顯示名 = email @ 前段
    display_name = email.split("@")[0] if email else "user"
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
                <span style="font-weight:700;font-size:1rem;">
                    {display_name}
                </span><br>
                <span style="opacity:0.6;font-size:0.72rem;">
                    {email}
                </span>
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
                      box-shadow:0 2px 8px rgba(0,0,0,0.18);">
                🚪 登出
            </a>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# Query param 偵測（logout + magic link callback + email confirm）
# ============================================================

def _check_logout_query():
    try:
        if st.query_params.get("logout") == "1":
            logout()
            st.query_params.clear()
            st.rerun()
    except Exception:
        pass


def _check_auth_callback():
    """處理 Magic Link / Email confirm 回調

    Supabase 完成驗證後會 redirect 帶以下 URL params：
    - ?access_token=...&refresh_token=...&type=magiclink
    - ?type=signup&access_token=...
    - ?type=recovery&access_token=...

    我哋要：
    1. 攞到 token
    2. set session 入 client
    3. 清 URL params
    4. rerun 進入正常 flow
    """
    try:
        qp = st.query_params
        access_token = qp.get("access_token")
        refresh_token = qp.get("refresh_token")
        if not access_token:
            return

        client = _get_supabase_client()
        if not client:
            return

        # 將 token 設入 session
        try:
            resp = client.auth.set_session(
                access_token, refresh_token or "")
            user = resp.user if hasattr(resp, "user") else None
            if user:
                st.session_state["auth_user"] = {
                    "id": user.id,
                    "email": user.email,
                }
                # 清 URL params 避免無限 loop
                st.query_params.clear()
                # 顯示成功訊息
                st.toast("✅ 登入成功！正在載入...", icon="🎉")
                st.rerun()
        except Exception:
            pass
    except Exception:
        pass


def init_auth():
    """app_header 開頭 call。
    處理順序：
    1. Magic Link / Email confirm callback（URL params）
    2. Logout query param
    3. require_login
    """
    _check_auth_callback()
    _check_logout_query()
    require_login()
