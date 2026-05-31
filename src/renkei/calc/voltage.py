"""電圧変動・力率の計算。

逆潮流（送電）時の連系点電圧上昇を %Z 法で近似する。
  ΔV[%] ≈ ( P[MW]·R[%] + Q[Mvar]·X[%] ) / Sb[MVA]
ここで R[%], X[%] は連系点から系統電源側を見た総合インピーダンス（基準容量基準）。
P は逆潮流有効電力（送電を正）、Q は無効電力。

無効電力の符号（要確認）:
  本実装では「遅れ力率＝Q>0（誘導性, 電圧を上げる向き）」「進み力率＝Q<0（容量性,
  電圧上昇を抑える向き）」と定義する。各社・各現場の符号定義に合わせて要確認。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from renkei.calc.impedance import ImpedanceResult
from renkei.models.project import Project


@dataclass
class VoltageResult:
    base_mva: float
    p_mw: float
    q_mvar: float
    r_pct: float
    x_pct: float
    delta_v_pct: float


def reactive_power_mvar(p_mw: float, power_factor: float, mode: str) -> float:
    """有効電力・力率・進み遅れから無効電力 [Mvar]（符号付き）を求める。

    Q = ±P·tan(acos(pf)) ; 遅れ:+ / 進み:- （docstring の符号定義に従う）
    """
    pf = max(min(power_factor, 1.0), 1e-9)
    q_mag = p_mw * math.tan(math.acos(pf))
    return q_mag if mode == "遅れ" else -q_mag


def voltage_variation(
    project: Project, impedance: ImpedanceResult
) -> VoltageResult:
    """逆潮流時の連系点電圧変動 ΔV[%] を求める。"""
    sb = project.base_mva
    p = project.export_power_mw
    q = reactive_power_mvar(
        p, project.operating_power_factor, project.power_factor_mode
    )
    r = impedance.total_r_pct
    x = impedance.total_x_pct
    delta_v = (p * r + q * x) / sb
    return VoltageResult(
        base_mva=sb,
        p_mw=p,
        q_mvar=q,
        r_pct=r,
        x_pct=x,
        delta_v_pct=delta_v,
    )
