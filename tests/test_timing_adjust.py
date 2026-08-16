"""SubtitleTimingAdjuster のパディング・最小表示時間・重複防止機能の単体テスト。"""

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


class TestSubtitleTimingAdjusterSingleSegment:
    """adjust_single_segment の単体テスト。"""

    def test_adjust_single_segment_without_next_start(self) -> None:
        """次発話がない場合、余韻パディングが適用され重複防止フラグが False であること。"""
        adjuster = SubtitleTimingAdjuster(
            end_padding=1.0, min_duration=0.0, min_gap=0.1
        )
        seg = _make_seg(1.0, 3.0)
        adj_seg, overlap_prevented, raw_target_end = adjuster.adjust_single_segment(
            seg=seg, next_start=None
        )
        assert adj_seg.start == 1.0
        assert adj_seg.end == 4.0
        assert not overlap_prevented
        assert raw_target_end == 4.0

    def test_adjust_single_segment_with_overlap(self) -> None:
        """次発話と重複する場合、重複防止フラグが True になり終了時刻が短縮されること。"""
        adjuster = SubtitleTimingAdjuster(
            end_padding=2.0, min_duration=0.0, min_gap=0.2
        )
        seg = _make_seg(1.0, 3.0)  # padding -> 5.0s
        adj_seg, overlap_prevented, raw_target_end = adjuster.adjust_single_segment(
            seg=seg, next_start=4.0
        )
        # next_start(4.0) - min_gap(0.2) = 3.8s
        assert adj_seg.start == 1.0
        assert adj_seg.end == 3.8
        assert overlap_prevented
        assert raw_target_end == 5.0

    def test_adjust_single_segment_next_start_before_min_gap(self) -> None:
        """次発話が極端に近い場合、next_start までにクランプされること。"""
        adjuster = SubtitleTimingAdjuster(
            end_padding=1.0, min_duration=0.0, min_gap=5.0
        )
        seg = _make_seg(1.0, 3.0)
        adj_seg, overlap_prevented, raw_target_end = adjuster.adjust_single_segment(
            seg=seg, next_start=3.5
        )
        assert adj_seg.end == 3.5
        assert overlap_prevented
        assert raw_target_end == 4.0

    def test_adjust_single_segment_total_duration(self) -> None:
        """total_duration を超えないこと。"""
        adjuster = SubtitleTimingAdjuster(
            end_padding=5.0, min_duration=0.0, min_gap=0.1
        )
        seg = _make_seg(1.0, 4.0)
        adj_seg, _, _ = adjuster.adjust_single_segment(
            seg=seg, next_start=None, total_duration=5.0
        )
        assert adj_seg.end == 5.0

    def test_adjust_single_segment_gap_exact_boundary(self) -> None:
        """余韻後の終了時刻が next_start - min_gap と完全に一致する場合、重複短縮扱いにならないことを検証。"""
        # Arrange: target_end = 3.0 + 1.0 = 4.0, next_start = 4.1, min_gap = 0.1
        # max_allowed_end = 4.1 - 0.1 = 4.0 (target_end と完全に一致)
        adjuster = SubtitleTimingAdjuster(
            end_padding=1.0, min_duration=0.0, min_gap=0.1
        )
        seg = _make_seg(1.0, 3.0)

        # Act
        adj_seg, overlap_prevented, raw_target_end = adjuster.adjust_single_segment(
            seg=seg, next_start=4.1
        )

        # Assert
        assert adj_seg.end == 4.0
        assert not overlap_prevented
        assert raw_target_end == 4.0

    def test_adjust_single_segment_min_duration_conflicts_with_next_start(self) -> None:
        """min_duration による延長と次発話重複が競合した場合、重複防止が確実に優先されることを検証。"""
        # Arrange: min_duration = 3.0 -> raw_target_end = 1.0 + 3.0 = 4.0
        # next_start = 2.5, min_gap = 0.1 -> max_allowed_end = 2.4
        adjuster = SubtitleTimingAdjuster(
            end_padding=0.0, min_duration=3.0, min_gap=0.1
        )
        seg = _make_seg(1.0, 1.5)

        # Act
        adj_seg, overlap_prevented, raw_target_end = adjuster.adjust_single_segment(
            seg=seg, next_start=2.5
        )

        # Assert: min_duration(4.0) よりも重複防止(2.4) が優先される
        assert adj_seg.end == 2.4
        assert overlap_prevented
        assert raw_target_end == 4.0
