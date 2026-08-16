"""CLI ユーザーインターフェース表示およびコールバックハンドラモジュール。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from audio_transcriber.config import AppConfig
from audio_transcriber.exporter import SubtitleExporter
from audio_transcriber.models import SubtitleSegment
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
            if stage == "text_confirmed":
                if isinstance(message, SubtitleSegment):
                    s_str = SubtitleExporter.format_timestamp(message.start)
                    e_str = SubtitleExporter.format_timestamp(message.end)
                    dur = max(0.0, message.end - message.start)
                    txt = message.text
                elif isinstance(message, dict):
                    s_str = SubtitleExporter.format_timestamp(message.get("start", 0.0))
                    e_str = SubtitleExporter.format_timestamp(message.get("end", 0.0))
                    dur = float(message.get("end", 0.0)) - float(
                        message.get("start", 0.0)
                    )
                    txt = str(message.get("text", ""))
                else:
                    txt = str(message)
                    s_str, e_str, dur = "00:00:00,000", "00:00:00,000", 0.0
                console.print(
                    f"[bold green]{escape('[Text]')}[/bold green] {s_str} --> {e_str} ({dur:.2f}s) {escape(txt)}"
                )
            return

        if stage == "vad_chunks":
            return
        if stage == "vad_chunk_start":
            if isinstance(message, (tuple, list)) and len(message) >= 2:
                v_start, v_end = float(message[0]), float(message[1])
                dur = max(0.0, v_end - v_start)
                s_str = SubtitleExporter.format_timestamp(v_start)
                e_str = SubtitleExporter.format_timestamp(v_end)
                console.print(
                    f"[bold magenta]{escape('[VAD]')}[/bold magenta] {s_str} --> {e_str} ({dur:.2f}s)"
                )
            else:
                console.print(
                    f"[bold magenta]{escape('[VAD]')}[/bold magenta] {escape(str(message))}"
                )
        elif stage == "whisper_raw":
            if isinstance(message, dict):
                s_str = SubtitleExporter.format_timestamp(message.get("start", 0.0))
                e_str = SubtitleExporter.format_timestamp(message.get("end", 0.0))
                dur = float(message.get("duration", 0.0))
                txt = str(message.get("text", ""))
                console.print(
                    f"  [bold cyan]{escape('[Whisper]')}[/bold cyan] {s_str} --> {e_str} ({dur:.2f}s) {escape(txt)}"
                )
            else:
                console.print(
                    f"  [bold cyan]{escape('[Whisper]')}[/bold cyan] {escape(str(message))}"
                )
        elif stage == "postprocess_replaced":
            if isinstance(message, dict):
                old_t = str(message.get("old_text", ""))
                new_t = str(message.get("new_text", ""))
                console.print(
                    f"  [green]{escape('[テキスト置換]')}[/green] '{escape(old_t)}' ➔ '{escape(new_t)}'"
                )
            else:
                console.print(
                    f"  [green]{escape('[テキスト置換]')}[/green] {escape(str(message))}"
                )
        elif stage == "postprocess_repeat":
            if isinstance(message, dict):
                old_t = str(message.get("old_text", ""))
                new_t = str(message.get("new_text", ""))
                console.print(
                    f"  [yellow]{escape('[リピート短縮]')}[/yellow] '{escape(old_t)}' ➔ '{escape(new_t)}'"
                )
            else:
                console.print(
                    f"  [yellow]{escape('[リピート短縮]')}[/yellow] {escape(str(message))}"
                )
        elif stage == "postprocess_drop_no_speech":
            console.print(
                f"  [yellow]{escape('[無音捏造除外]')}[/yellow] {escape(str(message))}"
            )
        elif stage == "postprocess_drop_speed":
            console.print(
                f"  [yellow]{escape('[異常発話速度除外]')}[/yellow] {escape(str(message))}"
            )
        elif stage == "postprocess_drop_loop":
            console.print(
                f"  [yellow]{escape('[ループ重複除外]')}[/yellow] {escape(str(message))}"
            )
        elif stage == "postprocess_drop_empty":
            console.print(
                f"  [yellow]{escape('[空文字除外]')}[/yellow] {escape(str(message))}"
            )
        elif stage == "postprocess_dropped":
            console.print(
                f"  [yellow]{escape('[無音捏造等除外]')}[/yellow] {escape(str(message))}"
            )
        elif stage == "postprocess_overlap_prevented":
            console.print(
                f"  [magenta]{escape('[重複防止]')}[/magenta] {escape(str(message))}"
            )
        elif stage == "text_confirmed":
            if isinstance(message, SubtitleSegment):
                s_str = SubtitleExporter.format_timestamp(message.start)
                e_str = SubtitleExporter.format_timestamp(message.end)
                dur = max(0.0, message.end - message.start)
                txt = message.text
            elif isinstance(message, dict):
                s_str = SubtitleExporter.format_timestamp(message.get("start", 0.0))
                e_str = SubtitleExporter.format_timestamp(message.get("end", 0.0))
                dur = float(message.get("end", 0.0)) - float(message.get("start", 0.0))
                txt = str(message.get("text", ""))
            else:
                txt = str(message)
                s_str, e_str, dur = "00:00:00,000", "00:00:00,000", 0.0
            console.print(
                f"  [bold green]{escape('[Text]')}[/bold green] {s_str} --> {e_str} ({dur:.2f}s) {escape(txt)}"
            )
        elif stage == "postprocess_summary":
            console.print(
                f"[bold white]▶ {escape('[postprocess_summary]')}[/bold white] {escape(str(message))}"
            )
        elif stage == "vad":
            console.print(
                f"[bold magenta]▶ {escape('[vad]')}[/bold magenta] {escape(str(message))}"
            )
        else:
            console.print(
                f"[bold cyan]▶ {escape(f'[{stage}]')}[/bold cyan] {escape(str(message))}"
            )

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
        _ = seg

    return handle_segment
