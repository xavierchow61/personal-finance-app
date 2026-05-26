"""提取單據 — 上傳圖片/PDF，經 Gemini Vision 自動提取並入賬"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import tempfile
import streamlit as st

from streamlit_app._common import C, app_header, check_api_key, init_dbs

st.set_page_config(
    page_title="提取單據", page_icon="📤", layout="wide",
    initial_sidebar_state="expanded",
)
init_dbs()

app_header("提取單據", "📤",
            "上傳 JPG / PDF 檔案，系統會自動辨識內容並寫入賬目")

check_api_key()

st.markdown(
    """
    <div style="background:rgba(0,166,224,0.08);
                border:2px dashed rgba(0,166,224,0.4);
                border-radius:14px;padding:0.9rem 1.2rem;
                margin-bottom:0.8rem;">
        <span style="font-weight:600;color:#1A1A2E;">💡 小貼士：</span>
        <span style="color:#1A1A2E;">
        可以直接把檔案 <b>拖拉</b> 進下方虛線框內，
        或按按鈕逐個選擇。支援多檔案、PDF 多頁、自動跳過重複單據。
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

uploaded = st.file_uploader(
    "🎯 選擇單據檔案（可多選，可拖拉）",
    type=["jpg", "jpeg", "png", "bmp", "webp", "tiff", "pdf"],
    accept_multiple_files=True,
)

if uploaded:
    st.info(f"📁 已選擇 {len(uploaded)} 個檔案，請按下方按鈕開始提取。")

    col_a, col_b = st.columns([2, 5])
    with col_a:
        auto_post = st.checkbox("自動寫入個人記賬", value=True)

    if st.button("🚀 開始提取", type="primary"):
        import database as invdb
        from extractor import extract_receipt
        invdb.init_db()

        progress = st.progress(0, text="準備中...")
        log_area = st.empty()
        log_lines = []
        ok = fail = skip = 0
        posted = 0

        for i, f in enumerate(uploaded):
            pct = int(i / len(uploaded) * 100)
            progress.progress(pct,
                              text=f"處理中 {i+1}/{len(uploaded)}：{f.name}")

            # 暫存為臨時檔案
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=Path(f.name).suffix
            ) as tmp:
                tmp.write(f.read())
                tmp_path = Path(tmp.name)

            try:
                data = extract_receipt(tmp_path)
                # 檢查是否重複
                dup = invdb.is_duplicate(data)
                if dup:
                    log_lines.append(
                        f"⚠️ {f.name} 與 #{dup['id']} 重複，已跳過")
                    skip += 1
                    continue
                # 寫入單據
                inv_id = invdb.save_invoice(data)
                log_lines.append(
                    f"✅ #{inv_id} ｜ {data.get('store_name', '未知')} ｜ "
                    f"{data.get('category', '未知')} ｜ "
                    f"${data.get('total_amount', 0):.2f}"
                )
                ok += 1
                # 自動入賬
                if auto_post:
                    try:
                        from personal_finance import posting as pfpost
                        entry_id = pfpost.post_invoice(
                            {**data, "id": inv_id})
                        log_lines.append(
                            f"   💰 已寫入個人記賬（分錄 #{entry_id}）")
                        posted += 1
                    except Exception as pe:
                        log_lines.append(f"   ⚠️ 寫入記賬失敗：{pe}")
            except Exception as e:
                fail += 1
                log_lines.append(f"❌ {f.name} → {e}")
            finally:
                tmp_path.unlink(missing_ok=True)

            log_area.markdown(
                "```\n" + "\n".join(log_lines[-12:]) + "\n```"
            )

        progress.progress(100, text="完成")
        st.success(
            f"✅ 成功提取 {ok}/{len(uploaded)}"
            + (f" · 跳過 {skip} 張" if skip else "")
            + (f" · 失敗 {fail} 張" if fail else "")
            + (f" · 已入賬 {posted} 張" if posted else "")
        )

        if ok:
            st.info("👉 請前往「📋 單據紀錄」或「💰 個人記賬」查閱結果")

# === 側欄 ===
with st.sidebar:
    st.markdown("### 💡 提示")
    st.markdown("""
- 支援**多檔案**一次上傳
- **PDF 多頁面**會全部讀取
- 已匯入過的單據會**自動跳過**
- 勾選自動入賬後會同時寫入分錄
""")
