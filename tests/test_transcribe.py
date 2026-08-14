"""Tests for faster-whisper transcription module."""

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

from audio_transcriber.transcribe import transcribe_audio


@dataclass
class DummySegment:
    """Mock whisper segment."""

    id: int
    start: float
    end: float
    text: str


def test_transcribe_audio_with_file_output(tmp_path: Path):
    """Test transcribe_audio converts segments to SRT and writes to output file."""
    input_audio = tmp_path / "audio.wav"
    output_srt = tmp_path / "nested" / "output.srt"
    input_audio.write_bytes(b"dummy audio")

    mock_segments = [
        DummySegment(id=1, start=0.0, end=2.5, text=" こんにちは世界 "),
        DummySegment(id=2, start=3.0, end=5.0, text=" テストです "),
    ]

    mock_model_instance = MagicMock()
    mock_model_instance.transcribe.return_value = (iter(mock_segments), MagicMock())

    with patch(
        "audio_transcriber.transcribe.WhisperModel", return_value=mock_model_instance
    ) as mock_cls:
        srt_content, segment_dicts = transcribe_audio(
            audio_path=input_audio,
            output_srt_path=output_srt,
            model_size="small",
            device="cpu",
            compute_type="int8",
            language="ja",
            initial_prompt="ゲーム実況",
            vad_filter=True,
        )

        mock_cls.assert_called_once_with("small", device="cpu", compute_type="int8")
        mock_model_instance.transcribe.assert_called_once_with(
            str(input_audio),
            language="ja",
            initial_prompt="ゲーム実況",
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )

        assert "こんにちは世界" in srt_content
        assert output_srt.exists()
        saved_text = output_srt.read_text(encoding="utf-8")
        assert "こんにちは世界" in saved_text
        assert "テストです" in saved_text

        assert len(segment_dicts) == 2
        assert segment_dicts[0] == {
            "id": 1,
            "start": 0.0,
            "end": 2.5,
            "text": "こんにちは世界",
        }
        assert segment_dicts[1] == {
            "id": 2,
            "start": 3.0,
            "end": 5.0,
            "text": "テストです",
        }


def test_transcribe_audio_without_file_output(tmp_path: Path):
    """Test transcribe_audio without output_srt_path returns result without writing file."""
    input_audio = tmp_path / "audio.wav"
    input_audio.write_bytes(b"dummy audio")

    mock_segments = [
        DummySegment(id=1, start=0.0, end=1.0, text="無保存テスト"),
    ]

    mock_model_instance = MagicMock()
    mock_model_instance.transcribe.return_value = (iter(mock_segments), MagicMock())

    with patch(
        "audio_transcriber.transcribe.WhisperModel", return_value=mock_model_instance
    ):
        srt_content, segment_dicts = transcribe_audio(
            audio_path=input_audio,
            output_srt_path=None,
        )

        assert "無保存テスト" in srt_content
        assert len(segment_dicts) == 1
        assert segment_dicts[0]["text"] == "無保存テスト"
