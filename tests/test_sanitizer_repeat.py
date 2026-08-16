"""SegmentSanitizer のリピート短縮・エコー重複・ループ除外機能の単体テスト。"""

from types import SimpleNamespace
from typing import Any

from audio_transcriber.models import SubtitleSegment
from audio_transcriber.sanitizer import SegmentSanitizer


def test_sanitizer_reduces_intra_segment_repetition() -> None:
    """セグメント内のリピートがハルシネーション条件で短縮されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    segments: list[Any] = [
        SimpleNamespace(
            start=0.0,
            end=2.0,
            text="あいうえおあいうえお",
            no_speech_prob=0.2,
            compression_ratio=1.5,
        ),
        SimpleNamespace(
            start=2.5,
            end=4.5,
            text="かきくけこかきくけこ",
            no_speech_prob=0.05,
            compression_ratio=2.5,
        ),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 2
    assert results[0].text == "あいうえお"
    assert results[1].text == "かきくけこ"


def test_sanitizer_preserves_natural_intra_repetition() -> None:
    """自然な繰り返し (低無音確率かつ低圧縮率) が短縮されずに維持されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    segments: list[Any] = [
        SimpleNamespace(
            start=0.0,
            end=2.0,
            text="もしもしもしもし",
            no_speech_prob=0.05,
            compression_ratio=1.2,
        ),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 1
    assert results[0].text == "もしもしもしもし"


def test_sanitizer_drops_consecutive_loop_in_silence() -> None:
    """無音時における同一または部分一致テキストの連続ループが除外されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    segments: list[Any] = [
        SimpleNamespace(
            start=0.0, end=1.5, text="チャンネル登録お願いします", no_speech_prob=0.05
        ),
        SimpleNamespace(
            start=1.6, end=3.0, text="チャンネル登録お願いします", no_speech_prob=0.3
        ),
        SimpleNamespace(start=3.1, end=4.5, text="チャンネル登録", no_speech_prob=0.4),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 1
    assert results[0].text == "チャンネル登録お願いします"


def test_sanitizer_preserves_intentional_consecutive_repeat() -> None:
    """意図的な連続発言 (低無音確率) がループと誤認されず維持されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    segments: list[Any] = [
        SimpleNamespace(start=0.0, end=1.0, text="はい", no_speech_prob=0.05),
        SimpleNamespace(start=1.1, end=2.0, text="はい", no_speech_prob=0.05),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 2
    assert results[0].text == "はい"
    assert results[1].text == "はい"


def test_sanitizer_loop_no_speech_prob_exact_boundary() -> None:
    """直前と同一発話であっても no_speech_prob が 0.1 ちょうど（閾値以下）ならループ除外されないことを検証。"""
    # Arrange: no_speech_prob=0.10 (<= 0.1 なので除外されない)
    sanitizer = SegmentSanitizer()
    seg1 = SimpleNamespace(start=0.0, end=1.0, text="はい", no_speech_prob=0.05)
    seg2 = SimpleNamespace(start=1.1, end=2.0, text="はい", no_speech_prob=0.10)

    # Act
    res1 = sanitizer.sanitize_with_result(seg1)
    res2 = sanitizer.sanitize_with_result(seg2)

    # Assert
    assert res1.segment is not None
    assert res2.segment is not None
    assert res2.drop_reason is None
