"""SegmentSanitizer (サニタイザー) の E2E・単体テストモジュール。

Features 2-6 (無音/ハルシネーション除外、発話速度制限、セグメント内リピート短縮、
ループ重複除外、単語タイムスタンプ補正) に対する Tier 1 & Tier 2 要件駆動テスト。
"""

from dataclasses import dataclass
from typing import Any

import pytest

from audio_transcriber.sanitizer import SegmentSanitizer


@dataclass
class MockWhisperSegment:
    """Whisper 認識結果セグメントのモックデータクラス。"""

    start: float
    end: float
    text: str
    no_speech_prob: float = 0.0
    compression_ratio: float = 1.0
    words: list[Any] | None = None


@pytest.mark.e2e
def test_sanitizer_drops_segments_above_no_speech_threshold() -> None:
    """無音確率が閾値 (0.6) を超えるハルシネーションセグメントの除外テスト (Tier 1)。"""
    # Arrange
    sanitizer = SegmentSanitizer(no_speech_threshold=0.6)
    segments = [
        MockWhisperSegment(start=0.0, end=2.0, text="有効な発話", no_speech_prob=0.1),
        MockWhisperSegment(
            start=2.5, end=4.0, text="無音捏造テキスト", no_speech_prob=0.85
        ),
    ]

    # Act
    cleaned = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(cleaned) == 1
    assert cleaned[0].text == "有効な発話"


@pytest.mark.e2e
def test_sanitizer_drops_excessive_speech_rate() -> None:
    """物理的発話速度 (12.0文字/秒) を超える捏造セグメントの除外テスト (Tier 1)。"""
    # Arrange
    sanitizer = SegmentSanitizer(max_chars_per_second=12.0)
    segments = [
        MockWhisperSegment(
            start=0.0, end=2.0, text="通常の速度の発話です", no_speech_prob=0.0
        ),
        MockWhisperSegment(
            start=2.0,
            end=2.2,
            text="極端に短い時間で長文が詰め込まれたハルシネーション",
            no_speech_prob=0.0,
        ),
    ]

    # Act
    cleaned = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(cleaned) == 1
    assert cleaned[0].text == "通常の速度の発話です"


@pytest.mark.e2e
def test_sanitizer_intra_segment_repetition_reduction() -> None:
    """低信頼度時にセグメント内の2等分リピートを検出し半分に短縮するテスト (Tier 1)。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    segments = [
        MockWhisperSegment(
            start=0.0,
            end=3.0,
            text="あいうえおあいうえお",
            no_speech_prob=0.2,
            compression_ratio=2.5,
        )
    ]

    # Act
    cleaned = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(cleaned) == 1
    assert cleaned[0].text == "あいうえお"


@pytest.mark.e2e
def test_sanitizer_inter_segment_loop_repeat_drop() -> None:
    """無音区間で発生する直前セグメントと同一または包含されるループの除外テスト (Tier 1)。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    phrase = "ご視聴ありがとうございました"
    segments = [
        MockWhisperSegment(start=0.0, end=2.0, text=phrase, no_speech_prob=0.0),
        MockWhisperSegment(start=2.5, end=4.0, text=phrase, no_speech_prob=0.3),
        MockWhisperSegment(
            start=4.5, end=6.0, text="ありがとうございました", no_speech_prob=0.25
        ),
    ]

    # Act
    cleaned = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(cleaned) == 1
    assert cleaned[0].text == "ご視聴ありがとうございました"


@pytest.mark.e2e
def test_sanitizer_word_timestamp_alignment() -> None:
    """単語タイムスタンプが存在する場合、先頭単語の開始位置へ補正するテスト (Tier 1)。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    segments = [
        MockWhisperSegment(
            start=1.0,
            end=3.0,
            text="単語開始補正",
            words=[
                {"start": 1.45, "end": 2.0, "word": "単語"},
                {"start": 2.1, "end": 2.8, "word": "開始補正"},
            ],
        )
    ]

    # Act
    cleaned = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(cleaned) == 1
    assert cleaned[0].start == 1.45
    assert cleaned[0].end == 3.0


@pytest.mark.e2e
def test_sanitizer_boundary_threshold_conditions() -> None:
    """境界値 (閾値と同一値、短文保護 len<=4) の挙動テスト (Tier 2)。"""
    # Arrange
    sanitizer = SegmentSanitizer(no_speech_threshold=0.6, max_chars_per_second=12.0)
    segments = [
        # no_speech_prob == 0.6 は通過 (厳密な > 判定)
        MockWhisperSegment(start=0.0, end=1.0, text="境界判定1", no_speech_prob=0.6),
        # 4文字以下は速度制限の除外対象 (保護される)
        MockWhisperSegment(start=1.0, end=1.1, text="はい!", no_speech_prob=0.0),
        # 5文字以上かつ 12.0 c/s 超はドロップ
        MockWhisperSegment(start=2.0, end=2.2, text="あいうえお", no_speech_prob=0.0),
    ]

    # Act
    cleaned = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(cleaned) == 2
    assert cleaned[0].text == "境界判定1"
    assert cleaned[1].text == "はい!"


@pytest.mark.e2e
def test_sanitizer_intra_repeat_confidence_preservation() -> None:
    """高信頼度 (自然な繰り返し) 時はセグメント内リピートを保持するテスト (Tier 2)。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    segments = [
        MockWhisperSegment(
            start=0.0,
            end=2.0,
            text="はいはい",
            no_speech_prob=0.01,
            compression_ratio=1.0,
        ),
        MockWhisperSegment(
            start=2.5,
            end=4.5,
            text="あいうあい",  # 奇数長 (len=5) -> 分割対象外
            no_speech_prob=0.8,
            compression_ratio=3.0,
        ),
    ]

    # Act
    cleaned = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(cleaned) == 1
    assert cleaned[0].text == "はいはい"


@pytest.mark.e2e
def test_sanitizer_empty_and_whitespace_inputs() -> None:
    """空文字列・空白のみセグメントおよび空リストの安全な処理テスト (Tier 2)。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    segments = [
        MockWhisperSegment(start=0.0, end=1.0, text="   "),
        MockWhisperSegment(start=1.0, end=2.0, text="\n\t"),
        MockWhisperSegment(start=2.0, end=3.0, text=""),
    ]

    # Act
    res1 = sanitizer.sanitize_segments(segments)
    res2 = sanitizer.sanitize_segments([])

    # Assert
    assert res1 == []
    assert res2 == []


@pytest.mark.e2e
def test_sanitizer_zero_duration_and_word_structure_variants() -> None:
    """duration 0.0s のゼロ除算保護と単語オブジェクト構造の柔軟性テスト (Tier 2)。"""
    # Arrange

    class DummyWord:
        def __init__(self, start: float) -> None:
            self.start = start

    sanitizer = SegmentSanitizer()
    segments = [
        # start == end (0除算防止 duration=0.1) かつ文字数<=4で保護
        MockWhisperSegment(
            start=1.0, end=1.0, text="よし", words=[DummyWord(start=1.05)]
        ),
        # words に start 属性がない場合は元の start を利用
        MockWhisperSegment(
            start=2.0, end=3.0, text="通常発話", words=[{"invalid_key": 99}]
        ),
    ]

    # Act
    cleaned = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(cleaned) == 2
    assert cleaned[0].start == 1.05
    assert cleaned[1].start == 2.0


@pytest.mark.e2e
def test_sanitizer_custom_configuration() -> None:
    """カスタム閾値設定 (0.85, 20.0 c/s) の反映テスト (Tier 2)。"""
    # Arrange
    sanitizer = SegmentSanitizer(no_speech_threshold=0.85, max_chars_per_second=20.0)
    segments = [
        # no_speech_prob=0.8 (0.85未満のため保持)
        MockWhisperSegment(start=0.0, end=2.0, text="許容無音発話", no_speech_prob=0.8),
        # 15文字/秒 (20.0文字/秒未満のため保持)
        MockWhisperSegment(
            start=2.0, end=3.0, text="123456789012345", no_speech_prob=0.0
        ),
    ]

    # Act
    cleaned = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(cleaned) == 2
    assert cleaned[0].text == "許容無音発話"
    assert cleaned[1].text == "123456789012345"
