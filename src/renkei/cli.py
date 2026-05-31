"""コマンドラインインタフェース。

  renkei calc <案件YAML>       計算してレポートを標準出力
  renkei calc <案件YAML> -o out.txt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from renkei.calc.impedance import build_impedance
from renkei.calc.shortcircuit import short_circuit
from renkei.calc.voltage import voltage_variation
from renkei.models.project import load_project
from renkei.report import build_report


def _cmd_calc(args: argparse.Namespace) -> int:
    project = load_project(args.project)
    impedance = build_impedance(project)
    sc = short_circuit(project, impedance)
    vr = voltage_variation(project, impedance)
    report = build_report(project, impedance, sc, vr)

    if args.output:
        Path(args.output).write_text(report + "\n", encoding="utf-8")
        print(f"レポートを書き出しました: {args.output}")
    else:
        print(report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="renkei",
        description="特別高圧 接続検討 設計計算ツール",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_calc = sub.add_parser("calc", help="案件情報から設計計算を実行")
    p_calc.add_argument("project", help="案件情報 YAML/JSON ファイル")
    p_calc.add_argument("-o", "--output", help="レポート出力先ファイル")
    p_calc.set_defaults(func=_cmd_calc)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
