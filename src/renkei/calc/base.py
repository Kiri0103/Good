"""%Z 法（パーセントインピーダンス法）の基本換算ユーティリティ。

すべての要素インピーダンスを共通の基準容量 `base_mva`（基準電圧は各電圧階級の
公称電圧）に換算し、複素数 `R% + jX%`（単位 %, 基準容量基準）として扱う。

換算式（基準容量 Sb [MVA]、基準電圧 Vb [kV]）:
  基準電流  Ib [kA]      = Sb / (√3 · Vb)
  基準インピーダンス Zb [Ω] = Vb^2 / Sb
  Ω → %Z                : %Z = 100 · Z[Ω] / Zb = 100 · Z[Ω] · Sb / Vb^2
  自己容量%Z → 基準%Z   : %Z_base = %Z_self · (Sb / S_self)
  三相短絡容量 → %Z     : %Z = 100 · Sb / S_sc

これらはいずれも電力系統解析の標準式（例:『電気設備技術基準』関連の標準的な
%Z 法の教科書）に基づく。複素数表現により直列合成は単純な加算で行える。
"""
from __future__ import annotations

import cmath
import math

SQRT3 = math.sqrt(3.0)


def base_current_ka(base_mva: float, voltage_kv: float) -> float:
    """基準電流 Ib [kA] = Sb / (√3 · Vb)。"""
    return base_mva / (SQRT3 * voltage_kv)


def base_impedance_ohm(base_mva: float, voltage_kv: float) -> float:
    """基準インピーダンス Zb [Ω] = Vb^2 / Sb。"""
    return voltage_kv**2 / base_mva


def split_rx(pct_z_mag: float, xr_ratio: float) -> complex:
    """%Z の大きさと X/R 比から複素 %Z（R% + jX%）を作る。

    |Z| = sqrt(R^2 + X^2), X/R = xr_ratio より
      R = |Z| / sqrt(1 + (X/R)^2),  X = R · (X/R)
    """
    r = pct_z_mag / math.sqrt(1.0 + xr_ratio**2)
    x = r * xr_ratio
    return complex(r, x)


def grid_pct_z(
    *, short_circuit_capacity_mva: float, base_mva: float, xr_ratio: float
) -> complex:
    """系統の三相短絡容量から基準容量における複素 %Z を求める。"""
    mag = 100.0 * base_mva / short_circuit_capacity_mva
    return split_rx(mag, xr_ratio)


def transformer_pct_z(
    *, pct_z_self: float, rated_mva: float, base_mva: float, xr_ratio: float
) -> complex:
    """変圧器の自己容量基準%Z を基準容量へ換算した複素 %Z。"""
    mag = pct_z_self * (base_mva / rated_mva)
    return split_rx(mag, xr_ratio)


def line_pct_z(
    *,
    length_km: float,
    r_ohm_per_km: float,
    x_ohm_per_km: float,
    voltage_kv: float,
    base_mva: float,
    n_parallel: int = 1,
) -> complex:
    """線路・ケーブルの単位長インピーダンスから複素 %Z を求める。

    並列回線は Ω を 1/n 倍にしてから %Z 換算する。
    """
    r_ohm = r_ohm_per_km * length_km / n_parallel
    x_ohm = x_ohm_per_km * length_km / n_parallel
    zb = base_impedance_ohm(base_mva, voltage_kv)
    return complex(100.0 * r_ohm / zb, 100.0 * x_ohm / zb)


def pct_to_pu(pct_z: complex) -> complex:
    """%Z → 単位法（pu）。"""
    return pct_z / 100.0


def magnitude(pct_z: complex) -> float:
    """複素 %Z の大きさ |Z| [%]。"""
    return abs(pct_z)


def angle_deg(pct_z: complex) -> float:
    """複素 %Z の偏角 [deg]。"""
    return math.degrees(cmath.phase(pct_z))
