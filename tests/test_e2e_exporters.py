"""SubtitleExporter (字幕エクスポート) の E2E・単体テストモジュール。

Features 7-9 (DaVinci Resolve SRT 出力、WebVTT 出力、JSON エクスポート、
自動拡張子ディスパッチ) に対する Tier 1 & Tier 2 要件駆動テスト。
"""

import json
from pathlib import Path

import pytest

from audio_transcriber.exporter import SubtitleExporter
from audio_transcriber.models import SubtitleSegment


@pytest.mark.e2e
def test_exporter_save_srt_davinci_compliance(tmp_path: Path) -> None:
    """DaVinci Resolve 準拠の SRT ファイル (カンマミリ秒、1起番、UTF-8) 出力テスト (Tier 1)。"""
    # Arrange
    srt_path = tmp_path / "output.srt"
    segments = [
        SubtitleSegment(start=0.0, end=2.5, text="こんにちは"),
        SubtitleSegment(start=3.123, end=5.678, text="DaVinci Resolve 互換テスト"),
    ]

    # Act
    SubtitleExporter.save_srt(segments, srt_path)

    # Assert
    assert srt_path.exists()
    content = srt_path.read_text(encoding="utf-8")
    assert "1\n00:00:00,000 --> 00:00:02,500\nこんにちは" in content
    assert "2\n00:00:03,123 --> 00:00:05,678\nDaVinci Resolve 互換テスト" in content


@pytest.mark.e2e
def test_exporter_save_vtt_format_compliance(tmp_path: Path) -> None:
    """WebVTT 規格 (WEBVTT ヘッダー、ドットミリ秒、UTF-8) 出力テスト (Tier 1)。"""
    # Arrange
    vtt_path = tmp_path / "output.vtt"
    segments = [
        SubtitleSegment(start=1.5, end=3.75, text="WebVTT 字幕テスト"),
    ]

    # Act
    SubtitleExporter.save_vtt(segments, vtt_path)

    # Assert
    assert vtt_path.exists()
    content = vtt_path.read_text(encoding="utf-8")
    assert content.startswith("WEBVTT")
    assert "00:00:01.500 --> 00:00:03.750" in content
    assert "WebVTT 字幕テスト" in content


@pytest.mark.e2e
def test_exporter_save_json_structure(tmp_path: Path) -> None:
    """構造化 JSON 字幕 (indent=2, ensure_ascii=False) 出力テスト (Tier 1)。"""
    # Arrange
    json_path = tmp_path / "output.json"
    segments = [
        SubtitleSegment(start=0.0, end=1.0, text="JSON 1"),
        SubtitleSegment(start=1.5, end=2.5, text="JSON 2"),
    ]

    # Act
    SubtitleExporter.save_json(segments, json_path)

    # Assert
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0] == {"start": 0.0, "end": 1.0, "text": "JSON 1"}
    assert data[1] == {"start": 1.5, "end": 2.5, "text": "JSON 2"}


@pytest.mark.e2e
def test_exporter_save_subtitles_auto_dispatch(tmp_path: Path) -> None:
    """拡張子 (.srt, .vtt, .json) による自動フォーマットディスパッチテスト (Tier 1)。"""
    # Arrange
    srt_file = tmp_path / "test.srt"
    vtt_file = tmp_path / "test.vtt"
    json_file = tmp_path / "test.json"
    segments = [SubtitleSegment(start=0.0, end=1.0, text="共通字幕")]

    # Act
    SubtitleExporter.save_subtitles(segments, srt_file)
    SubtitleExporter.save_subtitles(segments, vtt_file)
    SubtitleExporter.save_subtitles(segments, json_file)

    # Assert
    assert "00:00:00,000 --> 00:00:01,000" in srt_file.read_text(encoding="utf-8")
    assert "WEBVTT" in vtt_file.read_text(encoding="utf-8")
    json_data = json.loads(json_file.read_text(encoding="utf-8"))
    assert json_data == [{"start": 0.0, "end": 1.0, "text": "共通字幕"}]


@pytest.mark.e2e
def test_exporter_save_subtitles_explicit_format(tmp_path: Path) -> None:
    """大文字小文字を問わない明示的 fmt 引数指定テスト (Tier 1)。"""
    # Arrange
    out_file = tmp_path / "custom_output"
    segments = [SubtitleSegment(start=0.0, end=1.0, text="テスト")]

    # Act & Assert
    SubtitleExporter.save_subtitles(segments, out_file, fmt="SRT")
    assert "00:00:00,000 --> 00:00:01,000" in out_file.read_text(encoding="utf-8")

    SubtitleExporter.save_subtitles(segments, out_file, fmt="vtt")
    assert "WEBVTT" in out_file.read_text(encoding="utf-8")

    SubtitleExporter.save_subtitles(segments, out_file, fmt="JSON")
    json_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert json_data == [{"start": 0.0, "end": 1.0, "text": "テスト"}]


@pytest.mark.e2e
def test_exporter_timestamp_formatting_boundaries() -> None:
    """タイムスタンプフォーマッタ (0秒、ミリ秒丸め、24時間超) の境界値テスト (Tier 2)。"""
    # Arrange & Act
    srt_zero = SubtitleExporter.format_timestamp(0.0)
    vtt_zero = SubtitleExporter.format_vtt_timestamp(0.0)
    srt_25h = SubtitleExporter.format_timestamp(90061.500)
    vtt_25h = SubtitleExporter.format_vtt_timestamp(90061.500)

    # Assert
    assert srt_zero == "00:00:00,000"
    assert vtt_zero == "00:00:00.000"
    assert srt_25h == "25:01:01,500"
    assert vtt_25h == "25:01:01.500"


@pytest.mark.e2e
def test_exporter_auto_mkdir_deep_directory(tmp_path: Path) -> None:
    """保存先ディレクトリが存在しない場合の自動親ディレクトリ生成テスト (Tier 2)。"""
    # Arrange
    deep_path = tmp_path / "sub1" / "sub2" / "output.srt"
    segments = [SubtitleSegment(start=1.0, end=2.0, text="階層テスト")]

    # Act
    SubtitleExporter.save_srt(segments, deep_path)

    # Assert
    assert deep_path.exists()
    assert deep_path.parent.is_dir()


@pytest.mark.e2e
def test_exporter_empty_segments_handling(tmp_path: Path) -> None:
    """空のセグメントリスト渡却時の安全なエクスポートテスト (Tier 2)。"""
    # Arrange
    srt_path = tmp_path / "empty.srt"
    vtt_path = tmp_path / "empty.vtt"
    json_path = tmp_path / "empty.json"

    # Act
    SubtitleExporter.save_srt([], srt_path)
    SubtitleExporter.save_vtt([], vtt_path)
    SubtitleExporter.save_json([], json_path)

    # Assert
    assert srt_path.exists()
    assert "WEBVTT" in vtt_path.read_text(encoding="utf-8")
    assert json.loads(json_path.read_text(encoding="utf-8")) == []


@pytest.mark.e2e
def test_exporter_unsupported_format_raises_error(tmp_path: Path) -> None:
    """未対応の拡張子または未対応フォーマット指定時の ValueError 送出テスト (Tier 2)。"""
    # Arrange
    invalid_ext = tmp_path / "output.docx"
    segments = [SubtitleSegment(start=0.0, end=1.0, text="テスト")]

    # Act & Assert
    with pytest.raises(ValueError, match="未対応の拡張子"):
        SubtitleExporter.save_subtitles(segments, invalid_ext)

    with pytest.raises(ValueError, match="未対応のフォーマット"):
        SubtitleExporter.save_subtitles(segments, tmp_path / "out", fmt="xml")
