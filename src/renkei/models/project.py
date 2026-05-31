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

    # --- 様式記入用（AK1T 様式３の４ 逆変換装置）。未指定の欄は空欄のまま ---
    maker: str | None = Field(default=None, description="メーカ")
    generator_no: str = Field(default="1", description="号発電機（例: 1, 1～10）")
    install_type: Literal["新設", "増設", "既設"] = Field(default="新設")
    prime_mover: str = Field(default="太陽光発電", description="原動機の種類")
    electric_system: str | None = Field(
        default=None, description="電気方式（例: 三相３線式）"
    )
    rated_voltage_kv: float | None = Field(
        default=None, gt=0, description="定格電圧 [kV]"
    )
    output_min_kw: float | None = Field(default=None, description="出力変化範囲 下限 [kW]")
    output_max_kw: float | None = Field(default=None, description="出力変化範囲 上限 [kW]")
    voltage_range_min_pu: float | None = Field(default=None, description="運転可能電圧範囲 下限 [pu]")
    voltage_range_max_pu: float | None = Field(default=None, description="運転可能電圧範囲 上限 [pu]")
    pf_rated_pct: float | None = Field(
        default=None, description="力率（定格）[%]。未指定なら power_factor×100"
    )
    pf_range_lag_pct: float | None = Field(default=None, description="力率運転可能範囲 遅れ [%]")
    pf_range_lead_pct: float | None = Field(default=None, description="力率運転可能範囲 進み [%]")
    voltage_reactive_control: str | None = Field(
        default=None, description="電圧・無効電力制御（例: 電圧一定制御、力率一定制御）"
    )
    rated_frequency_hz: float | None = Field(default=None, description="定格周波数 [Hz]")
    cont_freq_min_hz: float | None = Field(default=None, description="連続運転可能周波数 下限 [Hz]")
    cont_freq_max_hz: float | None = Field(default=None, description="連続運転可能周波数 上限 [Hz]")
    auto_sync_check: str | None = Field(
        default=None, description="自動同期検定機能（有/無, 自励式の場合）"
    )
    current_limit_pct: float | None = Field(default=None, description="通電電流制限値 [%]")
    pf_control_time_ms: float | None = Field(default=None, description="系統事故時の力率制御時間 [ms]")
    main_circuit: str | None = Field(default=None, description="主回路方式")
    output_control: str | None = Field(default=None, description="出力制御方式")
    frt_applied: str | None = Field(default=None, description="FRT要件適用の有無（有/無）")
    harmonic_total_pct: float | None = Field(default=None, description="高調波電流歪率 総合 [%]")

    @property
    def pf_rated_pct_value(self) -> float:
        return self.pf_rated_pct if self.pf_rated_pct is not None else self.power_factor * 100.0


class Battery(BaseModel):
    """蓄電池設備（容量等の記録用。インピーダンス計算には PCS を用いる）。"""

    model: str = "蓄電池"
    energy_kwh: float = Field(gt=0)
    power_kw: float = Field(gt=0)


class Contact(BaseModel):
    """連絡先窓口（様式１(8)）。"""

    address: str | None = Field(default=None, description="住所（〒含む）")
    company: str | None = Field(default=None, description="事業者名")
    department: str | None = Field(default=None, description="所属")
    person: str | None = Field(default=None, description="担当者名")
    phone: str | None = Field(default=None, description="電話")
    email: str | None = Field(default=None, description="e-mail")


class JpDate(BaseModel):
    """和暦・西暦を問わない年月日（様式の年/月/日セル用）。"""

    year: int | None = None
    month: int | None = None
    day: int | None = None


class Form1(BaseModel):
    """様式１ 基本情報。"""

    installer_name: str | None = Field(default=None, description="(1)発電設備等設置者名")
    installer_kana: str | None = Field(default=None, description="(1)フリガナ")
    same_corporation: str | None = Field(
        default=None, description="一般送配電事業者と同一法人等の該当有無（有/無）"
    )
    plant_name: str | None = Field(default=None, description="(2)発電所名")
    plant_name_kana: str | None = Field(default=None, description="(2)フリガナ")
    site_address: str | None = Field(default=None, description="(3)設置場所の住所")
    connect_utility: str | None = Field(default=None, description="(4)連系先")
    existing_access: str | None = Field(default=None, description="(5)既設アクセス設備の有無")
    change_type: str | None = Field(default=None, description="(6)発電設備等変更の有無")
    contract_type: str | None = Field(default=None, description="(7)契約種別")
    representative: str | None = Field(default=None, description="申込者 代表者氏名")
    applicant_company: str | None = Field(default=None, description="申込者 事業者名")
    applicant_address: str | None = Field(default=None, description="申込者 住所")
    contact: Contact | None = Field(default=None, description="(8)連絡先窓口")


class Form2(BaseModel):
    """様式２ 発電設備等の概要。"""

    access_start: JpDate | None = Field(default=None, description="(1)アクセス設備運用開始希望日")
    trial_start: JpDate | None = Field(default=None, description="(2)連系開始希望日（試運転）")
    commercial_start: JpDate | None = Field(default=None, description="(3)連系開始希望日（営業運転）")
    desired_voltage_kv: float | None = Field(default=None, description="希望受電電圧 [kV]")
    reserve_line: str | None = Field(default=None, description="予備電線路希望の有無（有/無）")
    reserve_service: str | None = Field(default=None, description="希望する予備送電サービス")
    reserve_contract_kw: float | None = Field(default=None, description="予備送電サービス契約電力 [kW]")
    source_type: str | None = Field(default=None, description="新設・増設の電源種別（例: 太陽光）")
    # ４．発電設備等の定格出力合計（変更後）
    rated_total_type: str | None = Field(default=None, description="定格出力合計 電源種別")
    rated_total_count: int | None = Field(default=None, description="定格出力合計 台数 [台]")
    rated_total_kw: float | None = Field(default=None, description="定格出力合計 [kW]")
    # ５．受電地点における受電電力（変更後・送電を正、受電を負）
    received_power_max_kw: float | None = Field(default=None, description="受電電力 最大 [kW]（送電は負）")
    received_power_min_kw: float | None = Field(default=None, description="受電電力 最小 [kW]")
    # ６．自家消費電力
    house_load_max_kw: float | None = Field(default=None, description="自家消費電力 最大 [kW]")
    house_load_max_pf: float | None = Field(default=None, description="自家消費電力 最大 力率 [%]")
    house_load_min_kw: float | None = Field(default=None, description="自家消費電力 最小 [kW]")
    house_load_min_pf: float | None = Field(default=None, description="自家消費電力 最小 力率 [%]")


class Form4_2(BaseModel):
    """様式４の２ 受電設備および負荷設備。"""

    insulation_method: str | None = Field(default=None, description="(1)絶縁方式（例: ガス絶縁）")
    breaker_maker: str | None = Field(default=None, description="連系用遮断器 メーカ")
    breaker_model: str | None = Field(default=None, description="連系用遮断器 型式")
    breaker_voltage_kv: float | None = Field(default=None, description="定格電圧 [kV]")
    breaker_current_a: float | None = Field(default=None, description="定格電流 [A]")
    breaker_breaking_ka: float | None = Field(default=None, description="定格遮断電流 [kA]")
    breaker_breaking_time: str | None = Field(default=None, description="定格遮断時間（例: 5）")
    pfc_type: str | None = Field(default=None, description="調相設備 種類")
    pfc_capacity_ehv: str | None = Field(default=None, description="調相設備 電圧別容量 特別高圧")
    pfc_capacity_hv: str | None = Field(default=None, description="調相設備 電圧別容量 高圧")
    pfc_capacity_lv: str | None = Field(default=None, description="調相設備 電圧別容量 低圧")
    pfc_capacity_total: str | None = Field(default=None, description="調相設備 合計容量")
    pfc_auto_control: str | None = Field(default=None, description="自動力率制御装置の有無（有/無）")


class Form4_3(BaseModel):
    """様式４の３ 監視制御（給電情報）。"""

    phone_line_form: str | None = Field(default=None, description="保安通信用電話 通信回線形態")
    phone_location: str | None = Field(default=None, description="保安通信用電話 設置場所")
    info_line_form: str | None = Field(default=None, description="情報伝送装置 通信回線形態")
    info_device_type: str | None = Field(default=None, description="情報伝送装置 装置の種類")
    info_location: str | None = Field(default=None, description="情報伝送装置 設置場所")
    monitoring_control: str | None = Field(default=None, description="監視制御方式")


class DemandPattern(BaseModel):
    """様式５の５ 24時間運用パターン（1時間刻み・00:00〜23:00）。

    太陽光版: active=発電[kW], buy=買電[kW]（停止時は idle_* を使用）
    蓄電池版: active=放電[kW], buy=充電[kW]
    各リストは 24 要素（00時〜23時）。未指定の時間帯は 0 とみなす。
    """

    season: str = Field(default="通　年", description="時季（通年/春季/夏季/秋季/冬季）")
    active_a: list[float] = Field(default_factory=list, description="稼働時の発電/放電 [kW]")
    active_b: list[float] = Field(default_factory=list, description="稼働時の買電/充電 [kW]")
    idle_a: list[float] = Field(default_factory=list, description="停止時の発電/放電 [kW]")
    idle_b: list[float] = Field(default_factory=list, description="停止時の買電/充電 [kW]")

    def _at(self, lst: list[float], hour: int) -> float | None:
        return lst[hour] if hour < len(lst) else None


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

    form1: Form1 | None = Field(default=None, description="様式１ 基本情報")
    form2: Form2 | None = Field(default=None, description="様式２ 発電設備等の概要")
    form4_2: Form4_2 | None = Field(default=None, description="様式４の２ 受電設備")
    form4_3: Form4_3 | None = Field(default=None, description="様式４の３ 監視制御")
    demand_pv: DemandPattern | None = Field(
        default=None, description="様式５の５（太陽光）24時間運用パターン"
    )
    demand_battery: DemandPattern | None = Field(
        default=None, description="様式５の５（蓄電池）24時間運用パターン"
    )

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
