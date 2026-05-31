"""単線結線図（Single-Line Diagram）の SVG 自動生成。

案件情報（Project）の系統構成から、系統電源 → 線路 → 変圧器 → … → 連系点 →
PCS（＋蓄電池）という縦並びの単線結線図を SVG で描く。様式５の４（単線結線図）は
空の作図キャンバスのため、生成した SVG を印刷・添付する運用を想定する。

JIS C 0617 等の厳密なシンボルではなく、接続検討時のレビューに足る簡略記号を用いる。
"""
from __future__ import annotations

from pathlib import Path

from renkei.forms._svg import esc as _esc
from renkei.forms._svg import font_stack
from renkei.models.project import Line, Project, Transformer

# レイアウト定数 [px]
_W = 520
_BUS_X = 260           # 主母線（縦線）の X
_TOP = 60              # 最上部 Y
_STEP = 110            # 機器間の縦ピッチ
_LABEL_X = _BUS_X + 70  # 右側ラベル


def _grid_symbol(cx: float, cy: float) -> str:
    """系統電源（円の中に〜）。"""
    return (
        f'<circle cx="{cx}" cy="{cy}" r="22" fill="white" stroke="black" stroke-width="2"/>'
        f'<path d="M {cx-12} {cy} q 6 -10 12 0 q 6 10 12 0" '
        f'fill="none" stroke="black" stroke-width="2"/>'
    )


def _transformer_symbol(cx: float, cy: float) -> str:
    """変圧器（二重円）。"""
    return (
        f'<circle cx="{cx}" cy="{cy-12}" r="16" fill="none" stroke="black" stroke-width="2"/>'
        f'<circle cx="{cx}" cy="{cy+12}" r="16" fill="none" stroke="black" stroke-width="2"/>'
    )


def _line_symbol(cx: float, cy: float) -> str:
    """線路区間（縦線上の小さなジグザグ＝こう長を示す）。"""
    return (
        f'<path d="M {cx} {cy-22} l 8 8 l -16 8 l 16 8 l -8 8" '
        f'fill="none" stroke="black" stroke-width="2"/>'
    )


def _breaker_symbol(cx: float, cy: float) -> str:
    """遮断器（四角）。"""
    return (
        f'<rect x="{cx-10}" y="{cy-10}" width="20" height="20" '
        f'fill="white" stroke="black" stroke-width="2"/>'
    )


def _pcs_symbol(cx: float, cy: float, label: str) -> str:
    """PCS（逆変換装置, 四角に = と 〜）。"""
    return (
        f'<rect x="{cx-26}" y="{cy-20}" width="52" height="40" '
        f'fill="white" stroke="black" stroke-width="2"/>'
        f'<line x1="{cx}" y1="{cy-20}" x2="{cx}" y2="{cy+20}" stroke="black" stroke-width="1.5"/>'
        f'<text x="{cx-13}" y="{cy+5}" text-anchor="middle" font-size="14">=</text>'
        f'<text x="{cx+13}" y="{cy+5}" text-anchor="middle" font-size="14">~</text>'
    )


def _battery_symbol(cx: float, cy: float) -> str:
    """蓄電池（電池記号）。"""
    return (
        f'<line x1="{cx-14}" y1="{cy-10}" x2="{cx-14}" y2="{cy+10}" stroke="black" stroke-width="3"/>'
        f'<line x1="{cx-2}" y1="{cy-5}" x2="{cx-2}" y2="{cy+5}" stroke="black" stroke-width="2"/>'
        f'<line x1="{cx+8}" y1="{cy-10}" x2="{cx+8}" y2="{cy+10}" stroke="black" stroke-width="3"/>'
        f'<line x1="{cx+18}" y1="{cy-5}" x2="{cx+18}" y2="{cy+5}" stroke="black" stroke-width="2"/>'
    )


def _text(x: float, y: float, s: str, anchor: str = "start", size: int = 13) -> str:
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
        f'font-size="{size}" font-family="{font_stack()}">{_esc(s)}</text>'
    )


def build_sld_svg(project: Project) -> str:
    """案件情報から単線結線図 SVG 文字列を生成する。"""
    parts: list[str] = []
    y = _TOP

    # 系統電源
    parts.append(_grid_symbol(_BUS_X, y))
    parts.append(_text(_LABEL_X, y + 5, project.grid.name))
    parts.append(_text(_LABEL_X, y + 22, f"{project.grid.voltage_kv:g} kV", size=11))
    prev_y = y

    # 直列構成（系統→連系点）
    for comp in project.network:
        y += _STEP
        parts.append(
            f'<line x1="{_BUS_X}" y1="{prev_y}" x2="{_BUS_X}" y2="{y}" '
            f'stroke="black" stroke-width="2"/>'
        )
        if isinstance(comp, Transformer):
            parts.append(_transformer_symbol(_BUS_X, y))
            parts.append(_text(_LABEL_X, y - 4, comp.name))
            parts.append(
                _text(_LABEL_X, y + 13, f"{comp.rated_mva:g}MVA {comp.primary_kv:g}/{comp.secondary_kv:g}kV", size=11)
            )
        elif isinstance(comp, Line):
            parts.append(_line_symbol(_BUS_X, y))
            parts.append(_text(_LABEL_X, y - 4, comp.name))
            parts.append(
                _text(_LABEL_X, y + 13, f"{comp.length_km:g}km × {comp.n_parallel}回線", size=11)
            )
        prev_y = y

    # 連系点（受電点）
    y += _STEP
    parts.append(
        f'<line x1="{_BUS_X}" y1="{prev_y}" x2="{_BUS_X}" y2="{y}" '
        f'stroke="black" stroke-width="2"/>'
    )
    parts.append(_breaker_symbol(_BUS_X, y))
    parts.append(_text(_LABEL_X, y + 5, f"連系点 (受電点) {project.poc_kv:g}kV"))
    prev_y = y

    # PCS（＋蓄電池）
    if project.pcs:
        y += _STEP
        parts.append(
            f'<line x1="{_BUS_X}" y1="{prev_y}" x2="{_BUS_X}" y2="{y}" '
            f'stroke="black" stroke-width="2"/>'
        )
        pcs = project.pcs[0]
        parts.append(_pcs_symbol(_BUS_X, y, pcs.model))
        total_kw = project.total_pcs_kw
        parts.append(_text(_LABEL_X, y - 4, f"PCS {pcs.model} ×{pcs.count}"))
        parts.append(_text(_LABEL_X, y + 13, f"合計 {total_kw:,.0f} kW", size=11))
        prev_y = y

        if project.battery:
            y += _STEP
            parts.append(
                f'<line x1="{_BUS_X}" y1="{prev_y}" x2="{_BUS_X}" y2="{y}" '
                f'stroke="black" stroke-width="2"/>'
            )
            parts.append(_battery_symbol(_BUS_X, y))
            e = sum(b.energy_kwh for b in project.battery)
            pw = sum(b.power_kw for b in project.battery)
            parts.append(_text(_LABEL_X, y - 4, "蓄電池"))
            parts.append(_text(_LABEL_X, y + 13, f"{e:,.0f}kWh / {pw:,.0f}kW", size=11))

    height = y + _TOP
    title = f"単線結線図 — {project.name}"
    body = "\n  ".join(parts)
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_W}" height="{height}" '
        f'viewBox="0 0 {_W} {height}">\n'
        f'  <rect width="{_W}" height="{height}" fill="white"/>\n'
        f'  {_text(20, 28, title, size=16)}\n'
        f'  {body}\n'
        f'</svg>\n'
    )


def write_sld_svg(project: Project, output_path: str | Path) -> Path:
    """単線結線図 SVG をファイルに書き出す。"""
    p = Path(output_path)
    p.write_text(build_sld_svg(project), encoding="utf-8")
    return p
