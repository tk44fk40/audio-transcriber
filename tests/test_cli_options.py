"""CLI 引数パース、ヘルプ表示、および設定オーバーライドの単体テスト。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from audio_transcriber.cli import app

runner = CliRunner()


def test_cli_help() -> None:
    """CLI --help が利用可能な全オプションを表示することを検証します。"""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--mic-track" in result.stdout
    assert "--remux" in result.stdout
    assert "--output-dir" in result.stdout
    assert "--config" in result.stdout
    assert "--denoise" in result.stdout


def test_cli_conflicting_options(tmp_path: Path) -> None:
    """--denoise-only と --transcribe-only を両方指定した際にエラーとなることを検証します。"""
    dummy_file = tmp_path / "dummy.mp4"
    dummy_file.write_bytes(b"content")
    result = runner.invoke(
        app, [str(dummy_file), "--denoise-only", "--transcribe-only"]
    )
    assert result.exit_code == 1
    assert "Cannot specify both" in result.stdout


def test_cli_fallback_to_config_default_video_path(tmp_path: Path) -> None:
    """input_file 引数が省略された場合に DEFAULT_VIDEO_PATH が使われることを検証します。"""
    default_video = tmp_path / "default_sample.mov"
    default_video.write_bytes(b"video content")

    config_content = f"""
[path]
DEFAULT_VIDEO_PATH = "{default_video}"
"""
    config_file = tmp_path / "test_cfg.toml"
    config_file.write_text(config_content, encoding="utf-8")

    mock_result = MagicMock()
    mock_result.remuxed_video = None
    mock_result.denoised_audio = None
    mock_result.srt_file = None

    with patch(
        "audio_transcriber.cli.run_pipeline", return_value=mock_result
    ) as mock_run:
        result = runner.invoke(app, ["-C", str(config_file)])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["input_path"] == default_video


def test_cli_missing_input_file_and_no_config_raises_error(tmp_path: Path) -> None:
    """input_file も default 設定もない場合に適切なエラーで終了することを検証します。"""
    config_content = """
[path]
OUTPUT_DIR = "./out"
"""
    config_file = tmp_path / "test_cfg.toml"
    config_file.write_text(config_content, encoding="utf-8")

    result = runner.invoke(app, ["-C", str(config_file)])
    assert result.exit_code == 2
    assert "Input file is required" in result.stdout or "Error" in result.stdout


def test_cli_mode_switches_and_model_options(tmp_path: Path) -> None:
    """CLI の denoise-only, transcribe-only およびモデル設定の上書きを検証します。"""
    dummy_file = tmp_path / "gameplay.mp4"
    dummy_file.write_bytes(b"content")

    with patch("audio_transcriber.cli.run_pipeline") as mock_run:
        # 1. denoise-only & cpu device fallback
        result1 = runner.invoke(
            app,
            [
                str(dummy_file),
                "--denoise-only",
                "--device",
                "cpu",
                "--compute-type",
                "float16",
            ],
        )
        assert result1.exit_code == 0
        _, kwargs1 = mock_run.call_args
        assert kwargs1["denoise"] is True
        assert kwargs1["transcribe"] is False
        assert kwargs1["cfg"].model.device == "cpu"

        # 2. transcribe-only & options
        result2 = runner.invoke(
            app,
            [
                str(dummy_file),
                "--transcribe-only",
                "--model-size",
                "large-v3",
                "--language",
                "en",
                "--prompt",
                "custom prompt",
                "--min-silence-ms",
                "300",
                "--mastering-enabled",
                "--noise-gate-threshold",
                "0.02",
                "--loudness-i",
                "-14.0",
                "--loudness-tp",
                "-1.5",
                "--loudness-lra",
                "9.0",
                "--final-limit-db",
                "-1.0",
            ],
        )
        assert result2.exit_code == 0
        _, kwargs2 = mock_run.call_args
        assert kwargs2["denoise"] is False
        assert kwargs2["transcribe"] is True
        cfg2 = kwargs2["cfg"]
        assert cfg2.model.model_size == "large-v3"
        assert cfg2.transcribe.language == "en"
        assert cfg2.transcribe.initial_prompt == "custom prompt"
        assert cfg2.transcribe.vad.min_silence_duration_ms == 300
        assert cfg2.mastering.enabled is True
        assert cfg2.mastering.noise_gate_threshold == 0.02
        assert cfg2.mastering.loudness_i == -14.0
        assert cfg2.mastering.loudness_tp == -1.5
        assert cfg2.mastering.loudness_lra == 9.0
        assert cfg2.mastering.final_limit_db == -1.0

        # 3. explicit --no-denoise
        result3 = runner.invoke(app, [str(dummy_file), "--no-denoise"])
        assert result3.exit_code == 0
        _, kwargs3 = mock_run.call_args
        assert kwargs3["denoise"] is False


def test_cli_all_arguments_and_overrides(tmp_path: Path) -> None:
    """全 CLI オプションの網羅的パースおよび AppConfig への反映を検証します。"""
    dummy_file = tmp_path / "gameplay.mp4"
    dummy_file.write_bytes(b"content")

    mock_result = MagicMock()

    with patch(
        "audio_transcriber.cli.run_pipeline", return_value=mock_result
    ) as mock_run:
        result = runner.invoke(
            app,
            [
                str(dummy_file),
                "--output-dir",
                str(tmp_path / "out"),
                "--mic-track",
                "1",
                "--no-remux",
                "--debug-output-dir",
                "./debug",
                "--custom-dict-path",
                "./dict.toml",
                "--denoise-engine",
                "passthrough",
                "--denoise-model-path",
                "./model.rnnn",
                "--media-sample-rate",
                "16000",
                "--beam-size",
                "10",
                "--no-condition-on-previous-text",
                "--transcribe-no-speech-threshold",
                "0.5",
                "--vad-threshold",
                "0.4",
                "--no-replace-terms",
                "--lower",
                "--remove-punct",
                "--pp-no-speech-threshold",
                "0.4",
                "--max-chars-per-second",
                "10.0",
                "--end-padding",
                "2.0",
                "--min-duration",
                "2.0",
                "--min-gap",
                "0.1",
                "--subtitle-formats",
                "srt,vtt",
                "--chunk-size-ms",
                "200",
                "--buffer-size-seconds",
                "5.0",
                "--stream-sample-rate",
                "48000",
                "--flush-timeout-ms",
                "500",
                "--word-gap-split-threshold",
                "2.0",
                "--streaming-log",
            ],
        )
        assert result.exit_code == 0
        _, kwargs = mock_run.call_args
        cfg_arg = kwargs["cfg"]
        assert cfg_arg.paths.output_dir == tmp_path / "out"
        assert cfg_arg.media.mic_track == 1
        assert cfg_arg.pipeline.remux is False
        assert cfg_arg.paths.debug_output_dir == Path("./debug")
        assert cfg_arg.paths.custom_dict_path == Path("./dict.toml")
        assert cfg_arg.denoise.engine == "passthrough"
        assert cfg_arg.denoise.model_path == Path("./model.rnnn")
        assert cfg_arg.media.sample_rate == 16000
        assert cfg_arg.transcribe.beam_size == 10
        assert cfg_arg.transcribe.condition_on_previous_text is False
        assert cfg_arg.transcribe.no_speech_threshold == 0.5
        assert cfg_arg.transcribe.vad.vad_threshold == 0.4
        assert cfg_arg.post_process.replace_terms is False
        assert cfg_arg.post_process.lower is True
        assert cfg_arg.post_process.remove_punct is True
        assert cfg_arg.post_process.no_speech_threshold == 0.4
        assert cfg_arg.post_process.max_chars_per_second == 10.0
        assert cfg_arg.subtitle.end_padding == 2.0
        assert cfg_arg.subtitle.min_duration == 2.0
        assert cfg_arg.subtitle.min_gap == 0.1
        assert cfg_arg.subtitle.formats == ["srt", "vtt"]
        assert cfg_arg.stream.chunk_size_ms == 200
        assert cfg_arg.stream.buffer_size_seconds == 5.0
        assert cfg_arg.stream.sample_rate == 48000
        assert cfg_arg.stream.flush_timeout_ms == 500
        assert cfg_arg.stream.word_gap_split_threshold == 2.0
        assert cfg_arg.stream.streaming_log is True
