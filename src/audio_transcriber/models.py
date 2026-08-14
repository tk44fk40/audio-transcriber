"""音声認識・字幕セグメントデータモデルモジュール。

本モジュールは、タイムスタンプ付き発言字幕データを保持する
SubtitleSegment データクラスを提供します。
"""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SubtitleSegment:
    """タイムスタンプ付き発言字幕データモデル。

    Attributes:
        start (float): 発言開始時刻 (秒)。
        end (float): 発言終了時刻 (秒)。
        text (str): 発言字幕テキスト。
    """

    start: float
    end: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        """データモデルを辞書形式へ変換します。

        Returns:
            dict[str, Any]: 変換後の辞書データ。
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubtitleSegment":
        """辞書データからインスタンスを構築します。

        型変換 (float, str) および欠損キーに対する安全なデフォルト値を適用します。

        Args:
            data (dict[str, Any]): 変換元の辞書データ。

        Returns:
            SubtitleSegment: 構築された字幕セグメントインスタンス。
        """
        return cls(
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            text=str(data.get("text", "")),
        )
