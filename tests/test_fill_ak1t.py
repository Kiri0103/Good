"""AK1T 様式４の１ への転記が正しいセルへ入ることを検証。"""
import warnings
from pathlib import Path

import openpyxl
import pytest

from renkei.forms.ak1t import (
    SHEET_DEMAND_BAT,
    SHEET_DEMAND_PV,
    SHEET_F1,
    SHEET_F2,
    SHEET_F4_2,
    SHEET_F4_3,
    SHEET_PCS,
    SHEET_TR,
    fill_ak1t,
)
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


def test_form1_basic_cells(filled_wb):
    ws = filled_wb[SHEET_F1]
    assert ws["X24"].value == "●●●発電株式会社"          # (1)設置者名
    assert ws["AD23"].value == "マルマルマルハツデン"      # (1)フリガナ
    assert ws["X29"].value == "サンプル発電所（仮称）"      # (2)発電所名
    assert ws["X31"].value == "●●県●●市●●町●丁目●番●号"  # (3)住所
    assert ws["X35"].value == "無"                       # (5)既設アクセス設備
    assert ws["X38"].value == "新規"                     # (6)変更有無
    assert ws["X41"].value == "FIT"                      # (7)契約種別
    assert ws["AU20"].value == "●●　●●"                 # 代表者氏名
    # (8)連絡先窓口
    assert ws["AD45"].value == "〒●●●－●●●● 東京都●●区●●"
    assert ws["AD47"].value == "●●●発電株式会社"
    assert ws["AD49"].value == "●●　●●"
    assert ws["AD51"].value == "●●●@●●●"


def test_form2_overview_cells(filled_wb):
    ws = filled_wb[SHEET_F2]
    # 希望時期（年=AM, 月=AT, 日=AY）
    assert ws["AM6"].value == 2025 and ws["AT6"].value == 10 and ws["AY6"].value == 1
    assert ws["AM8"].value == 2026           # 営業運転開始 年
    assert ws["AM12"].value == "22"          # 希望受電電圧 kV（連系点と一致）
    assert ws["AM13"].value == "有"          # 予備電線路希望
    assert ws["AM14"].value == "Ａ（予備線）"  # 希望する予備送電サービス
    assert ws["AM15"].value == "9,000"       # 予備送電契約電力 kW
    assert ws["O20"].value == "太陽光"        # 電源種別
    # 定格出力合計（変更後）= PCS 500kW×18台
    assert ws["I45"].value == "太陽光" and ws["S45"].value == 18 and ws["X45"].value == "9,000"
    # 受電電力（変更後）送電は負
    assert ws["X51"].value == "-9,000"
    # 自家消費電力
    assert ws["L58"].value == "1,000" and ws["X58"].value == "95"


def test_form4_2_received_equipment_cells(filled_wb):
    ws = filled_wb[SHEET_F4_2]
    assert ws["AL7"].value == "ガス絶縁"               # 絶縁方式
    assert ws["Y10"].value == "○○電機"                # 遮断器 メーカ
    assert ws["AL11"].value == "24"                    # 定格電圧 kV（連系点22kVクラス）
    assert ws["AL12"].value == "2,000"                 # 定格電流 A
    assert ws["AL13"].value == "31.5"                  # 定格遮断電流 kA
    assert ws["AL14"].value == "5"                     # 定格遮断時間
    assert ws["AL17"].value == "リアクトル付進相コンデンサ"  # 調相設備 種類
    assert ws["AL21"].value == "4,000kvar"             # 合計容量
    assert ws["AL22"].value == "有"                    # 自動力率制御


def test_form4_3_monitoring_cells(filled_wb):
    ws = filled_wb[SHEET_F4_3]
    assert ws["AA7"].value == "メタル通信ケーブル"     # 保安通信 回線形態
    assert ws["AA8"].value == "発電設備等設置地点"     # 保安通信 設置場所
    assert ws["AA10"].value == "ＣＤＴ方式"            # 情報伝送 装置種類
    assert ws["O14"].value == "随時監視制御方式"        # 監視制御方式


def test_demand_pv_cells(filled_wb):
    # 様式５の５（太陽光）: 行12=00:00, 行24=12:00
    ws = filled_wb[SHEET_DEMAND_PV]
    assert ws["J6"].value == "通　年"
    assert ws["E24"].value == 9000      # 12:00 発電
    assert ws["G24"].value == 0         # 12:00 買電
    assert ws["G12"].value == 50        # 00:00 買電


def test_demand_battery_cells(filled_wb):
    # 様式５の５（蓄電池）: 行24=12:00 充電, 行29=17:00 放電
    ws = filled_wb[SHEET_DEMAND_BAT]
    assert ws["G24"].value == -4000     # 12:00 充電
    assert ws["E29"].value == 3000      # 17:00 放電
