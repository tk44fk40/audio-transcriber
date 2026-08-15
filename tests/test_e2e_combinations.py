"""Tier 3 cross-feature combination and interaction tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from audio_transcriber.cli import app
from audio_transcriber.config import AppConfig, load_config
from audio_transcriber.pipeline import PipelineResult, run_pipeline

runner = CliRunner()


def test_config_to_pipeline_parameters_interaction(
    tmp_path: Path, dummy_provider_class: type
) -> None:
    """TOML 設定から抽出したパラメータがパイプライン各層に過不足なく伝播することを検証する。"""
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

    transcriber = dummy_provider_class(
        model_size=cfg.model.model_size,
        device=cfg.model.device,
        compute_type=cfg.model.compute_type,
        language=cfg.transcribe.language,
        initial_prompt=cfg.transcribe.initial_prompt,
        vad_filter=cfg.transcribe.vad.vad_filter,
        min_silence_duration_ms=cfg.transcribe.vad.min_silence_duration_ms,
    )

    with patch(
        "audio_transcriber.pipeline.create_denoiser", return_value=mock_denoiser
    ):
        result = run_pipeline(
            input_path=input_wav,
            cfg=cfg,
            denoise=True,
            transcribe=True,
            denoiser=mock_denoiser,
            transcriber=transcriber,
        )

    assert result.denoised_audio == Path("./target_out").resolve() / "stream_clean.wav"
    assert transcriber.kwargs["model_size"] == "large-v3-turbo"
    assert transcriber.kwargs["initial_prompt"] == "ゲーム用語プロンプト"
    assert transcriber.kwargs["min_silence_duration_ms"] == 600


def test_cli_overrides_with_full_toml_config(tmp_path: Path) -> None:
    """TOML 設定と CLI フラグが同時に指定された際、CLI フラグが正確に最優先されることを検証する。"""
    video_file = tmp_path / "match.mkv"
    video_file.write_bytes(b"MKV_DATA")
    cfg_file = tmp_path / "base_cfg.toml"
    cfg_file.write_text(
        """
[path]
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

    assert result.exit_code == 0
    mock_pipeline.assert_called_once()
    _, kwargs = mock_pipeline.call_args
    cfg_arg = kwargs["cfg"]
    assert cfg_arg.paths.output_dir == tmp_path / "override_out"
    assert cfg_arg.media.mic_track == 2
    assert cfg_arg.model.model_size == "medium"


def test_video_multitrack_extraction_denoise_remux_flow(
    tmp_path: Path,
    base_config: AppConfig,
    dummy_provider_class: type,
) -> None:
    """動画の特定トラック抽出からノイズ除去・文字起こし・動画再結合までの一連の連携を検証する。"""
    in_video = tmp_path / "game_recording.mp4"
    in_video.write_bytes(b"MP4_DATA")
    out_dir = tmp_path / "combo_out"
    base_config.paths.output_dir = out_dir
    base_config.media.mic_track = 3
    base_config.pipeline.remux = True

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

    transcriber = dummy_provider_class(
        model_size=base_config.model.model_size,
    )

    with (
        patch(
            "audio_transcriber.pipeline.extract_audio_track", side_effect=fake_extract
        ) as mock_e,
        patch("audio_transcriber.pipeline.create_denoiser", return_value=mock_denoiser),
        patch(
            "audio_transcriber.pipeline.remux_video", side_effect=fake_remux
        ) as mock_r,
    ):
        res = run_pipeline(
            input_path=in_video,
            cfg=base_config,
            denoise=True,
            transcribe=True,
            denoiser=mock_denoiser,
            transcriber=transcriber,
        )

    assert res.denoised_audio == out_dir / "game_recording_clean.wav"
    assert res.srt_file == out_dir / "game_recording.srt"
    assert res.remuxed_video == out_dir / "game_recording_clean.mp4"
    mock_e.assert_called_once()
    mock_denoiser.denoise.assert_called_once()
    mock_r.assert_called_once()


def test_audio_only_no_remux_no_denoise_flow(
    tmp_path: Path,
    base_config: AppConfig,
    dummy_provider_class: type,
) -> None:
    """音声のみの入力に対してノイズ除去を行わず直接文字起こしする連携フローを検証する。"""
    in_audio = tmp_path / "podcast.wav"
    in_audio.write_bytes(b"AUDIO")
    out_dir = tmp_path / "podcast_out"
    base_config.paths.output_dir = out_dir
    base_config.pipeline.remux = False

    transcriber = dummy_provider_class()

    with patch("audio_transcriber.pipeline.create_denoiser") as mock_create_denoiser:
        res = run_pipeline(
            input_path=in_audio,
            cfg=base_config,
            denoise=False,
            transcribe=True,
            transcriber=transcriber,
        )

    assert res.denoised_audio is None
    assert res.remuxed_video is None
    assert res.srt_file == out_dir / "podcast.srt"
    assert "テスト" in str(res.transcript_text)
    mock_create_denoiser.assert_not_called()


def test_pipeline_output_paths_resolution_and_isolation(
    tmp_path: Path,
    base_config: AppConfig,
    dummy_provider_class: type,
) -> None:
    """複数回実行時に各出力ディレクトリが独立して解決され干渉しないことを検証する。"""
    wav1 = tmp_path / "file1.wav"
    wav2 = tmp_path / "file2.wav"
    wav1.write_bytes(b"WAV1")
    wav2.write_bytes(b"WAV2")
    out_dir1 = tmp_path / "run_1"
    out_dir2 = tmp_path / "run_2"

    cfg1 = AppConfig()
    cfg1.paths.output_dir = out_dir1

    cfg2 = AppConfig()
    cfg2.paths.output_dir = out_dir2

    transcriber = dummy_provider_class()

    res1 = run_pipeline(
        input_path=wav1, cfg=cfg1, denoise=False, transcriber=transcriber
    )
    res2 = run_pipeline(
        input_path=wav2, cfg=cfg2, denoise=False, transcriber=transcriber
    )

    assert res1.srt_file == out_dir1 / "file1.srt"
    assert res2.srt_file == out_dir2 / "file2.srt"
    assert res1.srt_file != res2.srt_file
