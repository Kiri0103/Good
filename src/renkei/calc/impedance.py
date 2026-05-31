"""ネットワークのインピーダンス合成（放射状・直列構成）。

系統電源から連系点までの各構成要素（系統・線路・変圧器）の複素 %Z を共通基準容量
に換算し、直列加算して連系点までの総合 %Z を求める。
"""
from __future__ import annotations

from dataclasses import dataclass

from renkei.calc import base
from renkei.models.project import Line, Project, Transformer


@dataclass
class ImpedanceTerm:
    """1 構成要素の %Z（基準容量基準, 複素）。"""

    name: str
    pct_z: complex

    @property
    def magnitude(self) -> float:
        return base.magnitude(self.pct_z)

    @property
    def r_pct(self) -> float:
        return self.pct_z.real

    @property
    def x_pct(self) -> float:
        return self.pct_z.imag


@dataclass
class ImpedanceResult:
    """連系点までの総合インピーダンス計算結果。"""

    base_mva: float
    terms: list[ImpedanceTerm]

    @property
    def total(self) -> complex:
        """直列総合 %Z（複素, 基準容量基準）。"""
        z = 0j
        for t in self.terms:
            z += t.pct_z
        return z

    @property
    def total_magnitude(self) -> float:
        return base.magnitude(self.total)

    @property
    def total_r_pct(self) -> float:
        return self.total.real

    @property
    def total_x_pct(self) -> float:
        return self.total.imag


def build_impedance(project: Project) -> ImpedanceResult:
    """案件情報から系統〜連系点の直列 %Z を構築する。"""
    sb = project.base_mva
    terms: list[ImpedanceTerm] = []

    # 系統
    g = project.grid
    if g.short_circuit_capacity_mva is not None:
        z_grid = base.grid_pct_z(
            short_circuit_capacity_mva=g.short_circuit_capacity_mva,
            base_mva=sb,
            xr_ratio=g.xr_ratio,
        )
    else:
        z_grid = base.split_rx(g.pct_z, g.xr_ratio)  # type: ignore[arg-type]
    terms.append(ImpedanceTerm(g.name, z_grid))

    # 直列構成要素（系統→連系点の順）
    for comp in project.network:
        if isinstance(comp, Transformer):
            if not comp.in_series:
                continue  # 下流の昇圧変圧器等は連系点までの直列経路に含めない
            z = base.transformer_pct_z(
                pct_z_self=comp.pct_z,
                rated_mva=comp.rated_mva,
                base_mva=sb,
                xr_ratio=comp.xr_ratio,
            )
        elif isinstance(comp, Line):
            z = base.line_pct_z(
                length_km=comp.length_km,
                r_ohm_per_km=comp.r_ohm_per_km,
                x_ohm_per_km=comp.x_ohm_per_km,
                voltage_kv=comp.voltage_kv,
                base_mva=sb,
                n_parallel=comp.n_parallel,
            )
        else:  # pragma: no cover - 型で保証
            raise TypeError(f"未知の構成要素: {comp!r}")
        terms.append(ImpedanceTerm(comp.name, z))

    return ImpedanceResult(base_mva=sb, terms=terms)
