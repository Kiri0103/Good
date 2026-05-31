"""SVG 生成の共通ユーティリティ（フォント解決・エスケープ）。

図面（単線結線図・配置図）の日本語が環境により豆腐（□）になる問題への対策。
一部の SVG レンダラ（cairosvg 等）はフォントスタックの先頭が存在しないと後続へ
フォールバックせず描画に失敗するため、実在する日本語フォントを fontconfig で検出し、
スタックの先頭に置く。検出できない場合も一般的な和文フォント名を並べて保険とする。
"""
from __future__ import annotations

import functools
import subprocess

# 検出できなかった場合のフォールバック（主要 OS の代表的な和文フォント名）。
_FALLBACK_STACK = (
    "'Noto Sans CJK JP','IPAexGothic','IPAGothic','Hiragino Kaku Gothic ProN',"
    "'Yu Gothic','Meiryo','MS PGothic',sans-serif"
)


@functools.lru_cache(maxsize=1)
def font_stack() -> str:
    """日本語を確実に表示するための font-family 文字列を返す。

    fontconfig（fc-match）で日本語向けの実在フォントファミリ名を取得し、先頭に置く。
    取得できない環境では一般的な和文フォント名のスタックのみを返す。
    """
    detected = _detect_jp_family()
    if detected:
        return f"'{detected}',{_FALLBACK_STACK}"
    return _FALLBACK_STACK


def _detect_jp_family() -> str | None:
    """fc-match で日本語フォントの実ファミリ名を1つ取得する。"""
    try:
        out = subprocess.run(
            ["fc-match", "-f", "%{family}", "sans-serif:lang=ja"],
            capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    # "IPAGothic,IPAゴシック" のようにカンマ区切りで返ることがある → 先頭を採用
    fam = out.stdout.strip().split(",")[0].strip()
    return fam or None


def esc(s: str) -> str:
    """SVG テキスト用の最小エスケープ。"""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
