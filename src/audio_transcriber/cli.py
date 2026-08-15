"""Command-line interface for audio-transcriber."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from audio_transcriber.config import load_config
from audio_transcriber.exporter import SubtitleExporter
from audio_transcriber.media import is_video_file
from audio_transcriber.pipeline import run_pipeline

app = typer.Typer(
    name="audio-transcriber",
    help="Denoise mic audio, transcribe to SRT, and remux multi-track video for DaVinci Resolve.",
    add_completion=False,
)
console = Console()


@app.command()
def main(
    input_file: Annotated[
        Path | None,
        typer.Argument(
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to input audio/video file. Defaults to DEFAULT_VIDEO_PATH in config.toml.",
        ),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-C",
            help="Path to TOML configuration file (defaults to ./config.toml if present).",
        ),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            "-o",
            help="Directory to save clean audio, video, and SRT files.",
        ),
    ] = None,
    mic_track: Annotated[
        int | None,
        typer.Option(
            "--mic-track",
            "-t",
            help="1-indexed audio track number for the microphone stream in multi-track video.",
        ),
    ] = None,
    model_size: Annotated[
        str | None,
        typer.Option(
            "--model-size",
            "-m",
            help="Whisper model size (tiny, base, small, medium, large-v3).",
        ),
    ] = None,
    device: Annotated[
        str | None,
        typer.Option(
            "--device",
            "-d",
            help="Inference device ('cuda' or 'cpu').",
        ),
    ] = None,
    compute_type: Annotated[
        str | None,
        typer.Option(
            "--compute-type",
            "-c",
            help="Quantization compute type ('float16', 'int8_float16', 'int8', 'float32').",
        ),
    ] = None,
    language: Annotated[
        str | None,
        typer.Option(
            "--language",
            "-l",
            help="Language code for transcription.",
        ),
    ] = None,
    initial_prompt: Annotated[
        str | None,
        typer.Option(
            "--prompt",
            "-p",
            help="Initial prompt to guide transcription context.",
        ),
    ] = None,
    denoise: Annotated[
        bool | None,
        typer.Option(
            "--denoise/--no-denoise",
            help="Enable/disable noise reduction (defaults to [denoise] ENABLED in config).",
        ),
    ] = None,
    denoise_only: Annotated[
        bool,
        typer.Option(
            "--denoise-only",
            help="Perform only noise/key-sound removal.",
        ),
    ] = False,
    transcribe_only: Annotated[
        bool,
        typer.Option(
            "--transcribe-only",
            help="Perform only transcription without noise reduction.",
        ),
    ] = False,
    remux: Annotated[
        bool | None,
        typer.Option(
            "--remux/--no-remux",
            help="Enable/disable remuxing video with cleaned mic track.",
        ),
    ] = None,
    vad: Annotated[
        bool | None,
        typer.Option(
            "--vad/--no-vad",
            help="Enable/disable Silero-VAD filtering (defaults to [transcribe.vad] VAD_FILTER).",
        ),
    ] = None,
    min_silence_ms: Annotated[
        int | None,
        typer.Option(
            "--min-silence-ms",
            help="Minimum silence duration in ms for VAD splitting.",
        ),
    ] = None,
    mastering_enabled: Annotated[
        bool | None,
        typer.Option(
            "--mastering-enabled/--no-mastering",
            help="Enable/disable mastering filters.",
        ),
    ] = None,
    noise_gate_threshold: Annotated[
        float | None,
        typer.Option(
            "--noise-gate-threshold",
            help="Noise gate threshold.",
        ),
    ] = None,
    loudness_i: Annotated[
        float | None,
        typer.Option(
            "--loudness-i",
            help="Target loudness LUFS.",
        ),
    ] = None,
    loudness_tp: Annotated[
        float | None,
        typer.Option(
            "--loudness-tp",
            help="True peak limit dBTP.",
        ),
    ] = None,
    loudness_lra: Annotated[
        float | None,
        typer.Option(
            "--loudness-lra",
            help="Loudness range LU.",
        ),
    ] = None,
    final_limit_db: Annotated[
        float | None,
        typer.Option(
            "--final-limit-db",
            help="Final hard limiter dB.",
        ),
    ] = None,
    debug_output_dir: Annotated[
        Path | None,
        typer.Option(
            "--debug-output-dir",
            help="Debug output directory.",
        ),
    ] = None,
    custom_dict_path: Annotated[
        Path | None,
        typer.Option(
            "--custom-dict-path",
            help="Custom dictionary path.",
        ),
    ] = None,
    denoise_engine: Annotated[
        str | None,
        typer.Option(
            "--denoise-engine",
            help="Denoise engine (rnnoise etc.).",
        ),
    ] = None,
    denoise_model_path: Annotated[
        Path | None,
        typer.Option(
            "--denoise-model-path",
            help="Custom denoise model path.",
        ),
    ] = None,
    media_sample_rate: Annotated[
        int | None,
        typer.Option(
            "--media-sample-rate",
            help="Media extraction sample rate.",
        ),
    ] = None,
    beam_size: Annotated[
        int | None,
        typer.Option(
            "--beam-size",
            help="Whisper beam size.",
        ),
    ] = None,
    condition_on_previous_text: Annotated[
        bool | None,
        typer.Option(
            "--condition-on-previous-text/--no-condition-on-previous-text",
            help="Condition on previous text for Whisper.",
        ),
    ] = None,
    transcribe_no_speech_threshold: Annotated[
        float | None,
        typer.Option(
            "--transcribe-no-speech-threshold",
            help="No speech threshold for transcribe.",
        ),
    ] = None,
    vad_threshold: Annotated[
        float | None,
        typer.Option(
            "--vad-threshold",
            help="VAD threshold.",
        ),
    ] = None,
    replace_terms: Annotated[
        bool | None,
        typer.Option(
            "--replace-terms/--no-replace-terms",
            help="Enable term replacement.",
        ),
    ] = None,
    lower: Annotated[
        bool | None,
        typer.Option(
            "--lower/--no-lower",
            help="Lowercase text.",
        ),
    ] = None,
    remove_punct: Annotated[
        bool | None,
        typer.Option(
            "--remove-punct/--no-remove-punct",
            help="Remove punctuation.",
        ),
    ] = None,
    pp_no_speech_threshold: Annotated[
        float | None,
        typer.Option(
            "--pp-no-speech-threshold",
            help="Post-process no speech threshold.",
        ),
    ] = None,
    max_chars_per_second: Annotated[
        float | None,
        typer.Option(
            "--max-chars-per-second",
            help="Max chars per second.",
        ),
    ] = None,
    end_padding: Annotated[
        float | None,
        typer.Option(
            "--end-padding",
            help="Subtitle end padding.",
        ),
    ] = None,
    min_duration: Annotated[
        float | None,
        typer.Option(
            "--min-duration",
            help="Subtitle min duration.",
        ),
    ] = None,
    min_gap: Annotated[
        float | None,
        typer.Option(
            "--min-gap",
            help="Subtitle min gap.",
        ),
    ] = None,
    subtitle_formats: Annotated[
        str | None,
        typer.Option(
            "--subtitle-formats",
            help="Comma-separated subtitle formats (srt,vtt,json).",
        ),
    ] = None,
    chunk_size_ms: Annotated[
        int | None,
        typer.Option(
            "--chunk-size-ms",
            help="Streaming chunk size in ms.",
        ),
    ] = None,
    buffer_size_seconds: Annotated[
        float | None,
        typer.Option(
            "--buffer-size-seconds",
            help="Streaming buffer size in seconds.",
        ),
    ] = None,
    stream_sample_rate: Annotated[
        int | None,
        typer.Option(
            "--stream-sample-rate",
            help="Streaming sample rate in Hz.",
        ),
    ] = None,
    flush_timeout_ms: Annotated[
        int | None,
        typer.Option(
            "--flush-timeout-ms",
            help="Flush timeout in ms for streaming.",
        ),
    ] = None,
    word_gap_split_threshold: Annotated[
        float | None,
        typer.Option(
            "--word-gap-split-threshold",
            help="Word gap split threshold in seconds.",
        ),
    ] = None,
    streaming_log: Annotated[
        bool | None,
        typer.Option(
            "--streaming-log/--no-streaming-log",
            help="Enable/disable real-time tree log output.",
        ),
    ] = None,
) -> None:
    """Process microphone audio: Remove keyboard/gamepad noise, generate SRT, and remux video."""
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

    resolved_input_file = (
        input_file if input_file is not None else cfg.default_video_path
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

    resolved_output_dir = output_dir if output_dir is not None else cfg.output_dir
    resolved_mic_track = mic_track if mic_track is not None else cfg.media.mic_track
    resolved_model_size = model_size if model_size is not None else cfg.model.model_size
    resolved_device = device if device is not None else cfg.model.device
    resolved_compute_type = (
        compute_type if compute_type is not None else cfg.model.compute_type
    )
    if resolved_device.lower() == "cpu" and resolved_compute_type.lower() in (
        "float16",
        "int8_float16",
    ):
        resolved_compute_type = "int8"
    resolved_language = language if language is not None else cfg.transcribe.language
    resolved_prompt = (
        initial_prompt if initial_prompt is not None else cfg.transcribe.initial_prompt
    )
    resolved_remux = remux if remux is not None else cfg.pipeline.remux

    if transcribe_only:
        do_denoise = False
    elif denoise_only:
        do_denoise = True
    elif denoise is not None:
        do_denoise = denoise
    else:
        do_denoise = cfg.denoise.enabled

    do_transcribe = not denoise_only
    resolved_vad_filter = vad if vad is not None else cfg.transcribe.vad.vad_filter
    resolved_min_silence = (
        min_silence_ms
        if min_silence_ms is not None
        else cfg.transcribe.vad.min_silence_duration_ms
    )

    is_video = is_video_file(resolved_input_file)

    # CLI オプションを AppConfig に上書き (Single Source of Truth)
    if output_dir is not None:
        cfg.paths.output_dir = resolved_output_dir
    if mic_track is not None:
        cfg.media.mic_track = resolved_mic_track
    if model_size is not None:
        cfg.model.model_size = resolved_model_size
    if device is not None:
        cfg.model.device = resolved_device
    if compute_type is not None:
        cfg.model.compute_type = resolved_compute_type
    if language is not None:
        cfg.transcribe.language = resolved_language
    if initial_prompt is not None:
        cfg.transcribe.initial_prompt = resolved_prompt
    if vad is not None:
        cfg.transcribe.vad.vad_filter = resolved_vad_filter
    if min_silence_ms is not None:
        cfg.transcribe.vad.min_silence_duration_ms = resolved_min_silence
    if remux is not None:
        cfg.pipeline.remux = resolved_remux
    if mastering_enabled is not None:
        cfg.mastering.enabled = mastering_enabled
    if noise_gate_threshold is not None:
        cfg.mastering.noise_gate_threshold = noise_gate_threshold
    if loudness_i is not None:
        cfg.mastering.loudness_i = loudness_i
    if loudness_tp is not None:
        cfg.mastering.loudness_tp = loudness_tp
    if loudness_lra is not None:
        cfg.mastering.loudness_lra = loudness_lra
    if final_limit_db is not None:
        cfg.mastering.final_limit_db = final_limit_db
    if debug_output_dir is not None:
        cfg.paths.debug_output_dir = debug_output_dir
    if custom_dict_path is not None:
        cfg.paths.custom_dict_path = custom_dict_path
    if denoise_engine is not None:
        cfg.denoise.engine = denoise_engine
    if denoise_model_path is not None:
        cfg.denoise.model_path = denoise_model_path
    if media_sample_rate is not None:
        cfg.media.sample_rate = media_sample_rate
    if beam_size is not None:
        cfg.transcribe.beam_size = beam_size
    if condition_on_previous_text is not None:
        cfg.transcribe.condition_on_previous_text = condition_on_previous_text
    if transcribe_no_speech_threshold is not None:
        cfg.transcribe.no_speech_threshold = transcribe_no_speech_threshold
    if vad_threshold is not None:
        cfg.transcribe.vad.vad_threshold = vad_threshold
    if replace_terms is not None:
        cfg.post_process.replace_terms = replace_terms
    if lower is not None:
        cfg.post_process.lower = lower
    if remove_punct is not None:
        cfg.post_process.remove_punct = remove_punct
    if pp_no_speech_threshold is not None:
        cfg.post_process.no_speech_threshold = pp_no_speech_threshold
    if max_chars_per_second is not None:
        cfg.post_process.max_chars_per_second = max_chars_per_second
    if end_padding is not None:
        cfg.subtitle.end_padding = end_padding
    if min_duration is not None:
        cfg.subtitle.min_duration = min_duration
    if min_gap is not None:
        cfg.subtitle.min_gap = min_gap
    if subtitle_formats is not None:
        cfg.subtitle.formats = [
            f.strip().lower() for f in subtitle_formats.split(",") if f.strip()
        ]
    if chunk_size_ms is not None:
        cfg.stream.chunk_size_ms = chunk_size_ms
    if buffer_size_seconds is not None:
        cfg.stream.buffer_size_seconds = buffer_size_seconds
    if stream_sample_rate is not None:
        cfg.stream.sample_rate = stream_sample_rate
    if flush_timeout_ms is not None:
        cfg.stream.flush_timeout_ms = flush_timeout_ms
    if word_gap_split_threshold is not None:
        cfg.stream.word_gap_split_threshold = word_gap_split_threshold
    if streaming_log is not None:
        cfg.stream.streaming_log = streaming_log

    status_lines = [
        "[bold cyan]Audio Transcriber[/bold cyan]",
        f"Input: [yellow]{resolved_input_file.name}[/yellow] ({'Video' if is_video else 'Audio'})",
    ]
    if is_video:
        status_lines.append(
            f"Mic Track: [green]Track {cfg.media.mic_track}[/green] | "
            f"Remux Video: [green]{cfg.pipeline.remux}[/green]"
        )
    status_lines.append(
        f"Device: [green]{cfg.model.device}[/green] | "
        f"Whisper: [green]{cfg.model.model_size}[/green] | "
        f"Denoise: [green]{do_denoise}[/green]"
    )

    console.print(Panel.fit("\n".join(status_lines), border_style="cyan"))

    def handle_progress(stage: str, message: Any) -> None:
        if not cfg.stream.streaming_log:
            if stage in (
                "vad_chunks",
                "postprocess_dropped",
                "postprocess_replaced",
                "postprocess_overlap_prevented",
            ):
                return
            if stage == "postprocess_start":
                console.print(f"[bold cyan]▶ [postprocess][/bold cyan] {message}")
            elif stage == "postprocess_summary":
                console.print(f"  [bold white]└─ {message}[/bold white]")
            elif stage == "vad":
                console.print(f"[bold magenta]▶ [vad][/bold magenta] {message}")
            else:
                console.print(f"[bold cyan]▶ [{stage}][/bold cyan] {message}")
            return

        # Streaming log is True
        if stage == "vad_chunks":
            # 事前にまとめて渡される VADチャンクリストはここでは出力せず無視する
            pass
        elif stage == "vad_chunk_start":
            v_start, v_end = message
            dur = max(0.0, v_end - v_start)
            console.print(
                f"\n[bold magenta][VAD][/bold magenta] {SubtitleExporter.format_timestamp(v_start)} --> {SubtitleExporter.format_timestamp(v_end)} ({dur:.2f}s)"
            )
        elif stage == "postprocess_dropped":
            console.print(f"  [yellow][無音捏造等除外][/yellow] {message}")
        elif stage == "postprocess_replaced":
            console.print(f"  [green][テキスト置換][/green] {message}")
        elif stage == "postprocess_overlap_prevented":
            console.print(f"  [magenta][重複防止][/magenta] {message}")
        elif stage == "postprocess_start":
            console.print(f"\n[bold cyan]▶ [postprocess][/bold cyan] {message}")
        elif stage == "postprocess_summary":
            console.print(f"[bold white]└─ {message}[/bold white]\n")
        elif stage == "vad":
            console.print(f"[bold magenta]▶ [vad][/bold magenta] {message}")
        else:
            console.print(f"[bold cyan]▶ [{stage}][/bold cyan] {message}")

    def handle_segment(seg: dict[str, Any]) -> None:
        start_sec = float(seg.get("start", 0.0))
        end_sec = float(seg.get("end", 0.0))
        duration = max(0.0, end_sec - start_sec)
        start_str = SubtitleExporter.format_timestamp(start_sec)
        end_str = SubtitleExporter.format_timestamp(end_sec)
        text = str(seg.get("text", "")).strip()

        if cfg.stream.streaming_log:
            console.print(
                f'  [bold cyan][Whisper生][/bold cyan] {start_str} --> {end_str} ({duration:.2f}s) "{text}"'
            )
        else:
            console.print(
                f"  [dim cyan]{start_str} --> {end_str}[/dim cyan] [dim yellow]({duration:.1f}s)[/dim yellow] [dim white]{text}[/dim white]"
            )

    try:
        result = run_pipeline(
            input_path=resolved_input_file,
            cfg=cfg,
            denoise=do_denoise,
            transcribe=do_transcribe,
            on_progress=handle_progress,
            on_segment=handle_segment,
        )
    except Exception as e:
        console.print(f"[bold red]Pipeline failed:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    table = Table(title="Generated Outputs", border_style="green")
    table.add_column("Type", style="cyan")
    table.add_column("Path", style="yellow")

    if result.remuxed_video:
        table.add_row("Clean Video (Remuxed)", str(result.remuxed_video))
    if result.denoised_audio:
        table.add_row("Denoised Audio", str(result.denoised_audio))
    if result.srt_file:
        table.add_row("SRT Subtitle", str(result.srt_file))

    console.print(table)
    console.print(
        "[bold green]✓ Done![/bold green] Import clean media and SRT into DaVinci Resolve."
    )


if __name__ == "__main__":
    app()
