"""SubtitleTimingAdjuster (字幕タイミング補正) の E2E・単体テストモジュール。

Features 14-17 (余韻パディング、最小表示時間、重複防止ギャップ制御、
総再生時間クリッピング) に対する Tier 1 & Tier 2 要件駆動テスト。
"""

import pytest

from audio_transcriber.models import SubtitleSegment
from audio_transcriber.timing import SubtitleTimingAdjuster


@pytest.mark.e2e
def test_timing_adjuster_trailing_padding() -> None:
    """発話終了後の余韻パディング (+1.0秒) 付与のテスト (Tier 1)。"""
    # Arrange
    adjuster = SubtitleTimingAdjuster(end_padding=1.0, min_duration=0.0, min_gap=0.05)
    segments = [SubtitleSegment(start=1.0, end=3.0, text="余韻テスト")]

    # Act
    adjusted = adjuster.adjust_segments(segments)

    # Assert
    assert len(adjusted) == 1
    assert adjusted[0].start == 1.0
    assert adjusted[0].end == 4.0


@pytest.mark.e2e
def test_timing_adjuster_min_duration_enforcement() -> None:
    """短い発言に対する最小表示時間 (1.5秒) の確保テスト (Tier 1)。"""
    # Arrange
    adjuster = SubtitleTimingAdjuster(end_padding=0.1, min_duration=1.5, min_gap=0.05)
    # duration=0.2s -> padded=1.3s -> min_duration=1.0+1.5=2.5s
    segments = [SubtitleSegment(start=1.0, end=1.2, text="短い")]

    # Act
    adjusted = adjuster.adjust_segments(segments)

    # Assert
    assert len(adjusted) == 1
    assert adjusted[0].start == 1.0
    assert adjusted[0].end == 2.5


@pytest.mark.e2e
def test_timing_adjuster_overlap_clipping_with_min_gap() -> None:
    """次セグメントとの重複を防止する min_gap (0.05秒) 隙間クリッピングテスト (Tier 1)。"""
    # Arrange
    adjuster = SubtitleTimingAdjuster(end_padding=1.0, min_duration=1.5, min_gap=0.05)
    # target_end=4.0 -> clipped to 3.5 - 0.05 = 3.45
    segments = [
        SubtitleSegment(start=1.0, end=3.0, text="発言1"),
        SubtitleSegment(start=3.5, end=5.0, text="発言2"),
    ]

    # Act
    adjusted = adjuster.adjust_segments(segments)

    # Assert
    assert len(adjusted) == 2
    assert adjusted[0].end == 3.45
    assert adjusted[1].end == 6.0


@pytest.mark.e2e
def test_timing_adjuster_total_duration_clamping() -> None:
    """メディアの総再生時間 (total_duration) による字幕終了時刻の制限テスト (Tier 1)。"""
    # Arrange
    adjuster = SubtitleTimingAdjuster(end_padding=2.0, min_duration=1.5, min_gap=0.05)
    segments = [SubtitleSegment(start=8.0, end=9.5, text="最終発話")]

    # Act
    adjusted = adjuster.adjust_segments(segments, total_duration=10.0)

    # Assert
    assert len(adjusted) == 1
    assert adjusted[0].end == 10.0


@pytest.mark.e2e
def test_timing_adjuster_multiple_sequential_segments() -> None:
    """複数セグメントの連続調整と順序整合性のテスト (Tier 1)。"""
    # Arrange
    adjuster = SubtitleTimingAdjuster(end_padding=1.0, min_duration=1.5, min_gap=0.05)
    # 0.0 -> max(2.0, 1.5) = 2.0 -> clipped to 1.95
    # 2.0 -> max(3.2, 3.5) = 3.5 -> clipped to 3.95
    # 4.0 -> max(6.0, 5.5) = 6.0
    segments = [
        SubtitleSegment(start=0.0, end=1.0, text="第1文"),
        SubtitleSegment(start=2.0, end=2.2, text="第2文"),
        SubtitleSegment(start=4.0, end=5.0, text="第3文"),
    ]

    # Act
    adjusted = adjuster.adjust_segments(segments)

    # Assert
    assert len(adjusted) == 3
    assert adjusted[0].end == 1.95
    assert adjusted[1].end == 3.5
    assert adjusted[2].end == 6.0


@pytest.mark.e2e
def test_timing_adjuster_dense_adjacent_segments() -> None:
    """セグメント間隔が min_gap より狭い場合の安全なフォールバックテスト (Tier 2)。"""
    # Arrange
    adjuster = SubtitleTimingAdjuster(end_padding=1.0, min_duration=1.5, min_gap=0.05)
    # seg1 と seg2 の間隔が 0.01秒しかない場合の検証
    segments = [
        SubtitleSegment(start=2.0, end=2.01, text="密集発言1"),
        SubtitleSegment(start=2.02, end=3.0, text="密集発言2"),
    ]

    # Act
    adjusted = adjuster.adjust_segments(segments)

    # Assert
    assert len(adjusted) == 2
    # seg1.start (2.0) <= seg1.end <= next_start (2.02)
    assert adjusted[0].start <= adjusted[0].end
    assert adjusted[0].end <= 2.02


@pytest.mark.e2e
def test_timing_adjuster_total_duration_smaller_than_start() -> None:
    """total_duration が開始時刻より小さい異常入力時の start <= end 下限保証テスト (Tier 2)。"""
    # Arrange
    adjuster = SubtitleTimingAdjuster(end_padding=1.0, min_duration=1.5, min_gap=0.05)
    segments = [SubtitleSegment(start=5.0, end=6.0, text="境界発言")]

    # Act
    adjusted = adjuster.adjust_segments(segments, total_duration=4.0)

    # Assert
    assert len(adjusted) == 1
    assert adjusted[0].start == 5.0
    assert adjusted[0].end == 5.0  # max(seg.start, target_end) により 5.0 を下回らない


@pytest.mark.e2e
def test_timing_adjuster_empty_segments_input() -> None:
    """空のセグメントリスト渡却時の挙動テスト (Tier 2)。"""
    # Arrange
    adjuster = SubtitleTimingAdjuster(end_padding=1.0, min_duration=1.5, min_gap=0.05)

    # Act
    adjusted = adjuster.adjust_segments([])

    # Assert
    assert adjusted == []


@pytest.mark.e2e
def test_timing_adjuster_rounding_precision() -> None:
    """ミリ秒単位の丸め (round(..., 3)) の精度テスト (Tier 2)。"""
    # Arrange
    adjuster = SubtitleTimingAdjuster(
        end_padding=0.333333, min_duration=1.111111, min_gap=0.05
    )
    segments = [SubtitleSegment(start=1.123456, end=2.234567, text="精度確認")]

    # Act
    adjusted = adjuster.adjust_segments(segments)

    # Assert
    assert len(adjusted) == 1
    assert adjusted[0].start == 1.123
    # 2.234567 + 0.333333 = 2.5679 -> round to 3 places -> 2.568
    assert adjusted[0].end == 2.568
