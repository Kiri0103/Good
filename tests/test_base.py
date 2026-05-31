"""%Z 法 基本換算の検算（手計算と一致することを確認）。"""
import math

from renkei.calc import base


def test_base_current():
    # Ib = 10 / (√3 · 22) = 0.262433 kA
    assert math.isclose(base.base_current_ka(10.0, 22.0), 0.262433, rel_tol=1e-4)


def test_base_impedance():
    # Zb = 22^2 / 10 = 48.4 Ω
    assert math.isclose(base.base_impedance_ohm(10.0, 22.0), 48.4, rel_tol=1e-9)


def test_split_rx():
    z = base.split_rx(10.0, 10.0)  # |Z|=10, X/R=10
    assert math.isclose(abs(z), 10.0, rel_tol=1e-9)
    assert math.isclose(z.imag / z.real, 10.0, rel_tol=1e-9)


def test_grid_pct_z():
    # |Z| = 100 · 10 / 1500 = 0.66667 %
    z = base.grid_pct_z(short_circuit_capacity_mva=1500.0, base_mva=10.0, xr_ratio=10.0)
    assert math.isclose(abs(z), 100.0 * 10.0 / 1500.0, rel_tol=1e-9)


def test_transformer_pct_z():
    # 12% · (10/20) = 6.0 %
    z = base.transformer_pct_z(pct_z_self=12.0, rated_mva=20.0, base_mva=10.0, xr_ratio=20.0)
    assert math.isclose(abs(z), 6.0, rel_tol=1e-9)


def test_line_pct_z():
    # Zb(66kV,10MVA)=435.6Ω, R=0.2Ω→0.04591%, X=0.8Ω→0.18365%
    z = base.line_pct_z(
        length_km=2.0,
        r_ohm_per_km=0.1,
        x_ohm_per_km=0.4,
        voltage_kv=66.0,
        base_mva=10.0,
    )
    zb = 66.0**2 / 10.0
    assert math.isclose(z.real, 100.0 * 0.2 / zb, rel_tol=1e-9)
    assert math.isclose(z.imag, 100.0 * 0.8 / zb, rel_tol=1e-9)


def test_line_parallel_halves_impedance():
    single = base.line_pct_z(
        length_km=2.0, r_ohm_per_km=0.1, x_ohm_per_km=0.4, voltage_kv=66.0, base_mva=10.0
    )
    double = base.line_pct_z(
        length_km=2.0, r_ohm_per_km=0.1, x_ohm_per_km=0.4, voltage_kv=66.0,
        base_mva=10.0, n_parallel=2,
    )
    assert math.isclose(double.real, single.real / 2, rel_tol=1e-9)
    assert math.isclose(double.imag, single.imag / 2, rel_tol=1e-9)
