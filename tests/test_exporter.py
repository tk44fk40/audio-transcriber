"""SubtitleExporter モジュールの単体テスト。"""

import json
from pathlib import Path

import pytest

from audio_transcriber.exporter import SubtitleExporter
from audio_transcriber.models import SubtitleSegment


def test_exporter_format_timestamp_srt() -> None:
    """SRT 形式のタイムスタンプ文字列 (HH:MM:SS,mmm) 生成を検証します。"""
    # Arrange & Act & Assert
    assert SubtitleExporter.format_timestamp(0.0) == "00:00:00,000"
    assert SubtitleExporter.format_timestamp(12.345) == "00:00:12,345"
    assert SubtitleExporter.format_timestamp(3661.5) == "01:01:01,500"
    assert SubtitleExporter.format_timestamp(-1.0) == "00:00:00,000"


def test_exporter_format_timestamp_vtt() -> None:
    """WebVTT 形式のタイムスタンプ文字列 (HH:MM:SS.mmm) 生成を検証します。"""
    # Arrange & Act & Assert
    assert SubtitleExporter.format_vtt_timestamp(0.0) == "00:00:00.000"
    assert SubtitleExporter.format_vtt_timestamp(12.345) == "00:00:12.345"
    assert SubtitleExporter.format_vtt_timestamp(3661.5) == "01:01:01.500"
    assert SubtitleExporter.format_vtt_timestamp(-1.0) == "00:00:00.000"


def test_exporter_format_timestamp_rounding_overflow() -> None:
    """ミリ秒の四捨五入による秒・分・時の繰り上がりを検証します。"""
    # Arrange & Act & Assert
    assert SubtitleExporter.format_timestamp(59.9999) == "00:01:00,000"
    assert SubtitleExporter.format_timestamp(3599.9999) == "01:00:00,000"
    assert SubtitleExporter.format_vtt_timestamp(59.9999) == "00:01:00.000"
    assert SubtitleExporter.format_vtt_timestamp(3599.9999) == "01:00:00.000"


def test_exporter_save_srt(tmp_path: Path) -> None:
    """SRT ファイルが DaVinci Resolve 準拠仕様で出力されることを検証します。"""
    # Arrange
    segments = [
        SubtitleSegment(start=1.0, end=3.5, text="こんにちは"),
        SubtitleSegment(start=4.0, end=6.2, text="さようなら"),
    ]
    out_file = tmp_path / "subtitles.srt"

    # Act
    SubtitleExporter.save_srt(segments, out_file)

    # Assert
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    expected = (
        "1\n00:00:01,000 --> 00:00:03,500\nこんにちは\n\n"
        "2\n00:00:04,000 --> 00:00:06,200\nさようなら\n"
    )
    assert content == expected


def test_exporter_save_vtt(tmp_path: Path) -> None:
    """WebVTT ファイルが仕様通りに出力されることを検証します。"""
    # Arrange
    segments = [
        SubtitleSegment(start=1.0, end=2.5, text="VTTテスト"),
    ]
    out_file = tmp_path / "subtitles.vtt"

    # Act
    SubtitleExporter.save_vtt(segments, out_file)

    # Assert
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    expected = "WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.500\nVTTテスト\n"
    assert content == expected


def test_exporter_save_json(tmp_path: Path) -> None:
    """JSON ファイルが整形されて正しく出力されることを検証します。"""
    # Arrange
    segments = [
        SubtitleSegment(start=1.0, end=2.0, text="JSONテスト"),
    ]
    out_file = tmp_path / "subtitles.json"

    # Act
    SubtitleExporter.save_json(segments, out_file)

    # Assert
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    data = json.loads(content)
    assert data == [{"start": 1.0, "end": 2.0, "text": "JSONテスト"}]


def test_exporter_empty_segments(tmp_path: Path) -> None:
    """空のセグメントリストが各フォーマットでエラーなく保存されることを検証します。"""
    # Arrange
    segments: list[SubtitleSegment] = []
    srt_file = tmp_path / "empty.srt"
    vtt_file = tmp_path / "empty.vtt"
    json_file = tmp_path / "empty.json"

    # Act
    SubtitleExporter.save_srt(segments, srt_file)
    SubtitleExporter.save_vtt(segments, vtt_file)
    SubtitleExporter.save_json(segments, json_file)

    # Assert
    assert srt_file.read_text(encoding="utf-8") == ""
    assert vtt_file.read_text(encoding="utf-8") == "WEBVTT\n"
    assert json.loads(json_file.read_text(encoding="utf-8")) == []


def test_exporter_save_subtitles_auto_detect(tmp_path: Path) -> None:
    """save_subtitles における拡張子 (大文字小文字含む) からの自動判定を検証します。"""
    # Arrange
    segments = [SubtitleSegment(start=0.0, end=1.0, text="自動判定")]
    srt_p = tmp_path / "test.SRT"
    vtt_p = tmp_path / "test.VTT"
    json_p = tmp_path / "test.JSON"

    # Act
    SubtitleExporter.save_subtitles(segments, srt_p)
    SubtitleExporter.save_subtitles(segments, vtt_p)
    SubtitleExporter.save_subtitles(segments, json_p)

    # Assert
    assert "00:00:00,000 --> 00:00:01,000" in srt_p.read_text(encoding="utf-8")
    assert "WEBVTT\n\n1\n00:00:00.000 --> 00:00:01.000" in vtt_p.read_text(
        encoding="utf-8"
    )
    assert json.loads(json_p.read_text(encoding="utf-8")) == [
        {"start": 0.0, "end": 1.0, "text": "自動判定"}
    ]


def test_exporter_save_subtitles_explicit_fmt(tmp_path: Path) -> None:
    """save_subtitles における明示的 fmt 指定を検証します。"""
    # Arrange
    segments = [SubtitleSegment(start=0.0, end=1.0, text="明示的指定")]
    custom_srt = tmp_path / "out1.custom"
    custom_vtt = tmp_path / "out2.custom"
    custom_json = tmp_path / "out3.custom"

    # Act
    SubtitleExporter.save_subtitles(segments, custom_srt, fmt="SRT")
    SubtitleExporter.save_subtitles(segments, custom_vtt, fmt="vtt")
    SubtitleExporter.save_subtitles(segments, custom_json, fmt="json")

    # Assert
    assert "00:00:00,000 --> 00:00:01,000" in custom_srt.read_text(encoding="utf-8")
    assert "WEBVTT" in custom_vtt.read_text(encoding="utf-8")
    assert json.loads(custom_json.read_text(encoding="utf-8")) == [
        {"start": 0.0, "end": 1.0, "text": "明示的指定"}
    ]


def test_exporter_unsupported_extension_and_format(tmp_path: Path) -> None:
    """未対応の拡張子および未対応の fmt で ValueError が発生することを検証します。"""
    # Arrange
    segments = [SubtitleSegment(start=0.0, end=1.0, text="エラーテスト")]

    # Act & Assert
    with pytest.raises(ValueError, match="未対応の拡張子です"):
        SubtitleExporter.save_subtitles(segments, tmp_path / "test.txt")

    with pytest.raises(ValueError, match="未対応のフォーマットです"):
        SubtitleExporter.save_subtitles(segments, tmp_path / "test.custom", fmt="xml")


def test_exporter_creates_parent_directories(tmp_path: Path) -> None:
    """存在しない親ディレクトリが自動的に作成されて保存されることを検証します。"""
    # Arrange
    segments = [SubtitleSegment(start=0.0, end=1.0, text="階層作成テスト")]
    deep_path = tmp_path / "nested" / "dir" / "out.srt"

    # Act
    SubtitleExporter.save_srt(segments, deep_path)

    # Assert
    assert deep_path.exists()
    assert "階層作成テスト" in deep_path.read_text(encoding="utf-8")
