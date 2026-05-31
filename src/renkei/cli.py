"""コマンドラインインタフェース。

  renkei calc  <案件YAML> [-o out.txt]    設計計算レポート
  renkei fill  <案件YAML> -o out.xlsx     AK1T 様式へ自動転記
  renkei sld    <案件YAML> [-o out.svg]   単線結線図 SVG 生成
  renkei layout <案件YAML> [-o out.svg]   配置図 SVG 生成
  renkei check  <案件YAML>                提出前チェック（様式間整合の検証）
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


def _cmd_fill(args: argparse.Namespace) -> int:
    from renkei.forms.ak1t import fill_ak1t

    project = load_project(args.project)
    written = fill_ak1t(project, args.template, args.output)
    print(f"AK1T 様式へ転記しました: {args.output}")
    for sheet, n in written.items():
        print(f"  {sheet}: {n} 件")
    return 0


def _cmd_sld(args: argparse.Namespace) -> int:
    from renkei.forms.sld import write_sld_svg

    project = load_project(args.project)
    out = write_sld_svg(project, args.output)
    print(f"単線結線図 SVG を書き出しました: {out}")
    return 0


def _cmd_layout(args: argparse.Namespace) -> int:
    from renkei.forms.layout import write_layout_svg

    project = load_project(args.project)
    out = write_layout_svg(project, args.output)
    print(f"配置図 SVG を書き出しました: {out}")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    from renkei.validate import format_report, validate

    project = load_project(args.project)
    report = validate(project)
    text = format_report(report, project.name)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(f"チェック結果を書き出しました: {args.output}")
    else:
        print(text)
    # ERROR があれば終了コード 1（CI 等で検出できるように）
    return 0 if report.ok else 1


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

    p_fill = sub.add_parser("fill", help="案件情報を AK1T 様式へ転記")
    p_fill.add_argument("project", help="案件情報 YAML/JSON ファイル")
    p_fill.add_argument(
        "-t",
        "--template",
        default="reference/AK1T_202512r.xlsx",
        help="AK1T テンプレート xlsx（既定: reference/AK1T_202512r.xlsx）",
    )
    p_fill.add_argument(
        "-o", "--output", required=True, help="記入済み xlsx の出力先"
    )
    p_fill.set_defaults(func=_cmd_fill)

    p_sld = sub.add_parser("sld", help="機器構成から単線結線図 SVG を生成")
    p_sld.add_argument("project", help="案件情報 YAML/JSON ファイル")
    p_sld.add_argument(
        "-o", "--output", default="single_line_diagram.svg", help="SVG 出力先"
    )
    p_sld.set_defaults(func=_cmd_sld)

    p_layout = sub.add_parser("layout", help="敷地・機器配置から配置図 SVG を生成")
    p_layout.add_argument("project", help="案件情報 YAML/JSON ファイル")
    p_layout.add_argument(
        "-o", "--output", default="site_layout.svg", help="SVG 出力先"
    )
    p_layout.set_defaults(func=_cmd_layout)

    p_check = sub.add_parser("check", help="提出前チェック（様式間整合の検証）")
    p_check.add_argument("project", help="案件情報 YAML/JSON ファイル")
    p_check.add_argument("-o", "--output", help="チェック結果の出力先ファイル")
    p_check.set_defaults(func=_cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
