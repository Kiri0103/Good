"""配置図 SVG 生成と配置検証のテスト。"""
from pathlib import Path

import pytest

from renkei.forms.layout import build_layout_svg, write_layout_svg
from renkei.models.project import Equipment, SiteLayout, load_project
from renkei.validate import validate

ROOT = Path(__file__).parent.parent
SAMPLE = ROOT / "examples" / "sample_66kv.yaml"


@pytest.fixture
def project():
    return load_project(SAMPLE)


def test_svg_wellformed_and_contains_equipment(project):
    import xml.dom.minidom as minidom

    svg = build_layout_svg(project.layout, title="配置図")
    dom = minidom.parseString(svg)
    assert dom.documentElement.tagName == "svg"
    assert "PCS-A" in svg and "蓄電池盤" in svg


def test_write_layout_svg(project, tmp_path):
    out = tmp_path / "layout.svg"
    p = write_layout_svg(project, out)
    assert p.exists() and p.read_text(encoding="utf-8").startswith("<?xml")


def test_write_requires_layout(project):
    project.layout = None
    with pytest.raises(ValueError):
        write_layout_svg(project, "/tmp/x.svg")


def test_sample_layout_passes(project):
    """整合済みサンプルの配置は ERROR なし。"""
    report = validate(project)
    codes = {f.code for f in report.errors}
    assert "L-BOUNDS" not in codes
    assert "L-OVERLAP" not in codes


def test_detects_out_of_bounds(project):
    """手動配置（auto_arrange=False）での敷地外はみ出しを検出。"""
    project.layout.auto_arrange = False
    project.layout.equipment.append(
        Equipment(name="はみ出し", x_m=58, y_m=38, width_m=10, depth_m=10)
    )
    report = validate(project)
    assert "L-BOUNDS" in {f.code for f in report.errors}


def test_detects_overlap():
    """機器の重なりを検出。"""
    lay = SiteLayout(
        site_width_m=20, site_depth_m=20,
        equipment=[
            Equipment(name="A", x_m=0, y_m=0, width_m=10, depth_m=10),
            Equipment(name="B", x_m=5, y_m=5, width_m=10, depth_m=10),
        ],
    )
    from renkei.models.project import Project, GridSource

    p = Project(name="t", grid=GridSource(voltage_kv=22, short_circuit_capacity_mva=1000), layout=lay)
    report = validate(p)
    assert "L-OVERLAP" in {f.code for f in report.errors}


def test_detects_clearance_violation():
    """離隔不足を WARNING で検出。"""
    lay = SiteLayout(
        site_width_m=30, site_depth_m=20, min_clearance_m=2.0,
        equipment=[
            Equipment(name="A", x_m=0, y_m=0, width_m=10, depth_m=5),
            Equipment(name="B", x_m=10.5, y_m=0, width_m=10, depth_m=5),  # 隙間0.5m
        ],
    )
    from renkei.models.project import Project, GridSource

    p = Project(name="t", grid=GridSource(voltage_kv=22, short_circuit_capacity_mva=1000), layout=lay)
    report = validate(p)
    assert "L-CLEAR" in {f.code for f in report.warnings}
