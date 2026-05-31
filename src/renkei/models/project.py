"""案件情報（接続検討に必要な入力データ）のスキーマ。

すべての物理量はフィールド名に単位を含める（mva, kv, km, ohm_per_km, pct, kw,
kva, mvar）。pydantic によるバリデーションで、提出前に「ありえない値」を機械的に
弾くことを目的とする。

注意（要確認）:
  本スキーマは「系統 → 線路/変圧器 …（直列）… → 連系点」という放射状（ラジアル）
  構成を前提とする。特別高圧の太陽光・蓄電池の多くはこの構成だが、ループ・複数受電
  などがある場合は別途モデル拡張が必要。
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Union

import yaml
from pydantic import BaseModel, Field, model_validator


class GridSource(BaseModel):
    """系統（電力会社側）の条件。接続検討の前提として電力会社から提示される。

    `short_circuit_capacity_mva`（三相短絡容量）または `pct_z`（基準容量における
    %インピーダンス）のいずれかを指定する。両方未指定はエラー。
    """

    name: str = "系統"
    voltage_kv: float = Field(gt=0, description="連系点（受電点）の公称電圧 [kV]")
    short_circuit_capacity_mva: float | None = Field(
        default=None, gt=0, description="系統の三相短絡容量 [MVA]"
    )
    pct_z: float | None = Field(
        default=None, gt=0, description="基準容量における系統%Z [%]"
    )
    xr_ratio: float = Field(
        default=10.0, gt=0, description="系統の X/R 比（要確認・電力会社提示値があれば優先）"
    )

    @model_validator(mode="after")
    def _check_source(self) -> "GridSource":
        if self.short_circuit_capacity_mva is None and self.pct_z is None:
            raise ValueError(
                "系統条件は short_circuit_capacity_mva か pct_z のいずれかが必要です"
            )
        return self


class Transformer(BaseModel):
    """変圧器（受電用・連系用）。"""

    kind: Literal["transformer"] = "transformer"
    name: str
    rated_mva: float = Field(gt=0, description="定格容量 [MVA]")
    pct_z: float = Field(gt=0, description="自己容量基準の%インピーダンス（％IZ）[%]")
    xr_ratio: float = Field(
        default=15.0, gt=0, description="X/R 比（または下記 r_pct から算出）"
    )
    primary_kv: float = Field(gt=0)
    secondary_kv: float = Field(gt=0)
    tertiary_kv: float | None = Field(default=None, gt=0, description="3次電圧 [kV]")

    # --- 様式記入用（AK1T 様式４の１）。未指定ならインピーダンス計算には不要 ---
    role: Literal["連系用", "その他"] = Field(
        default="連系用", description="連系用変圧器か、その他（昇圧用等）変圧器か"
    )
    in_series: bool = Field(
        default=True,
        description="系統〜連系点の直列経路に含めるか（下流の昇圧変圧器は False）",
    )
    maker: str | None = Field(default=None, description="メーカ")
    model_name: str | None = Field(default=None, description="型式")
    connection_method: str | None = Field(
        default=None, description="結線方法（例: 高圧側 デルタ/低圧側 スター）"
    )
    neutral_grounding: str | None = Field(
        default=None, description="中性点接地方式（例: 非接地, 直接接地）"
    )
    count: int = Field(default=1, ge=1, description="台数")
    boost_target: str | None = Field(default=None, description="昇圧対象発電設備")
    xps_pct: float | None = Field(
        default=None,
        gt=0,
        description="様式記入用 Xps[%]（銘板リアクタンス）。未指定なら pct_z を用いる",
    )
    rated_kva_label: str | None = Field(
        default=None,
        description="定格容量の表記（例: '10,000／10,000'）。未指定なら rated_mva から生成",
    )
    base_kva: float | None = Field(
        default=None, gt=0, description="%Z の基準容量 [kVA]。未指定なら定格容量"
    )


class Line(BaseModel):
    """線路・ケーブル区間。"""

    kind: Literal["line"] = "line"
    name: str
    voltage_kv: float = Field(gt=0, description="区間の公称電圧 [kV]")
    length_km: float = Field(gt=0)
    r_ohm_per_km: float = Field(ge=0, description="正相抵抗 [Ω/km]")
    x_ohm_per_km: float = Field(ge=0, description="正相リアクタンス [Ω/km]")
    n_parallel: int = Field(default=1, ge=1, description="並列回線数")


NetworkComponent = Annotated[
    Union[Transformer, Line], Field(discriminator="kind")
]


class Pcs(BaseModel):
    """パワーコンディショナ（PCS）。"""

    model: str = "PCS"
    rated_kw: float = Field(gt=0, description="1台あたり定格有効電力 [kW]")
    rated_kva: float | None = Field(
        default=None, gt=0, description="1台あたり定格容量 [kVA]（未指定なら kW/力率）"
    )
    count: int = Field(ge=1, description="台数")
    power_factor: float = Field(
        default=1.0, gt=0, le=1, description="運転力率（絶対値）"
    )
    fault_current_pu: float = Field(
        default=1.1,
        ge=0,
        description="短絡時の出力電流（定格電流に対する倍率, pu）。要確認・メーカ仕様優先",
    )


class Battery(BaseModel):
    """蓄電池設備（容量等の記録用。インピーダンス計算には PCS を用いる）。"""

    model: str = "蓄電池"
    energy_kwh: float = Field(gt=0)
    power_kw: float = Field(gt=0)


class Project(BaseModel):
    """1 案件の全情報。"""

    name: str = Field(description="案件名")
    utility: str = Field(default="", description="提出先電力会社")
    base_mva: float = Field(default=10.0, gt=0, description="計算基準容量 [MVA]")

    point_of_connection_kv: float | None = Field(
        default=None,
        gt=0,
        description="連系点（受電点）の公称電圧 [kV]。未指定なら系統電圧を用いる",
    )

    grid: GridSource
    network: list[NetworkComponent] = Field(
        default_factory=list,
        description="系統側から連系点へ向かう順に並べた直列構成要素",
    )
    pcs: list[Pcs] = Field(default_factory=list)
    battery: list[Battery] = Field(default_factory=list)

    export_power_mw: float = Field(
        default=0.0, ge=0, description="逆潮流（送電）有効電力 [MW]"
    )
    operating_power_factor: float = Field(
        default=1.0, gt=0, le=1, description="連系点での運転力率（絶対値）"
    )
    power_factor_mode: Literal["進み", "遅れ"] = Field(
        default="進み",
        description="力率の進み/遅れ。電圧変動の無効電力符号に影響（要確認）",
    )

    @property
    def poc_kv(self) -> float:
        """連系点電圧 [kV]（未指定なら系統電圧）。"""
        return self.point_of_connection_kv or self.grid.voltage_kv

    @property
    def total_pcs_kw(self) -> float:
        return sum(p.rated_kw * p.count for p in self.pcs)

    @property
    def total_pcs_kva(self) -> float:
        total = 0.0
        for p in self.pcs:
            kva = p.rated_kva if p.rated_kva is not None else p.rated_kw / p.power_factor
            total += kva * p.count
        return total


def load_project(path: str | Path) -> Project:
    """YAML/JSON ファイルから案件情報を読み込み、バリデーションする。"""
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return Project.model_validate(data)
