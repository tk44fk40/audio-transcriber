"""Basic tests for audio-transcriber."""

from audio_transcriber.exporter import SubtitleExporter


def test_format_timestamp():
    """Test SRT timestamp formatting."""
    assert SubtitleExporter.format_timestamp(0.0) == "00:00:00,000"
    assert SubtitleExporter.format_timestamp(1.5) == "00:00:01,500"
    assert SubtitleExporter.format_timestamp(65.123) == "00:01:05,123"
    assert SubtitleExporter.format_timestamp(3661.050) == "01:01:01,050"
