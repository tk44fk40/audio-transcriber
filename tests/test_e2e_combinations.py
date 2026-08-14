"""Tier 3 cross-feature combination and interaction tests.

設定パース・CLI引数解決・メディア抽出・ノイズ除去・文字起こし・動画再結合間の相互作用を検証します。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from audio_transcriber.cli import app
from audio_transcriber.config import AppConfig, load_config
from audio_transcriber.pipeline import PipelineResult, run_pipeline

runner = CliRunner()


def test_config_to_pipeline_parameters_interaction(tmp_path: Path) -> None:
    """TOML 設定から抽出したパラメータがパイプライン各層に過不足なく伝播することを検証する。"""
    # Arrange
    cfg_file = tmp_path / "integration_cfg.toml"
    cfg_file.write_text(
        """
[path]
OUTPUT_DIR = "./target_out"
[media]
MIC_TRACK = 4
SAMPLE_RATE = 48000
[model]
MODEL_SIZE = "large-v3-turbo"
DEVICE = "cuda"
COMPUTE_TYPE = "float16"
[transcribe]
LANGUAGE = "ja"
INITIAL_PROMPT = "ゲーム用語プロンプト"
[transcribe.vad]
VAD_FILTER = true
MIN_SILENCE_DURATION_MS = 600
""",
        encoding="utf-8",
    )
    cfg: AppConfig = load_config(cfg_file)
    input_wav = tmp_path / "stream.wav"
    input_wav.write_bytes(b"DATA")

    mock_denoiser = MagicMock()
    mock_denoiser.denoise.side_effect = lambda inp, outp: outp

    with (
        patch("audio_transcriber.pipeline.create_denoiser", return_value=mock_denoiser),
        patch("audio_transcriber.pipeline.transcribe_audio") as mock_transcribe,
    ):
        mock_transcribe.return_value = ("文字起こし", [])

        # Act
        result = run_pipeline(
            input_path=input_wav,
            output_dir=cfg.output_dir,
            model_size=cfg.model.model_size,
            device=cfg.model.device,
            compute_type=cfg.model.compute_type,
            language=cfg.transcribe.language,
            initial_prompt=cfg.transcribe.initial_prompt,
            denoise=True,
            transcribe=True,
            vad_filter=cfg.transcribe.vad.vad_filter,
            min_silence_duration_ms=cfg.transcribe.vad.min_silence_duration_ms,
        )

    # Assert
    assert result.denoised_audio == Path("./target_out").resolve() / "stream_clean.wav"
    mock_transcribe.assert_called_once()
    _, kwargs = mock_transcribe.call_args
    assert kwargs["model_size"] == "large-v3-turbo"
    assert kwargs["initial_prompt"] == "ゲーム用語プロンプト"
    assert kwargs["min_silence_duration_ms"] == 600


def test_cli_overrides_with_full_toml_config(tmp_path: Path) -> None:
    """TOML 設定と CLI フラグが同時に指定された際、CLI フラグが正確に最優先されることを検証する。"""
    # Arrange
    video_file = tmp_path / "match.mkv"
    video_file.write_bytes(b"MKV_DATA")
    cfg_file = tmp_path / "base_cfg.toml"
    cfg_file.write_text(
        """
OUTPUT_DIR = "./base_out"
[media]
MIC_TRACK = 1
[model]
MODEL_SIZE = "small"
""",
        encoding="utf-8",
    )

    mock_res = PipelineResult(
        input_file=video_file,
        denoised_audio=tmp_path / "override_out" / "match_clean.wav",
        srt_file=tmp_path / "override_out" / "match.srt",
        transcript_text="実況",
        remuxed_video=tmp_path / "override_out" / "match_clean.mkv",
    )

    with patch(
        "audio_transcriber.cli.run_pipeline", return_value=mock_res
    ) as mock_pipeline:
        # Act
        result = runner.invoke(
            app,
            [
                str(video_file),
                "-C",
                str(cfg_file),
                "-o",
                str(tmp_path / "override_out"),
                "--mic-track",
                "2",
                "--model-size",
                "medium",
            ],
        )

    # Assert
    assert result.exit_code == 0
    mock_pipeline.assert_called_once()
    _, kwargs = mock_pipeline.call_args
    assert kwargs["output_dir"] == tmp_path / "override_out"
    assert kwargs["mic_track"] == 2
    assert kwargs["model_size"] == "medium"


def test_video_multitrack_extraction_denoise_remux_flow(tmp_path: Path) -> None:
    """動画の特定トラック抽出からノイズ除去・文字起こし・動画再結合までの一連の連携を検証する。"""
    # Arrange
    in_video = tmp_path / "game_recording.mp4"
    in_video.write_bytes(b"MP4_DATA")
    out_dir = tmp_path / "combo_out"

    def fake_extract(media_path: Path, track_number: int, output_wav: Path) -> Path:
        output_wav.write_bytes(b"EXT")
        return output_wav

    def fake_denoise(inp: Path, outp: Path, **kwargs) -> Path:
        outp.write_bytes(b"CLN")
        return outp

    def fake_remux(
        original_video: Path,
        mic_track_number: int,
        clean_audio: Path,
        output_video: Path,
    ) -> Path:
        output_video.write_bytes(b"RMX")
        return output_video

    mock_denoiser = MagicMock()
    mock_denoiser.denoise.side_effect = fake_denoise

    with (
        patch(
            "audio_transcriber.pipeline.extract_audio_track", side_effect=fake_extract
        ) as mock_e,
        patch("audio_transcriber.pipeline.create_denoiser", return_value=mock_denoiser),
        patch(
            "audio_transcriber.pipeline.transcribe_audio", return_value=("字幕", [])
        ) as mock_t,
        patch(
            "audio_transcriber.pipeline.remux_video", side_effect=fake_remux
        ) as mock_r,
    ):
        # Act
        res = run_pipeline(
            input_path=in_video,
            output_dir=out_dir,
            mic_track=3,
            denoise=True,
            transcribe=True,
            remux=True,
        )

    # Assert
    assert res.denoised_audio == out_dir / "game_recording_clean.wav"
    assert res.srt_file == out_dir / "game_recording.srt"
    assert res.remuxed_video == out_dir / "game_recording_clean.mp4"
    mock_e.assert_called_once()
    mock_denoiser.denoise.assert_called_once()
    mock_t.assert_called_once()
    mock_r.assert_called_once()


def test_audio_only_no_remux_no_denoise_flow(tmp_path: Path) -> None:
    """音声のみの入力に対してノイズ除去を行わず直接文字起こしする連携フローを検証する。"""
    # Arrange
    in_audio = tmp_path / "podcast.wav"
    in_audio.write_bytes(b"AUDIO")
    out_dir = tmp_path / "podcast_out"

    with (
        patch("audio_transcriber.pipeline.create_denoiser") as mock_create_denoiser,
        patch("audio_transcriber.pipeline.transcribe_audio") as mock_transcribe,
    ):
        mock_transcribe.return_value = ("ポッドキャスト文字起こし", [])

        # Act
        res = run_pipeline(
            input_path=in_audio,
            output_dir=out_dir,
            denoise=False,
            transcribe=True,
            remux=False,
        )

    # Assert
    assert res.denoised_audio is None
    assert res.remuxed_video is None
    assert res.srt_file == out_dir / "podcast.srt"
    assert res.transcript_text == "ポッドキャスト文字起こし"
    mock_create_denoiser.assert_not_called()
    mock_transcribe.assert_called_once()


def test_pipeline_output_paths_resolution_and_isolation(tmp_path: Path) -> None:
    """複数回実行時に各出力ディレクトリが独立して解決され干渉しないことを検証する。"""
    # Arrange
    wav1 = tmp_path / "file1.wav"
    wav2 = tmp_path / "file2.wav"
    wav1.write_bytes(b"WAV1")
    wav2.write_bytes(b"WAV2")
    out_dir1 = tmp_path / "run_1"
    out_dir2 = tmp_path / "run_2"

    with patch("audio_transcriber.pipeline.transcribe_audio", return_value=("", [])):
        # Act
        res1 = run_pipeline(input_path=wav1, output_dir=out_dir1, denoise=False)
        res2 = run_pipeline(input_path=wav2, output_dir=out_dir2, denoise=False)

    # Assert
    assert res1.srt_file == out_dir1 / "file1.srt"
    assert res2.srt_file == out_dir2 / "file2.srt"
    assert res1.srt_file != res2.srt_file
