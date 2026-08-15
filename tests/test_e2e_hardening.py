"""Tier 5 adversarial hardening and resilience tests.

非ASCIIパス、特殊文字、極端なパラメータ、不正設定、および例外カスケードに対する耐性を検証します。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from audio_transcriber.cli import app
from audio_transcriber.config import AppConfig, load_config, parse_config_dict
from audio_transcriber.pipeline import run_pipeline

runner = CliRunner()


def test_hardening_non_ascii_and_special_character_paths(
    tmp_path: Path,
    base_config: AppConfig,
    dummy_provider_class: type,
) -> None:
    """日本語・記号・空白を含むメディアファイルパスが正常に処理されることを検証する。"""
    # Arrange
    special_name = "【実況】テスト 動画 (2026) #1 [1080p] 特殊文字.mp4"
    special_file = tmp_path / special_name
    special_file.write_bytes(b"DATA")
    out_dir = tmp_path / "出力先 ディレクトリ (日本語)"

    base_config.paths.output_dir = out_dir
    base_config.media.mic_track = 2

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
        vad_filter=base_config.transcribe.vad.vad_filter,
        beam_size=base_config.transcribe.beam_size,
    )
    transcriber.transcribe_file = MagicMock(
        return_value=[{"start": 0.0, "end": 1.0, "text": "文字起こし"}]
    )

    with (
        patch(
            "audio_transcriber.pipeline.extract_audio_track", side_effect=fake_extract
        ),
        patch("audio_transcriber.pipeline.create_denoiser", return_value=mock_denoiser),
        patch("audio_transcriber.pipeline.remux_video", side_effect=fake_remux),
    ):
        # Act
        result = run_pipeline(
            input_path=special_file,
            cfg=base_config,
            denoise=True,
            transcribe=True,
            transcriber=transcriber,
        )

    # Assert
    stem = "【実況】テスト 動画 (2026) #1 [1080p] 特殊文字"
    assert result.input_file == special_file
    assert result.srt_file == out_dir / f"{stem}.srt"
    assert result.remuxed_video == out_dir / f"{stem}_clean.mp4"
    assert transcriber.kwargs["model_size"] == base_config.model.model_size
    assert transcriber.kwargs["vad_filter"] == base_config.transcribe.vad.vad_filter
    assert transcriber.kwargs["beam_size"] == base_config.transcribe.beam_size


def test_hardening_extreme_numeric_config_parameters() -> None:
    """極端に大きい数値や微小な浮動小数点数がエラーなく安全にパースされることを検証する。"""
    # Arrange
    raw_data = {
        "media": {
            "mic_track": 99,
            "sample_rate": 192000,
        },
        "transcribe": {
            "beam_size": 100,
            "no_speech_threshold": 0.9999,
            "vad": {
                "min_silence_duration_ms": 999999,
                "vad_threshold": 0.0001,
            },
        },
        "post_process": {
            "no_speech_threshold": 0.9999,
            "max_chars_per_second": 1000.0,
        },
        "subtitle": {
            "end_padding": 100.0,
            "min_duration": 100.0,
            "min_gap": 0.00001,
        },
    }

    # Act
    cfg = parse_config_dict(raw_data)

    # Assert
    assert cfg.media.mic_track == 99
    assert cfg.media.sample_rate == 192000
    assert cfg.transcribe.beam_size == 100
    assert cfg.transcribe.no_speech_threshold == 0.9999
    assert cfg.transcribe.vad.min_silence_duration_ms == 999999
    assert cfg.subtitle.end_padding == 100.0


def test_hardening_empty_zero_byte_media_file(
    tmp_path: Path,
    base_config: AppConfig,
    dummy_provider_class: type,
) -> None:
    """0バイトの空ファイルが入力された場合でもパイプラインが適切に動作することを検証する。"""
    # Arrange
    empty_file = tmp_path / "empty_input.wav"
    empty_file.write_bytes(b"")
    out_dir = tmp_path / "empty_out"

    base_config.paths.output_dir = out_dir

    mock_denoiser = MagicMock()
    mock_denoiser.denoise.side_effect = lambda inp, outp: outp.write_bytes(b"")

    transcriber = dummy_provider_class(
        model_size=base_config.model.model_size,
        vad_filter=base_config.transcribe.vad.vad_filter,
        beam_size=base_config.transcribe.beam_size,
    )
    transcriber.transcribe_file = MagicMock(return_value=[])

    with (
        patch("audio_transcriber.pipeline.create_denoiser", return_value=mock_denoiser),
    ):
        # Act
        result = run_pipeline(
            input_path=empty_file,
            cfg=base_config,
            denoise=True,
            transcribe=True,
            transcriber=transcriber,
        )

    # Assert
    assert result.input_file == empty_file
    assert result.denoised_audio == out_dir / "empty_input_clean.wav"
    assert result.srt_file == out_dir / "empty_input.srt"
    assert result.transcript_text == ""
    assert transcriber.kwargs["model_size"] == base_config.model.model_size
    assert transcriber.kwargs["vad_filter"] == base_config.transcribe.vad.vad_filter
    assert transcriber.kwargs["beam_size"] == base_config.transcribe.beam_size


def test_hardening_corrupted_toml_config_recovery(tmp_path: Path) -> None:
    """構文エラーを含む TOML 設定ファイルに対して安全に ValueError が送出されることを検証する。"""
    # Arrange
    corrupted_toml = tmp_path / "corrupted.toml"
    corrupted_toml.write_text("invalid_syntax = [[[[ 123", encoding="utf-8")

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        load_config(corrupted_toml)
    assert "Failed to parse TOML configuration" in str(exc_info.value)


def test_hardening_pipeline_exception_propagation_to_cli(tmp_path: Path) -> None:
    """パイプライン深層での OSError(ディスク容量不足等)が CLI で
    適切に捕捉されることを検証する。
    """
    # Arrange
    dummy_wav = tmp_path / "failing_audio.wav"
    dummy_wav.write_bytes(b"DATA")

    with patch(
        "audio_transcriber.cli.run_pipeline",
        side_effect=OSError("No space left on device"),
    ):
        # Act
        result = runner.invoke(app, [str(dummy_wav)])

    # Assert
    assert result.exit_code == 1
    assert "Pipeline failed:" in result.stdout
    assert "No space left on device" in result.stdout
