"""Configuration management and TOML loading for audio-transcriber.

設定管理およびTOML設定ファイルの読み込み機能を提供します。
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any

from audio_transcriber.config_models import (
    AppConfig,
    DenoiseConfig,
    MasteringConfig,
    MediaConfig,
    ModelConfig,
    PathConfig,
    PipelineConfig,
    PostProcessConfig,
    StreamConfig,
    StreamContextConfig,
    SubtitleConfig,
    TranscribeConfig,
    VadConfig,
)

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_FILENAME = "config.toml"

__all__ = [
    "DEFAULT_CONFIG_FILENAME",
    "AppConfig",
    "DenoiseConfig",
    "MasteringConfig",
    "MediaConfig",
    "ModelConfig",
    "PathConfig",
    "PipelineConfig",
    "PostProcessConfig",
    "StreamConfig",
    "StreamContextConfig",
    "SubtitleConfig",
    "TranscribeConfig",
    "VadConfig",
    "load_config",
    "parse_config_dict",
]


def _normalize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """辞書のキーを再帰的に小文字化して正規化する。"""
    normalized: dict[str, Any] = {}
    for k, v in data.items():
        normalized[k.lower()] = _normalize_dict(v) if isinstance(v, dict) else v
    return normalized


def _get_val(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """辞書から最初に見つかった非Noneのキーの値を返す。"""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _get_path(
    d: dict[str, Any], *keys: str, default: Path | None = None
) -> Path | None:
    """辞書から最初に見つかった非Noneのキーの値をPathとして返す。"""
    val = _get_val(d, *keys)
    return Path(val) if val is not None else default


def parse_config_dict(data: dict[str, Any]) -> AppConfig:
    """TOMLから読み込んだ辞書をAppConfigインスタンスに変換する。"""
    norm = _normalize_dict(data)

    # Paths
    path_d = norm.get("path") or norm.get("paths") or {}
    paths = PathConfig(
        output_dir=Path(_get_val(path_d, "output_dir", default="./output")),
        default_video_path=_get_path(path_d, "default_video_path", "default_video"),
        debug_output_dir=_get_path(path_d, "debug_output_dir", "debug_dir"),
        custom_dict_path=_get_path(
            path_d,
            "custom_dict_path",
            "custom_dictionary_path",
            "dictionary_path",
        ),
    )

    # Pipeline, Denoise, Media, Model
    pipe_d = norm.get("pipeline", {})
    pipeline = PipelineConfig(remux=bool(_get_val(pipe_d, "remux", default=True)))

    denoise_d = norm.get("denoise", {})
    denoise = DenoiseConfig(
        enabled=bool(_get_val(denoise_d, "enabled", default=True)),
        engine=str(_get_val(denoise_d, "engine", default="rnnoise")),
        model_path=_get_path(denoise_d, "model_path", "model"),
    )

    media_d = norm.get("media", {})
    media = MediaConfig(
        mic_track=int(_get_val(media_d, "mic_track", default=2)),
        sample_rate=int(_get_val(media_d, "sample_rate", default=48000)),
    )

    model_d = norm.get("model", {})
    model = ModelConfig(
        model_size=str(_get_val(model_d, "model_size", default="small")),
        device=str(_get_val(model_d, "device", default="cuda")),
        compute_type=str(_get_val(model_d, "compute_type", default="float16")),
    )

    # Transcribe & VAD
    trans_d = norm.get("transcribe", {})
    vad_d = trans_d.get("vad") or norm.get("vad", {})
    vad = VadConfig(
        min_silence_duration_ms=int(
            _get_val(vad_d, "min_silence_duration_ms", default=500)
        ),
        vad_threshold=float(_get_val(vad_d, "vad_threshold", default=0.5)),
    )
    raw_prompt = _get_val(trans_d, "initial_prompt", "prompt")
    initial_prompt = str(raw_prompt).strip() if raw_prompt is not None else None

    transcribe = TranscribeConfig(
        language=str(_get_val(trans_d, "language", default="ja")),
        beam_size=int(_get_val(trans_d, "beam_size", default=5)),
        condition_on_previous_text=bool(
            _get_val(trans_d, "condition_on_previous_text", default=True)
        ),
        no_speech_threshold=float(
            _get_val(trans_d, "no_speech_threshold", default=0.6)
        ),
        initial_prompt=initial_prompt,
        vad=vad,
    )

    # Post process
    post_d = (
        norm.get("post_process")
        or norm.get("postprocess")
        or norm.get("post_processing")
        or {}
    )
    post_process = PostProcessConfig(
        replace_terms=bool(_get_val(post_d, "replace_terms", default=True)),
        lower=bool(_get_val(post_d, "lower", default=False)),
        remove_punct=bool(_get_val(post_d, "remove_punct", default=False)),
        no_speech_threshold=float(_get_val(post_d, "no_speech_threshold", default=0.6)),
        max_chars_per_second=float(
            _get_val(post_d, "max_chars_per_second", default=12.0)
        ),
    )

    # Subtitle
    sub_d = norm.get("subtitle") or norm.get("subtitles") or {}
    raw_fmt = _get_val(
        sub_d,
        "formats",
        "subtitle_formats",
        "output_formats",
        default=["srt", "vtt", "json"],
    )
    if isinstance(raw_fmt, str):
        parsed_formats = [f.strip().lower() for f in raw_fmt.split(",") if f.strip()]
    elif isinstance(raw_fmt, list):
        parsed_formats = [str(f).strip().lower() for f in raw_fmt if str(f).strip()]
    else:
        parsed_formats = ["srt", "vtt", "json"]

    subtitle = SubtitleConfig(
        end_padding=float(_get_val(sub_d, "end_padding", default=1.0)),
        min_duration=float(_get_val(sub_d, "min_duration", default=1.5)),
        min_gap=float(_get_val(sub_d, "min_gap", default=0.05)),
        formats=parsed_formats,
    )

    # Stream & Context
    stream_d = norm.get("stream", {})
    context_d = stream_d.get("context", {})
    context = StreamContextConfig(
        context_max_length=int(_get_val(context_d, "context_max_length", default=200)),
        context_timeout_seconds=float(
            _get_val(context_d, "context_timeout_seconds", default=3.0)
        ),
    )
    stream = StreamConfig(
        chunk_size_ms=int(_get_val(stream_d, "chunk_size_ms", default=100)),
        buffer_size_seconds=float(
            _get_val(stream_d, "buffer_size_seconds", default=10.0)
        ),
        sample_rate=int(_get_val(stream_d, "sample_rate", default=16000)),
        flush_timeout_ms=int(_get_val(stream_d, "flush_timeout_ms", default=1000)),
        word_gap_split_threshold=float(
            _get_val(stream_d, "word_gap_split_threshold", default=1.0)
        ),
        streaming_log=bool(_get_val(stream_d, "streaming_log", default=False)),
        chunk_min_seconds=float(_get_val(stream_d, "chunk_min_seconds", default=1.0)),
        chunk_max_seconds=float(_get_val(stream_d, "chunk_max_seconds", default=30.0)),
        context=context,
    )

    # Mastering
    master_d = norm.get("mastering", {})
    mastering = MasteringConfig(
        enabled=bool(_get_val(master_d, "enabled", default=False)),
        noise_gate_threshold=float(
            _get_val(master_d, "noise_gate_threshold", default=0.04)
        ),
        loudness_i=float(_get_val(master_d, "loudness_i", default=-16.0)),
        loudness_tp=float(_get_val(master_d, "loudness_tp", default=-2.0)),
        loudness_lra=float(_get_val(master_d, "loudness_lra", default=11.0)),
        final_limit_db=float(_get_val(master_d, "final_limit_db", default=-2.0)),
    )

    return AppConfig(
        paths=paths,
        pipeline=pipeline,
        denoise=denoise,
        media=media,
        model=model,
        transcribe=transcribe,
        post_process=post_process,
        subtitle=subtitle,
        stream=stream,
        mastering=mastering,
    )


def load_config(config_path: Path | str | None = None) -> AppConfig:
    """TOMLファイルから設定を読み込み、存在しない場合はデフォルト設定を返す。"""
    if config_path is not None:
        target_path = Path(config_path)
        if not target_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
    else:
        default_file = Path(DEFAULT_CONFIG_FILENAME)
        target_path = default_file if default_file.is_file() else None

    if target_path is None:
        logger.debug("No configuration file found; using default configuration.")
        return AppConfig()

    logger.info(f"Loading configuration from {target_path}")
    try:
        with open(target_path, "rb") as f:
            return parse_config_dict(tomllib.load(f))
    except tomllib.TOMLDecodeError as e:
        raise ValueError(
            f"Failed to parse TOML configuration '{target_path}': {e}"
        ) from e
