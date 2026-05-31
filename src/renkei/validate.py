"""提出前チェックリストの自動検証。

案件情報（Project）に対し、様式間の整合・計算結果との突合・必須項目・物理的妥当性を
ルールで検査し、ミスを機械的に検出する。「確実で間違いのない提出物」を担保する要。

各ルールは Finding（重大度・対象・メッセージ）を返す。重大度:
  ERROR   : 提出前に必ず是正すべき不整合（数値の食い違い・必須欠落など）
  WARNING : 是正が望ましい、または要確認（前提値・空欄など）
  INFO    : 参考情報

許容誤差 `REL_TOL` は浮動小数の丸めや単位換算の差を吸収する相対許容（既定 1%）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from renkei.calc.impedance import build_impedance
from renkei.calc.shortcircuit import short_circuit
from renkei.models.project import Line, Project, Transformer

REL_TOL = 0.01


class Severity(IntEnum):
    INFO = 0
    WARNING = 1
    ERROR = 2

    @property
    def label(self) -> str:
        return {Severity.INFO: "INFO", Severity.WARNING: "WARN", Severity.ERROR: "ERROR"}[self]


@dataclass
class Finding:
    severity: Severity
    code: str          # ルール識別子（例: V-VOLT-POC）
    location: str      # 対象（様式名・項目）
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.label:5}] {self.code:14} {self.location}: {self.message}"


@dataclass
class ValidationReport:
    findings: list[Finding] = field(default_factory=list)

    def add(self, severity: Severity, code: str, location: str, message: str) -> None:
        self.findings.append(Finding(severity, code, location, message))

    def error(self, code: str, location: str, message: str) -> None:
        self.add(Severity.ERROR, code, location, message)

    def warn(self, code: str, location: str, message: str) -> None:
        self.add(Severity.WARNING, code, location, message)

    def info(self, code: str, location: str, message: str) -> None:
        self.add(Severity.INFO, code, location, message)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.WARNING]

    @property
    def ok(self) -> bool:
        """ERROR が 1 件も無ければ True。"""
        return len(self.errors) == 0

    def counts(self) -> dict[str, int]:
        return {
            "error": len(self.errors),
            "warning": len(self.warnings),
            "info": len([f for f in self.findings if f.severity == Severity.INFO]),
        }


def _close(a: float, b: float, rel_tol: float = REL_TOL) -> bool:
    if a == b:
        return True
    scale = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / scale <= rel_tol


# ---------------------------------------------------------------------------
# 個別ルール
# ---------------------------------------------------------------------------

def _check_voltages(p: Project, r: ValidationReport) -> None:
    """電圧の整合（連系点・希望受電電圧・遮断器・連系用変圧器2次）。"""
    poc = p.poc_kv

    if p.form2 and p.form2.desired_voltage_kv is not None:
        if not _close(p.form2.desired_voltage_kv, poc):
            r.error(
                "V-VOLT-POC", "様式2 希望受電電圧",
                f"希望受電電圧 {p.form2.desired_voltage_kv:g}kV が連系点電圧 {poc:g}kV と不一致",
            )

    if p.form4_2 and p.form4_2.breaker_voltage_kv is not None:
        # 連系用遮断器は連系点（受電点）に設置されるため、定格電圧は連系点電圧以上
        if p.form4_2.breaker_voltage_kv < poc - 1e-9:
            r.error(
                "V-VOLT-CB", "様式4の2 連系用遮断器",
                f"遮断器定格電圧 {p.form4_2.breaker_voltage_kv:g}kV < 連系点電圧 {poc:g}kV",
            )

    # 連系用変圧器の2次電圧は連系点電圧と一致すべき
    renkei_tr = [c for c in p.network if isinstance(c, Transformer) and c.role == "連系用"]
    for tr in renkei_tr:
        if not _close(tr.secondary_kv, poc):
            r.warn(
                "V-VOLT-TR2", f"様式4の1 {tr.name}",
                f"連系用変圧器2次電圧 {tr.secondary_kv:g}kV が連系点電圧 {poc:g}kV と不一致",
            )


def _check_pcs_transformer(p: Project, r: ValidationReport) -> None:
    """PCSと昇圧変圧器・台数の整合。"""
    if not p.pcs:
        return
    pcs = p.pcs[0]
    boost = [c for c in p.network if isinstance(c, Transformer) and c.role == "その他"]
    for tr in boost:
        # 昇圧変圧器の低圧側(2次)電圧 と PCS定格電圧 の整合
        if pcs.rated_voltage_kv is not None and not _close(tr.secondary_kv, pcs.rated_voltage_kv):
            r.warn(
                "V-PCS-TRKV", f"様式4の1 {tr.name}",
                f"昇圧変圧器2次電圧 {tr.secondary_kv:g}kV が PCS定格電圧 {pcs.rated_voltage_kv:g}kV と不一致",
            )


def _check_rated_output(p: Project, r: ValidationReport) -> None:
    """定格出力合計（様式2）と PCS 合計出力の整合。"""
    if not (p.form2 and p.form2.rated_total_kw is not None and p.pcs):
        return
    total_pcs = p.total_pcs_kw
    if not _close(p.form2.rated_total_kw, total_pcs, rel_tol=0.05):
        r.error(
            "V-OUT-TOTAL", "様式2 定格出力合計",
            f"定格出力合計 {p.form2.rated_total_kw:,.0f}kW が PCS合計出力 {total_pcs:,.0f}kW と不一致",
        )


def _check_received_power(p: Project, r: ValidationReport) -> None:
    """受電電力（様式2, 送電は負）と逆潮流 export_power_mw の整合。"""
    if not (p.form2 and p.form2.received_power_max_kw is not None):
        return
    export_kw = p.export_power_mw * 1000.0
    # 送電（逆潮流）は受電電力が負。最大送電 ≈ -export
    if export_kw > 0:
        expected = -export_kw
        if not _close(p.form2.received_power_max_kw, expected, rel_tol=0.05):
            r.warn(
                "V-RECV-EXPORT", "様式2 受電電力",
                f"受電電力(最大) {p.form2.received_power_max_kw:,.0f}kW が "
                f"逆潮流 {export_kw:,.0f}kW（送電は負）と不整合の可能性",
            )


def _check_source_type(p: Project, r: ValidationReport) -> None:
    """電源種別（様式2）と PCS 原動機（様式3の4）の整合。"""
    if not (p.form2 and p.form2.source_type and p.pcs):
        return
    pm = p.pcs[0].prime_mover or ""
    st = p.form2.source_type
    # 「太陽光」「蓄電池」などの語が相互に含まれるかで緩く判定
    if st not in pm and pm.replace("発電", "") not in st:
        r.warn(
            "V-SRC-TYPE", "様式2/様式3の4",
            f"電源種別「{st}」と PCS原動機「{pm}」が一致しない可能性",
        )


def _check_short_circuit(p: Project, r: ValidationReport) -> None:
    """遮断器定格遮断電流 ≥ 連系点短絡電流（計算値）。"""
    if not (p.form4_2 and p.form4_2.breaker_breaking_ka is not None):
        return
    try:
        imp = build_impedance(p)
        sc = short_circuit(p, imp)
    except Exception as e:  # 計算不能時はスキップ（別途データ検証で拾う）
        r.warn("V-SC-CALC", "短絡計算", f"短絡電流計算に失敗: {e}")
        return
    isc = sc.total_isc_ka
    if p.form4_2.breaker_breaking_ka < isc - 1e-9:
        r.error(
            "V-SC-CB", "様式4の2 定格遮断電流",
            f"遮断器定格遮断電流 {p.form4_2.breaker_breaking_ka:g}kA "
            f"< 連系点短絡電流 {isc:.2f}kA（PCS寄与含む）。遮断容量不足",
        )
    else:
        r.info(
            "V-SC-CB", "様式4の2 定格遮断電流",
            f"遮断器 {p.form4_2.breaker_breaking_ka:g}kA ≥ 短絡電流 {isc:.2f}kA（OK）",
        )


def _check_power_factor(p: Project, r: ValidationReport) -> None:
    """力率の物理的妥当性（0<pf≤1, 力率範囲の上下関係）。"""
    for i, pcs in enumerate(p.pcs):
        if pcs.pf_rated_pct is not None and not (0 < pcs.pf_rated_pct <= 100):
            r.error(
                "V-PF-RANGE", f"様式3の4 PCS[{i}] 力率(定格)",
                f"力率 {pcs.pf_rated_pct}% が 0〜100% の範囲外",
            )
    if not (0 < p.operating_power_factor <= 1):
        r.error("V-PF-OP", "運転力率", f"運転力率 {p.operating_power_factor} が (0,1] の範囲外")


def _check_demand_pattern(p: Project, r: ValidationReport) -> None:
    """需給パターン（様式5の5）の点数・発電上限の妥当性。"""
    for name, d in (("太陽光", p.demand_pv), ("蓄電池", p.demand_battery)):
        if d is None:
            continue
        for attr in ("active_a", "active_b", "idle_a", "idle_b"):
            vals = getattr(d, attr)
            if vals and len(vals) != 24:
                r.error(
                    "V-DEM-LEN", f"様式5の5 {name} {attr}",
                    f"24時間分必要だが {len(vals)} 点",
                )
    # 太陽光の発電ピークがPCS合計出力を超えていないか
    if p.demand_pv and p.demand_pv.active_a and p.pcs:
        peak = max(p.demand_pv.active_a)
        total = p.total_pcs_kw
        if peak > total * (1 + 0.05):
            r.warn(
                "V-DEM-PEAK", "様式5の5 太陽光",
                f"発電ピーク {peak:,.0f}kW が PCS合計 {total:,.0f}kW を超過",
            )


def _check_required(p: Project, r: ValidationReport) -> None:
    """提出に必要な主要項目の欠落チェック（WARNING）。"""
    if p.form1 is None:
        r.warn("R-FORM1", "様式1", "基本情報（form1）が未入力")
    else:
        for fld, label in [
            ("installer_name", "設置者名"),
            ("plant_name", "発電所名"),
            ("site_address", "設置場所住所"),
            ("connect_utility", "連系先"),
        ]:
            if not getattr(p.form1, fld):
                r.warn("R-FORM1", "様式1", f"{label}が未入力")
    if not p.pcs:
        r.warn("R-PCS", "様式3の4", "PCS（逆変換装置）が未登録")
    if not any(isinstance(c, Transformer) and c.role == "連系用" for c in p.network):
        r.warn("R-TR", "様式4の1", "連系用変圧器が未登録")


_RULES = [
    _check_voltages,
    _check_pcs_transformer,
    _check_rated_output,
    _check_received_power,
    _check_source_type,
    _check_short_circuit,
    _check_power_factor,
    _check_demand_pattern,
    _check_required,
]


def validate(project: Project) -> ValidationReport:
    """全ルールを実行し検証レポートを返す。"""
    report = ValidationReport()
    for rule in _RULES:
        rule(project, report)
    # 重大度の高い順・コード順に整列
    report.findings.sort(key=lambda f: (-int(f.severity), f.code))
    return report


def format_report(report: ValidationReport, project_name: str = "") -> str:
    """検証レポートを人が読めるテキストに整形。"""
    lines: list[str] = []
    a = lines.append
    a("=" * 64)
    a(f"提出前チェック : {project_name}" if project_name else "提出前チェック")
    a("=" * 64)
    if not report.findings:
        a("指摘なし。")
    for f in report.findings:
        a(str(f))
    c = report.counts()
    a("-" * 64)
    a(f"ERROR={c['error']}  WARNING={c['warning']}  INFO={c['info']}")
    a("判定: " + ("OK（ERROR なし）" if report.ok else "要是正（ERROR あり）"))
    a("=" * 64)
    return "\n".join(lines)
