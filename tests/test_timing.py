"""SubtitleTimingAdjuster の単体テスト。"""

from audio_transcriber.models import SubtitleSegment
from audio_transcriber.timing import SubtitleTimingAdjuster


def _make_seg(start: float, end: float, text: str = "テスト") -> SubtitleSegment:
    return SubtitleSegment(start=start, end=end, text=text)


class TestSubtitleTimingAdjusterBasic:
    """基本的なタイミング補正テスト。"""

    def test_empty_returns_empty(self) -> None:
        """空リストを渡した場合は空リストが返ること。"""
        adjuster = SubtitleTimingAdjuster(
            end_padding=1.0, min_duration=1.5, min_gap=0.05
        )
        assert adjuster.adjust_segments([]) == []

    def test_end_padding_applied(self) -> None:
        """余韻パディングが終了時刻に加算されること。"""
        # Arrange
        adjuster = SubtitleTimingAdjuster(
            end_padding=1.0, min_duration=0.0, min_gap=0.0
        )
        seg = _make_seg(0.0, 2.0)
        # Act
        result = adjuster.adjust_segments([seg])
        # Assert
        assert result[0].end == 3.0

    def test_min_duration_enforced(self) -> None:
        """最小表示時間が確保されること。"""
        # Arrange
        adjuster = SubtitleTimingAdjuster(
            end_padding=0.0, min_duration=2.0, min_gap=0.0
        )
        seg = _make_seg(0.0, 0.5)  # duration = 0.5s < min_duration = 2.0s
        # Act
        result = adjuster.adjust_segments([seg])
        # Assert
        assert result[0].end >= 2.0

    def test_start_unchanged(self) -> None:
        """開始時刻は変更されないこと。"""
        adjuster = SubtitleTimingAdjuster(
            end_padding=1.0, min_duration=1.5, min_gap=0.05
        )
        seg = _make_seg(5.0, 7.0)
        result = adjuster.adjust_segments([seg])
        assert result[0].start == 5.0


class TestSubtitleTimingAdjusterOverlap:
    """隣接セグメントとの重複防止テスト。"""

    def test_no_overlap_with_next_segment(self) -> None:
        """余韻延長後も次セグメントと重複しないこと。"""
        # Arrange
        adjuster = SubtitleTimingAdjuster(
            end_padding=5.0, min_duration=0.0, min_gap=0.05
        )
        segs = [_make_seg(0.0, 1.0), _make_seg(2.0, 3.0)]
        # Act
        result = adjuster.adjust_segments(segs)
        # Assert: 1件目の end が 2件目の start - min_gap を超えないこと
        assert result[0].end <= 2.0 - 0.05 + 0.001  # 浮動小数点許容

    def test_total_duration_clamps_end(self) -> None:
        """total_duration を超えないよう終了時刻がクランプされること。"""
        adjuster = SubtitleTimingAdjuster(
            end_padding=10.0, min_duration=0.0, min_gap=0.0
        )
        seg = _make_seg(8.0, 9.0)
        result = adjuster.adjust_segments([seg], total_duration=10.0)
        assert result[0].end <= 10.0

    def test_end_never_before_start(self) -> None:
        """終了時刻が開始時刻より前にならないこと。"""
        adjuster = SubtitleTimingAdjuster(
            end_padding=0.0, min_duration=0.0, min_gap=100.0
        )
        segs = [_make_seg(0.0, 0.1), _make_seg(0.2, 0.3)]
        result = adjuster.adjust_segments(segs)
        assert result[0].end >= result[0].start
