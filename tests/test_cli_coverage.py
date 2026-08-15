from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from audio_transcriber.cli import app

runner = CliRunner()


def test_cli_coverage_callbacks_and_logging(tmp_path: Path) -> None:
    dummy_file = tmp_path / "gameplay.mp4"
    dummy_file.write_bytes(b"content")

    mock_result = MagicMock()
    mock_result.remuxed_video = None
    mock_result.denoised_audio = None
    mock_result.srt_file = None
    mock_result.vad_chunks = []
    mock_result.raw_segments = [
        {"start": 1.0, "end": 2.0, "text": "hello"},
        {"start": 2.5, "end": 3.0, "text": "world"},
        {"start": 5.0, "end": 6.0, "text": "unmatched"},
    ]
    mock_result.processing_events = [
        {"start": 1.0, "type": "無音捏造等除外", "message": "msg1"},
        {"start": 1.0, "type": "テキスト置換", "message": "msg2"},
        {"start": 1.0, "type": "重複防止", "message": "msg3"},
        {"start": 2.5, "type": "不明なイベント", "message": "msg4"},
    ]

    def fake_run_pipeline(*args, **kwargs):
        on_progress = kwargs["on_progress"]
        on_segment = kwargs["on_segment"]

        on_progress("vad_chunks", [(0.0, 1.0)])
        on_progress("postprocess_dropped", "ignore")
        on_progress("postprocess_replaced", "ignore")
        on_progress("postprocess_overlap_prevented", "ignore")
        on_progress("postprocess_start", "start")
        on_progress("postprocess_summary", "summary")
        on_progress("vad", "vad msg")
        on_progress("other_stage", "other")

        on_segment({"start": 0.0, "end": 1.5, "text": "seg"})
        on_segment({})
        return mock_result

    with (
        patch("audio_transcriber.cli.run_pipeline", side_effect=fake_run_pipeline),
        patch("audio_transcriber.cli.console.print") as mock_print,
    ):
        result = runner.invoke(app, [str(dummy_file), "--no-streaming-log"])
        assert result.exit_code == 0
        mock_print.assert_any_call("[bold cyan]▶ [postprocess][/bold cyan] start")


def test_cli_coverage_misc(tmp_path: Path) -> None:
    dummy_file = tmp_path / "gameplay.mp4"
    dummy_file.write_bytes(b"content")

    # cover --denoise-only and --transcribe-only at the same time
    result = runner.invoke(
        app, [str(dummy_file), "--denoise-only", "--transcribe-only"]
    )
    assert result.exit_code == 1

    # invalid config
    result = runner.invoke(app, [str(dummy_file), "--config", "invalid.toml"])
    assert result.exit_code == 1

    # no input file
    with patch("audio_transcriber.cli.load_config") as mock_cfg:
        mock_cfg.return_value = MagicMock(default_video_path=None)
        result = runner.invoke(app, [])
        assert result.exit_code == 2

    # non-existent input file
    with patch("audio_transcriber.cli.load_config") as mock_cfg:
        mock_cfg.return_value = MagicMock(
            default_video_path=tmp_path / "nonexistent.mp4"
        )
        result = runner.invoke(app, [])
        assert result.exit_code == 2

    # options combinations
    with patch("audio_transcriber.cli.run_pipeline"):
        # device cpu + float16 -> int8
        result = runner.invoke(
            app,
            [
                str(dummy_file),
                "--device",
                "cpu",
                "--compute-type",
                "float16",
                "--denoise-only",
            ],
        )
        assert result.exit_code == 0

        result = runner.invoke(app, [str(dummy_file), "--transcribe-only"])
        assert result.exit_code == 0

        # remux and vad options
        result = runner.invoke(
            app,
            [
                str(dummy_file),
                "--output-dir",
                str(tmp_path),
                "--mic-track",
                "1",
                "--model-size",
                "base",
                "--language",
                "en",
                "--prompt",
                "hello",
                "--denoise",
                "--remux",
                "--no-vad",
                "--min-silence-ms",
                "100",
                "--mastering-enabled",
                "--noise-gate-threshold",
                "0.01",
                "--loudness-i",
                "-14",
                "--loudness-tp",
                "-1",
                "--loudness-lra",
                "10",
                "--final-limit-db",
                "-1",
            ],
        )
        assert result.exit_code == 0

    # pipeline failure
    with patch("audio_transcriber.cli.run_pipeline", side_effect=Exception("error")):
        result = runner.invoke(app, [str(dummy_file)])
        assert result.exit_code == 1


def test_cli_all_arguments(tmp_path: Path) -> None:
    """Test that all CLI arguments override config correctly to ensure 100% coverage."""
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

        # Just verifying they got set avoids coverage drop
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


def test_cli_streaming_log_callbacks(tmp_path: Path) -> None:
    """Test handle_progress and handle_segment when streaming_log is True."""
    dummy_file = tmp_path / "gameplay.mp4"
    dummy_file.write_bytes(b"content")

    # We mock run_pipeline to simulate calling the callbacks
    def fake_run_pipeline(
        input_path, cfg, denoise, transcribe, on_progress, on_segment
    ):
        # Call all progress stages
        on_progress("vad_chunks", [(0.0, 1.0)])
        on_progress("postprocess_dropped", "dropped msg")
        on_progress("postprocess_replaced", "replaced msg")
        on_progress("postprocess_overlap_prevented", "overlap msg")
        on_progress("postprocess_start", "start msg")
        on_progress("postprocess_summary", "summary msg")
        on_progress("vad_chunk_start", (0.0, 1.0))
        on_progress("vad", "vad msg")
        on_progress("other", "other msg")
        on_segment({"start": 0.0, "end": 1.0, "text": "hello"})

        mock_result = MagicMock()
        mock_result.remuxed_video = None
        mock_result.denoised_audio = None
        mock_result.srt_file = None
        return mock_result

    with patch("audio_transcriber.cli.run_pipeline", side_effect=fake_run_pipeline):
        result = runner.invoke(app, [str(dummy_file), "--streaming-log"])
        assert result.exit_code == 0
        assert "[VAD]" in result.stdout
        assert "dropped msg" in result.stdout
        assert "replaced msg" in result.stdout
        assert "overlap msg" in result.stdout
        assert "start msg" in result.stdout
        assert "summary msg" in result.stdout
        assert "vad msg" in result.stdout
        assert "other msg" in result.stdout
        assert "[Whisper生]" in result.stdout


def test_cli_no_streaming_log_callbacks(tmp_path: Path) -> None:
    """Test handle_progress and handle_segment when streaming_log is False."""
    dummy_file = tmp_path / "gameplay.mp4"
    dummy_file.write_bytes(b"content")

    def fake_run_pipeline(
        input_path, cfg, denoise, transcribe, on_progress, on_segment
    ):
        on_progress("vad_chunks", [(0.0, 1.0)])
        on_progress("postprocess_dropped", "dropped msg")
        on_progress("postprocess_replaced", "replaced msg")
        on_progress("postprocess_overlap_prevented", "overlap msg")
        on_segment({"start": 0.0, "end": 1.0, "text": "hello"})

        mock_result = MagicMock()
        mock_result.remuxed_video = None
        mock_result.denoised_audio = None
        mock_result.srt_file = None
        return mock_result

    with patch("audio_transcriber.cli.run_pipeline", side_effect=fake_run_pipeline):
        result = runner.invoke(app, [str(dummy_file), "--no-streaming-log"])
        assert result.exit_code == 0
        assert "[VAD]" not in result.stdout
        assert "dropped msg" not in result.stdout
        assert "replaced msg" not in result.stdout
        assert "hello" in result.stdout
