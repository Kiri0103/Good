"""仮想案件（房総みらい）が整合し、全成果物が生成できることを確認。"""
from pathlib import Path

import pytest

from renkei.models.project import load_project
from renkei.validate import validate

ROOT = Path(__file__).parent.parent
CASE = ROOT / "cases" / "boso_mirai.yaml"
TEMPLATE = ROOT / "reference" / "AK1T_202512r.xlsx"


@pytest.fixture
def project():
    return load_project(CASE)


def test_case_loads(project):
    assert project.name.startswith("房総みらい")
    assert project.total_pcs_kw == 20000.0       # 2500kW × 8台
    assert project.poc_kv == 22.0


def test_case_passes_check(project):
    """仮想案件は様式間整合 ERROR なし。"""
    report = validate(project)
    assert report.ok, "\n".join(str(f) for f in report.errors)


def test_case_short_circuit_within_breaker(project):
    """合計短絡電流が遮断器定格遮断電流以内。"""
    from renkei.calc.impedance import build_impedance
    from renkei.calc.shortcircuit import short_circuit

    sc = short_circuit(project, build_impedance(project))
    assert sc.total_isc_ka < project.form4_2.breaker_breaking_ka


def test_case_build_all(project, tmp_path):
    from renkei.cli import main

    out = tmp_path / "out"
    rc = main(["build", str(CASE), "-d", str(out), "-t", str(TEMPLATE)])
    assert rc == 0
    for f in ["report.txt", "single_line_diagram.svg", "site_layout.svg", "check.txt"]:
        assert (out / f).exists()
