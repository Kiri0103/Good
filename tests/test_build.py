"""一括生成コマンド build と SVG フォント解決のテスト。"""
from pathlib import Path

import pytest

from renkei.cli import main
from renkei.forms._svg import font_stack

ROOT = Path(__file__).parent.parent
SAMPLE = ROOT / "examples" / "sample_66kv.yaml"
TEMPLATE = ROOT / "reference" / "AK1T_202512r.xlsx"


def test_font_stack_nonempty():
    """フォントスタックが取得でき、sans-serif で終わる。"""
    fs = font_stack()
    assert fs.endswith("sans-serif")
    assert "," in fs


def test_build_generates_all_artifacts(tmp_path):
    out = tmp_path / "out"
    rc = main(["build", str(SAMPLE), "-d", str(out), "-t", str(TEMPLATE)])
    assert rc == 0  # サンプルは ERROR なし
    assert (out / "report.txt").exists()
    assert (out / "single_line_diagram.svg").exists()
    assert (out / "site_layout.svg").exists()
    assert (out / "check.txt").exists()
    if TEMPLATE.exists():
        assert (out / "AK1T.xlsx").exists()


def test_build_skips_xlsx_without_template(tmp_path):
    out = tmp_path / "out2"
    rc = main(["build", str(SAMPLE), "-d", str(out), "-t", str(tmp_path / "nope.xlsx")])
    assert rc == 0
    assert (out / "report.txt").exists()
    assert not (out / "AK1T.xlsx").exists()  # テンプレート無し → スキップ


def test_build_returns_1_on_error(tmp_path):
    """ERROR を含む案件は終了コード 1（成果物は生成される）。"""
    import yaml

    data = yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))
    data["form2"]["desired_voltage_kv"] = 999.0  # 連系点電圧と不一致 → ERROR
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    out = tmp_path / "out3"
    rc = main(["build", str(bad), "-d", str(out), "-t", "nonexistent.xlsx"])
    assert rc == 1
    assert (out / "check.txt").exists()
    assert "ERROR" in (out / "check.txt").read_text(encoding="utf-8")


def test_svg_uses_detected_font():
    """生成 SVG にフォントスタックが埋め込まれている。"""
    from renkei.forms.sld import build_sld_svg
    from renkei.models.project import load_project

    svg = build_sld_svg(load_project(SAMPLE))
    assert "font-family=" in svg
    assert font_stack() in svg
