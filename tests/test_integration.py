"""サンプル案件のエンドツーエンド検算。"""
import math
from pathlib import Path

import pytest

from renkei.calc.impedance import build_impedance
from renkei.calc.shortcircuit import short_circuit
from renkei.calc.voltage import reactive_power_mvar, voltage_variation
from renkei.models.project import load_project

SAMPLE = Path(__file__).parent.parent / "examples" / "sample_66kv.yaml"


@pytest.fixture
def project():
    return load_project(SAMPLE)


def test_total_impedance(project):
    imp = build_impedance(project)
    # 手計算: R=0.41187%, X=6.83945%, |Z|=6.8519%
    assert math.isclose(imp.total_r_pct, 0.41187, abs_tol=1e-3)
    assert math.isclose(imp.total_x_pct, 6.83945, abs_tol=1e-3)
    assert math.isclose(imp.total_magnitude, 6.8519, abs_tol=1e-3)


def test_short_circuit(project):
    imp = build_impedance(project)
    sc = short_circuit(project, imp)
    # 三相短絡容量 = 10·100/6.8519 = 145.95 MVA
    assert math.isclose(sc.fault_mva, 145.95, rel_tol=2e-3)
    # 系統側短絡電流 ≈ 3.83 kA @22kV
    assert math.isclose(sc.grid_isc_ka, 3.830, rel_tol=2e-3)
    # PCS 寄与 ≈ 0.286 kA
    assert math.isclose(sc.pcs_isc_ka, 0.286, rel_tol=5e-3)


def test_reactive_power_sign():
    # 進み力率は Q<0（電圧上昇を抑える向き）, 遅れは Q>0
    assert reactive_power_mvar(9.0, 0.95, "進み") < 0
    assert reactive_power_mvar(9.0, 0.95, "遅れ") > 0
    # 力率1.0 なら Q=0
    assert math.isclose(reactive_power_mvar(9.0, 1.0, "進み"), 0.0, abs_tol=1e-9)


def test_voltage_variation(project):
    imp = build_impedance(project)
    vr = voltage_variation(project, imp)
    # ΔV ≈ -1.65 %（進み力率により電圧上昇を抑制）
    assert math.isclose(vr.delta_v_pct, -1.652, abs_tol=5e-3)
