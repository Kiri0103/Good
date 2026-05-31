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

from renkei.models.project import Project, Transformer

SHEET_TR = "様式４の１(変圧器・線路)"


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

    wb.save(output_path)
    return written
