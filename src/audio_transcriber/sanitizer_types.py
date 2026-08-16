"""音声セグメントのハルシネーション検出およびサニタイズ用の型定義。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from audio_transcriber.models import SubtitleSegment

__all__ = ["DropReason", "SanitizeResult"]


class DropReason(StrEnum):
    """サニタイズによるセグメント除外理由の列挙型。"""

    EMPTY = "empty"
    NO_SPEECH = "no_speech"
    SPEED = "speed"
    LOOP = "loop"


@dataclass(frozen=True)
class SanitizeResult:
    """サニタイズ判定の詳細結果データクラス。"""

    segment: SubtitleSegment | None
    drop_reason: DropReason | None = None
    drop_detail: str | None = None
    repeat_shortened: bool = False
    original_text: str = ""
    cleaned_text: str = ""
