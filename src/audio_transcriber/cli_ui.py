"""CLI ユーザーインターフェース表示およびコールバックハンドラモジュール。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from audio_transcriber.config import AppConfig
from audio_transcriber.exporter import SubtitleExporter
from audio_transcriber.pipeline import PipelineResult


def print_status_panel(
    console: Console,
    input_file: Path,
    is_video: bool,
    cfg: AppConfig,
    do_denoise: bool,
) -> None:
    """処理開始前のステータスパネルを表示します。

    Args:
        console: Rich Console インスタンス。
        input_file: 入力メディアファイルパス。
        is_video: 動画ファイルかどうかのフラグ。
        cfg: アプリケーション設定オブジェクト。
        do_denoise: ノイズ除去を実行するかどうかのフラグ。
    """
    status_lines = [
        "[bold cyan]Audio Transcriber[/bold cyan]",
        f"Input: [yellow]{input_file.name}[/yellow] ({'Video' if is_video else 'Audio'})",
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


def print_result_table(console: Console, result: PipelineResult) -> None:
    """生成された出力ファイルのサマリーテーブルを表示します。

    Args:
        console: Rich Console インスタンス。
        result: パイプライン実行結果オブジェクト。
    """
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


def create_progress_handler(
    console: Console, cfg: AppConfig
) -> Callable[[str, Any], None]:
    """進捗通知を受け取るコールバック関数を生成します。

    Args:
        console: Rich Console インスタンス。
        cfg: アプリケーション設定オブジェクト。

    Returns:
        Callable[[str, Any], None]: 進捗ハンドラ関数。
    """

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

        if stage == "vad_chunks":
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

    return handle_progress


def create_segment_handler(
    console: Console, cfg: AppConfig
) -> Callable[[dict[str, Any]], None]:
    """認識セグメントを受け取るコールバック関数を生成します。

    Args:
        console: Rich Console インスタンス。
        cfg: アプリケーション設定オブジェクト。

    Returns:
        Callable[[dict[str, Any]], None]: セグメントハンドラ関数。
    """

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

    return handle_segment
