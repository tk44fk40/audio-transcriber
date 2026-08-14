"""Tests for audio-transcriber pipeline orchestration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from audio_transcriber.pipeline import run_pipeline


def test_run_pipeline_audio_file(tmp_path: Path):
    """Test run_pipeline with standard audio file input."""
    dummy_wav = tmp_path / "mic_input.wav"
    dummy_wav.write_bytes(b"RIFFdummydata")
    out_dir = tmp_path / "output"

    mock_denoiser = MagicMock()

    def fake_denoise(inp: Path, outp: Path):
        outp.write_bytes(b"clean")
        return outp

    mock_denoiser.denoise.side_effect = fake_denoise

    with patch("audio_transcriber.pipeline.transcribe_audio") as mock_transcribe:
        mock_transcribe.return_value = ("テスト文字起こし", [])

        result = run_pipeline(
            input_path=dummy_wav,
            output_dir=out_dir,
            denoise=True,
            transcribe=True,
            denoiser=mock_denoiser,
        )

    assert result.input_file == dummy_wav
    assert result.denoised_audio == out_dir / "mic_input_clean.wav"
    assert result.srt_file == out_dir / "mic_input.srt"
    assert result.transcript_text == "テスト文字起こし"
    assert result.remuxed_video is None
    mock_denoiser.denoise.assert_called_once()


def test_run_pipeline_video_file_with_remux(tmp_path: Path):
    """Test run_pipeline with video input performing extraction, denoise, transcribe, and remux."""
    dummy_mp4 = tmp_path / "gameplay.mp4"
    dummy_mp4.write_bytes(b"dummy_mp4_content")
    out_dir = tmp_path / "output"

    mock_denoiser = MagicMock()

    def fake_extract(media_path: Path, track_number: int, output_wav: Path):
        output_wav.write_bytes(b"extracted_audio")
        return output_wav

    def fake_denoise(inp: Path, outp: Path):
        outp.write_bytes(b"clean_audio")
        return outp

    def fake_remux(
        original_video: Path,
        mic_track_number: int,
        clean_audio: Path,
        output_video: Path,
    ):
        output_video.write_bytes(b"clean_video")
        return output_video

    mock_denoiser.denoise.side_effect = fake_denoise

    with (
        patch(
            "audio_transcriber.pipeline.extract_audio_track", side_effect=fake_extract
        ) as mock_extract,
        patch("audio_transcriber.pipeline.create_denoiser", return_value=mock_denoiser),
        patch("audio_transcriber.pipeline.transcribe_audio") as mock_transcribe,
        patch(
            "audio_transcriber.pipeline.remux_video", side_effect=fake_remux
        ) as mock_remux,
    ):
        mock_transcribe.return_value = ("実況字幕テキスト", [])

        result = run_pipeline(
            input_path=dummy_mp4,
            output_dir=out_dir,
            mic_track=2,
            denoise=True,
            transcribe=True,
            remux=True,
        )

    assert result.input_file == dummy_mp4
    assert result.denoised_audio == out_dir / "gameplay_clean.wav"
    assert result.srt_file == out_dir / "gameplay.srt"
    assert result.remuxed_video == out_dir / "gameplay_clean.mp4"
    assert result.transcript_text == "実況字幕テキスト"
    mock_extract.assert_called_once()
    mock_remux.assert_called_once()
    mock_denoiser.denoise.assert_called_once()
