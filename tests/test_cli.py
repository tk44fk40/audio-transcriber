"""Tests for CLI arguments and execution."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from audio_transcriber.cli import app

runner = CliRunner()


def test_cli_help():
    """Test CLI --help displays available options."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--mic-track" in result.stdout
    assert "--remux" in result.stdout
    assert "--output-dir" in result.stdout
    assert "--config" in result.stdout


def test_cli_conflicting_options(tmp_path: Path):
    """Test error when both --denoise-only and --transcribe-only are given."""
    dummy_file = tmp_path / "dummy.mp4"
    dummy_file.write_bytes(b"content")
    result = runner.invoke(
        app, [str(dummy_file), "--denoise-only", "--transcribe-only"]
    )
    assert result.exit_code == 1
    assert "Cannot specify both" in result.stdout


def test_cli_config_error(tmp_path: Path):
    """Test CLI exits with code 1 when configuration loading fails."""
    dummy_file = tmp_path / "gameplay.mp4"
    dummy_file.write_bytes(b"content")

    result = runner.invoke(
        app, [str(dummy_file), "--config", "/non/existent/config.toml"]
    )
    assert result.exit_code == 1
    assert "Configuration error:" in result.stdout


def test_cli_pipeline_failure(tmp_path: Path):
    """Test CLI handles pipeline exception gracefully and exits with code 1."""
    dummy_file = tmp_path / "gameplay.mp4"
    dummy_file.write_bytes(b"content")

    with patch(
        "audio_transcriber.cli.run_pipeline",
        side_effect=RuntimeError("Pipeline internal crash"),
    ):
        result = runner.invoke(app, [str(dummy_file)])
        assert result.exit_code == 1
        assert "Pipeline failed:" in result.stdout
        assert "Pipeline internal crash" in result.stdout


def test_cli_successful_run_with_config(tmp_path: Path):
    """Test CLI loads custom config and merges with CLI parameters."""
    dummy_file = tmp_path / "gameplay.mp4"
    dummy_file.write_bytes(b"content")

    config_content = """
[path]
OUTPUT_DIR = "./custom_out"

[pipeline]
REMUX = false

[media]
MIC_TRACK = 3

[model]
MODEL_SIZE = "medium"

[transcribe]
INITIAL_PROMPT = "Apex用語集"

[transcribe.vad]
MIN_SILENCE_DURATION_MS = 700
"""
    config_file = tmp_path / "test_cfg.toml"
    config_file.write_text(config_content, encoding="utf-8")

    mock_result = MagicMock()
    mock_result.remuxed_video = tmp_path / "custom_out" / "gameplay_clean.mp4"
    mock_result.denoised_audio = tmp_path / "custom_out" / "gameplay_clean.wav"
    mock_result.srt_file = tmp_path / "custom_out" / "gameplay.srt"

    with patch(
        "audio_transcriber.cli.run_pipeline", return_value=mock_result
    ) as mock_run:
        result = runner.invoke(app, [str(dummy_file), "-C", str(config_file)])
        assert result.exit_code == 0
        assert "Clean Video (Remuxed)" in result.stdout
        assert "Denoised Audio" in result.stdout
        assert "SRT Subtitle" in result.stdout
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["output_dir"] == Path("./custom_out")
        assert kwargs["mic_track"] == 3
        assert kwargs["model_size"] == "medium"
        assert kwargs["initial_prompt"] == "Apex用語集"
        assert kwargs["remux"] is False
        assert kwargs["min_silence_duration_ms"] == 700
