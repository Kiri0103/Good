"""配置図（機器レイアウト図）の SVG 自動生成。

敷地（SiteLayout）と機器（Equipment）の平面配置を、縮尺・寸法線・方位（N）付きの
SVG で描く。座標系は原点が敷地左下、x=右・y=上のメートル系。SVG は y が下向きの
ため描画時に上下反転する。

種別（category）で色分けし、機器名と寸法ラベルを付す。接続検討の配置確認・添付用。
"""
from __future__ import annotations

from pathlib import Path

from renkei.forms._svg import esc as _esc
from renkei.forms._svg import font_stack
from renkei.models.project import Equipment, Project, SiteLayout

# 描画パラメータ
_MARGIN = 70          # 図郭外の余白 [px]
_TARGET_W = 700       # 敷地描画幅の目安 [px]（ここからスケール px/m を決める）

# 種別 → 塗り色
_COLORS = {
    "PCS": "#cfe8ff",
    "蓄電池": "#d6f5d6",
    "受変電": "#ffe6cc",
    "その他": "#eeeeee",
    "設備": "#eeeeee",
}


def _color(cat: str) -> str:
    return _COLORS.get(cat, _COLORS["設備"])


def _mm(meters: float) -> str:
    """メートル値を図面用の mm 表記文字列に整形（桁区切り付き, 例: 60000）。"""
    return f"{round(meters * 1000):,}"


def _text(x: float, y: float, s: str, anchor: str = "start", size: int = 12,
          color: str = "black") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-size="{size}" font-family="{font_stack()}" fill="{color}">{_esc(s)}</text>'
    )


def build_layout_svg(layout: SiteLayout, title: str = "") -> str:
    """敷地・機器配置から配置図 SVG を生成する。"""
    scale = _TARGET_W / layout.site_width_m  # px per m
    site_w_px = layout.site_width_m * scale
    site_h_px = layout.site_depth_m * scale
    W = site_w_px + 2 * _MARGIN
    H = site_h_px + 2 * _MARGIN

    def px(x_m: float, y_m: float) -> tuple[float, float]:
        """メートル座標 → SVG ピクセル座標（y 反転）。"""
        return (_MARGIN + x_m * scale, _MARGIN + (layout.site_depth_m - y_m) * scale)

    parts: list[str] = []

    # タイトル
    if title:
        parts.append(_text(_MARGIN, 30, title, size=16))

    # 方位（N 矢印, 右上）
    nx = W - 40
    parts.append(
        f'<line x1="{nx}" y1="55" x2="{nx}" y2="25" stroke="black" stroke-width="2"/>'
        f'<path d="M {nx-5} 32 L {nx} 22 L {nx+5} 32 Z" fill="black"/>'
        + _text(nx, 70, "N", anchor="middle", size=13)
    )

    # 敷地境界
    parts.append(
        f'<rect x="{_MARGIN:.1f}" y="{_MARGIN:.1f}" width="{site_w_px:.1f}" '
        f'height="{site_h_px:.1f}" fill="#fafafa" stroke="black" stroke-width="2"/>'
    )

    # セットバック線（破線）
    if layout.setback_m > 0:
        s = layout.setback_m * scale
        parts.append(
            f'<rect x="{_MARGIN + s:.1f}" y="{_MARGIN + s:.1f}" '
            f'width="{site_w_px - 2*s:.1f}" height="{site_h_px - 2*s:.1f}" '
            f'fill="none" stroke="#cc4444" stroke-width="1" stroke-dasharray="6 4"/>'
        )

    # 機器
    for eq in layout.equipment:
        x_px, y_top_px = px(eq.x_m, eq.y_m + eq.depth_m)  # 左上
        w_px = eq.width_m * scale
        h_px = eq.depth_m * scale
        parts.append(
            f'<rect x="{x_px:.1f}" y="{y_top_px:.1f}" width="{w_px:.1f}" '
            f'height="{h_px:.1f}" fill="{_color(eq.category)}" stroke="black" stroke-width="1.5"/>'
        )
        cx = x_px + w_px / 2
        cy = y_top_px + h_px / 2
        # 機器名: 矩形幅に収まるようフォントを縮める（最小7px）
        name_size = max(7, min(12, int(w_px / max(len(eq.name), 1) * 1.6)))
        parts.append(_text(cx, cy, eq.name, anchor="middle", size=name_size))
        # 寸法ラベルは矩形が十分広い場合のみ（密集時の重なりを回避）
        dim_label = f"{_mm(eq.width_m)}×{_mm(eq.depth_m)}mm"
        if w_px >= 7 * len(dim_label) and h_px >= 24:
            parts.append(
                _text(cx, cy + 14, dim_label, anchor="middle", size=9, color="#555")
            )

    # 寸法線（敷地 幅・奥行）
    # 幅（下辺の下）
    y_dim = _MARGIN + site_h_px + 26
    parts.append(
        f'<line x1="{_MARGIN:.1f}" y1="{y_dim:.1f}" x2="{_MARGIN + site_w_px:.1f}" '
        f'y2="{y_dim:.1f}" stroke="#333" stroke-width="1" '
        f'marker-start="url(#arr)" marker-end="url(#arr)"/>'
    )
    parts.append(_text(_MARGIN + site_w_px / 2, y_dim - 5,
                       f"幅 {_mm(layout.site_width_m)} mm", anchor="middle", size=12, color="#333"))
    # 奥行（左辺の左）
    x_dim = _MARGIN - 26
    parts.append(
        f'<line x1="{x_dim:.1f}" y1="{_MARGIN:.1f}" x2="{x_dim:.1f}" '
        f'y2="{_MARGIN + site_h_px:.1f}" stroke="#333" stroke-width="1" '
        f'marker-start="url(#arr)" marker-end="url(#arr)"/>'
    )
    parts.append(
        f'<text x="{x_dim - 6:.1f}" y="{_MARGIN + site_h_px / 2:.1f}" '
        f'text-anchor="middle" font-size="12" fill="#333" font-family="{font_stack()}" '
        f'transform="rotate(-90 {x_dim - 6:.1f} {_MARGIN + site_h_px / 2:.1f})">'
        f'奥行 {_mm(layout.site_depth_m)} mm</text>'
    )

    # スケールバー（10m 相当, 左下）
    bar_m = _nice_bar_length(layout.site_width_m)
    bar_px = bar_m * scale
    by = H - 24
    parts.append(
        f'<line x1="{_MARGIN:.1f}" y1="{by:.1f}" x2="{_MARGIN + bar_px:.1f}" '
        f'y2="{by:.1f}" stroke="black" stroke-width="3"/>'
        + _text(_MARGIN, by - 6, f"{_mm(bar_m)} mm", size=11)
    )

    defs = (
        '<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="4" refY="4" '
        'orient="auto"><path d="M0 4 L8 1 L8 7 Z" fill="#333"/></marker></defs>'
    )
    body = "\n  ".join(parts)
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" '
        f'viewBox="0 0 {W:.0f} {H:.0f}">\n'
        f'  {defs}\n'
        f'  <rect width="{W:.0f}" height="{H:.0f}" fill="white"/>\n'
        f'  {body}\n'
        f'</svg>\n'
    )


def _nice_bar_length(site_w_m: float) -> float:
    """スケールバーの見やすい長さ（敷地幅の 1/10 程度を 1/2/5/10… に丸める）。"""
    target = site_w_m / 10.0
    for base in (1, 2, 5, 10, 20, 50, 100, 200, 500):
        if base >= target:
            return float(base)
    return 1000.0


def write_layout_svg(project: Project, output_path: str | Path) -> Path:
    """配置図 SVG をファイルに書き出す。layout 未設定なら ValueError。

    layout.auto_arrange が True の場合は、セットバック内へ自動配置してから描画する。
    """
    from renkei.forms.arrange import arranged_layout

    if project.layout is None:
        raise ValueError("配置情報（layout）が未設定です")
    layout = arranged_layout(project.layout)
    svg = build_layout_svg(layout, title=f"配置図 — {project.name}")
    p = Path(output_path)
    p.write_text(svg, encoding="utf-8")
    return p
