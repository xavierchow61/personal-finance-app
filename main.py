"""命令列版本 - 唔想開 GUI 嘅話用呢個

用法:
    python main.py receipt.jpg              # 單張
    python main.py folder_path/             # 整個資料夾
    python main.py receipt.jpg --export     # 提取後即時匯出 Excel
    python main.py --export-only            # 只匯出（用 DB 入面已有嘅資料）
"""
import argparse
import sys
from pathlib import Path

import database
import excel_exporter
from extractor import extract_batch, extract_receipt


def main():
    parser = argparse.ArgumentParser(description="商店單據 AI 提取 + Excel Dashboard")
    parser.add_argument("input", nargs="?", help="單據圖片 / PDF / 資料夾")
    parser.add_argument("--export", action="store_true",
                        help="提取後即時匯出 Excel")
    parser.add_argument("--export-only", action="store_true",
                        help="只匯出 Excel（用 DB 已有資料）")
    args = parser.parse_args()

    database.init_db()

    if args.export_only:
        if database.count() == 0:
            print("❌ DB 入面冇單據，請先提取。")
            sys.exit(1)
        path = excel_exporter.export_excel()
        print(f"✅ 已匯出：{path}")
        return

    if not args.input:
        parser.print_help()
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 唔存在：{input_path}")
        sys.exit(1)

    if input_path.is_dir():
        print(f"\n📂 批量處理：{input_path}")
        print("=" * 60)

        def progress(i, total, name):
            print(f"  [{i}/{total}] {name}")

        results = extract_batch(input_path, progress_callback=progress)
        ok = 0
        for r in results:
            if "_error" in r:
                print(f"❌ {Path(r['source_file']).name}: {r['_error']}")
            else:
                inv_id = database.save_invoice(r)
                ok += 1
                print(f"✅ #{inv_id} | {r.get('store_name', '?')} | "
                      f"{r.get('category', '?')} | "
                      f"${r.get('total_amount', 0):.2f}")
        print(f"\n📊 成功 {ok}/{len(results)}")
    else:
        print(f"\n🔍 處理：{input_path}")
        data = extract_receipt(input_path)
        inv_id = database.save_invoice(data)
        print(f"\n✅ 已存入 DB (id={inv_id})")
        print(f"  購買日期：{data.get('purchase_date')}")
        print(f"  商店：{data.get('store_name')}")
        print(f"  類別：{data.get('category')}")
        print(f"  金額：{data.get('total_amount')} {data.get('currency')}")
        print(f"  付款：{data.get('payment_method')}")
        if data.get("items"):
            print(f"  產品：")
            for it in data["items"]:
                print(f"    • {it.get('name')} x{it.get('quantity')} ${it.get('price')}")

    if args.export:
        path = excel_exporter.export_excel()
        print(f"\n📊 Excel 已匯出：{path}")


if __name__ == "__main__":
    main()
