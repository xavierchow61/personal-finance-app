"""PDF → PIL Image。優先用 pypdfium2（純 Python，唔使 poppler），
fallback 去 pdf2image（如果有 poppler）。"""
from pathlib import Path

from PIL import Image


def pdf_to_images(path: str | Path, dpi: int = 200, max_pages: int = 10) -> list[Image.Image]:
    """將 PDF 每一頁 render 成 PIL Image list。

    Args:
        path: PDF 路徑
        dpi: 解像度（200 = 標準清晰、300 = 高清）
        max_pages: 最多 render 幾頁（防爆 token）

    Returns:
        PIL Image list（每頁一個）

    Raises:
        RuntimeError: 完全讀唔到
    """
    path = Path(path)

    # === 優先 pypdfium2（純 Python wheel，無外部 dep）===
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(path))
        try:
            if len(pdf) == 0:
                raise RuntimeError("PDF 冇任何頁面")
            scale = dpi / 72.0
            n_pages = min(len(pdf), max_pages)
            images = []
            for i in range(n_pages):
                page = pdf[i]
                images.append(page.render(scale=scale).to_pil())
            return images
        finally:
            pdf.close()
    except ImportError:
        last_error = "pypdfium2 唔喺度"
    except Exception as e:
        last_error = f"pypdfium2: {e}"

    # === Fallback：pdf2image（要 poppler）===
    try:
        from pdf2image import convert_from_path
        pages = convert_from_path(str(path), dpi=dpi, last_page=max_pages)
        if pages:
            return list(pages)
        raise RuntimeError("pdf2image 攞唔到頁面")
    except ImportError:
        raise RuntimeError(
            f"PDF 處理失敗，請安裝 pypdfium2：\n"
            f"  pip install pypdfium2\n"
            f"({last_error})"
        )
    except Exception as e:
        raise RuntimeError(
            f"兩個 PDF backend 都失敗：\n"
            f"  pypdfium2: {last_error}\n"
            f"  pdf2image: {e}"
        )


def pdf_first_page_to_image(path: str | Path, dpi: int = 200) -> Image.Image:
    """淨係 render 第一頁（向後兼容 + 預覽用）"""
    images = pdf_to_images(path, dpi=dpi, max_pages=1)
    return images[0]
