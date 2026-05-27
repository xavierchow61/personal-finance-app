"""🐱 哆啦 A 夢主題玻璃樣式 — 藍身體 + 白肚皮 + 紅黃點綴"""
from textwrap import dedent
import streamlit as st

# === 哆啦 A 夢色票 ===
PALETTE = {
    # 背景漸層（淺天藍 → 哆啦藍 → 深藍）
    "bg_a": "#E0F4FC",         # 雲朵白藍
    "bg_b": "#7DD3FC",         # 天空藍
    "bg_c": "#00A6E0",         # 哆啦 A 夢經典身體藍
    # 文字（在白卡上要深色才看得清）
    "text": "#1A1A2E",         # 深海軍藍
    "subtext": "#3B3B5C",      # 中深藍灰
    "muted": "#6B7BA0",        # 柔灰藍
    # 哆啦 A 夢招牌色
    "accent": "#00A6E0",       # 哆啦藍（主色）
    "accent_dark": "#0078BA",  # 深哆啦藍（漸層深端）
    "success": "#00B894",      # 開心綠
    "warning": "#FFC700",      # 🔔 鈴鐺黃
    "red": "#E60012",          # 👃 鼻子紅 / 領巾紅
    "info": "#7ED4F0",         # 淺天藍
    "pink": "#FFB7C8",         # 👅 舌頭粉
    "mauve": "#5DADE2",        # 中藍
    "teal": "#1ABC9C",
    # 玻璃（白色肚皮感）
    "glass": "rgba(255,255,255,0.85)",
    "glass_border": "rgba(255,255,255,1)",
    "glass_strong": "rgba(255,255,255,0.92)",
    # 側欄專用（深藍 + 白字）
    "sidebar_bg": "#0091D5",
    "sidebar_text": "#FFFFFF",
}


def inject_glass_style():
    """注入哆啦 A 夢風格 CSS。每個頁面開頭調用一次。"""
    css = f"""
    <style>
    /* ============ 天空藍漸層背景 + 鈴鐺黃 / 鼻子紅飄浮光暈 ============ */
    .stApp {{
        background: linear-gradient(135deg,
            {PALETTE['bg_a']} 0%,
            {PALETTE['bg_b']} 50%,
            {PALETTE['bg_c']} 100%);
        background-attachment: fixed;
        color: {PALETTE['text']};
    }}
    .stApp::before {{
        content: "";
        position: fixed;
        top: -10%;
        right: -10%;
        width: 600px;
        height: 600px;
        background: radial-gradient(circle,
            rgba(255,199,0,0.28) 0%, transparent 70%);
        border-radius: 50%;
        z-index: 0;
        pointer-events: none;
        animation: floatA 18s ease-in-out infinite;
    }}
    .stApp::after {{
        content: "";
        position: fixed;
        bottom: -10%;
        left: -10%;
        width: 500px;
        height: 500px;
        background: radial-gradient(circle,
            rgba(230,0,18,0.18) 0%, transparent 70%);
        border-radius: 50%;
        z-index: 0;
        pointer-events: none;
        animation: floatB 22s ease-in-out infinite;
    }}
    @keyframes floatA {{
        0%, 100% {{ transform: translate(0, 0); }}
        50% {{ transform: translate(-30px, 40px); }}
    }}
    @keyframes floatB {{
        0%, 100% {{ transform: translate(0, 0); }}
        50% {{ transform: translate(40px, -30px); }}
    }}

    /* ============ 隱藏預設 chrome ============ */
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    header[data-testid="stHeader"] {{
        background: transparent !important;
        backdrop-filter: blur(8px);
    }}
    [data-testid="stSidebarNav"] {{ display: none !important; }}

    /* ============ 主內容區 ============ */
    .main .block-container {{
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1400px;
        position: relative;
        z-index: 1;
    }}

    /* ============ 主區文字（深色，在淺背景上）============ */
    .stApp, .stApp p, .stApp span, .stApp label, .stApp li,
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {{
        color: {PALETTE['text']};
    }}
    .stApp h2, .stApp h3 {{
        font-weight: 700;
        letter-spacing: -0.01em;
    }}
    .stCaption, [data-testid="stCaptionContainer"] {{
        color: {PALETTE['muted']} !important;
    }}

    /* ============ 側欄（深哆啦藍 + 白字 + 黏住不動）============ */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg,
            {PALETTE['accent']} 0%,
            {PALETTE['accent_dark']} 100%) !important;
        backdrop-filter: blur(8px);
        border-right: 3px solid rgba(255,255,255,0.25);
        box-shadow: 4px 0 20px rgba(0,120,186,0.3);
        position: sticky !important;
        top: 0 !important;
        height: 100vh !important;
    }}
    /* 隱藏側欄收合按鈕，避免用家不小心收起 */
    [data-testid="stSidebarCollapseButton"] {{ display: none !important; }}
    [data-testid="stSidebarCollapsedControl"] {{ display: none !important; }}
    [data-testid="stSidebar"] * {{
        color: {PALETTE['sidebar_text']} !important;
    }}
    [data-testid="stSidebar"] a {{
        background: rgba(255,255,255,0.12) !important;
        border: 1px solid rgba(255,255,255,0.25) !important;
        border-radius: 10px !important;
        padding: 8px 14px !important;
        margin-bottom: 4px !important;
        transition: all 0.25s ease !important;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.2) !important;
        font-size: 0.95rem !important;
        /* 強制統一高度，避免 active state 改變尺寸 */
        min-height: 42px !important;
        display: flex !important;
        align-items: center !important;
        line-height: 1.2 !important;
    }}
    /* Streamlit 對「目前頁面」嘅 page_link 預設會加 background tint，
       而家覆寫令其只係加邊框光暈，唔改 height */
    [data-testid="stSidebar"] a[aria-current="page"],
    [data-testid="stSidebar"] a.active,
    [data-testid="stSidebar"] [data-testid="stPageLink"][aria-current="page"] a {{
        background: linear-gradient(135deg,
            rgba(255,255,255,0.28),
            rgba(255,255,255,0.15)) !important;
        border: 1px solid rgba(255,255,255,0.6) !important;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.4),
                    0 0 0 2px rgba(255,199,0,0.35) !important;
        padding: 8px 14px !important;
        min-height: 42px !important;
    }}
    /* 側欄整體更緊湊（減少 scroll）*/
    [data-testid="stSidebar"] [data-testid="stSidebarUserContent"],
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
        padding-top: 0.6rem !important;
        padding-bottom: 0.6rem !important;
    }}
    [data-testid="stSidebar"] hr {{
        margin: 0.6rem 0 !important;
    }}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
        margin-bottom: 0 !important;
    }}
    [data-testid="stSidebar"] a:hover {{
        background: rgba(255,255,255,0.28) !important;
        border-color: rgba(255,255,255,0.5);
        transform: translateX(3px);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.4),
                    0 4px 14px rgba(0,0,0,0.15);
    }}

    /* ============ Dataframe（白肚皮卡）============ */
    [data-testid="stDataFrame"] {{
        background: rgba(255,255,255,0.92);
        backdrop-filter: blur(14px);
        border: 2px solid rgba(255,255,255,1);
        border-radius: 16px;
        padding: 6px;
        box-shadow: 0 8px 24px rgba(0,120,186,0.18),
                    inset 0 1px 0 rgba(255,255,255,0.8);
    }}
    [data-testid="stDataFrame"] [role="gridcell"],
    [data-testid="stDataFrame"] [role="columnheader"] {{
        color: {PALETTE['text']} !important;
    }}

    /* ============ Buttons（哆啦藍漸層）============ */
    .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
        background: linear-gradient(135deg,
            {PALETTE['accent']}, {PALETTE['accent_dark']});
        color: white !important;
        border: none;
        border-radius: 999px;          /* 圓潤膠囊狀 */
        padding: 0.6rem 1.8rem;
        font-weight: 600;
        box-shadow: 0 4px 14px rgba(0,120,186,0.4),
                    inset 0 1px 0 rgba(255,255,255,0.35);
        transition: all 0.25s ease;
    }}
    .stButton > button:hover, .stDownloadButton > button:hover,
    .stFormSubmitButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 22px rgba(0,120,186,0.55),
                    inset 0 1px 0 rgba(255,255,255,0.5);
    }}
    .stButton > button[kind="secondary"] {{
        background: white !important;
        color: {PALETTE['accent']} !important;
        border: 2px solid {PALETTE['accent']};
        box-shadow: none;
    }}
    .stButton > button[kind="secondary"]:hover {{
        background: {PALETTE['bg_a']} !important;
    }}

    /* ============ Inputs（白底深字）============ */
    .stTextInput input, .stNumberInput input, .stTextArea textarea,
    .stDateInput input, .stTimeInput input {{
        background: rgba(255,255,255,0.98) !important;
        border: 2px solid rgba(0,166,224,0.3) !important;
        border-radius: 10px !important;
        color: {PALETTE['text']} !important;
        font-weight: 500;
    }}
    .stTextInput input:focus, .stNumberInput input:focus,
    .stTextArea textarea:focus, .stDateInput input:focus {{
        border-color: {PALETTE['accent']} !important;
        box-shadow: 0 0 0 3px rgba(0,166,224,0.2) !important;
    }}
    /* Placeholder 文字（input 內的灰提示）*/
    .stTextInput input::placeholder,
    .stNumberInput input::placeholder,
    .stTextArea textarea::placeholder,
    .stDateInput input::placeholder {{
        color: rgba(26,26,46,0.45) !important;
        opacity: 1 !important;
    }}
    /* Input label（"餐飲"、"金額" 等）強制深色加粗 */
    .stTextInput label, .stNumberInput label, .stTextArea label,
    .stDateInput label, .stTimeInput label, .stSelectbox label,
    .stMultiSelect label, .stRadio label, .stCheckbox label,
    .stFileUploader label, .stSlider label {{
        color: {PALETTE['text']} !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
    }}

    /* Selectbox */
    .stSelectbox > div > div, .stMultiSelect > div > div {{
        background: rgba(255,255,255,0.95) !important;
        border: 2px solid rgba(0,166,224,0.3) !important;
        border-radius: 10px !important;
        color: {PALETTE['text']} !important;
    }}
    [data-baseweb="popover"] [role="listbox"] {{
        background: white !important;
        border: 1px solid rgba(0,166,224,0.3) !important;
        border-radius: 12px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.15);
    }}
    [data-baseweb="popover"] li {{ color: {PALETTE['text']} !important; }}
    [data-baseweb="popover"] li:hover {{
        background: {PALETTE['bg_a']} !important;
    }}

    /* Checkbox / Radio */
    .stCheckbox label, .stRadio label {{ color: {PALETTE['text']} !important; }}

    /* ============ Metric（白卡）============ */
    [data-testid="stMetric"] {{
        background: white;
        border: 2px solid rgba(255,255,255,1);
        border-radius: 16px;
        padding: 1rem 1.2rem;
        box-shadow: 0 8px 24px rgba(0,120,186,0.18),
                    inset 0 1px 0 rgba(255,255,255,0.8);
    }}
    [data-testid="stMetricValue"] {{
        color: {PALETTE['accent']} !important;
        font-weight: 700;
    }}
    [data-testid="stMetricLabel"] {{
        color: {PALETTE['muted']} !important;
    }}

    /* ============ Tabs ============ */
    .stTabs [data-baseweb="tab-list"] {{
        background: rgba(255,255,255,0.7);
        backdrop-filter: blur(14px);
        border-radius: 999px;
        padding: 6px;
        gap: 4px;
        border: 2px solid rgba(255,255,255,1);
        box-shadow: 0 4px 14px rgba(0,120,186,0.18);
    }}
    .stTabs [data-baseweb="tab"] {{
        background: transparent !important;
        border-radius: 999px;
        color: {PALETTE['subtext']} !important;
        border: none !important;
        padding: 8px 22px;
        transition: all 0.2s ease;
        font-weight: 600;
    }}
    .stTabs [data-baseweb="tab"]:hover {{
        background: rgba(0,166,224,0.1) !important;
        color: {PALETTE['accent']} !important;
    }}
    .stTabs [aria-selected="true"] {{
        background: linear-gradient(135deg,
            {PALETTE['accent']}, {PALETTE['accent_dark']}) !important;
        color: white !important;
        box-shadow: 0 4px 14px rgba(0,120,186,0.45);
    }}
    .stTabs [data-baseweb="tab-panel"] {{
        padding-top: 1.2rem;
    }}

    /* ============ Alert ============ */
    [data-testid="stAlert"] {{
        background: rgba(255,255,255,0.92) !important;
        border: 2px solid rgba(255,255,255,1);
        border-radius: 14px;
        color: {PALETTE['text']} !important;
        box-shadow: 0 6px 18px rgba(0,120,186,0.15);
    }}
    [data-testid="stAlert"] * {{ color: {PALETTE['text']} !important; }}

    /* ============ Expander ============ */
    [data-testid="stExpander"] {{
        background: rgba(255,255,255,0.95) !important;
        backdrop-filter: blur(14px);
        border: 2px solid rgba(255,255,255,1);
        border-radius: 14px;
        overflow: hidden;
        box-shadow: 0 4px 14px rgba(0,120,186,0.15);
    }}
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary * {{
        color: {PALETTE['text']} !important;
        padding: 0.5rem 1rem;
        font-weight: 700;
    }}
    /* Expander 內所有文字皆深色 */
    [data-testid="stExpander"] p,
    [data-testid="stExpander"] span,
    [data-testid="stExpander"] label,
    [data-testid="stExpander"] div,
    [data-testid="stExpanderDetails"] * {{
        color: {PALETTE['text']} !important;
    }}

    /* ============ Divider ============ */
    hr {{
        border-color: rgba(0,166,224,0.25) !important;
        margin: 1.4rem 0;
    }}

    /* ============ Progress bar ============ */
    .stProgress > div > div > div {{
        background: linear-gradient(90deg,
            {PALETTE['accent']}, {PALETTE['warning']}) !important;
        border-radius: 999px;
    }}
    .stProgress > div > div {{
        background: rgba(0,166,224,0.15) !important;
        border-radius: 999px;
    }}

    /* ============ File uploader ============ */
    [data-testid="stFileUploader"] {{
        background: rgba(255,255,255,0.85);
        backdrop-filter: blur(14px);
        border: 3px dashed {PALETTE['accent']};
        border-radius: 20px;
        padding: 1.4rem;
        transition: all 0.2s ease;
    }}
    [data-testid="stFileUploader"]:hover {{
        background: rgba(0,166,224,0.08);
        border-color: {PALETTE['accent_dark']};
    }}
    [data-testid="stFileUploader"] button {{
        background: linear-gradient(135deg,
            {PALETTE['accent']}, {PALETTE['accent_dark']}) !important;
        color: white !important;
    }}
    [data-testid="stFileUploaderDropzone"] {{ background: transparent; }}
    [data-testid="stFileUploaderDropzone"] * {{ color: {PALETTE['text']} !important; }}

    /* ============ 表單容器（白底深字）============ */
    [data-testid="stForm"],
    div[data-testid="stForm"] {{
        background: rgba(255,255,255,0.95) !important;
        backdrop-filter: blur(14px);
        border: 2px solid rgba(255,255,255,1);
        border-radius: 20px;
        padding: 1.4rem;
        box-shadow: 0 8px 24px rgba(0,120,186,0.18);
    }}
    /* Form 內所有文字皆深色 */
    [data-testid="stForm"] p,
    [data-testid="stForm"] span,
    [data-testid="stForm"] label,
    [data-testid="stForm"] .stCaption,
    [data-testid="stForm"] [data-testid="stCaptionContainer"] {{
        color: {PALETTE['text']} !important;
    }}
    [data-testid="stForm"] .stCaption,
    [data-testid="stForm"] [data-testid="stCaptionContainer"] {{
        color: {PALETTE['subtext']} !important;
    }}

    /* ============ Plotly chart ============ */
    [data-testid="stPlotlyChart"] {{
        background: rgba(255,255,255,0.92);
        backdrop-filter: blur(14px);
        border: 2px solid rgba(255,255,255,1);
        border-radius: 20px;
        padding: 0.8rem;
        box-shadow: 0 8px 24px rgba(0,120,186,0.18);
    }}

    /* ============ Image ============ */
    [data-testid="stImage"] img {{
        border-radius: 14px;
        box-shadow: 0 8px 24px rgba(0,120,186,0.3);
    }}

    /* ============ Sub-page 大按鈕（頁面頂部導航）============ */
    .main [data-testid="stPageLink"] a,
    .main [data-testid="stPageLink-NavLink"] {{
        background: linear-gradient(135deg,
            rgba(0,166,224,0.15) 0%,
            rgba(0,120,186,0.08) 100%) !important;
        border: 2px solid rgba(0,166,224,0.4) !important;
        border-radius: 14px !important;
        padding: 0.85rem 1.4rem !important;
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        color: {PALETTE['accent_dark']} !important;
        box-shadow: 0 4px 14px rgba(0,120,186,0.15),
                    inset 0 1px 0 rgba(255,255,255,0.6) !important;
        transition: all 0.25s ease !important;
        text-align: center !important;
        justify-content: center !important;
        display: flex !important;
        align-items: center !important;
        margin-bottom: 0.3rem !important;
    }}
    .main [data-testid="stPageLink"] a *,
    .main [data-testid="stPageLink-NavLink"] * {{
        color: {PALETTE['accent_dark']} !important;
        font-weight: 700 !important;
        font-size: 1.05rem !important;
    }}
    .main [data-testid="stPageLink"] a:hover,
    .main [data-testid="stPageLink-NavLink"]:hover {{
        background: linear-gradient(135deg,
            {PALETTE['accent']} 0%,
            {PALETTE['accent_dark']} 100%) !important;
        border-color: {PALETTE['accent_dark']} !important;
        transform: translateY(-2px);
        box-shadow: 0 8px 22px rgba(0,120,186,0.4),
                    inset 0 1px 0 rgba(255,255,255,0.4) !important;
    }}
    .main [data-testid="stPageLink"] a:hover *,
    .main [data-testid="stPageLink-NavLink"]:hover * {{
        color: white !important;
    }}

    /* ============ Code 區塊 ============ */
    .stCodeBlock, pre, code {{
        background: rgba(26,26,46,0.95) !important;
        border: 1px solid rgba(0,166,224,0.3) !important;
        border-radius: 12px !important;
        color: #FFC700 !important;        /* 鈴鐺黃字 */
    }}

    /* ============ Scrollbar ============ */
    ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
    ::-webkit-scrollbar-track {{ background: rgba(0,166,224,0.08); }}
    ::-webkit-scrollbar-thumb {{
        background: linear-gradient(180deg,
            {PALETTE['accent']}, {PALETTE['accent_dark']});
        border-radius: 5px;
    }}
    ::-webkit-scrollbar-thumb:hover {{ background: {PALETTE['accent_dark']}; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def glass_title(title: str, emoji: str = "", subtitle: str = ""):
    """哆啦藍漸層標題"""
    sub_html = ""
    if subtitle:
        sub_html = (
            f'<p style="color:{PALETTE["muted"]};font-size:0.95rem;'
            f'margin-top:0.4rem;margin-bottom:0;font-weight:500;">'
            f'{subtitle}</p>'
        )
    html = (
        '<div style="margin-bottom:1.4rem;position:relative;z-index:1;">'
        f'<h1 style="'
        f'background:linear-gradient(135deg,{PALETTE["accent_dark"]} 0%,'
        f'{PALETTE["accent"]} 50%,{PALETTE["red"]} 100%);'
        '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
        'background-clip:text;font-size:2.4rem;font-weight:800;'
        'letter-spacing:-0.02em;margin:0;line-height:1.1;'
        f'">{emoji} {title}</h1>'
        f'{sub_html}'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def glass_kpi(col, label: str, value, color: str = None, emoji: str = "",
              delta: str = None):
    """白肚皮 KPI 卡片"""
    if color is None:
        color = PALETTE["accent"]

    if isinstance(value, (int, float)):
        value_str = f"${value:,.2f}"
    else:
        value_str = str(value)

    delta_html = ""
    if delta:
        delta_html = (
            f'<div style="color:{PALETTE["muted"]};font-size:0.78rem;'
            f'margin-top:6px;font-weight:500;">{delta}</div>'
        )

    hover_in = ("this.style.transform='translateY(-4px)';"
                "this.style.boxShadow='0 14px 36px rgba(0,120,186,0.35)';")
    hover_out = ("this.style.transform='translateY(0)';"
                 "this.style.boxShadow='0 8px 24px rgba(0,120,186,0.22)';")

    html = (
        f'<div style="'
        'background:white;'
        'border:2px solid rgba(255,255,255,1);'
        'border-radius:20px;padding:1.1rem 1.3rem;'
        'box-shadow:0 8px 24px rgba(0,120,186,0.22),'
        ' inset 0 1px 0 rgba(255,255,255,0.9);'
        'position:relative;overflow:hidden;'
        'transition:transform 0.25s ease, box-shadow 0.25s ease;"'
        f' onmouseover="{hover_in}" onmouseout="{hover_out}">'
        # 右上角彩色圓圈（哆啦 A 夢風）
        f'<div style="position:absolute;top:-25px;right:-25px;'
        'width:90px;height:90px;'
        f'background:radial-gradient(circle,{color}33 0%,transparent 75%);'
        'border-radius:50%;"></div>'
        # 標籤
        f'<div style="color:{PALETTE["muted"]};font-size:0.78rem;'
        'font-weight:600;letter-spacing:0.05em;text-transform:uppercase;'
        'position:relative;z-index:1;">'
        f'{emoji} {label}</div>'
        # 數值
        f'<div style="color:{color};font-size:1.85rem;font-weight:800;'
        f'margin-top:8px;line-height:1.1;position:relative;z-index:1;">'
        f'{value_str}</div>'
        f'{delta_html}'
        '</div>'
    )
    col.markdown(html, unsafe_allow_html=True)


def glass_card_open(padding: str = "1.4rem"):
    """開啟白肚皮卡片容器（需配對 glass_card_close）"""
    html = (
        f'<div style="'
        'background:rgba(255,255,255,0.92);'
        'backdrop-filter:blur(18px);'
        'border:2px solid rgba(255,255,255,1);'
        'border-radius:20px;'
        f'padding:{padding};'
        'box-shadow:0 8px 24px rgba(0,120,186,0.2);'
        'margin-bottom:1rem;">'
    )
    st.markdown(html, unsafe_allow_html=True)


def glass_card_close():
    st.markdown("</div>", unsafe_allow_html=True)


def plotly_glass_layout(fig, height: int = 380):
    """為 Plotly 圖表套用哆啦風格（白底深字）"""
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PALETTE["text"], family="Inter, sans-serif"),
        legend=dict(
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="rgba(0,166,224,0.3)",
            borderwidth=1,
            font=dict(color=PALETTE["text"]),
        ),
        xaxis=dict(
            gridcolor="rgba(0,166,224,0.12)",
            linecolor="rgba(0,166,224,0.3)",
            tickfont=dict(color=PALETTE["subtext"]),
            title=dict(font=dict(color=PALETTE["subtext"])),
        ),
        yaxis=dict(
            gridcolor="rgba(0,166,224,0.12)",
            linecolor="rgba(0,166,224,0.3)",
            tickfont=dict(color=PALETTE["subtext"]),
            title=dict(font=dict(color=PALETTE["subtext"])),
        ),
        margin=dict(t=30, b=40, l=50, r=20),
    )
    return fig
