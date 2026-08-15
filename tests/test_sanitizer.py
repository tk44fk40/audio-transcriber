"""SegmentSanitizer モジュールの単体テスト。"""

import logging
from types import SimpleNamespace
from typing import Any

import pytest

from audio_transcriber.models import SubtitleSegment
from audio_transcriber.sanitizer import SegmentSanitizer


def test_sanitizer_init_defaults() -> None:
    """SegmentSanitizer の初期設定デフォルト値を検証します。"""
    # Arrange & Act
    sanitizer = SegmentSanitizer()

    # Assert
    assert sanitizer.no_speech_threshold == 0.6
    assert sanitizer.max_chars_per_second == 12.0


def test_sanitizer_drops_high_no_speech_prob() -> None:
    """無音確率が閾値を超えるセグメントが無音捏造として除外されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer(no_speech_threshold=0.6)
    segments: list[Any] = [
        SimpleNamespace(start=0.0, end=2.0, text="正常発話", no_speech_prob=0.1),
        SimpleNamespace(start=2.5, end=4.0, text="無音捏造発話", no_speech_prob=0.8),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 1
    assert results[0].text == "正常発話"


def test_sanitizer_retains_low_no_speech_prob_boundary() -> None:
    """無音確率が閾値以下のセグメント (境界値含む) が保持されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer(no_speech_threshold=0.6)
    segments: list[Any] = [
        SimpleNamespace(start=0.0, end=2.0, text="境界値テスト", no_speech_prob=0.6),
        SimpleNamespace(start=2.0, end=4.0, text="正常テスト", no_speech_prob=0.3),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 2
    assert results[0].text == "境界値テスト"
    assert results[1].text == "正常テスト"


def test_sanitizer_drops_excessive_speech_rate() -> None:
    """物理的限界を超える異常発話速度 (12文字/秒超、4文字超) が除外されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer(max_chars_per_second=12.0)
    segments: list[Any] = [
        SimpleNamespace(start=0.0, end=2.0, text="こんにちは", no_speech_prob=0.05),
        SimpleNamespace(
            start=2.0, end=2.3, text="これは異常発話速度のテキスト", no_speech_prob=0.05
        ),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 1
    assert results[0].text == "こんにちは"


def test_sanitizer_protects_short_utterances() -> None:
    """4文字以下の短い相槌等が発話速度チェックから保護されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer(max_chars_per_second=12.0)
    segments: list[Any] = [
        SimpleNamespace(start=0.0, end=0.1, text="はい", no_speech_prob=0.05),
        SimpleNamespace(start=0.5, end=0.7, text="了解です", no_speech_prob=0.05),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 2
    assert results[0].text == "はい"
    assert results[1].text == "了解です"


def test_sanitizer_speech_rate_boundary_5_chars() -> None:
    """5文字の発話で速度上限を超過した場合に正しく除外されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer(max_chars_per_second=12.0)
    segments: list[Any] = [
        SimpleNamespace(start=0.0, end=0.2, text="あいうえお", no_speech_prob=0.05),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 0


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


def test_sanitizer_adjusts_start_time_from_words() -> None:
    """単語タイムスタンプが存在する場合、文頭単語の開始時刻に補正されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    words = [
        SimpleNamespace(start=0.35, end=1.0, word="文頭"),
        SimpleNamespace(start=1.0, end=2.0, word="単語テスト"),
    ]
    segments: list[Any] = [
        SimpleNamespace(
            start=0.0, end=2.0, text="文頭単語テスト", no_speech_prob=0.05, words=words
        ),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 1
    assert results[0].start == 0.35
    assert results[0].end == 2.0


def test_sanitizer_handles_dict_and_object_segments() -> None:
    """辞書形式およびオブジェクト形式のセグメントが同一に処理されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    segments: list[dict[str, Any]] = [
        {
            "start": 0.0,
            "end": 2.0,
            "text": "辞書セグメント",
            "no_speech_prob": 0.05,
            "words": [{"start": 0.15, "end": 1.9, "word": "辞書セグメント"}],
        }
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 1
    assert results[0].start == 0.15
    assert results[0].end == 1.9
    assert results[0].text == "辞書セグメント"


def test_sanitizer_ignores_empty_and_whitespace_segments() -> None:
    """空文字列や空白文字のみのセグメントが無視されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    segments: list[Any] = [
        SimpleNamespace(start=0.0, end=1.0, text="", no_speech_prob=0.05),
        SimpleNamespace(start=1.0, end=2.0, text="   \n\t  ", no_speech_prob=0.05),
        SimpleNamespace(start=2.0, end=3.0, text="有効セグメント", no_speech_prob=0.05),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 1
    assert results[0].text == "有効セグメント"


def test_sanitizer_get_word_time_helper() -> None:
    """get_word_time 静的メソッドの各入力形式 (dict, オブジェクト, 不正値) を検証します。"""
    # Arrange & Act & Assert
    assert SegmentSanitizer.get_word_time({"start": 1.5}, "start") == 1.5
    assert SegmentSanitizer.get_word_time(SimpleNamespace(end=4.0), "end") == 4.0
    assert SegmentSanitizer.get_word_time({"start": "invalid"}, "start") is None
    assert SegmentSanitizer.get_word_time(SimpleNamespace(start=None), "start") is None
    assert SegmentSanitizer.get_word_time("invalid_type", "start") is None


def test_sanitizer_logging(caplog: pytest.LogCaptureFixture) -> None:
    """進行状況ログ (total_duration あり・なし両方) の出力を検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    segments: list[Any] = [
        SimpleNamespace(start=0.0, end=2.0, text="テスト1", no_speech_prob=0.05)
    ]

    # Act & Assert with total_duration > 0
    with caplog.at_level(logging.INFO):
        sanitizer.sanitize_segments(segments, total_duration=10.0)
    assert "発言検出 [  2.0s /  10.0s ( 20%)] [0.00s -> 2.00s]: テスト1" in caplog.text

    # Act & Assert with total_duration == 0
    caplog.clear()
    with caplog.at_level(logging.INFO):
        sanitizer.sanitize_segments(segments, total_duration=0.0)
    assert "発言検出 [0.00s -> 2.00s]: テスト1" in caplog.text
