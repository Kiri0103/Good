"""機器自動配置（セットバック内グリッド配置）と mm 表記のテスト。"""
import pytest

from renkei.forms.arrange import arrange, arranged_layout
from renkei.models.project import Equipment, GridSource, Project, SiteLayout


def _layout(**kw):
    base = dict(
        site_width_m=60, site_depth_m=40, setback_m=2.0,
        min_clearance_m=1.0, auto_arrange=True,
        equipment=[
            Equipment(name="A", width_m=12, depth_m=6, category="受変電"),
            Equipment(name="B", width_m=8, depth_m=4, category="PCS"),
        ],
    )
    base.update(kw)
    return SiteLayout(**base)


def test_arrange_within_setback():
    """配置された全機器がセットバック内に収まる。"""
    lay = _layout()
    res = arrange(lay)
    assert not res.overflow
    sb = lay.setback_m
    for e in res.placed:
        assert e.x_m >= sb - 1e-9
        assert e.y_m >= sb - 1e-9
        assert e.x_m + e.width_m <= lay.site_width_m - sb + 1e-9
        assert e.y_m + e.depth_m <= lay.site_depth_m - sb + 1e-9


def test_arrange_respects_clearance():
    """同一行で隣接する機器が min_clearance 以上離れる。"""
    lay = _layout()
    res = arrange(lay)
    a, b = res.placed[0], res.placed[1]
    # 同じ行（y 同じ）に並ぶ想定
    gap = b.x_m - (a.x_m + a.width_m)
    assert gap >= lay.min_clearance_m - 1e-9


def test_arrange_wraps_to_new_row():
    """幅を超える機器数は次の行へ折り返す。"""
    eqs = [Equipment(name=f"E{i}", width_m=20, depth_m=5) for i in range(4)]
    lay = SiteLayout(site_width_m=50, site_depth_m=40, setback_m=2.0,
                     min_clearance_m=1.0, auto_arrange=True, equipment=eqs)
    res = arrange(lay)
    ys = {round(e.y_m, 3) for e in res.placed}
    assert len(ys) >= 2  # 複数行に分かれる


def test_arrange_overflow_detected():
    """配置可能領域より大きい機器は overflow。"""
    eqs = [Equipment(name="巨大", width_m=100, depth_m=100)]
    lay = SiteLayout(site_width_m=60, site_depth_m=40, setback_m=2.0,
                     auto_arrange=True, equipment=eqs)
    res = arrange(lay)
    assert "巨大" in res.overflow


def test_arranged_layout_noop_when_disabled():
    """auto_arrange=False なら元の layout をそのまま返す。"""
    lay = _layout(auto_arrange=False)
    assert arranged_layout(lay) is lay


def test_overflow_reported_as_error():
    """overflow は check で L-OVERFLOW ERROR。"""
    from renkei.validate import validate

    eqs = [Equipment(name="巨大", width_m=100, depth_m=100)]
    lay = SiteLayout(site_width_m=60, site_depth_m=40, setback_m=2.0,
                     auto_arrange=True, equipment=eqs)
    p = Project(name="t", grid=GridSource(voltage_kv=22, short_circuit_capacity_mva=1000),
                layout=lay)
    report = validate(p)
    assert "L-OVERFLOW" in {f.code for f in report.errors}


def test_layout_svg_uses_mm():
    """配置図 SVG が mm 表記を含む。"""
    from renkei.forms.layout import build_layout_svg

    svg = build_layout_svg(_layout())
    assert "mm" in svg
    assert "60,000 mm" in svg  # 敷地幅 60m → 60,000mm
