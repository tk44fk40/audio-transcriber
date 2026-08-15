"""End-to-End CLI command execution, option resolution, and table output tests.

Typer CLI 引数・オプションの解決、排他制御、エラーハンドリング、および Rich 結果表示を検証します。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from audio_transcriber.cli import app
from audio_transcriber.pipeline import PipelineResult

runner = CliRunner()


def test_cli_help_displays_all_options() -> None:
    """CLI の --help オプションですべてのオプションが表示され exit 0 となることを検証する。"""
    # Arrange & Act
    result = runner.invoke(app, ["--help"])

    # Assert
    assert result.exit_code == 0
    assert "--config" in result.stdout
    assert "--output-dir" in result.stdout
    assert "--mic-track" in result.stdout
    assert "--model-size" in result.stdout
    assert "--device" in result.stdout
    assert "--compute-type" in result.stdout
    assert "--language" in result.stdout
    assert "--prompt" in result.stdout
    assert "--denoise-only" in result.stdout
    assert "--transcribe-only" in result.stdout
    assert "--remux" in result.stdout
    assert "--min-silence-ms" in result.stdout


def test_cli_mutual_exclusion_denoise_and_transcribe_only(tmp_path: Path) -> None:
    """--denoise-only と --transcribe-only の同時指定時に
    排他エラー(exit 1)となることを検証する。
    """
    # Arrange
    dummy_file = tmp_path / "sample.mp4"
    dummy_file.write_bytes(b"DATA")

    # Act
    result = runner.invoke(
        app, [str(dummy_file), "--denoise-only", "--transcribe-only"]
    )

    # Assert
    assert result.exit_code == 1
    assert "Cannot specify both" in result.stdout


def test_cli_nonexistent_input_file_returns_error() -> None:
    """存在しない入力ファイルパスを指定した場合に exit 2 となることを検証する。"""
    # Arrange & Act
    result = runner.invoke(app, ["/nonexistent/media/file.mp4"])

    # Assert
    assert result.exit_code == 2


def test_cli_nonexistent_config_file_returns_error(tmp_path: Path) -> None:
    """存在しない設定ファイルパスを指定した場合に exit 1 となることを検証する。"""
    # Arrange
    dummy_file = tmp_path / "sample.mp4"
    dummy_file.write_bytes(b"DATA")

    # Act
    result = runner.invoke(app, [str(dummy_file), "-C", "/nonexistent/config.toml"])

    # Assert
    assert result.exit_code == 1
    assert "Configuration error:" in result.stdout


def test_cli_pipeline_runtime_error_handled(tmp_path: Path) -> None:
    """パイプライン処理中に例外が発生した場合に捕捉して exit 1 となることを検証する。"""
    # Arrange
    dummy_file = tmp_path / "sample.wav"
    dummy_file.write_bytes(b"DATA")

    with patch(
        "audio_transcriber.cli.run_pipeline",
        side_effect=RuntimeError("GPU Memory Exhausted"),
    ):
        # Act
        result = runner.invoke(app, [str(dummy_file)])

    # Assert
    assert result.exit_code == 1
    assert "Pipeline failed:" in result.stdout
    assert "GPU Memory Exhausted" in result.stdout


def test_cli_successful_run_prints_panel_and_table(tmp_path: Path) -> None:
    """正常実行時にステータスパネルおよび生成ファイル一覧テーブルが出力されることを検証する。"""
    # Arrange
    dummy_file = tmp_path / "stream_audio.wav"
    dummy_file.write_bytes(b"DATA")
    mock_res = PipelineResult(
        input_file=dummy_file,
        denoised_audio=tmp_path / "output" / "stream_audio_clean.wav",
        srt_file=tmp_path / "output" / "stream_audio.srt",
        transcript_text="実況テキスト",
        remuxed_video=None,
    )

    with patch("audio_transcriber.cli.run_pipeline", return_value=mock_res):
        # Act
        result = runner.invoke(app, [str(dummy_file), "-o", str(tmp_path / "output")])

    # Assert
    assert result.exit_code == 0
    assert "Audio Transcriber" in result.stdout
    assert "Generated Outputs" in result.stdout
    assert "Denoised Audio" in result.stdout
    assert "SRT Subtitle" in result.stdout
    assert "Done!" in result.stdout


def test_cli_options_override_config_file(tmp_path: Path) -> None:
    """設定ファイルで定義された値が CLI オプションで上書きされることを検証する。"""
    # Arrange
    dummy_file = tmp_path / "gameplay.mp4"
    dummy_file.write_bytes(b"DATA")
    cfg_file = tmp_path / "custom.toml"
    cfg_file.write_text(
        """
OUTPUT_DIR = "./toml_out"
[media]
MIC_TRACK = 1
[model]
MODEL_SIZE = "tiny"
""",
        encoding="utf-8",
    )

    mock_res = PipelineResult(
        input_file=dummy_file,
        denoised_audio=None,
        srt_file=tmp_path / "cli_out" / "gameplay.srt",
        transcript_text="字幕",
        remuxed_video=None,
    )

    with patch("audio_transcriber.cli.run_pipeline", return_value=mock_res) as mock_run:
        # Act
        result = runner.invoke(
            app,
            [
                str(dummy_file),
                "-C",
                str(cfg_file),
                "-o",
                str(tmp_path / "cli_out"),
                "-t",
                "3",
                "-m",
                "large-v3",
                "--prompt",
                "CLI優先プロンプト",
            ],
        )

    # Assert
    assert result.exit_code == 0
    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    cfg_arg = kwargs["cfg"]
    assert cfg_arg.paths.output_dir == tmp_path / "cli_out"
    assert cfg_arg.media.mic_track == 3
    assert cfg_arg.model.model_size == "large-v3"
    assert cfg_arg.transcribe.initial_prompt == "CLI優先プロンプト"
