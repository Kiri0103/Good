"""提出前チェック（検証エンジン）の検証。"""
import copy
from pathlib import Path

import pytest

from renkei.models.project import load_project
from renkei.validate import Severity, validate

ROOT = Path(__file__).parent.parent
SAMPLE = ROOT / "examples" / "sample_66kv.yaml"


@pytest.fixture
def project():
    return load_project(SAMPLE)


def test_sample_passes(project):
    """整合済みサンプルは ERROR なし。"""
    report = validate(project)
    assert report.ok, "\n".join(str(f) for f in report.errors)


def test_detects_voltage_mismatch(project):
    """希望受電電圧と連系点電圧の不一致を検出。"""
    p = project.model_copy(deep=True)
    p.form2.desired_voltage_kv = 66.0  # 連系点は22kV
    report = validate(p)
    codes = {f.code for f in report.errors}
    assert "V-VOLT-POC" in codes


def test_detects_output_total_mismatch(project):
    """定格出力合計と PCS 合計出力の不一致を検出。"""
    p = project.model_copy(deep=True)
    p.form2.rated_total_kw = 5000.0  # 実際は 9000kW
    report = validate(p)
    codes = {f.code for f in report.errors}
    assert "V-OUT-TOTAL" in codes


def test_detects_breaker_undersized(project):
    """遮断器の定格遮断電流が短絡電流未満なら ERROR。"""
    p = project.model_copy(deep=True)
    p.form4_2.breaker_breaking_ka = 1.0  # 短絡電流(約4kA)未満
    report = validate(p)
    codes = {f.code for f in report.errors}
    assert "V-SC-CB" in codes


def test_detects_breaker_voltage_low(project):
    """遮断器定格電圧が連系点電圧未満なら ERROR。"""
    p = project.model_copy(deep=True)
    p.form4_2.breaker_voltage_kv = 6.6  # 連系点22kV未満
    report = validate(p)
    codes = {f.code for f in report.errors}
    assert "V-VOLT-CB" in codes


def test_detects_demand_length(project):
    """需給パターンが24点でないと ERROR。"""
    p = project.model_copy(deep=True)
    p.demand_pv.active_a = [100.0, 200.0]  # 2点のみ
    report = validate(p)
    codes = {f.code for f in report.errors}
    assert "V-DEM-LEN" in codes


def test_missing_form1_warns(project):
    """様式1未入力は WARNING。"""
    p = project.model_copy(deep=True)
    p.form1 = None
    report = validate(p)
    codes = {f.code for f in report.warnings}
    assert "R-FORM1" in codes


def test_report_exit_semantics(project):
    """ERROR があれば ok=False。"""
    p = project.model_copy(deep=True)
    p.form2.desired_voltage_kv = 999.0
    report = validate(p)
    assert not report.ok
    assert any(f.severity == Severity.ERROR for f in report.findings)
