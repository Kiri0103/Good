"""機器の自動配置（セットバック内グリッド配置）。

敷地境界からセットバック分だけ内側に縮めた「配置可能領域」に、機器を行優先
（左→右、下→上）で並べる。機器相互は min_clearance_m 以上の間隔を確保する。
座標系は原点が敷地左下、x=右・y=上のメートル系。

接続検討段階の概略配置を素早く得るためのシンプルなヒューリスティック。厳密な
最適化ではなく、与えられた寸法・台数が領域に収まるかの確認と叩き台の生成が目的。
"""
from __future__ import annotations

from dataclasses import dataclass

from renkei.models.project import Equipment, SiteLayout


@dataclass
class ArrangeResult:
    placed: list[Equipment]      # 座標が確定した機器（コピー）
    overflow: list[str]          # 領域に収まらなかった機器名


def arrange(layout: SiteLayout) -> ArrangeResult:
    """セットバック内に機器を行優先でグリッド配置する。

    元の SiteLayout は変更せず、座標を設定した Equipment のコピー列を返す。
    """
    sb = layout.setback_m
    clr = layout.min_clearance_m

    # 配置可能領域（セットバック内）
    x0, y0 = sb, sb
    avail_w = layout.site_width_m - 2 * sb
    avail_h = layout.site_depth_m - 2 * sb

    placed: list[Equipment] = []
    overflow: list[str] = []

    # 行優先で詰める。cursor は次に置く左下座標。
    cur_x = x0
    cur_y = y0
    row_max_depth = 0.0  # 現在行の最大奥行（次行の y 送り量）

    for eq in layout.equipment:
        # 領域に対して単体で大きすぎる場合は overflow
        if eq.width_m > avail_w + 1e-9 or eq.depth_m > avail_h + 1e-9:
            overflow.append(eq.name)
            continue

        # 現在行に収まらなければ改行
        if cur_x + eq.width_m > x0 + avail_w + 1e-9:
            cur_x = x0
            cur_y += row_max_depth + clr
            row_max_depth = 0.0

        # 縦方向にも収まらなければ overflow
        if cur_y + eq.depth_m > y0 + avail_h + 1e-9:
            overflow.append(eq.name)
            continue

        placed.append(
            eq.model_copy(update={"x_m": round(cur_x, 4), "y_m": round(cur_y, 4)})
        )
        cur_x += eq.width_m + clr
        row_max_depth = max(row_max_depth, eq.depth_m)

    return ArrangeResult(placed=placed, overflow=overflow)


def arranged_layout(layout: SiteLayout) -> SiteLayout:
    """auto_arrange が True なら自動配置済みの SiteLayout を返す。

    False の場合や配置不要な場合は元の layout をそのまま返す。
    """
    if not layout.auto_arrange:
        return layout
    result = arrange(layout)
    return layout.model_copy(update={"equipment": result.placed})
