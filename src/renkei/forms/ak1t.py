"""OCCTO 接続検討申込書（特別高圧 様式 AK1T）への自動転記。

案件情報（Project）を、AK1T の Excel テンプレートの該当セルへ書き込み、記入済み
ブックを出力する。手作業による転記ミスを排除することが目的。

セル番地は `reference/AK1T_202512r.xlsx` の様式を `tools/dump_form.py` で解析して
確定したもの。結合セルへは左上セルに書き込む（openpyxl の仕様）。

実装済みシート（データ転記）:
  - 様式1（基本情報）
  - 様式2（発電設備等の概要：希望時期・希望受電電圧・予備電線路・電源種別・
           定格出力合計・受電電力・自家消費電力）
  - 様式３の４(逆変換装置＝PCS)
  - 様式４の１(変圧器・線路) : 連系用変圧器 / その他の変圧器
  - 様式４の２(受電設備) : 絶縁方式・連系用遮断器・調相設備
  - 様式４の３(給電情報) : 通信形態・監視制御方式

対象外: 様式３の１〜３/５（他電源種別用）、様式５系・様式６（作図/別紙シート）。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import openpyxl

from renkei.models.project import Pcs, Project, Transformer

SHEET_TR = "様式４の１(変圧器・線路)"
SHEET_PCS = "様式３の４(逆変換装置)"
SHEET_F1 = "様式1"
SHEET_F2 = "様式2"
SHEET_F4_2 = "様式４の２(受電設備)"
SHEET_F4_3 = "様式４の３(給電情報)"
SHEET_DEMAND_PV = "様式５の５"
SHEET_DEMAND_BAT = "様式５の５(蓄電池)"

# 様式５の５: 行12(00:00)〜行35(23:00)、列 E=稼働A G=稼働B I=停止A K=停止B
_DEMAND_FIRST_ROW = 12
_DEMAND_HOURS = 24


@dataclass(frozen=True)
class TrCellMap:
    """様式４の１の1変圧器ブロックの入力セル（結合範囲の左上）。"""

    maker: str
    model_name: str
    name: str
    rated_kva: str
    rated_kv: str
    connection: str
    pctz_base_kva: str
    xps: str
    xst: str
    xtp: str
    count: str
    boost_target: str
    neutral_grounding: str | None = None  # その他変圧器ブロックには無い


# 連系用変圧器（１．）
TR_RENKEI = TrCellMap(
    maker="Y7",
    model_name="AR7",
    name="AB8",
    rated_kva="AL9",
    rated_kv="AL10",
    connection="AL11",
    pctz_base_kva="AS16",
    xps="AO17",
    xst="AX17",
    xtp="BG17",
    neutral_grounding="AL18",
    count="AL19",
    boost_target="AL20",
)

# その他の変圧器（２．）
TR_SONOTA = TrCellMap(
    maker="Y26",
    model_name="AR26",
    name="AB27",
    rated_kva="AL28",
    rated_kv="AL29",
    connection="AL30",
    pctz_base_kva="AS35",
    xps="AO36",
    xst="AX36",
    xtp="BG36",
    count="AL37",
    boost_target="AL38",
)


def _num(value: float) -> str:
    """数値を様式向けに整形（整数は桁区切り、端数は保持）。"""
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:g}"


def _opt_num(value) -> str | None:
    return None if value is None else _num(value)


def _rated_kva_label(tr: Transformer) -> str:
    if tr.rated_kva_label:
        return tr.rated_kva_label
    kva = _num(tr.rated_mva * 1000.0)
    return f"{kva}／{kva}"  # 1次／2次（同容量を既定とする）


def _rated_kv_label(tr: Transformer) -> str:
    parts = [_num(tr.primary_kv), _num(tr.secondary_kv)]
    if tr.tertiary_kv is not None:
        parts.append(_num(tr.tertiary_kv))
    return "／".join(parts)


def _write(ws, cell: str | None, value) -> None:
    """セルへ書き込む。結合セルの非左上が指定された場合は左上へ解決する。"""
    if cell is None or value is None:
        return
    from openpyxl.cell.cell import MergedCell

    target = ws[cell]
    if isinstance(target, MergedCell):
        for rng in ws.merged_cells.ranges:
            if cell in rng:
                ws.cell(rng.min_row, rng.min_col).value = value
                return
        return  # 解決不能なら安全のためスキップ
    target.value = value


def _fill_transformer(ws, tr: Transformer, m: TrCellMap) -> None:
    _write(ws, m.maker, tr.maker)
    _write(ws, m.model_name, tr.model_name)
    _write(ws, m.name, tr.name)
    _write(ws, m.rated_kva, _rated_kva_label(tr))
    _write(ws, m.rated_kv, _rated_kv_label(tr))
    _write(ws, m.connection, tr.connection_method)
    _write(ws, m.pctz_base_kva, _num((tr.base_kva or tr.rated_mva * 1000.0)))
    _write(ws, m.xps, _num(tr.xps_pct if tr.xps_pct is not None else tr.pct_z))
    _write(ws, m.count, tr.count)
    _write(ws, m.boost_target, tr.boost_target)
    _write(ws, m.neutral_grounding, tr.neutral_grounding)


def _fill_pcs(ws, pcs: Pcs) -> None:
    """様式３の４（逆変換装置）の1台分（先頭PCS）を転記する。"""
    w = lambda cell, val: _write(ws, cell, val)  # noqa: E731

    # １．全般
    w("AR5", pcs.generator_no)              # 号発電機
    w("BA5", pcs.install_type)              # 既設/新設/増設
    w("AR7", pcs.prime_mover)               # 原動機の種類
    w("AR8", pcs.count)                     # 台数 [台]

    # ２．逆変換装置
    w("Y11", pcs.maker)                     # メーカ
    w("AR11", pcs.model)                    # 型式
    w("T12", pcs.electric_system)           # 電気方式
    w("T13", _opt_num(pcs.rated_kva if pcs.rated_kva is not None
                      else pcs.rated_kw / pcs.power_factor))  # 定格容量 [kVA]
    w("T14", _opt_num(pcs.rated_kw))        # 定格出力 [kW]
    w("T15", _opt_num(pcs.output_min_kw))   # 出力変化範囲 下限
    w("AR15", _opt_num(pcs.output_max_kw))  # 出力変化範囲 上限
    w("T16", _opt_num(pcs.rated_voltage_kv))            # 定格電圧 [kV]
    w("AV16", _opt_num(pcs.voltage_range_min_pu))       # 運転可能電圧範囲 下限 [pu]
    w("BE16", _opt_num(pcs.voltage_range_max_pu))       # 運転可能電圧範囲 上限 [pu]
    w("AL17", _opt_num(pcs.pf_rated_pct_value))         # 力率（定格）[%]
    w("AO18", _opt_num(pcs.pf_range_lag_pct))           # 力率運転可能範囲 遅れ [%]
    w("BC18", _opt_num(pcs.pf_range_lead_pct))          # 力率運転可能範囲 進み [%]
    w("T19", pcs.voltage_reactive_control)              # 電圧・無効電力制御
    w("AL20", _opt_num(pcs.rated_frequency_hz))         # 定格周波数 [Hz]
    w("T21", _opt_num(pcs.cont_freq_min_hz))            # 連続運転可能周波数 下限 [Hz]
    w("AC21", _opt_num(pcs.cont_freq_max_hz))           # 連続運転可能周波数 上限 [Hz]
    w("AR30", pcs.auto_sync_check)          # 自動同期検定機能（自励式）
    w("AR32", _opt_num(pcs.current_limit_pct))          # 通電電流制限値 [%]
    w("AR33", _opt_num(pcs.pf_control_time_ms))         # 系統事故時の力率制御時間 [ms]
    w("AR34", pcs.main_circuit)             # 主回路方式
    w("AR35", pcs.output_control)           # 出力制御方式
    w("AR36", pcs.frt_applied)              # FRT要件適用の有無
    w("AR37", _opt_num(pcs.harmonic_total_pct))         # 高調波電流歪率 総合 [%]


def _fill_form1(ws, f) -> None:
    """様式１（基本情報）を転記。入力セルは様式の結合範囲から確定。"""
    w = lambda cell, val: _write(ws, cell, val)  # noqa: E731
    # 申込者ブロック（上部）
    w("AU15", f.applicant_address)   # 住所（本体）
    w("AU18", f.applicant_company)   # 事業者名
    w("AU20", f.representative)      # 代表者氏名
    # (1)発電設備等設置者名
    w("X24", f.installer_name)
    w("AD23", f.installer_kana)
    # 同一法人等 該当有無
    w("X26", f.same_corporation)
    # (2)発電所名
    w("X29", f.plant_name)
    w("AD28", f.plant_name_kana)
    # (3)〜(7)
    w("X31", f.site_address)
    w("X33", f.connect_utility)
    w("X35", f.existing_access)
    w("X38", f.change_type)
    w("X41", f.contract_type)
    # (8)連絡先窓口
    if f.contact is not None:
        c = f.contact
        w("AD45", c.address)
        w("AD47", c.company)
        w("AD48", c.department)
        w("AD49", c.person)
        w("AD50", c.phone)
        w("AD51", c.email)


def _fill_date(ws, d, year_cell: str, month_cell: str, day_cell: str) -> None:
    """年/月/日を該当セルへ。各セルは結合範囲の左上で検証済み。"""
    if d is None:
        return
    _write(ws, year_cell, d.year)
    _write(ws, month_cell, d.month)
    _write(ws, day_cell, d.day)


def _fill_form2(ws, f) -> None:
    """様式２（発電設備等の概要）を転記。入力セルは結合範囲から確定済み。

    収録: 希望時期(年月日)・希望受電電圧・予備電線路・電源種別・定格出力合計・
    受電電力・自家消費電力。受電電力は外気温別の表だが代表値（外気温なし）を記入。
    """
    w = lambda cell, val: _write(ws, cell, val)  # noqa: E731
    # １．希望時期（年=AM, 月=AT, 日=AY）
    _fill_date(ws, f.access_start, "AM6", "AT6", "AY6")
    _fill_date(ws, f.trial_start, "AM7", "AT7", "AY7")
    _fill_date(ws, f.commercial_start, "AM8", "AT8", "AY8")
    # ２．希望受電電圧・予備電線路
    w("AM12", _opt_num(f.desired_voltage_kv))   # 希望受電電圧 [kV]
    w("AM13", f.reserve_line)                    # 予備電線路希望の有無
    w("AM14", f.reserve_service)                 # 希望する予備送電サービス
    w("AM15", _opt_num(f.reserve_contract_kw))   # 予備送電サービス契約電力 [kW]
    # ３．電源種別（新設・増設）
    w("O20", f.source_type)
    # ４．定格出力合計（変更後行: 種別I45 / 台数S45 / 出力X45）
    w("I45", f.rated_total_type)
    w("S45", f.rated_total_count)
    w("X45", _opt_num(f.rated_total_kw))
    # ５．受電電力（変更後: 最大X51 / 最小X52）
    w("X51", _opt_num(f.received_power_max_kw))
    w("X52", _opt_num(f.received_power_min_kw))
    # ６．自家消費電力（最大: kW=L58 力率=X58 / 最小: kW=L59 力率=X59）
    w("L58", _opt_num(f.house_load_max_kw))
    w("X58", _opt_num(f.house_load_max_pf))
    w("L59", _opt_num(f.house_load_min_kw))
    w("X59", _opt_num(f.house_load_min_pf))


def _fill_form4_2(ws, f) -> None:
    """様式４の２（受電設備および負荷設備）を転記。"""
    w = lambda cell, val: _write(ws, cell, val)  # noqa: E731
    w("AL7", f.insulation_method)            # 絶縁方式
    w("Y10", f.breaker_maker)                # 連系用遮断器 メーカ
    w("AR10", f.breaker_model)               # 連系用遮断器 型式
    w("AL11", _opt_num(f.breaker_voltage_kv))    # 定格電圧 [kV]
    w("AL12", _opt_num(f.breaker_current_a))     # 定格電流 [A]
    w("AL13", _opt_num(f.breaker_breaking_ka))   # 定格遮断電流 [kA]
    w("AL14", f.breaker_breaking_time)       # 定格遮断時間
    w("AL17", f.pfc_type)                    # 調相設備 種類
    w("AL18", f.pfc_capacity_ehv)            # 電圧別容量 特別高圧
    w("AL19", f.pfc_capacity_hv)             # 電圧別容量 高圧
    w("AL20", f.pfc_capacity_lv)             # 電圧別容量 低圧
    w("AL21", f.pfc_capacity_total)          # 合計容量
    w("AL22", f.pfc_auto_control)            # 自動力率制御装置の有無


def _fill_demand(ws, d) -> None:
    """様式５の５（運用パターン）を転記。

    時季(J6) と 24時間分の稼働/停止×A/B列(E/G/I/K)。グラフは様式側が
    CL〜CP の関数列経由で自動連動するため、こちらは生データのみ書き込む。
    """
    _write(ws, "J6", d.season)
    for h in range(_DEMAND_HOURS):
        r = _DEMAND_FIRST_ROW + h
        _write(ws, f"E{r}", d._at(d.active_a, h))
        _write(ws, f"G{r}", d._at(d.active_b, h))
        _write(ws, f"I{r}", d._at(d.idle_a, h))
        _write(ws, f"K{r}", d._at(d.idle_b, h))


def _fill_form4_3(ws, f) -> None:
    """様式４の３（監視制御）を転記。"""
    w = lambda cell, val: _write(ws, cell, val)  # noqa: E731
    w("AA7", f.phone_line_form)      # 保安通信用電話 通信回線形態
    w("AA8", f.phone_location)       # 保安通信用電話 設置場所
    w("AA9", f.info_line_form)       # 情報伝送装置 通信回線形態
    w("AA10", f.info_device_type)    # 情報伝送装置 装置の種類
    w("AA11", f.info_location)       # 情報伝送装置 設置場所
    w("O14", f.monitoring_control)   # 監視制御方式


def fill_ak1t(
    project: Project,
    template_path: str | Path,
    output_path: str | Path,
) -> dict[str, int]:
    """案件情報を AK1T テンプレートへ転記し、記入済みブックを保存する。

    戻り値: 書き込んだシートごとの転記項目数（サマリ）。
    """
    wb = openpyxl.load_workbook(template_path)
    written: dict[str, int] = {}

    if project.form1 is not None:
        _fill_form1(wb[SHEET_F1], project.form1)
        written[SHEET_F1] = 1
    if project.form2 is not None:
        _fill_form2(wb[SHEET_F2], project.form2)
        written[SHEET_F2] = 1
    if project.form4_2 is not None:
        _fill_form4_2(wb[SHEET_F4_2], project.form4_2)
        written[SHEET_F4_2] = 1
    if project.form4_3 is not None:
        _fill_form4_3(wb[SHEET_F4_3], project.form4_3)
        written[SHEET_F4_3] = 1
    if project.demand_pv is not None:
        _fill_demand(wb[SHEET_DEMAND_PV], project.demand_pv)
        written[SHEET_DEMAND_PV] = 1
    if project.demand_battery is not None:
        _fill_demand(wb[SHEET_DEMAND_BAT], project.demand_battery)
        written[SHEET_DEMAND_BAT] = 1

    transformers = [c for c in project.network if isinstance(c, Transformer)]
    renkei = [t for t in transformers if t.role == "連系用"]
    sonota = [t for t in transformers if t.role == "その他"]

    ws = wb[SHEET_TR]
    n = 0
    if renkei:
        _fill_transformer(ws, renkei[0], TR_RENKEI)
        n += 1
    if sonota:
        _fill_transformer(ws, sonota[0], TR_SONOTA)
        n += 1
    written[SHEET_TR] = n

    if project.pcs:
        _fill_pcs(wb[SHEET_PCS], project.pcs[0])
        written[SHEET_PCS] = 1

    wb.save(output_path)
    return written
