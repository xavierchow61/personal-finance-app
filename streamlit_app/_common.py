"""共用工具 — 樣式注入、標題、KPI 卡片、資料庫初始化"""
import sys
from pathlib import Path

# 將父資料夾加入 sys.path，方便引用 personal_finance、database、extractor
APP_ROOT = Path(__file__).parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import streamlit as st

from style import (
    PALETTE,
    inject_glass_style,
    glass_title,
    glass_kpi,
    glass_card_open,
    glass_card_close,
    plotly_glass_layout,
)

# === 顏色（沿用舊鍵名，避免其他頁面要改太多）===
C = {
    "bg": PALETTE["bg_a"],
    "text": PALETTE["text"],
    "subtext": PALETTE["subtext"],
    "muted": PALETTE["muted"],
    "accent": PALETTE["accent"],
    "success": PALETTE["success"],
    "warning": PALETTE["warning"],
    "red": PALETTE["red"],
    "mauve": PALETTE["mauve"],
    "teal": PALETTE["teal"],
    "pink": PALETTE["pink"],
    "info": PALETTE["info"],
}


def render_sidebar_nav():
    """共用玻璃側欄 — 哆啦 A 夢品牌 + 6 個快速入口"""
    with st.sidebar:
        # 哆啦 A 夢風品牌標題 — 鈴鐺黃 + 白字（精簡版）
        st.markdown(
            '<div style="text-align:center;padding:0.3rem 0 0.1rem 0;'
            'color:white;font-size:1.25rem;font-weight:800;'
            'letter-spacing:0.04em;'
            'text-shadow:0 2px 6px rgba(0,0,0,0.2);">'
            '🔔 哆啦理財 🐱</div>'
            '<div style="text-align:center;color:#FFC700;'
            'font-size:0.7rem;font-weight:600;letter-spacing:0.18em;'
            'margin-bottom:0.5rem;">PERSONAL FINANCE</div>',
            unsafe_allow_html=True,
        )
        # === 精簡側欄：只 3 個 hub + 儀表板 ===
        st.page_link("Home.py", label="儀表板", icon="🏠")
        st.write("")
        st.page_link("pages/1_📤_提取單據.py",
                      label="單據處理", icon="📤")
        st.page_link("pages/3_💰_個人記賬.py",
                      label="個人記賬", icon="💰")
        st.page_link("pages/7_⚙️_設定.py",
                      label="系統設定", icon="⚙️")
        st.divider()


# === 子頁面分組（用於頁面頂部 sub-nav）===
SUBPAGE_GROUPS = {
    "invoice": [
        ("提取單據", "pages/1_📤_提取單據.py", "📤"),
        ("單據紀錄", "pages/2_📋_單據紀錄.py", "📋"),
    ],
    "ledger": [
        ("個人記賬", "pages/3_💰_個人記賬.py", "💰"),
        ("預算與實績", "pages/4_🎯_預算.py", "🎯"),
        ("財務報表", "pages/5_📈_財務報表.py", "📈"),
        ("報銷追蹤", "pages/6_🏢_報銷追蹤.py", "🏢"),
    ],
}


def render_subpage_nav(group_key: str):
    """渲染頁面頂部嘅子頁面導航（一排按鈕）

    Args:
        group_key: SUBPAGE_GROUPS 嘅 key（"invoice" / "ledger"）
    """
    group = SUBPAGE_GROUPS.get(group_key, [])
    if not group:
        return
    cols = st.columns(len(group))
    for col, (label, page_path, icon) in zip(cols, group):
        with col:
            st.page_link(
                page_path,
                label=f"{icon} {label}",
                use_container_width=True,
            )
    st.divider()


def render_doraemon_fab():
    """🎒 哆啦 A 夢 4D 口袋浮動按鈕 + 神奇道具選單

    懸停或點擊口袋 → 彈出 6 個神奇道具（每個對應一個頁面）
    """
    # Streamlit 多頁面 URL slug = 檔名去掉 N_emoji_ prefix + .py 副檔名
    html = """
<div class="doraemon-fab-container" title="4D 四次元口袋（懸停查看神奇道具）">

  <!-- 神奇道具選單（hover 才出現） -->
  <div class="fab-menu">
    <a href="/" target="_self" class="gadget" style="--delay:0.05s">
      <span class="gadget-icon">🚪</span>
      <span class="gadget-label">任意門<br><small>儀表板</small></span>
    </a>
    <a href="提取單據" target="_self" class="gadget" style="--delay:0.1s">
      <span class="gadget-icon">🥟</span>
      <span class="gadget-label">翻譯蒟蒻<br><small>AI 提取單據</small></span>
    </a>
    <a href="單據紀錄" target="_self" class="gadget" style="--delay:0.15s">
      <span class="gadget-icon">🍞</span>
      <span class="gadget-label">記憶麵包<br><small>單據紀錄</small></span>
    </a>
    <a href="個人記賬" target="_self" class="gadget" style="--delay:0.2s">
      <span class="gadget-icon">🌀</span>
      <span class="gadget-label">竹蜻蜓<br><small>個人記賬</small></span>
    </a>
    <a href="預算" target="_self" class="gadget" style="--delay:0.25s">
      <span class="gadget-icon">🎯</span>
      <span class="gadget-label">命中標靶<br><small>預算追蹤</small></span>
    </a>
    <a href="財務報表" target="_self" class="gadget" style="--delay:0.3s">
      <span class="gadget-icon">⏰</span>
      <span class="gadget-label">時光機<br><small>財務報表</small></span>
    </a>
    <a href="報銷追蹤" target="_self" class="gadget" style="--delay:0.35s">
      <span class="gadget-icon">🎌</span>
      <span class="gadget-label">追蹤雷達<br><small>報銷追蹤</small></span>
    </a>
    <a href="設定" target="_self" class="gadget" style="--delay:0.4s">
      <span class="gadget-icon">🧰</span>
      <span class="gadget-label">秘密工具<br><small>進階設定</small></span>
    </a>
  </div>

  <!-- 4D 口袋按鈕 -->
  <div class="doraemon-fab">
    <div class="pocket-opening"></div>
    <div class="pocket-shine"></div>
    <div class="pocket-sparkle">✨</div>
  </div>

</div>

<style>
.doraemon-fab-container {
    position: fixed;
    bottom: 28px;
    right: 28px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 14px;
}

/* === 4D 口袋按鈕本體 === */
.doraemon-fab {
    width: 72px;
    height: 72px;
    background: radial-gradient(circle at 30% 30%,
        #38bdf8 0%, #00A6E0 50%, #0078BA 100%);
    border-radius: 50%;
    box-shadow:
        0 6px 24px rgba(0,120,186,0.5),
        inset 0 -4px 8px rgba(0,0,0,0.15),
        inset 0 3px 6px rgba(255,255,255,0.35);
    cursor: pointer;
    position: relative;
    overflow: hidden;
    transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
    animation: pocketPulse 2.4s ease-in-out infinite;
}

.doraemon-fab:hover {
    transform: scale(1.12) rotate(-8deg);
    box-shadow:
        0 8px 36px rgba(0,120,186,0.65),
        0 0 50px rgba(255,199,0,0.4),
        inset 0 -4px 8px rgba(0,0,0,0.15),
        inset 0 3px 6px rgba(255,255,255,0.5);
}

/* 口袋開口（白色半圓）*/
.pocket-opening {
    position: absolute;
    top: 38%;
    left: 50%;
    transform: translate(-50%, 0);
    width: 56px;
    height: 28px;
    background: white;
    border-radius: 0 0 56px 56px;
    box-shadow:
        inset 0 -4px 8px rgba(0,0,0,0.15),
        inset 0 3px 4px rgba(0,166,224,0.2);
}

/* 口袋上方光澤 */
.pocket-shine {
    position: absolute;
    top: 14px;
    left: 22px;
    width: 14px;
    height: 14px;
    background: rgba(255,255,255,0.55);
    border-radius: 50%;
    filter: blur(3px);
}

/* 閃爍小星星 */
.pocket-sparkle {
    position: absolute;
    bottom: 6px;
    right: 8px;
    font-size: 16px;
    animation: sparkleSpin 3s linear infinite;
}

@keyframes pocketPulse {
    0%, 100% {
        box-shadow:
            0 6px 24px rgba(0,120,186,0.5),
            inset 0 -4px 8px rgba(0,0,0,0.15),
            inset 0 3px 6px rgba(255,255,255,0.35);
    }
    50% {
        box-shadow:
            0 6px 30px rgba(0,120,186,0.65),
            0 0 36px rgba(255,199,0,0.45),
            inset 0 -4px 8px rgba(0,0,0,0.15),
            inset 0 3px 6px rgba(255,255,255,0.45);
    }
}

@keyframes sparkleSpin {
    0% { transform: rotate(0deg) scale(1); opacity: 0.9; }
    50% { transform: rotate(180deg) scale(1.3); opacity: 1; }
    100% { transform: rotate(360deg) scale(1); opacity: 0.9; }
}

/* === 神奇道具選單 === */
.fab-menu {
    display: flex;
    flex-direction: column;
    gap: 10px;
    align-items: flex-end;
    opacity: 0;
    pointer-events: none;
    transform: translateY(20px) scale(0.85);
    transform-origin: bottom right;
    transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* hover 容器或聚焦時打開選單 */
.doraemon-fab-container:hover .fab-menu,
.doraemon-fab-container:focus-within .fab-menu {
    opacity: 1;
    pointer-events: auto;
    transform: translateY(0) scale(1);
}

/* 每個道具按鈕 */
.gadget {
    background: rgba(255,255,255,0.95);
    backdrop-filter: blur(14px);
    border: 2px solid rgba(0,166,224,0.4);
    border-radius: 999px;
    padding: 8px 16px 8px 14px;
    text-decoration: none !important;
    color: #1A1A2E !important;
    font-weight: 600;
    box-shadow:
        0 6px 18px rgba(0,120,186,0.25),
        inset 0 1px 0 rgba(255,255,255,0.8);
    transition: all 0.25s ease;
    display: flex;
    align-items: center;
    gap: 10px;
    white-space: nowrap;
    animation: gadgetSlideIn 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) both;
    animation-delay: var(--delay, 0s);
    min-width: 175px;
}

@keyframes gadgetSlideIn {
    from { opacity: 0; transform: translateX(30px); }
    to { opacity: 1; transform: translateX(0); }
}

.gadget:hover {
    background: linear-gradient(135deg, #FFC700 0%, #FFB7C8 100%) !important;
    border-color: #E60012;
    transform: translateX(-6px) scale(1.05);
    box-shadow:
        0 8px 24px rgba(230,0,18,0.3),
        inset 0 1px 0 rgba(255,255,255,0.9);
}

.gadget-icon {
    font-size: 1.65rem;
    filter: drop-shadow(0 2px 4px rgba(0,0,0,0.15));
    flex-shrink: 0;
}

.gadget-label {
    font-size: 0.9rem;
    color: #1A1A2E !important;
    line-height: 1.15;
}

.gadget-label small {
    font-size: 0.72rem;
    color: #6B7BA0 !important;
    font-weight: 500;
}

.gadget:hover .gadget-label small {
    color: #1A1A2E !important;
}

/* 點擊口袋瞬間的「彈跳」效果 */
.doraemon-fab:active {
    transform: scale(0.92);
}

/* 行動裝置：選單在點擊後保持顯示 */
@media (hover: none) {
    .doraemon-fab-container:hover .fab-menu {
        opacity: 0;
        pointer-events: none;
    }
}
</style>
"""
    st.markdown(html, unsafe_allow_html=True)


def app_header(title: str = "", emoji: str = "💰",
                subtitle: str = ""):
    """每個頁面頂部標題 — 自動注入樣式 + 共用側欄

    若 title 為空字串，則跳過標題渲染（用於 Home 等不想顯示標題的頁面）
    """
    inject_glass_style()
    render_sidebar_nav()
    if title:
        glass_title(title, emoji, subtitle)
    # 4D 口袋 FAB 已移除（與側欄重複，浪費版面）
    # 如需復活，呼叫：render_doraemon_fab()


def kpi_card(col, label: str, value, color: str = None, emoji: str = "",
             delta: str = None):
    """KPI 卡片（玻璃毛感）"""
    glass_kpi(col, label, value, color, emoji, delta)


def init_dbs():
    """確保資料庫已建立及完成初始化"""
    from personal_finance import db as pfdb, seed as pfseed
    pfdb.init_db()
    if not pfdb.list_accounts(active_only=False):
        pfseed.seed_all()


def check_api_key():
    """如果尚未設定 Gemini API key 則顯示警告"""
    import config
    if not config.GEMINI_API_KEY:
        st.warning(
            "⚠️ 尚未設定 GEMINI_API_KEY。單據提取功能將會失敗。"
            "請於 [Google AI Studio](https://aistudio.google.com/apikey) "
            "取得 API key，並寫入 `.env` 檔案。"
        )


# 將 plotly 工具暴露給其他頁面使用
__all__ = [
    "C", "PALETTE",
    "app_header", "kpi_card", "init_dbs", "check_api_key",
    "glass_card_open", "glass_card_close", "plotly_glass_layout",
    "render_subpage_nav", "SUBPAGE_GROUPS",
]
