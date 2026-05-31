# renkei — 特別高圧 接続検討申請 設計自動化

太陽光・蓄電池 EPC における、電力会社向け**特別高圧 接続検討申請書**の作成を
自動化するためのツール群。客先の案件情報から、設計成果物（インピーダンス計算・
配置図・工事工程・単線結線図）を**確実で間違いのない**形で生成し、申請様式へ
転記することを目的とする。

## 現状（v0.1: インピーダンス計算）

最優先の「インピーダンス計算」を実装。`%Z 法`（パーセントインピーダンス法）で
系統〜連系点の総合インピーダンスを求め、三相短絡電流・電圧変動・設備容量を算出する。

```bash
# セットアップ（pydantic / pyyaml が必要。開発時は pytest）
pip install -e ".[dev]"

# 計算レポートを出力
renkei calc examples/sample_66kv.yaml
#   または
PYTHONPATH=src python3 -m renkei.cli calc examples/sample_66kv.yaml

# テスト（手計算との一致を検証）
pytest -q
```

### 入力（案件情報）

`examples/sample_66kv.yaml` を雛形に、1 案件 = 1 ファイル（YAML/JSON）で記述する。
pydantic がスキーマ検証を行い、単位や必須項目の不備を提出前に機械的に弾く。

- `grid`: 系統条件（電力会社提示の三相短絡容量 or %Z、X/R）
- `network`: 系統 → 連系点へ向かう直列構成（線路・変圧器）
- `pcs` / `battery`: 機器仕様
- `export_power_mw` / `operating_power_factor` / `power_factor_mode`: 逆潮流条件

### 出力

計算過程をテキストレポート化（人によるレビュー用の中間成果物）:
1. インピーダンス（要素別・複素 %Z、総合）
2. 三相短絡（短絡容量・短絡電流、PCS 寄与含む）
3. 電圧変動（逆潮流時 ΔV）
4. 設備容量

## 様式への自動転記（AK1T）

OCCTO 接続検討申込書（特別高圧 様式 AK1T）の Excel テンプレートへ、案件情報を
自動転記する。手作業の転記ミスを排除するのが目的。

```bash
renkei fill examples/sample_66kv.yaml -o filled_AK1T.xlsx
#   テンプレートは既定で reference/AK1T_202512r.xlsx を使用（-t で変更可）
```

- 入力欄のセル番地は `tools/dump_form.py` で様式を解析して確定（記載例 PDF で裏取り）。
- **実装済み（データ転記）**:
  - 様式１（基本情報）
  - 様式２（概要：希望時期・希望受電電圧・予備電線路・電源種別・定格出力合計・受電電力・自家消費電力）
  - 様式３の４（逆変換装置＝PCS）
  - 様式４の１（変圧器・線路）
  - 様式４の２（受電設備：絶縁方式・連系用遮断器・調相設備）
  - 様式４の３（監視制御：通信形態・監視制御方式）
  - 様式５の５（需給バランス：太陽光・蓄電池の24時間運用パターン。グラフは様式側が自動連動）
- **対象外**: 様式３の１〜３/５（同期機・誘導機等＝他電源種別用）, 様式５系の図面（配置図・土地調査などの**作図シート**）。
- `reference/` に OCCTO 様式テンプレートと太陽光記載例を同梱（再ダウンロード不可のため）。

## 単線結線図（SVG 自動生成）

機器構成（系統→線路→変圧器→連系点→PCS→蓄電池）から単線結線図を SVG で生成する。
様式５の４（単線結線図）は空の作図キャンバスのため、生成 SVG を印刷・添付する運用。

```bash
renkei sld examples/sample_66kv.yaml -o single_line_diagram.svg
```

JIS の厳密なシンボルではなく、接続検討レビューに足る簡略記号（系統＝〜入り円、
変圧器＝二重円、PCS＝=/~ 箱、蓄電池＝電池記号など）を用いる。

## 配置図（SVG 自動生成）

敷地（`layout`）と機器（`equipment`）の平面配置を、縮尺・寸法線・方位・スケールバー
付きの SVG で生成する。入力の座標・寸法は [m]（原点＝敷地左下）だが、**図面の寸法
ラベルは mm 表記**（例: 幅 60,000 mm、8,000×4,000mm）。種別（PCS/蓄電池/受変電）で
色分けする。

```bash
renkei layout examples/sample_66kv.yaml -o site_layout.svg
```

### 自動配置（セットバック内グリッド配置）

`layout.auto_arrange: true` とすると、機器の座標は不要になり、**敷地境界から
`setback_m` だけ内側の領域に、機器を行優先（左→右・下→上）で自動配置**する。
機器相互は `min_clearance_m` 以上の間隔を確保する。寸法・台数だけ与えれば概略
配置の叩き台が得られる。

```yaml
layout:
  site_width_m: 60.0
  site_depth_m: 40.0
  setback_m: 2.0          # 敷地境界からのセットバック
  min_clearance_m: 1.0
  auto_arrange: true
  equipment:
    - {name: 受変電設備, width_m: 12, depth_m: 6, category: 受変電}
    - {name: PCS-A,     width_m: 8,  depth_m: 4, category: PCS}
    # 座標 x_m/y_m は自動配置時は不要
```

寸法整合は `renkei check` で自動検証される（コード L-BOUNDS 敷地外 / L-OVERLAP
重なり / L-CLEAR 離隔不足 / L-SETBACK 境界離隔 / L-OVERFLOW 自動配置で収まらない）。

## 提出前チェック（様式間整合の自動検証）

案件情報に対し、様式間の整合・計算結果との突合・必須項目・物理的妥当性をルールで
検査し、ミスを機械的に検出する。「確実で間違いのない提出物」を担保する要。

```bash
renkei check examples/sample_66kv.yaml
#   ERROR があれば終了コード 1（CI 等で検出可能）
```

重大度は ERROR（必ず是正）/ WARNING（要確認）/ INFO（参考）。主な検査:

| コード | 内容 |
|---|---|
| V-VOLT-POC | 希望受電電圧（様式2）＝連系点電圧 |
| V-VOLT-CB | 連系用遮断器の定格電圧 ≥ 連系点電圧 |
| V-VOLT-TR2 | 連系用変圧器2次電圧＝連系点電圧 |
| V-PCS-TRKV | 昇圧変圧器2次電圧＝PCS定格電圧 |
| V-OUT-TOTAL | 定格出力合計（様式2）＝PCS合計出力 |
| V-RECV-EXPORT | 受電電力（様式2, 送電は負）＝逆潮流 |
| V-SRC-TYPE | 電源種別（様式2）＝PCS原動機（様式3の4） |
| V-SC-CB | 遮断器定格遮断電流 ≥ 連系点短絡電流（計算値） |
| V-PF-* | 力率の物理的妥当性（0〜100% 等） |
| V-DEM-LEN/PEAK | 需給パターンが24点・発電ピーク≤PCS合計 |
| L-BOUNDS/OVERLAP | 配置図 機器の敷地外はみ出し・重なり |
| L-CLEAR/SETBACK | 配置図 機器離隔・境界セットバック |
| L-OVERFLOW | 自動配置でセットバック内に収まらない |
| R-FORM1/PCS/TR | 必須項目の欠落 |

## 一括生成（build）

1 案件から全成果物（計算レポート・AK1T 様式・単線結線図・配置図・チェック結果）を
出力ディレクトリにまとめて生成する。

```bash
renkei build examples/sample_66kv.yaml -d output
#   output/report.txt  AK1T.xlsx  single_line_diagram.svg  site_layout.svg  check.txt
#   提出前チェックで ERROR があれば終了コード 1
```

### 既知の制限（要確認）

- openpyxl はテンプレート保存時に **DrawingML 図形（shapes）を失う**（画像・グラフは保持）。
  セル罫線ベースの様式は問題ないが、図形描画を含むシートは欠落しうる。図面系
  （単線結線図・配置図）は別途作図機能で対応予定。

## 計算方法と前提

`src/renkei/calc/base.py` に換算式を明記。標準的な %Z 法に基づく。

| 換算 | 式 |
|---|---|
| 基準電流 | Ib[kA] = Sb / (√3·Vb) |
| 基準インピーダンス | Zb[Ω] = Vb²/Sb |
| Ω→%Z | %Z = 100·Z[Ω]·Sb/Vb² |
| 自己容量%Z→基準%Z | %Z = %Z_self·(Sb/S_self) |
| 短絡容量→%Z | %Z = 100·Sb/Ssc |
| 三相短絡電流 | Isc = Ib·100/\|%Z\| |
| 電圧変動 | ΔV[%] ≈ (P·R[%] + Q·X[%]) / Sb |

### 要確認の前提（レビュー必須）

設計の正しさに直結するため、運用前に必ず確認すること:

- **構成**: 放射状（直列）構成を前提。ループ・複数受電は未対応。
- **X/R 比**: 既定値（系統10 / 変圧器15〜20）はダミー。電力会社・メーカ提示値を優先。
- **PCS 短絡寄与** `fault_current_pu`: 既定 1.1。メーカ仕様で要設定。
- **無効電力の符号**: 「遅れ=Q>0（昇圧）/ 進み=Q<0（抑制）」と定義。各社定義に要整合。

## ロードマップ

- [x] **インピーダンス計算**（短絡電流・電圧変動・力率）
- [x] **AK1T 様式転記（データ系を網羅）**: 様式１, 様式２, 様式３の４（PCS）, 様式４の１（変圧器・線路）, 様式４の２（受電設備）, 様式４の３（監視制御）, 様式５の５（需給バランス）
- [x] **単線結線図**: 機器構成からの SVG 自動生成
- [x] **提出前チェック**: 様式間整合・計算突合・必須項目の自動検証
- [x] **配置図**: 敷地・機器配置からの SVG 自動生成（寸法チェック付き）
- [ ] **工事工程**: ガントチャート生成

## ディレクトリ構成

```
src/renkei/
  models/project.py   案件情報スキーマ（pydantic）
  calc/base.py        %Z 法 基本換算
  calc/impedance.py   ネットワーク合成
  calc/shortcircuit.py 短絡電流
  calc/voltage.py     電圧変動・力率
  forms/ak1t.py       AK1T 様式への自動転記
  forms/sld.py        単線結線図 SVG 生成
  forms/layout.py     配置図 SVG 生成（mm 表記）
  forms/arrange.py    機器の自動配置（セットバック内グリッド）
  forms/_svg.py       SVG 共通（日本語フォント解決）
  validate.py         提出前チェック（様式間整合の検証）
  report.py           計算レポート生成
  cli.py              コマンドライン（calc / fill / sld / layout / check / build）
tools/dump_form.py    様式 Excel の構造ダンプ（セルマップ作成補助）
reference/            OCCTO 様式テンプレート・記載例（同梱）
tests/                手計算と一致を検証
examples/             記入例
```
