"""OCCTO 接続検討申込書（特別高圧 様式 AK1T）への自動転記。

案件情報（Project）を、AK1T の Excel テンプレートの該当セルへ書き込み、記入済み
ブックを出力する。手作業による転記ミスを排除することが目的。

セル番地は `reference/AK1T_202512r.xlsx` の様式を `tools/dump_form.py` で解析して
確定したもの。結合セルへは左上セルに書き込む（openpyxl の仕様）。

実装済みシート:
  - 様式４の１(変圧器・線路) : 連系用変圧器 / その他の変圧器

未実装（順次拡張）: 様式１, 様式２, 様式３の４(逆変換装置), 様式４の２(受電設備) 等
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import openpyxl

from renkei.models.project import Pcs, Project, Transformer

SHEET_TR = "様式４の１(変圧器・線路)"
SHEET_PCS = "様式３の４(逆変換装置)"


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
    if cell is None or value is None:
        return
    ws[cell] = value


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


def _opt_num(value) -> str | None:
    return None if value is None else _num(value)


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
