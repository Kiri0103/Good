"""単線結線図 SVG 生成の検証。"""
from pathlib import Path

import pytest

from renkei.forms.sld import build_sld_svg, write_sld_svg
from renkei.models.project import load_project

ROOT = Path(__file__).parent.parent
SAMPLE = ROOT / "examples" / "sample_66kv.yaml"


@pytest.fixture
def project():
    return load_project(SAMPLE)


def test_svg_is_wellformed(project):
    import xml.dom.minidom as minidom

    svg = build_sld_svg(project)
    # パース可能（整形式 XML）であること
    dom = minidom.parseString(svg)
    assert dom.documentElement.tagName == "svg"


def test_svg_contains_components(project):
    svg = build_sld_svg(project)
    # 主要機器のラベルが含まれること
    assert "系統(66kV)" in svg
    assert "受電変圧器(66/22kV)" in svg
    assert "連系点" in svg
    assert "PCS-500" in svg
    assert "蓄電池" in svg


def test_write_sld_svg(project, tmp_path):
    out = tmp_path / "sld.svg"
    p = write_sld_svg(project, out)
    assert p.exists()
    assert p.read_text(encoding="utf-8").startswith("<?xml")
