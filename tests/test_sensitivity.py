"""前提値 感度分析の検証。"""
from pathlib import Path

import pytest

from renkei.models.project import load_project
from renkei.sensitivity import format_sensitivity, run_sensitivity

ROOT = Path(__file__).parent.parent
SAMPLE = ROOT / "examples" / "sample_66kv.yaml"


@pytest.fixture
def project():
    return load_project(SAMPLE)


def test_report_structure(project):
    rep = run_sensitivity(project)
    assert len(rep.xr) == 3
    assert len(rep.pcs_fault) == 4
    assert len(rep.pf_mode) == 2


def test_pcs_fault_increases_short_circuit(project):
    """PCS 短絡寄与を上げると合計短絡電流が単調増加する。"""
    rep = run_sensitivity(project)
    iscs = [s.metrics.total_isc_ka for s in rep.pcs_fault]
    assert iscs == sorted(iscs)
    assert iscs[-1] > iscs[0]


def test_pf_mode_flips_dv_sign(project):
    """進み/遅れで ΔV の符号が変わる（無効電力符号の影響を確認）。"""
    rep = run_sensitivity(project)
    by_label = {s.label: s.metrics.delta_v_pct for s in rep.pf_mode}
    assert by_label["力率 進み"] < 0 < by_label["力率 遅れ"]


def test_xr_barely_changes_impedance_magnitude(project):
    """X/R 比を振っても |Z| はほぼ不変（短絡電流に影響しない）。"""
    rep = run_sensitivity(project)
    zs = [s.metrics.total_z_pct for s in rep.xr]
    assert max(zs) - min(zs) < 0.01  # %


def test_format_contains_margins(project):
    text = format_sensitivity(project_name="t", report=run_sensitivity(project),
                              breaker_ka=31.5, dv_limit_pct=2.0)
    assert "遮断器定格遮断" in text
    assert "電圧変動上限" in text
    assert "OK" in text  # 遮断器は余裕大
