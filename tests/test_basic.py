"""Basic tests for audio-transcriber."""

from dataclasses import dataclass

from audio_transcriber import format_timestamp, segments_to_srt


def test_format_timestamp():
    """Test SRT timestamp formatting."""
    assert format_timestamp(0.0) == "00:00:00,000"
    assert format_timestamp(1.5) == "00:00:01,500"
    assert format_timestamp(65.123) == "00:01:05,123"
    assert format_timestamp(3661.050) == "01:01:01,050"


@dataclass
class DummySegment:
    start: float
    end: float
    text: str


def test_segments_to_srt():
    """Test conversion of segments to SRT string."""
    segments = [
        DummySegment(start=0.0, end=2.5, text=" こんにちは "),
        DummySegment(start=3.0, end=5.25, text=" ゲーム実況をはじめます "),
    ]
    srt = segments_to_srt(segments)
    expected = (
        "1\n00:00:00,000 --> 00:00:02,500\nこんにちは\n\n"
        "2\n00:00:03,000 --> 00:00:05,250\nゲーム実況をはじめます\n"
    )
    assert srt.strip() == expected.strip()
