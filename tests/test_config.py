"""Configuration loading and TOML parsing tests.

設定読み込みおよびTOMLパースの単体テストを提供します。
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

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
    load_config,
    parse_config_dict,
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


def test_load_config_no_file_returns_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """設定ファイルが存在しない場合にデフォルト設定が返されることを検証する。"""
    # Arrange & Act
    monkeypatch.chdir(tmp_path)
    cfg = load_config(None)

    # Assert
    assert cfg == AppConfig()


def test_load_config_full_custom_toml(tmp_path: Path) -> None:
    """全セクション・全キーを含む完全なTOMLから設定が正常に読み込まれることを検証する。"""
    # Arrange
    toml_content = """
    [path]
    OUTPUT_DIR = "/custom/output"
    DEFAULT_VIDEO_PATH = "data/custom.mp4"
    DEBUG_OUTPUT_DIR = "custom_debug"
    CUSTOM_DICT_PATH = "data/my_dict.toml"

    [pipeline]
    REMUX = false

    [denoise]
    ENABLED = true
    ENGINE = "resemble_enhance"
    MODEL_PATH = "data/custom_model.onnx"

    [media]
    MIC_TRACK = 3
    SAMPLE_RATE = 44100

    [model]
    MODEL_SIZE = "large-v3-turbo"
    DEVICE = "cpu"
    COMPUTE_TYPE = "int8"

    [transcribe]
    LANGUAGE = "en"
    BEAM_SIZE = 2
    CONDITION_ON_PREVIOUS_TEXT = false
    NO_SPEECH_THRESHOLD = 0.85
    INITIAL_PROMPT = "Custom prompt"

    [transcribe.vad]
    MIN_SILENCE_DURATION_MS = 800
    VAD_THRESHOLD = 0.4

    [post_process]
    REPLACE_TERMS = false
    LOWER = true
    REMOVE_PUNCT = true
    NO_SPEECH_THRESHOLD = 0.7
    MAX_CHARS_PER_SECOND = 15.0

    [subtitle]
    END_PADDING = 0.8
    MIN_DURATION = 1.2
    MIN_GAP = 0.1
    FORMATS = ["srt", "vtt"]

    [mastering]
    ENABLED = true
    NOISE_GATE_THRESHOLD = 0.02
    LOUDNESS_I = -14.0
    LOUDNESS_TP = -1.0
    LOUDNESS_LRA = 9.0
    FINAL_LIMIT_DB = -1.5
    """
    config_file = tmp_path / "custom_config.toml"
    config_file.write_text(toml_content, encoding="utf-8")

    # Act
    cfg = load_config(config_file)

    # Assert
    assert cfg.paths.output_dir == Path("/custom/output")
    assert cfg.output_dir == Path("/custom/output")
    assert cfg.paths.default_video_path == Path("data/custom.mp4")
    assert cfg.default_video_path == Path("data/custom.mp4")
    assert cfg.paths.debug_output_dir == Path("custom_debug")
    assert cfg.debug_output_dir == Path("custom_debug")
    assert cfg.paths.custom_dict_path == Path("data/my_dict.toml")
    assert cfg.custom_dict_path == Path("data/my_dict.toml")
    assert cfg.pipeline.remux is False
    assert (
        cfg.denoise.enabled,
        cfg.denoise.engine,
        cfg.denoise.model_path,
    ) == (True, "resemble_enhance", Path("data/custom_model.onnx"))
    assert (cfg.media.mic_track, cfg.media.sample_rate) == (3, 44100)
    assert (cfg.model.model_size, cfg.model.device, cfg.model.compute_type) == (
        "large-v3-turbo",
        "cpu",
        "int8",
    )
    assert (
        cfg.transcribe.language,
        cfg.transcribe.beam_size,
        cfg.transcribe.condition_on_previous_text,
    ) == ("en", 2, False)
    assert cfg.transcribe.no_speech_threshold == 0.85
    assert cfg.transcribe.initial_prompt == "Custom prompt"
    assert (
        cfg.transcribe.vad.min_silence_duration_ms,
        cfg.transcribe.vad.vad_threshold,
    ) == (800, 0.4)
    assert cfg.post_process.replace_terms is False
    assert (cfg.post_process.lower, cfg.post_process.remove_punct) == (True, True)
    assert (
        cfg.post_process.no_speech_threshold,
        cfg.post_process.max_chars_per_second,
    ) == (
        0.7,
        15.0,
    )
    assert (
        cfg.subtitle.end_padding,
        cfg.subtitle.min_duration,
        cfg.subtitle.min_gap,
    ) == (
        0.8,
        1.2,
        0.1,
    )
    assert cfg.subtitle.formats == ["srt", "vtt"]
    assert cfg.mastering.enabled is True
    assert cfg.mastering.noise_gate_threshold == 0.02
    assert cfg.mastering.loudness_i == -14.0
    assert cfg.mastering.loudness_tp == -1.0
    assert cfg.mastering.loudness_lra == 9.0
    assert cfg.mastering.final_limit_db == -1.5


def test_load_config_partial_fallback(tmp_path: Path) -> None:
    """一部のキーのみ指定された場合に未指定キーがデフォルト値にフォールバックすることを検証する。"""
    # Arrange
    toml_content = """
    [path]
    OUTPUT_DIR = "./custom_out"

    [post_process]
    TO_HANKAKU = true

    [subtitle]
    MIN_GAP = 0.2
    """
    config_file = tmp_path / "partial_config.toml"
    config_file.write_text(toml_content, encoding="utf-8")

    # Act
    cfg = load_config(config_file)

    # Assert
    assert cfg.output_dir == Path("./custom_out")
    assert cfg.post_process.replace_terms is True
    assert (cfg.subtitle.min_gap, cfg.subtitle.end_padding) == (0.2, 1.0)
    assert (cfg.model.model_size, cfg.transcribe.language) == ("small", "ja")


def test_load_config_case_insensitivity_and_aliases(tmp_path: Path) -> None:
    """小文字・大文字・エイリアスセクション名での設定読み込みを検証する。"""
    # Arrange
    toml_content = """
    [paths]
    output_dir = "./lowercase_out"
    custom_dict_path = "data/alias_dict.toml"

    [postprocess]
    replace_terms = false

    [subtitles]
    end_padding = 0.5
    formats = "srt, vtt"
    """
    config_file = tmp_path / "alias_config.toml"
    config_file.write_text(toml_content, encoding="utf-8")

    # Act
    cfg = load_config(config_file)

    # Assert
    assert cfg.output_dir == Path("./lowercase_out")
    assert cfg.custom_dict_path == Path("data/alias_dict.toml")
    assert cfg.paths.custom_dict_path == Path("data/alias_dict.toml")
    assert cfg.post_process.replace_terms is False
    assert cfg.subtitle.end_padding == 0.5
    assert cfg.subtitle.formats == ["srt", "vtt"]


def test_parse_config_dict_formats_fallback() -> None:
    """formats に不正な型が渡された場合にデフォルト形式へフォールバックすることを検証する。"""
    # Arrange & Act
    cfg = parse_config_dict({"subtitle": {"formats": 123}})

    # Assert
    assert cfg.subtitle.formats == ["srt", "vtt", "json"]


def test_max_segment_chars_absent_and_ignored(tmp_path: Path) -> None:
    """MAX_SEGMENT_CHARS が設定クラスに存在せず、TOML指定時も無視されることを検証する。"""
    # Arrange
    post_cfg = PostProcessConfig()
    field_names = [f.name for f in dataclasses.fields(PostProcessConfig)]
    config_file = tmp_path / "legacy_config.toml"
    config_file.write_text("[post_process]\nMAX_SEGMENT_CHARS = 25\n")

    # Act
    cfg = load_config(config_file)

    # Assert
    assert "max_segment_chars" not in field_names
    assert not hasattr(post_cfg, "max_segment_chars")
    assert not hasattr(cfg.post_process, "max_segment_chars")


def test_load_config_default_file_in_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """カレントディレクトリの config.toml が自動読み込みされることを検証する。"""
    # Arrange
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        "[path]\nOUTPUT_DIR = './local_out'\n[media]\nMIC_TRACK = 1\n"
    )
    monkeypatch.chdir(tmp_path)

    # Act
    cfg = load_config(None)

    # Assert
    assert (cfg.output_dir, cfg.media.mic_track, cfg.model.model_size) == (
        Path("./local_out"),
        1,
        "small",
    )


def test_load_config_file_not_found() -> None:
    """存在しない設定ファイルパスを指定した場合に FileNotFoundError が発生することを検証する。"""
    # Arrange & Act & Assert
    with pytest.raises(FileNotFoundError, match="Configuration file not found"):
        load_config(Path("/non/existent/path/config.toml"))


def test_load_config_invalid_toml(tmp_path: Path) -> None:
    """構文エラーを含むTOMLファイルを指定した場合に ValueError が発生することを検証する。"""
    # Arrange
    bad_toml = tmp_path / "bad.toml"
    bad_toml.write_text("invalid = = = toml", encoding="utf-8")

    # Act & Assert
    with pytest.raises(ValueError, match="Failed to parse TOML configuration"):
        load_config(bad_toml)


def test_parse_config_dict_empty() -> None:
    """空の辞書をパースした場合に全デフォルト値が設定されることを検証する。"""
    # Arrange & Act
    cfg = parse_config_dict({})

    # Assert
    assert cfg == AppConfig()


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


def test_load_config_stream_toml(tmp_path: Path) -> None:
    """TOMLファイルの [stream] および [stream.context] セクションから設定が正しく読み込まれることを検証する。"""
    # Arrange
    toml_content = """
    [stream]
    CHUNK_MIN_SECONDS = 2.5
    CHUNK_MAX_SECONDS = 60.0

    [stream.context]
    CONTEXT_MAX_LENGTH = 500
    CONTEXT_TIMEOUT_SECONDS = 10.0
    """
    config_file = tmp_path / "stream_config.toml"
    config_file.write_text(toml_content, encoding="utf-8")

    # Act
    cfg = load_config(config_file)

    # Assert
    assert cfg.stream.chunk_min_seconds == 2.5
    assert cfg.stream.chunk_max_seconds == 60.0
    assert cfg.stream.context.context_max_length == 500
    assert cfg.stream.context.context_timeout_seconds == 10.0
