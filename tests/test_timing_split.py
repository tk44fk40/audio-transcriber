"""単語間ギャップに基づくセグメント分割 (split_segments_by_word_gap) の単体テスト。"""

from typing import Any

from audio_transcriber.timing import split_segments_by_word_gap


def test_split_segments_by_word_gap_no_words() -> None:
    """単語リストが存在しない場合、オフセットのみ加算されて単一セグメントが返ることを検証。"""
    # Arrange
    seg: dict[str, Any] = {
        "start": 1.0,
        "end": 3.0,
        "text": "単語情報なし",
    }

    # Act
    results = split_segments_by_word_gap(seg, timecode_offset=10.0, gap_threshold=1.0)

    # Assert
    assert len(results) == 1
    assert results[0]["start"] == 11.0
    assert results[0]["end"] == 13.0
    assert results[0]["text"] == "単語情報なし"


def test_split_segments_by_word_gap_continuous_speech() -> None:
    """単語間ギャップが閾値未満の場合は分割されず単一セグメントとして返ることを検証。"""
    # Arrange
    seg: dict[str, Any] = {
        "start": 0.0,
        "end": 2.0,
        "text": "こんにちは世界",
        "words": [
            {"start": 0.0, "end": 0.8, "word": "こんにちは"},
            {"start": 0.9, "end": 2.0, "word": "世界"},
        ],
    }

    # Act
    results = split_segments_by_word_gap(seg, timecode_offset=5.0, gap_threshold=0.5)

    # Assert
    assert len(results) == 1
    assert results[0]["start"] == 5.0
    assert results[0]["end"] == 7.0
    assert results[0]["text"] == "こんにちは世界"


def test_split_segments_by_word_gap_splits_on_large_gap() -> None:
    """単語間ギャップが閾値以上の場合にセグメントが正しく複数に分割されることを検証。"""
    # Arrange
    seg: dict[str, Any] = {
        "start": 0.0,
        "end": 6.0,
        "text": "前半発言 後半発言",
        "words": [
            {"start": 0.0, "end": 1.0, "word": "前半発言"},
            {"start": 3.5, "end": 5.0, "word": "後半発言"},
        ],
    }

    # Act: gap = 3.5 - 1.0 = 2.5s >= gap_threshold (2.0s)
    results = split_segments_by_word_gap(seg, timecode_offset=2.0, gap_threshold=2.0)

    # Assert
    assert len(results) == 2
    assert results[0]["start"] == 2.0
    assert results[0]["end"] == 3.0
    assert results[0]["text"] == "前半発言"
    assert results[1]["start"] == 5.5
    assert results[1]["end"] == 7.0
    assert results[1]["text"] == "後半発言"


def test_split_segments_by_word_gap_three_chunks() -> None:
    """3つ以上のチャンクに分割されるケースを検証。"""
    # Arrange
    seg: dict[str, Any] = {
        "start": 0.0,
        "end": 10.0,
        "text": "1 2 3",
        "words": [
            {"start": 0.0, "end": 1.0, "word": "1"},
            {"start": 3.0, "end": 4.0, "word": "2"},
            {"start": 7.0, "end": 8.0, "word": "3"},
        ],
    }

    # Act
    results = split_segments_by_word_gap(seg, timecode_offset=0.0, gap_threshold=1.5)

    # Assert
    assert len(results) == 3
    assert results[0]["text"] == "1"
    assert results[1]["text"] == "2"
    assert results[2]["text"] == "3"
