#!/usr/bin/env python3
"""AK1T 様式 Excel の構造ダンプ（フィールドマップ作成・検証の補助ツール）。

使い方:
  python3 tools/dump_form.py <xlsx> [シート名]
  python3 tools/dump_form.py reference/AK1T_202512r.xlsx "様式４の１(変圧器・線路)"

シート名省略時はシート一覧を表示。
各シートについて、ラベル（文字列）セル・結合範囲・データ入力規則（ドロップダウン）を
セル番地つきで出力する。これを見ながら forms/ak1t/fieldmap.yaml を組み立てる。
"""
from __future__ import annotations

import sys
import warnings

import openpyxl

warnings.filterwarnings("ignore")


def dump_sheet(ws) -> None:
    print(f"\n########## SHEET: {ws.title}  dims={ws.dimensions} ##########")

    print("--- merged ranges ---")
    for rng in sorted(ws.merged_cells.ranges, key=lambda r: (r.min_row, r.min_col)):
        print(f"  {rng}")

    print("--- labels (non-empty text cells) ---")
    for row in ws.iter_rows():
        for c in row:
            if c.value is None:
                continue
            s = str(c.value).strip()
            if s:
                print(f"  {c.coordinate}\t{s}")

    print("--- data validations (dropdowns) ---")
    for dv in ws.data_validations.dataValidation:
        print(f"  {dv.sqref}\t{dv.type}\t{dv.formula1}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    wb = openpyxl.load_workbook(argv[1], data_only=False)
    if len(argv) >= 3:
        dump_sheet(wb[argv[2]])
    else:
        print("=== SHEETS ===")
        for ws in wb.worksheets:
            print(f"  [{ws.sheet_state}] {ws.title}  dims={ws.dimensions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
