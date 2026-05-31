"""AK1T 様式４の１ への転記が正しいセルへ入ることを検証。"""
import warnings
from pathlib import Path

import openpyxl
import pytest

from renkei.forms.ak1t import SHEET_PCS, SHEET_TR, fill_ak1t
from renkei.models.project import load_project

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent
SAMPLE = ROOT / "examples" / "sample_66kv.yaml"
TEMPLATE = ROOT / "reference" / "AK1T_202512r.xlsx"

pytestmark = pytest.mark.skipif(
    not TEMPLATE.exists(), reason="AK1T テンプレート未配置（reference/）"
)


@pytest.fixture
def filled_wb(tmp_path):
    project = load_project(SAMPLE)
    out = tmp_path / "filled.xlsx"
    fill_ak1t(project, TEMPLATE, out)
    return openpyxl.load_workbook(out)


@pytest.fixture
def filled(filled_wb):
    return filled_wb[SHEET_TR]


def test_renkei_transformer_cells(filled):
    # 連系用変圧器（１．）ブロック
    assert filled["Y7"].value == "○○電機"
    assert filled["AB8"].value == "受電変圧器(66/22kV)"
    assert filled["AL9"].value == "20,000／20,000"
    assert filled["AL10"].value == "66／22"
    assert filled["AS16"].value == "20,000"  # %Z 基準容量
    assert filled["AO17"].value == "12"       # Xps
    assert filled["AL18"].value == "非接地"
    assert filled["AL19"].value == 1


def test_sonota_transformer_cells(filled):
    # その他の変圧器（２．）ブロック = 下流 PCS 昇圧変圧器
    assert filled["AB27"].value == "PCS昇圧変圧器(0.69/22kV)"
    assert filled["AL28"].value == "2,100／2,100"
    assert filled["AL29"].value == "22／0.69"
    assert filled["AO36"].value == "6"
    assert filled["AL37"].value == 5
    assert filled["AL38"].value == "PCS1～5"


def test_pcs_inverter_cells(filled_wb):
    # 様式３の４（逆変換装置）
    ws = filled_wb[SHEET_PCS]
    assert ws["AR7"].value == "太陽光発電"     # 原動機の種類
    assert ws["AR8"].value == 18               # 台数
    assert ws["AR11"].value == "PCS-500"       # 型式
    assert ws["T12"].value == "三相３線式"      # 電気方式
    assert ws["T13"].value == "550"            # 定格容量 kVA
    assert ws["T14"].value == "500"            # 定格出力 kW
    assert ws["T16"].value == "0.69"           # 定格電圧 kV
    assert ws["AL17"].value == "95"            # 力率（定格）%
    assert ws["T19"].value == "電圧一定制御、力率一定制御"
    assert ws["AR34"].value == "自励式（電圧形）"
    assert ws["AR36"].value == "有"            # FRT
