"""音声セグメントのハルシネーション検出およびサニタイズモジュール。"""

from __future__ import annotations

from audio_transcriber.sanitizer_core import SegmentSanitizer
from audio_transcriber.sanitizer_types import DropReason, SanitizeResult

__all__ = ["DropReason", "SanitizeResult", "SegmentSanitizer"]
