"""短絡電流計算。

連系点までの総合 %Z（基準容量基準）から三相短絡容量・短絡電流を求める。
  三相短絡容量 Psc [MVA] = Sb · 100 / |%Z|
  三相短絡電流 Isc [kA]   = Ib · 100 / |%Z| = Psc / (√3 · V)

PCS（インバータ）は電流源としてふるまい、短絡電流への寄与は定格電流の数倍に
制限される（fault_current_pu）。系統側短絡電流に加算して連系点での合計を示す。
"""
from __future__ import annotations

from dataclasses import dataclass

from renkei.calc import base
from renkei.calc.impedance import ImpedanceResult
from renkei.models.project import Project


@dataclass
class ShortCircuitResult:
    base_mva: float
    voltage_kv: float
    total_pct_z: float
    fault_mva: float
    grid_isc_ka: float
    pcs_isc_ka: float

    @property
    def total_isc_ka(self) -> float:
        return self.grid_isc_ka + self.pcs_isc_ka


def short_circuit(
    project: Project, impedance: ImpedanceResult
) -> ShortCircuitResult:
    """連系点における三相短絡電流を求める。"""
    sb = project.base_mva
    v = project.poc_kv
    zmag = impedance.total_magnitude

    ib = base.base_current_ka(sb, v)
    grid_isc = ib * 100.0 / zmag
    fault_mva = sb * 100.0 / zmag

    # PCS の短絡電流寄与（定格電流 × fault_current_pu の総和）
    pcs_isc = 0.0
    for p in project.pcs:
        rated_kva = p.rated_kva if p.rated_kva is not None else p.rated_kw / p.power_factor
        rated_i_ka = (rated_kva / 1000.0) / (base.SQRT3 * v)
        pcs_isc += rated_i_ka * p.fault_current_pu * p.count

    return ShortCircuitResult(
        base_mva=sb,
        voltage_kv=v,
        total_pct_z=zmag,
        fault_mva=fault_mva,
        grid_isc_ka=grid_isc,
        pcs_isc_ka=pcs_isc,
    )
