"""設定データクラス構造およびデフォルト値の単体テスト。"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from audio_transcriber.config import (
    AppConfig,
    DenoiseConfig,
    MasteringConfig,
    MediaConfig,
    ModelConfig,
    PathConfig,
    PipelineConfig,
    PostProcessConfig,
    SubtitleConfig,
    TranscribeConfig,
    VadConfig,
)


def test_default_config_instances() -> None:
    """各設定データクラスのデフォルト値が正しく初期化されることを検証する。"""
    # Arrange & Act
    paths_cfg = PathConfig()
    denoise_cfg = DenoiseConfig()
    post_cfg = PostProcessConfig()
    sub_cfg = SubtitleConfig()
    mastering_cfg = MasteringConfig()
    app_cfg = AppConfig()

    # Assert - PathConfig defaults
    assert (paths_cfg.output_dir, paths_cfg.default_video_path) == (
        Path("./output"),
        None,
    )
    assert (paths_cfg.debug_output_dir, paths_cfg.custom_dict_path) == (None, None)

    # Assert - DenoiseConfig defaults
    assert (denoise_cfg.enabled, denoise_cfg.engine, denoise_cfg.model_path) == (
        True,
        "rnnoise",
        None,
    )

    # Assert - PostProcessConfig defaults
    assert post_cfg.replace_terms is True
    assert (post_cfg.lower, post_cfg.remove_punct) == (False, False)
    assert (post_cfg.no_speech_threshold, post_cfg.max_chars_per_second) == (0.6, 12.0)

    # Assert - SubtitleConfig defaults
    assert (sub_cfg.end_padding, sub_cfg.min_duration, sub_cfg.min_gap) == (
        1.0,
        1.5,
        0.05,
    )
    assert sub_cfg.formats == ["srt", "vtt", "json"]

    # Assert - MasteringConfig defaults
    assert mastering_cfg.enabled is False
    assert mastering_cfg.noise_gate_threshold == 0.04
    assert mastering_cfg.loudness_i == -16.0
    assert mastering_cfg.loudness_tp == -2.0
    assert mastering_cfg.loudness_lra == 11.0
    assert mastering_cfg.final_limit_db == -2.0

    # Assert - AppConfig root defaults
    assert (app_cfg.output_dir, app_cfg.default_video_path) == (Path("./output"), None)
    assert (app_cfg.debug_output_dir, app_cfg.custom_dict_path) == (None, None)
    assert app_cfg.paths == paths_cfg
    assert app_cfg.pipeline == PipelineConfig(remux=True)
    assert app_cfg.denoise == denoise_cfg
    assert app_cfg.media == MediaConfig(mic_track=2, sample_rate=48000)
    assert app_cfg.model == ModelConfig(
        model_size="small", device="cuda", compute_type="float16"
    )
    assert app_cfg.transcribe == TranscribeConfig(
        language="ja",
        beam_size=5,
        condition_on_previous_text=True,
        no_speech_threshold=0.6,
        initial_prompt=None,
        vad=VadConfig(min_silence_duration_ms=500, vad_threshold=0.5),
    )
    assert (app_cfg.post_process, app_cfg.subtitle) == (post_cfg, sub_cfg)
    assert app_cfg.mastering == mastering_cfg


def test_stream_config_defaults() -> None:
    """AppConfig.stream が StreamContextConfig を正しく保持し、期待されるデフォルト値が読み込まれることを検証する。"""
    # Arrange & Act
    app_cfg = AppConfig()

    # Assert
    assert hasattr(app_cfg, "stream")
    stream_cfg = app_cfg.stream

    assert hasattr(stream_cfg, "context")
    context_cfg = stream_cfg.context

    # Check default values
    assert context_cfg.context_max_length == 200
    assert context_cfg.context_timeout_seconds == 3.0
    assert stream_cfg.chunk_min_seconds == 1.0
    assert stream_cfg.chunk_max_seconds == 30.0


def test_max_segment_chars_absent_and_ignored() -> None:
    """MAX_SEGMENT_CHARS が設定クラスに存在しないことを検証する。"""
    post_cfg = PostProcessConfig()
    field_names = [f.name for f in dataclasses.fields(PostProcessConfig)]

    # Assert
    assert "max_segment_chars" not in field_names
    assert not hasattr(post_cfg, "max_segment_chars")
