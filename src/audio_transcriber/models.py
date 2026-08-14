"""音声認識・字幕・ストリーミング連携用データモデルモジュール。

本モジュールは、タイムスタンプ付き字幕データ (SubtitleSegment)、
音声認識結果セグメント (RecognizedSegment)、VAD状態 (VadState)、
および音響イベント (SoundEvent) のデータ構造を提供します。
"""

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class VadState(StrEnum):
    """VAD（音声区間検出）の状態を表す Enum。"""

    SILENCE = "silence"
    SPEECH_START = "speech_start"
    SPEECH = "speech"
    SPEECH_END = "speech_end"


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


@dataclass
class RecognizedSegment:
    """音声認識結果セグメントデータモデル。

    Attributes:
        start (float): 発言開始時刻 (秒)。
        end (float): 発言終了時刻 (秒)。
        text (str): 認識されたテキスト。
        confidence (float): 認識信頼度 / 平均対数確率（0.0 〜 1.0）。
        speaker_id (str | None): 話者識別子（任意）。
        words (list[dict[str, object]] | None): 単語単位の認識情報（任意）。
    """

    start: float
    end: float
    text: str
    confidence: float = 0.0
    speaker_id: str | None = None
    words: list[dict[str, object]] | None = None

    def to_dict(self) -> dict[str, object]:
        """データモデルを辞書形式へ変換します。

        Returns:
            dict[str, object]: 変換後の辞書データ。
        """
        result: dict[str, object] = {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "confidence": self.confidence,
            "speaker_id": self.speaker_id,
            "words": self.words,
        }
        return result

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "RecognizedSegment":
        """辞書データからインスタンスを構築します。

        Args:
            data (dict[str, object]): 変換元の辞書データ。

        Returns:
            RecognizedSegment: 構築された音声認識セグメントインスタンス。
        """
        raw_words = data.get("words")
        words_list: list[dict[str, object]] | None = None
        if isinstance(raw_words, list):
            words_list = [w for w in raw_words if isinstance(w, dict)]

        raw_speaker = data.get("speaker_id")
        speaker_id: str | None = str(raw_speaker) if raw_speaker is not None else None

        return cls(
            start=float(data.get("start", 0.0)),  # type: ignore[arg-type]
            end=float(data.get("end", 0.0)),  # type: ignore[arg-type]
            text=str(data.get("text", "")),
            confidence=float(data.get("confidence", 0.0)),  # type: ignore[arg-type]
            speaker_id=speaker_id,
            words=words_list,
        )


@dataclass
class SoundEvent:
    """音響イベント（音圧ピーク、笑い声、SE等）データモデル。

    Attributes:
        event_type (str): イベント種別（例: "peak_energy", "laughter", "cheer"）。
        timestamp (float): イベント発生時刻 (秒)。
        score (float): イベント検知スコア / 確信度 (0.0 〜 1.0)。
        metadata (dict[str, object] | None): 任意の付加情報。
    """

    event_type: str
    timestamp: float
    score: float = 1.0
    metadata: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        """データモデルを辞書形式へ変換します。

        Returns:
            dict[str, object]: 変換後の辞書データ。
        """
        result: dict[str, object] = {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "score": self.score,
            "metadata": self.metadata,
        }
        return result

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "SoundEvent":
        """辞書データからインスタンスを構築します。

        Args:
            data (dict[str, object]): 変換元の辞書データ。

        Returns:
            SoundEvent: 構築された音響イベントインスタンス。
        """
        raw_meta = data.get("metadata")
        metadata: dict[str, object] | None = (
            raw_meta if isinstance(raw_meta, dict) else None
        )

        return cls(
            event_type=str(data.get("event_type", "unknown")),
            timestamp=float(data.get("timestamp", 0.0)),  # type: ignore[arg-type]
            score=float(data.get("score", 0.0)),  # type: ignore[arg-type]
            metadata=metadata,
        )
