"""CLI メイン実行フロー、エラー終了ハンドリング、コールバック結合の単体テスト。"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from audio_transcriber.cli import app

runner = CliRunner()


def test_cli_config_error(tmp_path: Path) -> None:
    """設定ファイル読み込み失敗時に終了コード 1 で終了することを検証します。"""
    dummy_file = tmp_path / "gameplay.mp4"
    dummy_file.write_bytes(b"content")

    result = runner.invoke(
        app, [str(dummy_file), "--config", "/non/existent/config.toml"]
    )
    assert result.exit_code == 1
    assert "Configuration error:" in result.stdout


def test_cli_pipeline_failure(tmp_path: Path) -> None:
    """パイプライン実行中の例外が適切に処理され終了コード 1 で終了することを検証します。"""
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


def test_cli_successful_run_with_config(tmp_path: Path) -> None:
    """カスタム設定ファイルを読み込み、CLI オプションとマージして正常実行されることを検証します。"""
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
        cfg_arg = kwargs["cfg"]
        assert cfg_arg.paths.output_dir == Path("./custom_out")
        assert cfg_arg.media.mic_track == 3
        assert cfg_arg.model.model_size == "medium"
        assert cfg_arg.transcribe.initial_prompt == "Apex用語集"
        assert cfg_arg.pipeline.remux is False
        assert cfg_arg.transcribe.vad.min_silence_duration_ms == 700


def test_cli_streaming_log_and_callbacks_output(tmp_path: Path) -> None:
    """handle_progress および handle_segment の出力がストリーミングモードに応じて正しく行われることを検証します。"""
    dummy_file = tmp_path / "gameplay.mp4"
    dummy_file.write_bytes(b"content")

    def fake_run_pipeline(
        input_path: Any,
        cfg: Any,
        denoise: Any,
        transcribe: Any,
        on_progress: Any,
        on_segment: Any,
    ) -> MagicMock:
        on_progress("vad_chunks", [(0.0, 1.0)])
        on_progress("vad_chunk_start", (0.0, 1.0))
        on_progress(
            "whisper_raw",
            {"start": 0.0, "end": 1.0, "duration": 1.0, "text": "hello raw"},
        )
        on_progress("postprocess_dropped", "dropped msg")
        on_progress("postprocess_replaced", {"old_text": "旧", "new_text": "新"})
        on_progress("postprocess_overlap_prevented", "overlap msg")
        on_progress("postprocess_start", "start msg")
        on_progress("postprocess_summary", "summary msg")
        on_progress("text_confirmed", {"start": 0.0, "end": 1.0, "text": "hello"})
        on_progress("vad", "vad msg")
        on_progress("other", "other msg")
        on_segment({"start": 0.0, "end": 1.0, "text": "hello"})

        mock_result = MagicMock()
        mock_result.remuxed_video = None
        mock_result.denoised_audio = None
        mock_result.srt_file = None
        mock_result.raw_segments = [{"start": 1.0, "end": 2.0, "text": "hello"}]
        mock_result.processing_events = [
            {"start": 1.0, "type": "無音捏造等除外", "message": "msg1"}
        ]
        return mock_result

    with patch("audio_transcriber.cli.run_pipeline", side_effect=fake_run_pipeline):
        # 1. streaming_log = True
        res_stream = runner.invoke(app, [str(dummy_file), "--streaming-log"])
        assert res_stream.exit_code == 0
        assert "[VAD]" in res_stream.stdout
        assert "dropped msg" in res_stream.stdout
        assert "[Whisper]" in res_stream.stdout
        assert "[Text]" in res_stream.stdout

        # 2. streaming_log = False
        res_no_stream = runner.invoke(app, [str(dummy_file), "--no-streaming-log"])
        assert res_no_stream.exit_code == 0
        assert "[VAD]" not in res_no_stream.stdout
        assert "[Whisper]" not in res_no_stream.stdout
        assert "[Text]" in res_no_stream.stdout
        assert "hello" in res_no_stream.stdout
