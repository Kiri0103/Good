"""前提値の感度分析（実案件適用前の精度検証）。

接続検討では一部の入力（X/R 比・PCS の短絡寄与倍率・無効電力の進み/遅れ）が
メーカ仕様や電力会社提示待ちで暫定値のことがある。本モジュールはこれらを
妥当な範囲で振り、主要指標（連系点総合 %Z・三相短絡電流・逆潮流時 ΔV）への
影響量を定量化する。「前提値の不確かさが判定（遮断器容量・電圧変動）を覆さないか」
を機械的に確認し、確実な提出物を担保することが目的。

各シナリオは元の Project を複製して該当値のみ差し替え、calc を再実行する。
"""
from __future__ import annotations

from dataclasses import dataclass

from renkei.calc.impedance import build_impedance
from renkei.calc.shortcircuit import short_circuit
from renkei.calc.voltage import voltage_variation
from renkei.models.project import Line, Project, Transformer


@dataclass
class Metrics:
    """1 シナリオの主要指標。"""

    total_z_pct: float       # 連系点 総合 %Z（大きさ）
    grid_isc_ka: float       # 系統側短絡電流
    pcs_isc_ka: float        # PCS 寄与短絡電流
    total_isc_ka: float      # 合計短絡電流
    delta_v_pct: float       # 逆潮流時 電圧変動


@dataclass
class Scenario:
    label: str
    metrics: Metrics


def _metrics(project: Project) -> Metrics:
    imp = build_impedance(project)
    sc = short_circuit(project, imp)
    vr = voltage_variation(project, imp)
    return Metrics(
        total_z_pct=imp.total_magnitude,
        grid_isc_ka=sc.grid_isc_ka,
        pcs_isc_ka=sc.pcs_isc_ka,
        total_isc_ka=sc.total_isc_ka,
        delta_v_pct=vr.delta_v_pct,
    )


def _with_xr(project: Project, factor: float) -> Project:
    """全要素（系統・変圧器）の X/R 比を factor 倍した複製を返す。"""
    p = project.model_copy(deep=True)
    p.grid.xr_ratio = p.grid.xr_ratio * factor
    for comp in p.network:
        if isinstance(comp, Transformer):
            comp.xr_ratio = comp.xr_ratio * factor
    return p


def _with_pcs_fault(project: Project, value: float) -> Project:
    """全 PCS の fault_current_pu を value に置き換えた複製を返す。"""
    p = project.model_copy(deep=True)
    for pcs in p.pcs:
        pcs.fault_current_pu = value
    return p


def _with_pf_mode(project: Project, mode: str) -> Project:
    p = project.model_copy(deep=True)
    p.power_factor_mode = mode  # type: ignore[assignment]
    return p


@dataclass
class SensitivityReport:
    base: Metrics
    xr: list[Scenario]
    pcs_fault: list[Scenario]
    pf_mode: list[Scenario]


def run_sensitivity(
    project: Project,
    *,
    xr_factors: tuple[float, ...] = (0.5, 1.0, 2.0),
    pcs_fault_values: tuple[float, ...] = (1.0, 1.1, 1.5, 2.0),
) -> SensitivityReport:
    """前提値を振って感度分析を実行する。"""
    base = _metrics(project)

    xr = [
        Scenario(f"X/R ×{f:g}", _metrics(_with_xr(project, f)))
        for f in xr_factors
    ]
    pcs_fault = [
        Scenario(f"PCS寄与 {v:g}pu", _metrics(_with_pcs_fault(project, v)))
        for v in pcs_fault_values
    ]
    pf_mode = [
        Scenario(f"力率 {m}", _metrics(_with_pf_mode(project, m)))
        for m in ("進み", "遅れ")
    ]
    return SensitivityReport(base=base, xr=xr, pcs_fault=pcs_fault, pf_mode=pf_mode)


def format_sensitivity(
    report: SensitivityReport,
    project_name: str = "",
    breaker_ka: float | None = None,
    dv_limit_pct: float | None = None,
) -> str:
    """感度分析結果をテキスト整形。判定値（遮断器・ΔV上限）があれば余裕も表示。"""
    lines: list[str] = []
    a = lines.append
    a("=" * 70)
    a(f"前提値 感度分析 : {project_name}" if project_name else "前提値 感度分析")
    a("=" * 70)

    b = report.base
    a("【基準ケース】")
    a(f"  総合%Z = {b.total_z_pct:.4f} %")
    a(f"  短絡電流 = {b.total_isc_ka:.3f} kA "
      f"(系統 {b.grid_isc_ka:.3f} + PCS {b.pcs_isc_ka:.3f})")
    a(f"  ΔV = {b.delta_v_pct:+.3f} %")

    def _block(title: str, scenarios: list[Scenario], focus: str) -> None:
        a("")
        a(f"【{title}】")
        a(f"  {'シナリオ':<14}{'総合%Z':>10}{'短絡kA':>10}{'ΔV%':>10}")
        for s in scenarios:
            m = s.metrics
            a(f"  {s.label:<14}{m.total_z_pct:>10.4f}"
              f"{m.total_isc_ka:>10.3f}{m.delta_v_pct:>+10.3f}")

    _block("X/R 比 感度", report.xr, "dv")
    _block("PCS 短絡寄与 感度", report.pcs_fault, "isc")
    _block("無効電力 符号（進み/遅れ）感度", report.pf_mode, "dv")

    # 判定余裕（最悪ケースで評価）
    a("")
    a("【判定余裕（全シナリオの最悪値で評価）】")
    all_sc = report.xr + report.pcs_fault + report.pf_mode + [Scenario("基準", report.base)]
    worst_isc = max(s.metrics.total_isc_ka for s in all_sc)
    worst_dv = max(abs(s.metrics.delta_v_pct) for s in all_sc)
    a(f"  最大短絡電流 = {worst_isc:.3f} kA")
    if breaker_ka is not None:
        margin = breaker_ka - worst_isc
        ok = "OK" if margin >= 0 else "NG"
        a(f"    遮断器定格遮断 {breaker_ka:g} kA に対し余裕 {margin:+.3f} kA [{ok}]")
    a(f"  最大|ΔV| = {worst_dv:.3f} %")
    if dv_limit_pct is not None:
        margin = dv_limit_pct - worst_dv
        ok = "OK" if margin >= 0 else "NG"
        a(f"    電圧変動上限 {dv_limit_pct:g} % に対し余裕 {margin:+.3f} % [{ok}]")
    a("=" * 70)
    return "\n".join(lines)
