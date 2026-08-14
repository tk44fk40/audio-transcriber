"""SubtitleSegment データモデルの E2E・単体テストモジュール。

Feature 1 (SubtitleSegment Data Model) に対する Tier 1 (基本機能)
および Tier 2 (境界値・異常系) の要件駆動テストを検証します。
"""

from typing import Any

import pytest

from audio_transcriber.models import SubtitleSegment


@pytest.mark.e2e
def test_subtitle_segment_instantiation() -> None:
    """SubtitleSegment の直接インスタンス化とプロパティアクセスのテスト (Tier 1)。"""
    # Arrange & Act
    seg = SubtitleSegment(start=1.234, end=5.678, text="テスト字幕")

    # Assert
    assert seg.start == 1.234
    assert seg.end == 5.678
    assert seg.text == "テスト字幕"


@pytest.mark.e2e
def test_subtitle_segment_to_dict() -> None:
    """SubtitleSegment から辞書型へのシリアライズ (to_dict) のテスト (Tier 1)。"""
    # Arrange
    seg = SubtitleSegment(start=0.5, end=2.0, text="音声認識結果")

    # Act
    data = seg.to_dict()

    # Assert
    expected: dict[str, Any] = {"start": 0.5, "end": 2.0, "text": "音声認識結果"}
    assert data == expected


@pytest.mark.e2e
def test_subtitle_segment_from_dict_standard() -> None:
    """標準的な辞書型データからの SubtitleSegment 構築 (from_dict) のテスト (Tier 1)。"""
    # Arrange
    data: dict[str, Any] = {"start": 10.0, "end": 15.5, "text": "こんにちは世界"}

    # Act
    seg = SubtitleSegment.from_dict(data)

    # Assert
    assert seg.start == 10.0
    assert seg.end == 15.5
    assert seg.text == "こんにちは世界"


@pytest.mark.e2e
def test_subtitle_segment_roundtrip_serialization() -> None:
    """to_dict と from_dict によるシリアライズ・デシリアライズ往復整合性のテスト (Tier 1)。"""
    # Arrange
    original = SubtitleSegment(start=123.456, end=130.789, text="往復テスト")

    # Act
    serialized = original.to_dict()
    reconstructed = SubtitleSegment.from_dict(serialized)

    # Assert
    assert reconstructed.start == original.start
    assert reconstructed.end == original.end
    assert reconstructed.text == original.text
    assert reconstructed == original


@pytest.mark.e2e
def test_subtitle_segment_numeric_string_coercion() -> None:
    """from_dict における文字列型数値や整数値の float 型強制変換のテスト (Tier 1)。"""
    # Arrange
    data: dict[str, Any] = {"start": "12.5", "end": 20, "text": 12345}

    # Act
    seg = SubtitleSegment.from_dict(data)

    # Assert
    assert isinstance(seg.start, float)
    assert isinstance(seg.end, float)
    assert isinstance(seg.text, str)
    assert seg.start == 12.5
    assert seg.end == 20.0
    assert seg.text == "12345"


@pytest.mark.e2e
def test_subtitle_segment_from_dict_empty() -> None:
    """空辞書渡却時のデフォルトフォールバック動作のテスト (Tier 2)。"""
    # Arrange
    data: dict[str, Any] = {}

    # Act
    seg = SubtitleSegment.from_dict(data)

    # Assert
    assert seg.start == 0.0
    assert seg.end == 0.0
    assert seg.text == ""


@pytest.mark.e2e
def test_subtitle_segment_from_dict_partial_missing_keys() -> None:
    """辞書キーが一部欠落している場合の安全な構築テスト (Tier 2)。"""
    # Arrange
    data: dict[str, Any] = {"text": "テキストのみ"}

    # Act
    seg = SubtitleSegment.from_dict(data)

    # Assert
    assert seg.start == 0.0
    assert seg.end == 0.0
    assert seg.text == "テキストのみ"


@pytest.mark.e2e
def test_subtitle_segment_from_dict_none_or_extra_keys() -> None:
    """未定義の拡張キーが含まれる場合の透過的無視テスト (Tier 2)。"""
    # Arrange
    data: dict[str, Any] = {
        "start": 1.0,
        "end": 2.0,
        "text": "拡張データ",
        "extra_info": "ignore_me",
        "confidence": 0.99,
    }

    # Act
    seg = SubtitleSegment.from_dict(data)

    # Assert
    assert seg.start == 1.0
    assert seg.end == 2.0
    assert seg.text == "拡張データ"


@pytest.mark.e2e
def test_subtitle_segment_boundary_timestamps() -> None:
    """ゼロ秒、極小秒数、負値、および大容量タイムスタンプの許容テスト (Tier 2)。"""
    # Arrange & Act
    zero_seg = SubtitleSegment(start=0.0, end=0.0, text="")
    micro_seg = SubtitleSegment(start=0.0001, end=0.0002, text="微小時間")
    large_seg = SubtitleSegment(start=86400.0, end=90000.0, text="24時間超")

    # Assert
    assert zero_seg.start == 0.0 and zero_seg.end == 0.0
    assert micro_seg.start == 0.0001 and micro_seg.end == 0.0002
    assert large_seg.start == 86400.0 and large_seg.end == 90000.0


@pytest.mark.e2e
def test_subtitle_segment_unicode_and_multiline_text() -> None:
    """絵文字・特殊記号・改行を含む Unicode テキストのデータ保持テスト (Tier 2)。"""
    # Arrange
    complex_text = "🎉 特殊文字: © & <tag> \n 複数行テキスト 💡"
    seg = SubtitleSegment(start=5.0, end=8.0, text=complex_text)

    # Act
    dumped = seg.to_dict()
    restored = SubtitleSegment.from_dict(dumped)

    # Assert
    assert restored.text == complex_text
    assert "🎉" in restored.text
    assert "\n" in restored.text
