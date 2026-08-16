"""SanitizeResult および DropReason の判定・取得機能の単体テスト。"""

from types import SimpleNamespace

from audio_transcriber.sanitizer import DropReason, SanitizeResult, SegmentSanitizer


def test_sanitizer_result_success() -> None:
    """正常な発話セグメントが DropReason なしで取得されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    segment = SimpleNamespace(
        start=1.0, end=3.0, text="こんにちは世界", no_speech_prob=0.05
    )

    # Act
    result: SanitizeResult = sanitizer.sanitize_with_result(segment)

    # Assert
    assert result.segment is not None
    assert result.segment.text == "こんにちは世界"
    assert result.segment.start == 1.0
    assert result.segment.end == 3.0
    assert result.drop_reason is None
    assert result.drop_detail is None
    assert result.repeat_shortened is False
    assert result.original_text == "こんにちは世界"
    assert result.cleaned_text == "こんにちは世界"


def test_sanitizer_result_drop_empty() -> None:
    """空文字列セグメントが DropReason.EMPTY として判定されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    seg_empty = SimpleNamespace(start=0.0, end=1.0, text="", no_speech_prob=0.0)
    seg_spaces = SimpleNamespace(
        start=1.0, end=2.0, text="   \t\n  ", no_speech_prob=0.0
    )

    # Act
    res_empty = sanitizer.sanitize_with_result(seg_empty)
    res_spaces = sanitizer.sanitize_with_result(seg_spaces)

    # Assert
    assert res_empty.segment is None
    assert res_empty.drop_reason == DropReason.EMPTY
    assert res_spaces.segment is None
    assert res_spaces.drop_reason == DropReason.EMPTY


def test_sanitizer_result_drop_no_speech() -> None:
    """無音確率超過セグメントが DropReason.NO_SPEECH として判定されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer(no_speech_threshold=0.6)
    seg = SimpleNamespace(
        start=0.0, end=2.0, text="無音捏造テキスト", no_speech_prob=0.85
    )

    # Act
    res = sanitizer.sanitize_with_result(seg)

    # Assert
    assert res.segment is None
    assert res.drop_reason == DropReason.NO_SPEECH
    assert "0.85" in (res.drop_detail or "")


def test_sanitizer_result_drop_speed() -> None:
    """発話速度超過セグメントが DropReason.SPEED として判定されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer(max_chars_per_second=10.0)
    # 0.2秒に12文字 -> 60文字/秒
    seg = SimpleNamespace(
        start=0.0, end=0.2, text="超高速捏造テキストです", no_speech_prob=0.05
    )

    # Act
    res = sanitizer.sanitize_with_result(seg)

    # Assert
    assert res.segment is None
    assert res.drop_reason == DropReason.SPEED
    assert "chars/s" in (res.drop_detail or "") or "文字/秒" in (res.drop_detail or "")


def test_sanitizer_result_drop_loop() -> None:
    """ループ重複セグメントが DropReason.LOOP として判定されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    seg1 = SimpleNamespace(
        start=0.0, end=1.5, text="チャンネル登録", no_speech_prob=0.05
    )
    seg2 = SimpleNamespace(
        start=1.6, end=3.0, text="チャンネル登録", no_speech_prob=0.3
    )

    # Act
    res1 = sanitizer.sanitize_with_result(seg1)
    res2 = sanitizer.sanitize_with_result(seg2)

    # Assert
    assert res1.segment is not None
    assert res2.segment is None
    assert res2.drop_reason == DropReason.LOOP


def test_sanitizer_result_repeat_shortened() -> None:
    """リピート短縮されたセグメントで repeat_shortened が True になることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    seg = SimpleNamespace(
        start=0.0,
        end=2.0,
        text="テストテスト",
        no_speech_prob=0.2,
        compression_ratio=1.5,
    )

    # Act
    res = sanitizer.sanitize_with_result(seg)

    # Assert
    assert res.segment is not None
    assert res.repeat_shortened is True
    assert res.original_text == "テストテスト"
    assert res.cleaned_text == "テスト"
    assert res.segment.text == "テスト"
