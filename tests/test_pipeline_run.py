"""パイプライン実行オーケストレーション (音声・動画・コールバック・時間補正) の単体テスト。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audio_transcriber.config import AppConfig
from audio_transcriber.pipeline import run_pipeline


def test_run_pipeline_audio_file(
    tmp_path: Path,
    base_config: AppConfig,
    dummy_provider_class: type,
) -> None:
    """音声ファイルを直接処理するパイプライン実行フローを検証する。"""
    dummy_wav = tmp_path / "mic_input.wav"
    dummy_wav.write_bytes(b"RIFFdummydata")
    out_dir = tmp_path / "output"
    base_config.paths.output_dir = out_dir

    mock_denoiser = MagicMock()

    def fake_denoise(inp: Path, outp: Path) -> Path:
        outp.write_bytes(b"clean")
        return outp

    mock_denoiser.denoise.side_effect = fake_denoise

    transcriber = dummy_provider_class(
        model_size=base_config.model.model_size,
        beam_size=base_config.transcribe.beam_size,
    )

    result = run_pipeline(
        input_path=dummy_wav,
        cfg=base_config,
        denoise=True,
        transcribe=True,
        denoiser=mock_denoiser,
        transcriber=transcriber,
    )

    assert transcriber.kwargs["model_size"] == base_config.model.model_size
    assert transcriber.kwargs["beam_size"] == base_config.transcribe.beam_size

    assert result.input_file == dummy_wav
    assert result.denoised_audio == out_dir / "mic_input_clean.wav"
    assert result.srt_file == out_dir / "mic_input.srt"
    assert "テスト" in str(result.transcript_text)
    assert result.remuxed_video is None
    mock_denoiser.denoise.assert_called_once()


def test_run_pipeline_video_file_with_remux(
    tmp_path: Path,
    base_config: AppConfig,
    dummy_provider_class: type,
) -> None:
    """動画ファイルを音声抽出・ノイズ除去・文字起こし・再多重化するパイプラインフローを検証する。"""
    dummy_mp4 = tmp_path / "gameplay.mp4"
    dummy_mp4.write_bytes(b"dummy_mp4_content")
    out_dir = tmp_path / "output"
    base_config.paths.output_dir = out_dir
    base_config.media.mic_track = 2
    base_config.pipeline.remux = True

    mock_denoiser = MagicMock()

    def fake_extract(media_path: Path, track_number: int, output_wav: Path) -> Path:
        output_wav.write_bytes(b"extracted_audio")
        return output_wav

    def fake_denoise(inp: Path, outp: Path) -> Path:
        outp.write_bytes(b"clean_audio")
        return outp

    def fake_remux(
        original_video: Path,
        mic_track_number: int,
        clean_audio: Path,
        output_video: Path,
    ) -> Path:
        output_video.write_bytes(b"clean_video")
        return output_video

    mock_denoiser.denoise.side_effect = fake_denoise

    transcriber = dummy_provider_class(
        model_size=base_config.model.model_size,
        beam_size=base_config.transcribe.beam_size,
    )

    with (
        patch(
            "audio_transcriber.pipeline.extract_audio_track", side_effect=fake_extract
        ) as mock_extract,
        patch("audio_transcriber.pipeline.create_denoiser", return_value=mock_denoiser),
        patch(
            "audio_transcriber.pipeline.remux_video", side_effect=fake_remux
        ) as mock_remux,
    ):
        result = run_pipeline(
            input_path=dummy_mp4,
            cfg=base_config,
            denoise=True,
            transcribe=True,
            transcriber=transcriber,
        )

    assert transcriber.kwargs["model_size"] == base_config.model.model_size
    assert transcriber.kwargs["beam_size"] == base_config.transcribe.beam_size

    assert result.input_file == dummy_mp4
    assert result.denoised_audio == out_dir / "gameplay_clean.wav"
    assert result.srt_file == out_dir / "gameplay.srt"
    assert result.remuxed_video == out_dir / "gameplay_clean.mp4"
    assert "テスト" in str(result.transcript_text)
    mock_extract.assert_called_once()
    mock_remux.assert_called_once()
    mock_denoiser.denoise.assert_called_once()


def test_run_pipeline_triggers_progress_and_segment_callbacks(
    tmp_path: Path,
    base_config: AppConfig,
    dummy_provider_class: type,
) -> None:
    """各ステージにおける on_progress および on_segment コールバックの発火を検証する。"""
    dummy_wav = tmp_path / "mic_input.wav"
    dummy_wav.write_bytes(b"RIFFdummydata")
    out_dir = tmp_path / "output"
    base_config.paths.output_dir = out_dir

    progress_events: list[str] = []
    segment_events: list[str] = []

    def on_progress(stage: str, message: str) -> None:
        progress_events.append(f"{stage}: {message}")

    def on_segment(seg_dict: dict[str, object]) -> None:
        segment_events.append(str(seg_dict.get("text", "")))

    mock_denoiser = MagicMock()
    mock_denoiser.denoise.side_effect = lambda inp, outp: outp

    transcriber = dummy_provider_class(
        model_size=base_config.model.model_size,
        beam_size=base_config.transcribe.beam_size,
    )

    result = run_pipeline(
        input_path=dummy_wav,
        cfg=base_config,
        denoise=True,
        transcribe=True,
        denoiser=mock_denoiser,
        transcriber=transcriber,
        on_progress=on_progress,
        on_segment=on_segment,
    )

    assert result.input_file == dummy_wav
    assert transcriber.kwargs["model_size"] == base_config.model.model_size
    assert transcriber.kwargs["beam_size"] == base_config.transcribe.beam_size

    assert len(progress_events) >= 2
    assert len(segment_events) == 1
    assert "テスト" in segment_events[0]


def test_run_pipeline_applies_timecode_offset(
    tmp_path: Path,
    base_config: AppConfig,
    dummy_provider_class: type,
) -> None:
    """動画のタイムコードオフセットが字幕タイムスタンプに適用されることを検証する。"""
    dummy_mov = tmp_path / "clip.mov"
    dummy_mov.write_bytes(b"dummy_mov")
    out_dir = tmp_path / "output"
    base_config.paths.output_dir = out_dir
    base_config.pipeline.remux = False

    def fake_extract(media_path: Path, track_number: int, output_wav: Path) -> Path:
        output_wav.write_bytes(b"raw_wav")
        return output_wav

    transcriber = dummy_provider_class(
        model_size=base_config.model.model_size,
        beam_size=base_config.transcribe.beam_size,
    )

    with (
        patch("audio_transcriber.pipeline.is_video_file", return_value=True),
        patch(
            "audio_transcriber.pipeline.extract_audio_track", side_effect=fake_extract
        ),
        patch("audio_transcriber.pipeline.get_timecode_offset", return_value=100.0),
        patch(
            "audio_transcriber.pipeline.create_denoiser",
            return_value=MagicMock(denoise=lambda i, o: o.write_bytes(b"c")),
        ),
        patch("audio_transcriber.pipeline.remux_video", return_value=None),
    ):
        result = run_pipeline(
            input_path=dummy_mov,
            cfg=base_config,
            denoise=False,
            transcribe=True,
            transcriber=transcriber,
        )

    assert transcriber.kwargs["model_size"] == base_config.model.model_size
    assert transcriber.kwargs["beam_size"] == base_config.transcribe.beam_size

    assert result.srt_file is not None
    srt_content = result.srt_file.read_text(encoding="utf-8")
    assert "00:01:40,000" in srt_content
    assert "テスト" in srt_content


def test_pipeline_abort_on_extraction_error(tmp_path: Path) -> None:
    """音声抽出例外発生時に握りつぶさず正しく例外が送出されることを検証。"""
    mock_extract = MagicMock(side_effect=RuntimeError("extract error failed"))
    with (
        patch("audio_transcriber.pipeline.extract_audio_track", mock_extract),
        patch("audio_transcriber.pipeline.is_video_file", return_value=True),
    ):
        in_video = tmp_path / "test_video.mp4"
        in_video.write_text("dummy")
        with pytest.raises(RuntimeError, match="extract error failed"):
            run_pipeline(in_video, AppConfig(), denoise=False, transcribe=False)
