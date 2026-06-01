"""実案件ベース（SGET札幌 50MW/175.5MWh BESS）の整合確認。"""
from pathlib import Path

import pytest

from renkei.models.project import load_project
from renkei.validate import validate

ROOT = Path(__file__).parent.parent
CASE = ROOT / "cases" / "sget_sapporo.yaml"


@pytest.fixture
def project():
    return load_project(CASE)


def test_case_loads(project):
    assert "SGET札幌" in project.name
    # 50MW: 1,429kW × 35ユニット ≒ 50,015kW
    assert abs(project.total_pcs_kw - 50000.0) < 100.0
    # 175.5MWh
    assert project.battery[0].energy_kwh == 175525.0
    assert project.poc_kv == 33.0


def test_case_passes_check(project):
    report = validate(project)
    assert report.ok, "\n".join(str(f) for f in report.errors)


def test_battery_only_no_pv(project):
    assert project.demand_pv is None
    assert project.demand_battery is not None


def test_short_circuit_within_breaker(project):
    from renkei.calc.impedance import build_impedance
    from renkei.calc.shortcircuit import short_circuit

    sc = short_circuit(project, build_impedance(project))
    assert sc.total_isc_ka < project.form4_2.breaker_breaking_ka
