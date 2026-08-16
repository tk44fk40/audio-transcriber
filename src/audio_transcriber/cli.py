"""Command-line interface for audio-transcriber."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from audio_transcriber.cli_options import prepare_cli_execution
from audio_transcriber.cli_ui import (
    create_progress_handler,
    create_segment_handler,
    print_result_table,
    print_status_panel,
)
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
        typer.Option("--config", "-C", help="Path to TOML configuration file."),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Directory to save outputs."),
    ] = None,
    mic_track: Annotated[
        int | None,
        typer.Option("--mic-track", "-t", help="1-indexed microphone track."),
    ] = None,
    model_size: Annotated[
        str | None, typer.Option("--model-size", "-m", help="Whisper model size.")
    ] = None,
    device: Annotated[
        str | None,
        typer.Option("--device", "-d", help="Inference device ('cuda' or 'cpu')."),
    ] = None,
    compute_type: Annotated[
        str | None,
        typer.Option("--compute-type", "-c", help="Quantization compute type."),
    ] = None,
    language: Annotated[
        str | None, typer.Option("--language", "-l", help="Language code.")
    ] = None,
    initial_prompt: Annotated[
        str | None, typer.Option("--prompt", "-p", help="Initial prompt.")
    ] = None,
    denoise: Annotated[
        bool | None,
        typer.Option("--denoise/--no-denoise", help="Enable/disable noise reduction."),
    ] = None,
    denoise_only: Annotated[
        bool, typer.Option("--denoise-only", help="Perform only noise removal.")
    ] = False,
    transcribe_only: Annotated[
        bool, typer.Option("--transcribe-only", help="Perform only transcription.")
    ] = False,
    remux: Annotated[
        bool | None,
        typer.Option("--remux/--no-remux", help="Enable/disable remuxing video."),
    ] = None,
    min_silence_ms: Annotated[
        int | None, typer.Option("--min-silence-ms", help="Min silence duration in ms.")
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
        typer.Option("--noise-gate-threshold", help="Noise gate threshold."),
    ] = None,
    loudness_i: Annotated[
        float | None, typer.Option("--loudness-i", help="Target loudness LUFS.")
    ] = None,
    loudness_tp: Annotated[
        float | None, typer.Option("--loudness-tp", help="True peak limit dBTP.")
    ] = None,
    loudness_lra: Annotated[
        float | None, typer.Option("--loudness-lra", help="Loudness range LU.")
    ] = None,
    final_limit_db: Annotated[
        float | None, typer.Option("--final-limit-db", help="Final hard limiter dB.")
    ] = None,
    debug_output_dir: Annotated[
        Path | None, typer.Option("--debug-output-dir", help="Debug output directory.")
    ] = None,
    custom_dict_path: Annotated[
        Path | None, typer.Option("--custom-dict-path", help="Custom dictionary path.")
    ] = None,
    denoise_engine: Annotated[
        str | None, typer.Option("--denoise-engine", help="Denoise engine.")
    ] = None,
    denoise_model_path: Annotated[
        Path | None,
        typer.Option("--denoise-model-path", help="Custom denoise model path."),
    ] = None,
    media_sample_rate: Annotated[
        int | None, typer.Option("--media-sample-rate", help="Media sample rate.")
    ] = None,
    beam_size: Annotated[
        int | None, typer.Option("--beam-size", help="Whisper beam size.")
    ] = None,
    condition_on_previous_text: Annotated[
        bool | None,
        typer.Option(
            "--condition-on-previous-text/--no-condition-on-previous-text",
            help="Condition on previous text.",
        ),
    ] = None,
    transcribe_no_speech_threshold: Annotated[
        float | None,
        typer.Option(
            "--transcribe-no-speech-threshold", help="Transcribe no speech threshold."
        ),
    ] = None,
    vad_threshold: Annotated[
        float | None, typer.Option("--vad-threshold", help="VAD threshold.")
    ] = None,
    replace_terms: Annotated[
        bool | None,
        typer.Option(
            "--replace-terms/--no-replace-terms", help="Enable term replacement."
        ),
    ] = None,
    lower: Annotated[
        bool | None, typer.Option("--lower/--no-lower", help="Lowercase text.")
    ] = None,
    remove_punct: Annotated[
        bool | None,
        typer.Option("--remove-punct/--no-remove-punct", help="Remove punctuation."),
    ] = None,
    pp_no_speech_threshold: Annotated[
        float | None,
        typer.Option(
            "--pp-no-speech-threshold", help="Post-process no speech threshold."
        ),
    ] = None,
    max_chars_per_second: Annotated[
        float | None,
        typer.Option("--max-chars-per-second", help="Max chars per second."),
    ] = None,
    end_padding: Annotated[
        float | None, typer.Option("--end-padding", help="Subtitle end padding.")
    ] = None,
    min_duration: Annotated[
        float | None, typer.Option("--min-duration", help="Subtitle min duration.")
    ] = None,
    min_gap: Annotated[
        float | None, typer.Option("--min-gap", help="Subtitle min gap.")
    ] = None,
    subtitle_formats: Annotated[
        str | None,
        typer.Option("--subtitle-formats", help="Comma-separated subtitle formats."),
    ] = None,
    chunk_size_ms: Annotated[
        int | None, typer.Option("--chunk-size-ms", help="Streaming chunk size in ms.")
    ] = None,
    buffer_size_seconds: Annotated[
        float | None,
        typer.Option("--buffer-size-seconds", help="Streaming buffer size in seconds."),
    ] = None,
    stream_sample_rate: Annotated[
        int | None,
        typer.Option("--stream-sample-rate", help="Streaming sample rate in Hz."),
    ] = None,
    flush_timeout_ms: Annotated[
        int | None, typer.Option("--flush-timeout-ms", help="Flush timeout in ms.")
    ] = None,
    word_gap_split_threshold: Annotated[
        float | None,
        typer.Option("--word-gap-split-threshold", help="Word gap split threshold."),
    ] = None,
    streaming_log: Annotated[
        bool | None,
        typer.Option(
            "--streaming-log/--no-streaming-log", help="Enable/disable streaming log."
        ),
    ] = None,
) -> None:
    """Process microphone audio: Remove keyboard/gamepad noise, generate SRT, and remux video."""
    cfg, resolved_input, do_denoise, do_transcribe = prepare_cli_execution(
        console=console,
        input_file=input_file,
        config_path=config_path,
        denoise_only=denoise_only,
        transcribe_only=transcribe_only,
        denoise=denoise,
        device=device,
        compute_type=compute_type,
        output_dir=output_dir,
        mic_track=mic_track,
        model_size=model_size,
        language=language,
        initial_prompt=initial_prompt,
        min_silence_ms=min_silence_ms,
        remux=remux,
        mastering_enabled=mastering_enabled,
        noise_gate_threshold=noise_gate_threshold,
        loudness_i=loudness_i,
        loudness_tp=loudness_tp,
        loudness_lra=loudness_lra,
        final_limit_db=final_limit_db,
        debug_output_dir=debug_output_dir,
        custom_dict_path=custom_dict_path,
        denoise_engine=denoise_engine,
        denoise_model_path=denoise_model_path,
        media_sample_rate=media_sample_rate,
        beam_size=beam_size,
        condition_on_previous_text=condition_on_previous_text,
        transcribe_no_speech_threshold=transcribe_no_speech_threshold,
        vad_threshold=vad_threshold,
        replace_terms=replace_terms,
        lower=lower,
        remove_punct=remove_punct,
        pp_no_speech_threshold=pp_no_speech_threshold,
        max_chars_per_second=max_chars_per_second,
        end_padding=end_padding,
        min_duration=min_duration,
        min_gap=min_gap,
        subtitle_formats=subtitle_formats,
        chunk_size_ms=chunk_size_ms,
        buffer_size_seconds=buffer_size_seconds,
        stream_sample_rate=stream_sample_rate,
        flush_timeout_ms=flush_timeout_ms,
        word_gap_split_threshold=word_gap_split_threshold,
        streaming_log=streaming_log,
    )

    print_status_panel(
        console=console,
        input_file=resolved_input,
        is_video=is_video_file(resolved_input),
        cfg=cfg,
        do_denoise=do_denoise,
    )

    try:
        result = run_pipeline(
            input_path=resolved_input,
            cfg=cfg,
            denoise=do_denoise,
            transcribe=do_transcribe,
            on_progress=create_progress_handler(console=console, cfg=cfg),
            on_segment=create_segment_handler(console=console, cfg=cfg),
        )
    except Exception as e:
        console.print(f"[bold red]Pipeline failed:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    print_result_table(console=console, result=result)


if __name__ == "__main__":
    app()
