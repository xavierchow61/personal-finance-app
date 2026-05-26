"""用 Gemini Vision 由單據圖片/PDF 提取結構化資料"""
import json
import re
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image

from config import CATEGORIES, GEMINI_API_KEY, GEMINI_MODEL, IMAGE_EXTENSIONS, PDF_EXTENSIONS
from pdf_utils import pdf_first_page_to_image, pdf_to_images


EXTRACT_PROMPT = f"""你係專業嘅單據資料提取員。請仔細睇下面張單據相片/PDF（可能有多頁），提取所有有用資訊。

【任務】
提取以下欄位，輸出**純 JSON**（唔好加 markdown code fence、唔好解釋）：

{{
  "purchase_date": "YYYY-MM-DD",          // 購買日期，如果只見年月日格式請統一
  "store_name": "商店名稱",                // 例如「百佳超級市場」、「Starbucks」
  "category": "類別",                      // 從以下揀一個最啱：{', '.join(CATEGORIES)}
  "total_amount": 123.45,                  // 總金額（數字，唔要 $ 號）
  "currency": "HKD",                       // HKD / USD / CNY / JPY 等
  "payment_method": "現金/信用卡/八達通/支付寶...",  // 如果單上有寫
  "items": [                               // 全部個別產品/服務
    {{"name": "產品名", "quantity": 1, "price": 50.00}}
  ],
  "tax": 0.00,                             // 稅項（如有）
  "receipt_number": "單號",                // 如有
  "notes": ""                              // 任何其他重要資訊（例如取餐號、外賣/堂食）
}}

【⚠️ 極重要：捕捉所有 items】
1. **掃描每一頁、每一個 section**：如果有多頁 PDF / 多個訂單卡 / 多個人嘅 order，全部 items 都要包埋
2. **包括 $0 嘅 items**（例如配菜、贈品、「不需餐具」等選項）
3. **多人/多單情況**：例如外賣訂單可能分 2 個人 order，要 capture 兩個人嘅 items
4. **驗證**：items 入面所有 (price × quantity) 加埋 + tax，**應該等於 total_amount**
   - 如果加唔啱 → 你一定漏咗 item，再仔細睇一次
   - 如果張單本身有 sub-total 同 total（例如 service charge、discount），喺 notes 註明

【其他規則】
1. 如果某個欄位睇唔到，用 null（唔好亂估）
2. 日期一定要 YYYY-MM-DD 格式，例如「2025年5月23日」→「2025-05-23」
3. 金額要係數字（float），唔好夾帶幣值符號
4. 類別一定要從以下 list 揀一個最啱：{', '.join(CATEGORIES)}
5. 如果係餐廳/酒樓，category 用「餐飲」
6. 如果係超市/便利店，category 用「超市雜貨」
7. 只輸出 JSON object，由 {{ 開始，由 }} 結束
"""


def _strip_code_fence(text: str) -> str:
    """移除 Gemini 偶爾加嘅 markdown code fence"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _repair_truncated_json(text: str) -> str | None:
    """嘗試修補俾 token limit 切咗嘅 JSON。

    策略：搵 items array 入面最後一個完整 } 嘅位置，
    截到嗰度，閂返 array + 閂返 object。
    """
    if not text or not text.lstrip().startswith("{"):
        return None

    # 揾 "items" array 開始嘅位
    items_start = text.find('"items"')
    if items_start == -1:
        # 冇 items array，可能其他欄位被截
        # 試下單純喺最後加 "}"
        try:
            json.loads(text + "}")
            return text + "}"
        except json.JSONDecodeError:
            return None

    bracket_start = text.find("[", items_start)
    if bracket_start == -1:
        return None

    # 由 bracket_start 開始 scan，跟住 brace depth 揾最後一個完整 item }
    depth = 0
    in_string = False
    escape = False
    last_complete_obj_end = -1
    for i in range(bracket_start + 1, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                last_complete_obj_end = i  # 一個完整 item

    if last_complete_obj_end == -1:
        # items 一個都未完，砍走整個 items
        repaired = text[:items_start].rstrip().rstrip(",")
        repaired += "}"
    else:
        # 截到最後完整嗰個 item 之後，閂 array + object
        repaired = text[:last_complete_obj_end + 1] + "]}"

    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        # 最後 fallback：完全冇 items
        try:
            stripped = text[:items_start].rstrip().rstrip(",") + "}"
            json.loads(stripped)
            return stripped
        except json.JSONDecodeError:
            return None


def _get_finish_reason(response) -> str:
    """攞 finish_reason 用嚟 debug（MAX_TOKENS / STOP / SAFETY 等）"""
    try:
        return str(response.candidates[0].finish_reason)
    except (AttributeError, IndexError):
        return "unknown"


def _is_transient_error(err: Exception) -> bool:
    """係咪短暫錯誤（503/429/500/504/timeout）可以 retry"""
    s = str(err)
    return any(x in s for x in [
        "503", "UNAVAILABLE", "high demand",
        "429", "RESOURCE_EXHAUSTED", "rate limit",
        "500", "INTERNAL",
        "504", "DEADLINE_EXCEEDED",
        "timeout", "Connection", "ConnectionError",
    ])


def _call_gemini_with_retry(client, model: str, contents, config,
                              max_retries: int = 5,
                              progress_callback=None):
    """Wrapper：用 exponential backoff retry call Gemini。

    Retry on：503 (high demand)、429 (rate limit)、500/504、connection errors
    Backoff：2s → 4s → 8s → 16s → 32s
    """
    import time
    last_error = None
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model=model, contents=contents, config=config)
        except Exception as e:
            last_error = e
            if not _is_transient_error(e) or attempt == max_retries - 1:
                break
            delay = 2 ** (attempt + 1)
            if progress_callback:
                progress_callback(
                    f"⏳ Gemini 短暫錯誤 ({type(e).__name__})，等 {delay}s 再試 "
                    f"(第 {attempt + 1}/{max_retries} 次)")
            time.sleep(delay)
    raise last_error


def _load_image(path: Path) -> Image.Image:
    """載入圖片，自動旋轉 EXIF orientation"""
    img = Image.open(path)
    # 自動旋轉
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def _load_pdf_pages(path: Path, dpi: int = 250) -> list[Image.Image]:
    """PDF 全部頁面轉 PIL Image list（用 pypdfium2，純 Python 無外部 dep）

    DPI 用 250（清晰但唔太大）；如果係多頁 PDF 全部 send 俾 Gemini。
    """
    images = pdf_to_images(path, dpi=dpi, max_pages=10)
    out = []
    for img in images:
        if img.mode != "RGB":
            img = img.convert("RGB")
        out.append(img)
    return out


def _validate_items(data: dict, tolerance: float = 0.5) -> str | None:
    """檢查 items 加埋係咪等於 total。差太遠就返回 warning string"""
    items = data.get("items") or []
    if not items:
        return None
    total = data.get("total_amount") or 0
    if total <= 0:
        return None
    try:
        items_sum = sum(
            (it.get("price") or 0) * (it.get("quantity") or 1)
            for it in items
        )
    except (TypeError, ValueError):
        return None
    tax = data.get("tax") or 0
    expected = items_sum + tax
    diff = abs(expected - total)
    if diff > tolerance:
        return f"⚠️ Items 加埋 ${items_sum:.2f} + 稅 ${tax:.2f} = ${expected:.2f}，但 total = ${total:.2f}（差 ${diff:.2f}），可能漏咗 item"
    return None


def extract_receipt(file_path: str | Path) -> dict:
    """
    由單據圖片或 PDF 提取資料

    Returns:
        dict 包含：purchase_date, store_name, category, total_amount, currency,
                  payment_method, items, tax, receipt_number, notes,
                  source_file, extracted_at
    """
    if not GEMINI_API_KEY:
        raise ValueError(
            "❌ 未設定 GEMINI_API_KEY。\n"
            "請去 https://aistudio.google.com/apikey 攞 free key，"
            "然後寫入 .env 文件。"
        )

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"檔案唔存在：{path}")

    ext = path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        images = [_load_image(path)]
    elif ext in PDF_EXTENSIONS:
        images = _load_pdf_pages(path)
    else:
        raise ValueError(f"唔支援嘅格式：{ext}")

    # 多頁 PDF 嘅話加 prompt 提示
    prompt = EXTRACT_PROMPT
    if len(images) > 1:
        prompt = (f"【注意】呢張單據有 {len(images)} 頁，請仔細睇每一頁，"
                  f"items 全部都要 capture（每頁可能有唔同 person 嘅 order）。\n\n"
                  + EXTRACT_PROMPT)

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = _call_gemini_with_retry(
        client, GEMINI_MODEL,
        contents=[prompt, *images],
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8192,
            response_mime_type="application/json",
        ),
        max_retries=5,
    )

    raw = _strip_code_fence(response.text or "")
    finish_reason = _get_finish_reason(response)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        # 嘗試修補（特別係 MAX_TOKENS 截斷嘅情況）
        repaired = _repair_truncated_json(raw)
        if repaired is not None:
            try:
                data = json.loads(repaired)
                # 標記俾 user 知 items 可能不全
                data["_truncated"] = True
            except json.JSONDecodeError:
                repaired = None

        if not repaired:
            # 第二次 retry：要 AI 不返回 items 詳細，只要 totals
            retry_prompt = EXTRACT_PROMPT + (
                "\n\n【特別注意】上次輸出被截斷，今次 items array 最多列 10 個，"
                "其他並埋去 notes 入面。"
            )
            try:
                response2 = _call_gemini_with_retry(
                    client, GEMINI_MODEL,
                    contents=[retry_prompt, *images],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=8192,
                        response_mime_type="application/json",
                    ),
                    max_retries=5,
                )
                raw2 = _strip_code_fence(response2.text or "")
                data = json.loads(raw2)
            except (json.JSONDecodeError, Exception) as e2:
                # 仲係 fail，俾返清晰 error
                raise ValueError(
                    f"AI 返回 JSON 解析失敗 (finish_reason={finish_reason})：{e}\n"
                    f"已試過修補 + retry 都唔得。\n"
                    f"原文前 500 字：{raw[:500]}"
                )

    # 標準化欄位
    data.setdefault("purchase_date", None)
    data.setdefault("store_name", None)
    data.setdefault("category", "其他")
    data.setdefault("total_amount", 0.0)
    data.setdefault("currency", "HKD")
    data.setdefault("payment_method", None)
    data.setdefault("items", [])
    data.setdefault("tax", None)
    data.setdefault("receipt_number", None)
    data.setdefault("notes", None)

    # 確保 total_amount 係 float
    try:
        data["total_amount"] = float(data["total_amount"] or 0)
    except (TypeError, ValueError):
        data["total_amount"] = 0.0

    # 類別校正：如果 AI 返回唔喺 list 入面 → 強制改去「其他」
    if data["category"] not in CATEGORIES:
        # 嘗試 fuzzy 配對
        matched = None
        for cat in CATEGORIES:
            if cat in (data["category"] or "") or (data["category"] or "") in cat:
                matched = cat
                break
        data["category"] = matched or "其他"

    # === Validation: items 加埋啱唔啱 total？唔啱就 retry 一次 ===
    warning = _validate_items(data)
    if warning and not data.get("_truncated"):
        # 自動 retry：俾返之前 AI 出嘅 items 同 total，叫佢搵漏咗咩
        prev_items_json = json.dumps(data.get("items") or [], ensure_ascii=False)
        retry_prompt = EXTRACT_PROMPT + f"""

【⚠️ 第一次嘗試漏咗 item】
你上次返嘅 items 加埋 ≠ total {data.get('total_amount')}。
上次返嘅 items：{prev_items_json}
請再睇一次成張單（每一頁、每一個 section），搵返漏咗嘅 items。
items 加埋 + tax 一定要等於 total_amount。
"""
        try:
            response_retry = _call_gemini_with_retry(
                client, GEMINI_MODEL,
                contents=[retry_prompt, *images],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=8192,
                    response_mime_type="application/json",
                ),
                max_retries=5,
            )
            raw_retry = _strip_code_fence(response_retry.text or "")
            try:
                data_retry = json.loads(raw_retry)
            except json.JSONDecodeError:
                repaired = _repair_truncated_json(raw_retry)
                data_retry = json.loads(repaired) if repaired else None

            if data_retry:
                # 用 retry 結果如果 validation 比之前好
                new_warning = _validate_items(data_retry)
                if new_warning is None or (
                    new_warning and "差 $" in (warning or "") and "差 $" in new_warning
                    and float(new_warning.split("差 $")[1].split("）")[0]) <
                        float(warning.split("差 $")[1].split("）")[0])
                ):
                    # 保留原本 metadata，merge retry 結果
                    for k in ("items", "tax", "total_amount", "notes"):
                        if data_retry.get(k):
                            data[k] = data_retry[k]
                    warning = _validate_items(data)
        except Exception:
            pass  # retry 失敗就用原本結果

    # 喺 notes 加 warning，方便用家肉眼 check
    if warning:
        existing_notes = data.get("notes") or ""
        data["notes"] = f"{warning}\n{existing_notes}".strip()

    data["source_file"] = str(path.resolve())
    data["extracted_at"] = datetime.now().isoformat(timespec="seconds")

    return data


def extract_batch(folder: str | Path, progress_callback=None) -> list[dict]:
    """
    批量提取整個資料夾嘅單據

    Args:
        folder: 資料夾路徑
        progress_callback: callback(current, total, filename) - 每張單調用一次

    Returns:
        list of extracted dicts，包含 _error 欄位如果失敗
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError(f"唔係資料夾：{folder}")

    from config import SUPPORTED_EXTENSIONS
    files = sorted([
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ])

    results = []
    for i, f in enumerate(files, 1):
        if progress_callback:
            progress_callback(i, len(files), f.name)
        try:
            data = extract_receipt(f)
            results.append(data)
        except Exception as e:
            results.append({
                "source_file": str(f.resolve()),
                "_error": str(e),
                "extracted_at": datetime.now().isoformat(timespec="seconds"),
            })
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python extractor.py <receipt.jpg>")
        sys.exit(1)
    result = extract_receipt(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
