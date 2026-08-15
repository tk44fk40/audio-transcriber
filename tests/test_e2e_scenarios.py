"""Tier 4 real-world workload scenario tests (Scenarios 1-5).

ゲーム実況、技術講演、対談、高ノイズ環境、
DaVinci Resolve CLIワークフロー等の実運用シナリオを検証します。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from audio_transcriber.cli import app
from audio_transcriber.config import AppConfig
from audio_transcriber.pipeline import PipelineResult, run_pipeline

runner = CliRunner()


def test_scenario_1_gaming_commentary_multitrack(
    tmp_path: Path,
    base_config: AppConfig,
    dummy_provider_class: type,
) -> None:
    """シナリオ1: ゲーム実況動画のマルチトラック処理・ノイズ除去・字幕・再結合を検証する。"""
    # Arrange
    game_video = tmp_path / "apex_match.mp4"
    game_video.write_bytes(b"MP4_GAMEPLAY")
    out_dir = tmp_path / "scenario1_out"

    base_config.paths.output_dir = out_dir
    base_config.media.mic_track = 2
    base_config.transcribe.initial_prompt = "Apex, ヴァルキリー, クレーバー"

    def fake_extract(media_path: Path, track_number: int, output_wav: Path) -> Path:
        output_wav.write_bytes(b"TRACK2_RAW")
        return output_wav

    def fake_denoise(inp: Path, outp: Path, **kwargs) -> Path:
        outp.write_bytes(b"TRACK2_CLEAN")
        return outp

    def fake_remux(
        original_video: Path,
        mic_track_number: int,
        clean_audio: Path,
        output_video: Path,
    ) -> Path:
        output_video.write_bytes(b"REMUXED_VIDEO")
        return output_video

    mock_denoiser = MagicMock()
    mock_denoiser.denoise.side_effect = fake_denoise

    transcriber = dummy_provider_class(
        model_size=base_config.model.model_size,
        vad_filter=base_config.transcribe.vad.vad_filter,
        beam_size=base_config.transcribe.beam_size,
        initial_prompt=base_config.transcribe.initial_prompt,
    )

    def fake_transcribe(file_path, on_segment=None, on_progress=None):
        if on_segment:
            on_segment({"start": 1.0, "end": 2.5, "text": "ナイス!"})
        return []

    transcriber.transcribe_file = MagicMock(side_effect=fake_transcribe)

    with (
        patch(
            "audio_transcriber.pipeline.extract_audio_track", side_effect=fake_extract
        ),
        patch("audio_transcriber.pipeline.create_denoiser", return_value=mock_denoiser),
        patch("audio_transcriber.pipeline.remux_video", side_effect=fake_remux),
    ):
        # Act
        result = run_pipeline(
            input_path=game_video,
            cfg=base_config,
            denoise=True,
            transcribe=True,
            transcriber=transcriber,
        )

    # Assert
    assert result.remuxed_video == out_dir / "apex_match_clean.mp4"
    assert result.denoised_audio == out_dir / "apex_match_clean.wav"
    assert result.srt_file == out_dir / "apex_match.srt"
    assert "ナイス!" in str(result.transcript_text)
    assert transcriber.kwargs["model_size"] == base_config.model.model_size
    assert transcriber.kwargs["vad_filter"] == base_config.transcribe.vad.vad_filter
    assert transcriber.kwargs["beam_size"] == base_config.transcribe.beam_size


def test_scenario_2_technical_keynote_transcribe_only(
    tmp_path: Path,
    base_config: AppConfig,
    dummy_provider_class: type,
) -> None:
    """シナリオ2: 専門用語プロンプトを用いた長尺技術講演音声の文字起こし単体フローを検証する。"""
    # Arrange
    keynote_wav = tmp_path / "ai_keynote.wav"
    keynote_wav.write_bytes(b"KEYNOTE_AUDIO")
    out_dir = tmp_path / "scenario2_out"

    base_config.paths.output_dir = out_dir
    base_config.model.model_size = "large-v3"
    base_config.transcribe.initial_prompt = "DeepFilterNet, faster-whisper, 第VIII章"

    transcriber = dummy_provider_class(
        model_size=base_config.model.model_size,
        vad_filter=base_config.transcribe.vad.vad_filter,
        beam_size=base_config.transcribe.beam_size,
        initial_prompt=base_config.transcribe.initial_prompt,
    )

    def fake_transcribe(file_path, on_segment=None, on_progress=None):
        if on_segment:
            on_segment({"start": 0.0, "end": 5.0, "text": "第VIII章の解説を行います"})
        return []

    transcriber.transcribe_file = MagicMock(side_effect=fake_transcribe)

    # Act
    result = run_pipeline(
        input_path=keynote_wav,
        cfg=base_config,
        denoise=False,
        transcribe=True,
        transcriber=transcriber,
    )

    # Assert
    assert result.denoised_audio is None
    assert result.srt_file == out_dir / "ai_keynote.srt"
    assert "第VIII章" in str(result.transcript_text)
    transcriber.transcribe_file.assert_called_once()
    assert transcriber.kwargs["model_size"] == "large-v3"
    assert "第VIII章" in transcriber.kwargs["initial_prompt"]


def test_scenario_3_conversational_turn_taking_vad(
    tmp_path: Path,
    base_config: AppConfig,
    dummy_provider_class: type,
) -> None:
    """シナリオ3: 発話交代の多い対談音声に対する短無音区間 VAD パラメータ適用を検証する。"""
    # Arrange
    dialogue_wav = tmp_path / "interview_turn_taking.wav"
    dialogue_wav.write_bytes(b"DIALOGUE_AUDIO")
    out_dir = tmp_path / "scenario3_out"

    base_config.paths.output_dir = out_dir
    base_config.transcribe.vad.vad_filter = True
    base_config.transcribe.vad.min_silence_duration_ms = 300

    transcriber = dummy_provider_class(
        model_size=base_config.model.model_size,
        vad_filter=base_config.transcribe.vad.vad_filter,
        beam_size=base_config.transcribe.beam_size,
        vad_parameters={
            "min_silence_duration_ms": base_config.transcribe.vad.min_silence_duration_ms
        },
    )

    def fake_transcribe(file_path, on_segment=None, on_progress=None):
        if on_segment:
            on_segment({"start": 0.5, "end": 2.0, "text": "そうですね"})
        return []

    transcriber.transcribe_file = MagicMock(side_effect=fake_transcribe)

    # Act
    result = run_pipeline(
        input_path=dialogue_wav,
        cfg=base_config,
        denoise=False,
        transcribe=True,
        transcriber=transcriber,
    )

    # Assert
    assert result.srt_file == out_dir / "interview_turn_taking.srt"
    transcriber.transcribe_file.assert_called_once()
    assert transcriber.kwargs["vad_filter"] is True
    assert transcriber.kwargs["vad_parameters"]["min_silence_duration_ms"] == 300


def test_scenario_4_high_noise_podcast_denoise_and_transcribe(
    tmp_path: Path,
    base_config: AppConfig,
    dummy_provider_class: type,
) -> None:
    """シナリオ4: エアコン等の定常ノイズが多いポッドキャスト録音の
    ノイズ除去・文字起こしを検証する。
    """
    # Arrange
    noisy_podcast = tmp_path / "noisy_studio_podcast.wav"
    noisy_podcast.write_bytes(b"NOISY_AUDIO")
    out_dir = tmp_path / "scenario4_out"

    base_config.paths.output_dir = out_dir
    base_config.transcribe.vad.min_silence_duration_ms = 800

    mock_denoiser = MagicMock()
    mock_denoiser.denoise.side_effect = lambda inp, outp: outp.write_bytes(
        b"CLEAN_PODCAST"
    )

    transcriber = dummy_provider_class(
        model_size=base_config.model.model_size,
        vad_filter=base_config.transcribe.vad.vad_filter,
        beam_size=base_config.transcribe.beam_size,
        vad_parameters={
            "min_silence_duration_ms": base_config.transcribe.vad.min_silence_duration_ms
        },
    )

    def fake_transcribe(file_path, on_segment=None, on_progress=None):
        if on_segment:
            on_segment({"start": 1.0, "end": 4.0, "text": "本日のテーマは音声認識です"})
        return []

    transcriber.transcribe_file = MagicMock(side_effect=fake_transcribe)

    with patch(
        "audio_transcriber.pipeline.create_denoiser", return_value=mock_denoiser
    ):
        # Act
        result = run_pipeline(
            input_path=noisy_podcast,
            cfg=base_config,
            denoise=True,
            transcribe=True,
            transcriber=transcriber,
        )

    # Assert
    assert result.denoised_audio == out_dir / "noisy_studio_podcast_clean.wav"
    assert result.srt_file == out_dir / "noisy_studio_podcast.srt"
    assert "本日のテーマ" in str(result.transcript_text)
    assert transcriber.kwargs["model_size"] == base_config.model.model_size
    assert transcriber.kwargs["vad_filter"] == base_config.transcribe.vad.vad_filter
    assert transcriber.kwargs["beam_size"] == base_config.transcribe.beam_size


def test_scenario_5_davinci_resolve_cli_workflow(tmp_path: Path) -> None:
    """シナリオ5: TOML 設定・CLI 上書き・DaVinci Resolve 向け
    字幕生成の完全ワークフローを検証する。
    """
    # Arrange
    input_video = tmp_path / "editor_project.mp4"
    input_video.write_bytes(b"MP4_DATA")
    cfg_file = tmp_path / "davinci_config.toml"
    cfg_file.write_text(
        """
OUTPUT_DIR = "./davinci_out"
[pipeline]
REMUX = true
[media]
MIC_TRACK = 2
""",
        encoding="utf-8",
    )

    mock_res = PipelineResult(
        input_file=input_video,
        denoised_audio=tmp_path / "davinci_out" / "editor_project_clean.wav",
        srt_file=tmp_path / "davinci_out" / "editor_project.srt",
        transcript_text="DaVinci字幕",
        remuxed_video=tmp_path / "davinci_out" / "editor_project_clean.mp4",
    )

    with patch(
        "audio_transcriber.cli.run_pipeline", return_value=mock_res
    ) as mock_pipe:
        # Act
        result = runner.invoke(
            app,
            [
                str(input_video),
                "-C",
                str(cfg_file),
                "-o",
                str(tmp_path / "davinci_out"),
                "--prompt",
                "DaVinci Resolve 編集プロジェクト",
            ],
        )

    # Assert
    assert result.exit_code == 0
    assert "Generated Outputs" in result.stdout
    assert "Clean Video (Remuxed)" in result.stdout
    assert "SRT Subtitle" in result.stdout
    mock_pipe.assert_called_once()
    _, kwargs = mock_pipe.call_args
    assert kwargs["cfg"].paths.output_dir == tmp_path / "davinci_out"
    assert kwargs["cfg"].transcribe.initial_prompt == "DaVinci Resolve 編集プロジェクト"
