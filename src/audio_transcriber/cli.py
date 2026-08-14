"""Command-line interface for audio-transcriber."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from audio_transcriber.config import load_config
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
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to the input audio or video file (MP4, MKV, WAV, etc.).",
        ),
    ],
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
    min_silence_ms: Annotated[
        int | None,
        typer.Option(
            "--min-silence-ms",
            help="Minimum silence duration in ms for VAD splitting.",
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

    resolved_output_dir = output_dir if output_dir is not None else cfg.output_dir
    resolved_mic_track = mic_track if mic_track is not None else cfg.media.mic_track
    resolved_model_size = model_size if model_size is not None else cfg.model.model_size
    resolved_device = device if device is not None else cfg.model.device
    resolved_compute_type = (
        compute_type if compute_type is not None else cfg.model.compute_type
    )
    resolved_language = language if language is not None else cfg.transcribe.language
    resolved_prompt = (
        initial_prompt if initial_prompt is not None else cfg.transcribe.initial_prompt
    )
    resolved_remux = remux if remux is not None else cfg.pipeline.remux
    resolved_vad_filter = cfg.transcribe.vad.vad_filter
    resolved_min_silence = (
        min_silence_ms
        if min_silence_ms is not None
        else cfg.transcribe.vad.min_silence_duration_ms
    )

    do_denoise = not transcribe_only
    do_transcribe = not denoise_only
    is_video = is_video_file(input_file)

    status_lines = [
        "[bold cyan]Audio Transcriber[/bold cyan]",
        f"Input: [yellow]{input_file.name}[/yellow] ({'Video' if is_video else 'Audio'})",
    ]
    if is_video:
        status_lines.append(
            f"Mic Track: [green]Track {resolved_mic_track}[/green] | "
            f"Remux Video: [green]{resolved_remux}[/green]"
        )
    status_lines.append(
        f"Device: [green]{resolved_device}[/green] | "
        f"Whisper: [green]{resolved_model_size}[/green] | "
        f"Denoise: [green]{do_denoise}[/green]"
    )

    console.print(Panel.fit("\n".join(status_lines), border_style="cyan"))

    with console.status("[bold green]Processing media...[/bold green]") as status:
        try:
            if is_video:
                status.update(
                    f"[bold yellow]Extracting mic track {resolved_mic_track} "
                    "from video...[/bold yellow]"
                )
            if do_denoise:
                status.update(
                    "[bold yellow]Denoising microphone audio with RNNoise...[/bold yellow]"
                )
            result = run_pipeline(
                input_path=input_file,
                output_dir=resolved_output_dir,
                model_size=resolved_model_size,
                device=resolved_device,
                compute_type=resolved_compute_type,
                language=resolved_language,
                initial_prompt=resolved_prompt,
                denoise=do_denoise,
                transcribe=do_transcribe,
                mic_track=resolved_mic_track,
                remux=resolved_remux,
                vad_filter=resolved_vad_filter,
                min_silence_duration_ms=resolved_min_silence,
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
