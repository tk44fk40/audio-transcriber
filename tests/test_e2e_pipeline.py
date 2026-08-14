"""End-to-End pipeline execution, result data structures, and integration tests.

パイプライン実行、生成ファイルパス管理、PipelineResult 構造体、
および各処理モードの連携を検証します。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from audio_transcriber.pipeline import PipelineResult, run_pipeline


def test_pipeline_result_structure() -> None:
    """PipelineResult データクラスの各フィールドが正しく保持・参照できることを検証する。"""
    # Arrange & Act
    res = PipelineResult(
        input_file=Path("/tmp/input.wav"),
        denoised_audio=Path("/tmp/output/input_clean.wav"),
        srt_file=Path("/tmp/output/input.srt"),
        transcript_text="テスト文字起こし結果",
        remuxed_video=Path("/tmp/output/input_clean.mp4"),
    )

    # Assert
    assert res.input_file == Path("/tmp/input.wav")
    assert res.denoised_audio == Path("/tmp/output/input_clean.wav")
    assert res.srt_file == Path("/tmp/output/input.srt")
    assert res.transcript_text == "テスト文字起こし結果"
    assert res.remuxed_video == Path("/tmp/output/input_clean.mp4")


def test_run_pipeline_full_audio_flow(tmp_path: Path) -> None:
    """音声入力に対してノイズ除去と文字起こしが順次実行され結果が返されることを検証する。"""
    # Arrange
    input_wav = tmp_path / "voice_sample.wav"
    input_wav.write_bytes(b"RIFF_AUDIO")
    out_dir = tmp_path / "custom_output"

    mock_denoiser = MagicMock()
    mock_denoiser.denoise.side_effect = lambda inp, outp: outp.write_bytes(b"CLEAN")

    with (
        patch("audio_transcriber.pipeline.create_denoiser", return_value=mock_denoiser),
        patch("audio_transcriber.pipeline.transcribe_audio") as mock_transcribe,
    ):
        mock_transcribe.return_value = (
            "1\n00:00:00,000 --> 00:00:01,000\nこんにちは\n",
            [],
        )

        # Act
        result = run_pipeline(
            input_path=input_wav, output_dir=out_dir, denoise=True, transcribe=True
        )

    # Assert
    assert result.input_file == input_wav
    assert result.denoised_audio == out_dir / "voice_sample_clean.wav"
    assert result.srt_file == out_dir / "voice_sample.srt"
    assert "こんにちは" in str(result.transcript_text)
    assert result.remuxed_video is None
    mock_denoiser.denoise.assert_called_once()
    mock_transcribe.assert_called_once()


def test_run_pipeline_video_flow_with_remux(tmp_path: Path) -> None:
    """動画入力に対してトラック抽出・ノイズ除去・文字起こし・動画再結合が実行されることを検証する。"""
    # Arrange
    input_mp4 = tmp_path / "gaming_clip.mp4"
    input_mp4.write_bytes(b"MP4_DATA")
    out_dir = tmp_path / "output_video"

    def fake_extract(media_path: Path, track_number: int, output_wav: Path) -> Path:
        output_wav.write_bytes(b"EXTRACTED")
        return output_wav

    def fake_denoise(inp: Path, outp: Path) -> Path:
        outp.write_bytes(b"CLEAN")
        return outp

    def fake_remux(
        original_video: Path,
        mic_track_number: int,
        clean_audio: Path,
        output_video: Path,
    ):
        output_video.write_bytes(b"REMUXED")
        return output_video

    mock_denoiser = MagicMock()
    mock_denoiser.denoise.side_effect = fake_denoise

    with (
        patch(
            "audio_transcriber.pipeline.extract_audio_track", side_effect=fake_extract
        ) as mock_e,
        patch("audio_transcriber.pipeline.create_denoiser", return_value=mock_denoiser),
        patch(
            "audio_transcriber.pipeline.transcribe_audio", return_value=("実況字幕", [])
        ) as mock_t,
        patch(
            "audio_transcriber.pipeline.remux_video", side_effect=fake_remux
        ) as mock_r,
    ):
        # Act
        result = run_pipeline(
            input_path=input_mp4,
            output_dir=out_dir,
            mic_track=2,
            denoise=True,
            transcribe=True,
            remux=True,
        )

    # Assert
    assert result.input_file == input_mp4
    assert result.denoised_audio == out_dir / "gaming_clip_clean.wav"
    assert result.srt_file == out_dir / "gaming_clip.srt"
    assert result.remuxed_video == out_dir / "gaming_clip_clean.mp4"
    mock_e.assert_called_once()
    mock_denoiser.denoise.assert_called_once()
    mock_t.assert_called_once()
    mock_r.assert_called_once()


def test_run_pipeline_transcribe_only_mode(tmp_path: Path) -> None:
    """denoise=False 時にノイズ除去をスキップし入力音声を直接文字起こしすることを検証する。"""
    # Arrange
    input_wav = tmp_path / "raw_speech.wav"
    input_wav.write_bytes(b"RAW_SPEECH")
    out_dir = tmp_path / "out_trans_only"

    with (
        patch("audio_transcriber.pipeline.create_denoiser") as mock_create_denoiser,
        patch("audio_transcriber.pipeline.transcribe_audio") as mock_transcribe,
    ):
        mock_transcribe.return_value = ("直接文字起こし", [])

        # Act
        result = run_pipeline(
            input_path=input_wav, output_dir=out_dir, denoise=False, transcribe=True
        )

    # Assert
    assert result.denoised_audio is None
    assert result.srt_file == out_dir / "raw_speech.srt"
    mock_create_denoiser.assert_not_called()
    mock_transcribe.assert_called_once()


def test_run_pipeline_denoise_only_mode(tmp_path: Path) -> None:
    """transcribe=False 時に文字起こしを実行せずクリーン音声のみ生成することを検証する。"""
    # Arrange
    input_wav = tmp_path / "noisy.wav"
    input_wav.write_bytes(b"NOISY")
    out_dir = tmp_path / "out_denoise_only"

    mock_denoiser = MagicMock()
    mock_denoiser.denoise.side_effect = lambda inp, outp: outp.write_bytes(b"CLEAN")

    with (
        patch("audio_transcriber.pipeline.create_denoiser", return_value=mock_denoiser),
        patch("audio_transcriber.pipeline.transcribe_audio") as mock_transcribe,
    ):
        # Act
        result = run_pipeline(
            input_path=input_wav, output_dir=out_dir, denoise=True, transcribe=False
        )

    # Assert
    assert result.denoised_audio == out_dir / "noisy_clean.wav"
    assert result.srt_file is None
    assert result.transcript_text is None
    mock_denoiser.denoise.assert_called_once()
    mock_transcribe.assert_not_called()


def test_run_pipeline_creates_nonexistent_output_dir(tmp_path: Path) -> None:
    """存在しない出力ディレクトリが指定された場合に自動作成されることを検証する。"""
    # Arrange
    input_wav = tmp_path / "sample.wav"
    input_wav.write_bytes(b"WAV")
    nested_out_dir = tmp_path / "deep" / "nested" / "output_dir"

    with patch("audio_transcriber.pipeline.transcribe_audio", return_value=("", [])):
        # Act
        run_pipeline(
            input_path=input_wav,
            output_dir=nested_out_dir,
            denoise=False,
            transcribe=True,
        )

    # Assert
    assert nested_out_dir.is_dir()


def test_run_pipeline_passes_all_custom_parameters(tmp_path: Path) -> None:
    """Whisper推論やVADに関する詳細パラメータが正しく下位モジュールへ伝播されることを検証する。"""
    # Arrange
    input_wav = tmp_path / "param_test.wav"
    input_wav.write_bytes(b"WAV")

    with patch(
        "audio_transcriber.pipeline.transcribe_audio", return_value=("", [])
    ) as mock_transcribe:
        # Act
        run_pipeline(
            input_path=input_wav,
            output_dir=tmp_path / "out",
            model_size="large-v3",
            device="cpu",
            compute_type="int8",
            language="en",
            initial_prompt="Custom Prompt",
            denoise=False,
            transcribe=True,
            vad_filter=False,
            min_silence_duration_ms=1000,
        )

    # Assert
    mock_transcribe.assert_called_once()
    _, kwargs = mock_transcribe.call_args
    assert kwargs["model_size"] == "large-v3"
    assert kwargs["device"] == "cpu"
    assert kwargs["compute_type"] == "int8"
    assert kwargs["language"] == "en"
    assert kwargs["initial_prompt"] == "Custom Prompt"
    assert kwargs["vad_filter"] is False
    assert kwargs["min_silence_duration_ms"] == 1000
