"""Unit tests for pluggable audio denoise module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audio_transcriber.config import DenoiseConfig
from audio_transcriber.denoise import (
    AudioDenoiser,
    PassThroughDenoiser,
    RNNoiseDenoiser,
    create_denoiser,
)


def test_audio_denoiser_protocol_runtime_checkable():
    """AudioDenoiser Protocol is runtime checkable."""
    passthrough = PassThroughDenoiser()
    rnnoise = RNNoiseDenoiser()

    assert isinstance(passthrough, AudioDenoiser)
    assert isinstance(rnnoise, AudioDenoiser)


def test_passthrough_denoiser_success(tmp_path: Path):
    """PassThroughDenoiser copies input audio to output destination."""
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "out" / "output.wav"
    input_wav.write_bytes(b"dummy audio data")

    denoiser = PassThroughDenoiser()
    result = denoiser.denoise(input_wav, output_wav)

    assert result == output_wav.resolve()
    assert output_wav.exists()
    assert output_wav.read_bytes() == b"dummy audio data"


def test_passthrough_denoiser_missing_input(tmp_path: Path):
    """PassThroughDenoiser raises RuntimeError when input does not exist."""
    input_wav = tmp_path / "missing.wav"
    output_wav = tmp_path / "output.wav"

    denoiser = PassThroughDenoiser()
    with pytest.raises(RuntimeError, match="入力音声ファイルが存在しません"):
        denoiser.denoise(input_wav, output_wav)


def test_passthrough_denoiser_copy_failure(tmp_path: Path):
    """PassThroughDenoiser raises RuntimeError when copy fails."""
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "output.wav"
    input_wav.write_bytes(b"data")

    denoiser = PassThroughDenoiser()
    with (
        patch("shutil.copy2", side_effect=PermissionError("Denied")),
        pytest.raises(RuntimeError, match="音声ファイルのコピーに失敗しました"),
    ):
        denoiser.denoise(input_wav, output_wav)


def test_rnnoise_denoiser_default_success(tmp_path: Path):
    """RNNoiseDenoiser invokes ffmpeg with arnndn filter."""
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "clean" / "output.wav"
    input_wav.write_bytes(b"input data")

    denoiser = RNNoiseDenoiser()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = denoiser.denoise(input_wav, output_wav)

        assert result == output_wav.resolve()
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "ffmpeg" in cmd
        assert "-af" in cmd
        filter_idx = cmd.index("-af") + 1
        assert "aresample=48000,arnndn" in cmd[filter_idx]


def test_rnnoise_denoiser_with_model(tmp_path: Path):
    """RNNoiseDenoiser specifies model path in arnndn filter."""
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "output.wav"
    model_file = tmp_path / "custom.rnnn"
    input_wav.write_bytes(b"input data")
    model_file.write_bytes(b"model data")

    denoiser = RNNoiseDenoiser(model_path=model_file)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = denoiser.denoise(input_wav, output_wav)

        assert result == output_wav.resolve()
        cmd = mock_run.call_args[0][0]
        filter_idx = cmd.index("-af") + 1
        assert f"arnndn=m={model_file.resolve()}" in cmd[filter_idx]


def test_rnnoise_denoiser_missing_input(tmp_path: Path):
    """RNNoiseDenoiser raises RuntimeError when input audio is missing."""
    input_wav = tmp_path / "missing.wav"
    output_wav = tmp_path / "output.wav"

    denoiser = RNNoiseDenoiser()
    with pytest.raises(RuntimeError, match="入力音声ファイルが存在しません"):
        denoiser.denoise(input_wav, output_wav)


def test_rnnoise_denoiser_missing_model(tmp_path: Path):
    """RNNoiseDenoiser raises RuntimeError when specified model does not exist."""
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "output.wav"
    input_wav.write_bytes(b"data")
    missing_model = tmp_path / "missing.rnnn"

    denoiser = RNNoiseDenoiser(model_path=missing_model)
    with pytest.raises(
        RuntimeError, match="指定された RNNoise モデルファイルが見つかりません"
    ):
        denoiser.denoise(input_wav, output_wav)


def test_rnnoise_denoiser_ffmpeg_failure(tmp_path: Path):
    """RNNoiseDenoiser raises RuntimeError when FFmpeg command returns non-zero."""
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "output.wav"
    input_wav.write_bytes(b"data")

    denoiser = RNNoiseDenoiser()
    with (
        patch("subprocess.run") as mock_run,
        pytest.raises(RuntimeError, match="RNNoise ノイズ除去処理に失敗しました"),
    ):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Error decoding"
        )
        denoiser.denoise(input_wav, output_wav)


def test_rnnoise_denoiser_subprocess_exception(tmp_path: Path):
    """RNNoiseDenoiser raises RuntimeError when subprocess execution fails."""
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "output.wav"
    input_wav.write_bytes(b"data")

    denoiser = RNNoiseDenoiser()
    with (
        patch("subprocess.run", side_effect=OSError("ffmpeg not found")),
        pytest.raises(RuntimeError, match="FFmpeg の起動に失敗しました"),
    ):
        denoiser.denoise(input_wav, output_wav)


def test_create_denoiser_factory_default():
    """create_denoiser returns RNNoiseDenoiser by default."""
    denoiser = create_denoiser()
    assert isinstance(denoiser, RNNoiseDenoiser)
    assert denoiser.model_path is None


def test_create_denoiser_factory_disabled():
    """create_denoiser returns PassThroughDenoiser when enabled=False."""
    cfg = DenoiseConfig(enabled=False, engine="rnnoise")
    denoiser = create_denoiser(cfg)
    assert isinstance(denoiser, PassThroughDenoiser)


def test_create_denoiser_factory_passthrough_engines():
    """create_denoiser recognizes 'none' and 'passthrough' engines."""
    for eng in ["none", "passthrough", "disabled"]:
        cfg = DenoiseConfig(enabled=True, engine=eng)
        denoiser = create_denoiser(cfg)
        assert isinstance(denoiser, PassThroughDenoiser)


def test_create_denoiser_factory_rnnoise_custom_model(tmp_path: Path):
    """create_denoiser correctly passes model_path to RNNoiseDenoiser."""
    model_file = tmp_path / "model.rnnn"
    cfg = DenoiseConfig(enabled=True, engine="rnnoise", model_path=model_file)
    denoiser = create_denoiser(cfg)
    assert isinstance(denoiser, RNNoiseDenoiser)
    assert denoiser.model_path == model_file.resolve()


def test_create_denoiser_factory_unknown_engine():
    """create_denoiser raises ValueError for unknown engine names."""
    cfg = DenoiseConfig(enabled=True, engine="unknown-engine")
    with pytest.raises(ValueError, match="サポートされていないノイズ除去エンジンです"):
        create_denoiser(cfg)
