"""計算結果のレポート生成（テキスト）。

接続検討申請書への転記前に、計算過程と数値を人がレビューできるようにする中間
成果物。様式への自動転記は別モジュールで行う（様式ファイル受領後に実装）。
"""
from __future__ import annotations

from renkei.calc import base
from renkei.calc.impedance import ImpedanceResult
from renkei.calc.shortcircuit import ShortCircuitResult
from renkei.calc.voltage import VoltageResult
from renkei.models.project import Project


def build_report(
    project: Project,
    impedance: ImpedanceResult,
    sc: ShortCircuitResult,
    vr: VoltageResult,
) -> str:
    lines: list[str] = []
    a = lines.append

    a("=" * 64)
    a(f"接続検討 設計計算レポート : {project.name}")
    if project.utility:
        a(f"提出先 : {project.utility}")
    a(f"基準容量 Sb = {project.base_mva:.3f} MVA / 連系点電圧 = {project.poc_kv:.3f} kV")
    a("=" * 64)

    a("")
    a("【1】インピーダンス（基準容量基準, 複素 %Z）")
    a(f"  {'構成要素':<16}{'R[%]':>10}{'X[%]':>10}{'|Z|[%]':>10}{'∠[deg]':>10}")
    for t in impedance.terms:
        a(
            f"  {t.name:<16}{t.r_pct:>10.4f}{t.x_pct:>10.4f}"
            f"{t.magnitude:>10.4f}{base.angle_deg(t.pct_z):>10.2f}"
        )
    a("  " + "-" * 56)
    a(
        f"  {'総合（連系点）':<16}{impedance.total_r_pct:>10.4f}"
        f"{impedance.total_x_pct:>10.4f}{impedance.total_magnitude:>10.4f}"
        f"{base.angle_deg(impedance.total):>10.2f}"
    )

    a("")
    a("【2】三相短絡（連系点）")
    a(f"  三相短絡容量 Psc = {sc.fault_mva:,.1f} MVA")
    a(f"  系統側短絡電流   = {sc.grid_isc_ka:,.3f} kA")
    a(f"  PCS 寄与電流     = {sc.pcs_isc_ka:,.3f} kA")
    a(f"  合計短絡電流 Isc = {sc.total_isc_ka:,.3f} kA")

    a("")
    a("【3】電圧変動（逆潮流時）")
    a(f"  逆潮流 P = {vr.p_mw:.3f} MW / 無効 Q = {vr.q_mvar:.3f} Mvar "
      f"(力率 {project.operating_power_factor:.3f} {project.power_factor_mode})")
    a(f"  ΔV ≈ {vr.delta_v_pct:+.3f} %")

    a("")
    a("【4】設備容量")
    a(f"  PCS 合計 = {project.total_pcs_kw:,.1f} kW / {project.total_pcs_kva:,.1f} kVA")
    if project.battery:
        e = sum(b.energy_kwh for b in project.battery)
        pw = sum(b.power_kw for b in project.battery)
        a(f"  蓄電池合計 = {e:,.1f} kWh / {pw:,.1f} kW")

    a("")
    a("※ 本レポートは標準的な %Z 法による計算過程の確認用です。")
    a("※ X/R 比・PCS 短絡寄与・無効電力符号などの前提は要確認です。")
    a("=" * 64)
    return "\n".join(lines)
