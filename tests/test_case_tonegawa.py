"""仮想案件（利根川蓄電所 50MW/2H BESS）の整合と成果物生成を確認。"""
from pathlib import Path

import pytest

from renkei.models.project import load_project
from renkei.validate import validate

ROOT = Path(__file__).parent.parent
CASE = ROOT / "cases" / "tonegawa_bess.yaml"
TEMPLATE = ROOT / "reference" / "AK1T_202512r.xlsx"


@pytest.fixture
def project():
    return load_project(CASE)


def test_case_loads(project):
    assert project.name == "利根川蓄電所"
    # PowerTitan 2.0 2,500kW × 20台 = 50,000kW
    assert project.total_pcs_kw == 50000.0
    assert project.poc_kv == 22.0
    # 蓄電池 100,300kWh (= 5,015kWh × 20)
    assert project.battery[0].energy_kwh == 100300.0


def test_case_passes_check(project):
    report = validate(project)
    assert report.ok, "\n".join(str(f) for f in report.errors)


def test_no_pv_battery_only(project):
    """蓄電池単独: demand_pv は無し、demand_battery のみ。"""
    assert project.demand_pv is None
    assert project.demand_battery is not None


def test_short_circuit_within_breaker(project):
    from renkei.calc.impedance import build_impedance
    from renkei.calc.shortcircuit import short_circuit

    sc = short_circuit(project, build_impedance(project))
    assert sc.total_isc_ka < project.form4_2.breaker_breaking_ka
