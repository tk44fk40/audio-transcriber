"""SubtitleSegment データモデルの単体テスト。"""

from audio_transcriber.models import SubtitleSegment


def test_subtitle_segment_init() -> None:
    """SubtitleSegment の基本属性の初期化を検証します。"""
    # Arrange & Act
    seg = SubtitleSegment(start=1.234, end=5.678, text="こんにちは")

    # Assert
    assert seg.start == 1.234
    assert seg.end == 5.678
    assert seg.text == "こんにちは"


def test_subtitle_segment_equality() -> None:
    """SubtitleSegment の同値性判定を検証します。"""
    # Arrange
    seg1 = SubtitleSegment(start=1.0, end=2.0, text="テスト")
    seg2 = SubtitleSegment(start=1.0, end=2.0, text="テスト")
    seg3 = SubtitleSegment(start=1.0, end=2.0, text="別テキスト")
    seg4 = SubtitleSegment(start=1.5, end=2.0, text="テスト")

    # Act & Assert
    assert seg1 == seg2
    assert seg1 != seg3
    assert seg1 != seg4


def test_subtitle_segment_to_dict() -> None:
    """SubtitleSegment の to_dict による辞書変換を検証します。"""
    # Arrange
    seg = SubtitleSegment(start=1.5, end=4.0, text="こんにちは")

    # Act
    d = seg.to_dict()

    # Assert
    assert d == {"start": 1.5, "end": 4.0, "text": "こんにちは"}


def test_subtitle_segment_from_dict_standard() -> None:
    """from_dict による標準的な辞書からの復元を検証します。"""
    # Arrange
    data = {"start": 2.5, "end": 6.0, "text": "標準テスト"}

    # Act
    seg = SubtitleSegment.from_dict(data)

    # Assert
    assert seg.start == 2.5
    assert seg.end == 6.0
    assert seg.text == "標準テスト"


def test_subtitle_segment_from_dict_type_coercion() -> None:
    """from_dict における数値・文字列の型強制変換を検証します。"""
    # Arrange
    raw_data = {"start": 1, "end": "3.5", "text": 12345}

    # Act
    seg = SubtitleSegment.from_dict(raw_data)  # pyright: ignore[reportArgumentType]

    # Assert
    assert isinstance(seg.start, float)
    assert seg.start == 1.0
    assert isinstance(seg.end, float)
    assert seg.end == 3.5
    assert isinstance(seg.text, str)
    assert seg.text == "12345"


def test_subtitle_segment_from_dict_defaults() -> None:
    """from_dict におけるキー欠損時のデフォルトフォールバックを検証します。"""
    # Arrange
    empty_dict: dict[str, object] = {}
    partial_dict: dict[str, object] = {"text": "部分データ"}

    # Act
    seg_empty = SubtitleSegment.from_dict(empty_dict)
    seg_partial = SubtitleSegment.from_dict(partial_dict)

    # Assert
    assert seg_empty.start == 0.0
    assert seg_empty.end == 0.0
    assert seg_empty.text == ""

    assert seg_partial.start == 0.0
    assert seg_partial.end == 0.0
    assert seg_partial.text == "部分データ"


def test_subtitle_segment_roundtrip() -> None:
    """to_dict と from_dict の相互変換 (ラウンドトリップ) を検証します。"""
    # Arrange
    original = SubtitleSegment(start=10.123, end=20.456, text="ラウンドトリップテスト")

    # Act
    reconstructed = SubtitleSegment.from_dict(original.to_dict())

    # Assert
    assert reconstructed == original


def test_subtitle_segment_unicode_and_special_chars() -> None:
    """絵文字や改行、特殊文字を含むテキストの保持を検証します。"""
    # Arrange
    special_text = '🎉 特殊文字\n2行目 "ダブルクォート" & <tag>'
    seg = SubtitleSegment(start=0.0, end=1.0, text=special_text)

    # Act
    d = seg.to_dict()
    reconstructed = SubtitleSegment.from_dict(d)

    # Assert
    assert seg.text == special_text
    assert reconstructed.text == special_text
