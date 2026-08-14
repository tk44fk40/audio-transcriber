"""数字表現の正規化モジュール。

テキスト内の数字表現（漢数字、ローマ数字、丸数字、全角数字等）を
半角アラビア数字に統一正規化するユーティリティを提供します。
"""

import re
from typing import ClassVar


class NumberNormalizer:
    """数字表現の正規化を行うクラス。"""

    # 丸数字 → アラビア数字のマッピング
    _MARU_MAP: ClassVar[dict[str, str]] = {
        "①": "1",
        "②": "2",
        "③": "3",
        "④": "4",
        "⑤": "5",
        "⑥": "6",
        "⑦": "7",
        "⑧": "8",
        "⑨": "9",
        "⑩": "10",
        "⑪": "11",
        "⑫": "12",
        "⑬": "13",
        "⑭": "14",
        "⑮": "15",
        "⑯": "16",
        "⑰": "17",
        "⑱": "18",
        "⑲": "19",
        "⑳": "20",
    }

    # ローマ数字（長い順に変換して誤変換を防ぐ）
    _ROMAN_MAP: ClassVar[list[tuple[str, str]]] = [
        ("VIII", "8"),
        ("VII", "7"),
        ("III", "3"),
        ("VI", "6"),
        ("IV", "4"),
        ("IX", "9"),
        ("II", "2"),
        ("V", "5"),
        ("X", "10"),
        ("I", "1"),
        ("\u2167", "8"),
        ("\u2166", "7"),
        ("\u2162", "3"),
        ("\u2165", "6"),
        ("\u2163", "4"),
        ("\u2168", "9"),
        ("\u2161", "2"),
        ("\u2164", "5"),
        ("\u2169", "10"),
        ("\u2160", "1"),
    ]

    # 漢数字 → アラビア数字のマッピング
    _KANJI_MAP: ClassVar[list[tuple[str, str]]] = [
        ("十", "10"),
        ("九", "9"),
        ("八", "8"),
        ("七", "7"),
        ("六", "6"),
        ("五", "5"),
        ("四", "4"),
        ("三", "3"),
        ("二", "2"),
        ("一", "1"),
        ("〇", "0"),
        ("ゼロ", "0"),
    ]

    @staticmethod
    def normalize(text: str) -> str:
        """テキスト内の数字表現を半角アラビア数字に正規化します。

        以下の変換を順次適用します:
        1. 全角数字 → 半角数字
        2. 丸数字 (①〜⑳) → アラビア数字
        3. ローマ数字 (I〜X, Ⅰ〜Ⅹ) → アラビア数字
        4. 漢数字 (〇〜十) → アラビア数字
        5. 「10X」形式（十X の変換後崩れ）の補正

        Args:
            text (str): 対象文字列。

        Returns:
            str: 正規化済みの文字列。
        """
        if not text:
            return text

        # 1. 全角数字 → 半角数字
        text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))

        # 2. 丸数字の変換
        for src, dst in NumberNormalizer._MARU_MAP.items():
            text = text.replace(src, dst)

        # 3. ローマ数字の変換（長い順）
        for r_src, r_dst in NumberNormalizer._ROMAN_MAP:
            text = text.replace(r_src, r_dst)

        # 4. 漢数字の変換
        for k_src, k_dst in NumberNormalizer._KANJI_MAP:
            text = text.replace(k_src, k_dst)

        # 5. 「101」など（十1 → 11）の補正
        text = re.sub(r"10([1-9])", r"1\1", text)

        # 6. 最終的に全角数字へ統一
        zenkaku_table = str.maketrans("0123456789", "０１２３４５６７８９")
        text = text.translate(zenkaku_table)

        return text
