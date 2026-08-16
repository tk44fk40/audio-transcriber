"""CLI 引数および設定オーバーライドの処理モジュール。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from audio_transcriber.config import AppConfig, load_config


def resolve_pipeline_modes(
    denoise_only: bool,
    transcribe_only: bool,
    denoise_flag: bool | None,
    cfg_denoise_enabled: bool,
) -> tuple[bool, bool]:
    """CLIオプションからノイズ除去および文字起こしの実行フラグを解決します。

    Args:
        denoise_only: ノイズ除去のみ実行フラグ。
        transcribe_only: 文字起こしのみ実行フラグ。
        denoise_flag: --denoise/--no-denoise フラグ値。
        cfg_denoise_enabled: 設定ファイルのノイズ除去有効フラグ。

    Returns:
        tuple[bool, bool]: (do_denoise, do_transcribe) のタプル。
    """
    if transcribe_only:
        do_denoise = False
    elif denoise_only:
        do_denoise = True
    elif denoise_flag is not None:
        do_denoise = denoise_flag
    else:
        do_denoise = cfg_denoise_enabled

    do_transcribe = not denoise_only
    return do_denoise, do_transcribe


def resolve_input_and_device(
    input_file: Path | None,
    cfg: AppConfig,
    device: str | None,
    compute_type: str | None,
) -> tuple[Path | None, str, str]:
    """入力ファイルパスおよび推論デバイス・量子化型を解決します。

    Args:
        input_file: CLIから指定された入力ファイルパス。
        cfg: アプリケーション設定オブジェクト。
        device: CLIから指定された推論デバイス。
        compute_type: CLIから指定された量子化計算タイプ。

    Returns:
        tuple[Path | None, str, str]: (resolved_input_file, resolved_device, resolved_compute_type) のタプル。
    """
    resolved_input_file = (
        input_file if input_file is not None else cfg.default_video_path
    )
    resolved_device = device if device is not None else cfg.model.device
    resolved_compute = (
        compute_type if compute_type is not None else cfg.model.compute_type
    )
    if resolved_device.lower() == "cpu" and resolved_compute.lower() in (
        "float16",
        "int8_float16",
    ):
        resolved_compute = "int8"
    return resolved_input_file, resolved_device, resolved_compute


def apply_cli_overrides(cfg: AppConfig, **kwargs: Any) -> None:
    """CLI オプションで指定された値を AppConfig に上書き反映します。

    Args:
        cfg: 更新対象の AppConfig オブジェクト。
        **kwargs: 各種 CLI オプション値。
    """
    mapping = [
        ("output_dir", cfg.paths, "output_dir"),
        ("mic_track", cfg.media, "mic_track"),
        ("model_size", cfg.model, "model_size"),
        ("device", cfg.model, "device"),
        ("compute_type", cfg.model, "compute_type"),
        ("language", cfg.transcribe, "language"),
        ("initial_prompt", cfg.transcribe, "initial_prompt"),
        ("min_silence_ms", cfg.transcribe.vad, "min_silence_duration_ms"),
        ("remux", cfg.pipeline, "remux"),
        ("mastering_enabled", cfg.mastering, "enabled"),
        ("noise_gate_threshold", cfg.mastering, "noise_gate_threshold"),
        ("loudness_i", cfg.mastering, "loudness_i"),
        ("loudness_tp", cfg.mastering, "loudness_tp"),
        ("loudness_lra", cfg.mastering, "loudness_lra"),
        ("final_limit_db", cfg.mastering, "final_limit_db"),
        ("debug_output_dir", cfg.paths, "debug_output_dir"),
        ("custom_dict_path", cfg.paths, "custom_dict_path"),
        ("denoise_engine", cfg.denoise, "engine"),
        ("denoise_model_path", cfg.denoise, "model_path"),
        ("media_sample_rate", cfg.media, "sample_rate"),
        ("beam_size", cfg.transcribe, "beam_size"),
        ("condition_on_previous_text", cfg.transcribe, "condition_on_previous_text"),
        (
            "transcribe_no_speech_threshold",
            cfg.transcribe,
            "no_speech_threshold",
        ),
        ("vad_threshold", cfg.transcribe.vad, "vad_threshold"),
        ("replace_terms", cfg.post_process, "replace_terms"),
        ("lower", cfg.post_process, "lower"),
        ("remove_punct", cfg.post_process, "remove_punct"),
        ("pp_no_speech_threshold", cfg.post_process, "no_speech_threshold"),
        ("max_chars_per_second", cfg.post_process, "max_chars_per_second"),
        ("end_padding", cfg.subtitle, "end_padding"),
        ("min_duration", cfg.subtitle, "min_duration"),
        ("min_gap", cfg.subtitle, "min_gap"),
        ("chunk_size_ms", cfg.stream, "chunk_size_ms"),
        ("buffer_size_seconds", cfg.stream, "buffer_size_seconds"),
        ("stream_sample_rate", cfg.stream, "sample_rate"),
        ("flush_timeout_ms", cfg.stream, "flush_timeout_ms"),
        ("word_gap_split_threshold", cfg.stream, "word_gap_split_threshold"),
        ("streaming_log", cfg.stream, "streaming_log"),
    ]

    for key, target_obj, attr_name in mapping:
        val = kwargs.get(key)
        if val is not None:
            setattr(target_obj, attr_name, val)

    sub_formats = kwargs.get("subtitle_formats")
    if sub_formats is not None and isinstance(sub_formats, str):
        cfg.subtitle.formats = [
            f.strip().lower() for f in sub_formats.split(",") if f.strip()
        ]


def prepare_cli_execution(
    console: Console,
    input_file: Path | None,
    config_path: Path | None,
    denoise_only: bool,
    transcribe_only: bool,
    denoise: bool | None,
    device: str | None,
    compute_type: str | None,
    **cli_kwargs: Any,
) -> tuple[AppConfig, Path, bool, bool]:
    """CLI実行前のオプション検証、設定読み込み、パラメータ上書きを行います。

    Args:
        console: Rich Console インスタンス。
        input_file: 入力メディアファイルパス。
        config_path: 設定ファイルパス。
        denoise_only: ノイズ除去のみ実行フラグ。
        transcribe_only: 文字起こしのみ実行フラグ。
        denoise: ノイズ除去有効フラグ。
        device: 推論デバイス。
        compute_type: 量子化計算タイプ。
        **cli_kwargs: その他の CLI オプション。

    Returns:
        tuple[AppConfig, Path, bool, bool]: (cfg, resolved_input_file, do_denoise, do_transcribe) のタプル。

    Raises:
        typer.Exit: オプション矛盾、設定エラー、または入力ファイル未指定・未存在時。
    """
    if denoise_only and transcribe_only:
        console.print(
            "[red]Error:[/red] Cannot specify both --denoise-only and --transcribe-only."
        )
        raise typer.Exit(code=1)

    try:
        cfg = load_config(config_path)
    except Exception as e:
        console.print(f"[bold red]Configuration error:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    resolved_input_file, resolved_device, resolved_compute = resolve_input_and_device(
        input_file, cfg, device, compute_type
    )
    if resolved_input_file is None:
        console.print(
            "[bold red]Error:[/bold red] No input file specified and no DEFAULT_VIDEO_PATH found in config."
        )
        raise typer.Exit(code=2)

    if not resolved_input_file.is_file():
        console.print(
            f"[bold red]Error:[/bold red] Input file does not exist: {resolved_input_file}"
        )
        raise typer.Exit(code=2)

    do_denoise, do_transcribe = resolve_pipeline_modes(
        denoise_only=denoise_only,
        transcribe_only=transcribe_only,
        denoise_flag=denoise,
        cfg_denoise_enabled=cfg.denoise.enabled,
    )

    all_kwargs = dict(cli_kwargs)
    all_kwargs["device"] = resolved_device
    all_kwargs["compute_type"] = resolved_compute
    apply_cli_overrides(cfg, **all_kwargs)

    return cfg, resolved_input_file, do_denoise, do_transcribe
