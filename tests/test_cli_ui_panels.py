"""CLI UI のステータスパネルおよび結果テーブル描画の単体テスト。"""

import io
from pathlib import Path

from rich.console import Console

from audio_transcriber.cli_ui import (
    print_result_table,
    print_status_panel,
)
from audio_transcriber.config import AppConfig
from audio_transcriber.pipeline import PipelineResult


def create_test_console() -> tuple[Console, io.StringIO]:
    """テスト用の StringIO 出力を持つ Console インスタンスを生成します。

    Returns:
        tuple[Console, io.StringIO]: Console と出力バッファ。
    """
    string_io = io.StringIO()
    console = Console(file=string_io, color_system=None, width=120)
    return console, string_io


def test_cli_ui_panels_and_tables(tmp_path: Path) -> None:
    """print_status_panel および print_result_table の描画を検証します。"""
    # Arrange
    console, string_io = create_test_console()
    cfg = AppConfig()
    cfg.media.mic_track = 2
    cfg.pipeline.remux = True

    # Act & Assert Status Panel (Video)
    print_status_panel(
        console=console,
        input_file=tmp_path / "sample.mp4",
        is_video=True,
        cfg=cfg,
        do_denoise=True,
    )
    output1 = string_io.getvalue()
    assert "Audio Transcriber" in output1
    assert "sample.mp4" in output1
    assert "Track 2" in output1

    # Act & Assert Status Panel (Audio)
    string_io.seek(0)
    string_io.truncate(0)
    print_status_panel(
        console=console,
        input_file=tmp_path / "sample.wav",
        is_video=False,
        cfg=cfg,
        do_denoise=False,
    )
    output2 = string_io.getvalue()
    assert "sample.wav" in output2
    assert "Audio" in output2

    # Act & Assert Result Table
    string_io.seek(0)
    string_io.truncate(0)
    res = PipelineResult(
        input_file=tmp_path / "sample.mp4",
        denoised_audio=tmp_path / "sample_clean.wav",
        srt_file=tmp_path / "sample.srt",
        transcript_text="hello",
        remuxed_video=tmp_path / "sample_clean.mp4",
    )
    print_result_table(console=console, result=res)
    output3 = string_io.getvalue()
    assert "Generated Outputs" in output3
    assert "sample_clean.mp4" in output3
    assert "sample_clean.wav" in output3
    assert "sample.srt" in output3
