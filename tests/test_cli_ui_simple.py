"""CLI UI の STREAMING_LOG=false 時のシンプル出力・抑制制御・セグメントハンドラの単体テスト。"""

import io

from rich.console import Console

from audio_transcriber.cli_ui import (
    create_progress_handler,
    create_segment_handler,
)
from audio_transcriber.config import AppConfig
from audio_transcriber.models import SubtitleSegment


def create_test_console() -> tuple[Console, io.StringIO]:
    """テスト用の StringIO 出力を持つ Console インスタンスを生成します。

    Returns:
        tuple[Console, io.StringIO]: Console と出力バッファ。
    """
    string_io = io.StringIO()
    console = Console(file=string_io, color_system=None, width=120)
    return console, string_io


def test_cli_ui_streaming_log_false_simple_output() -> None:
    """STREAMING_LOG=false 時のシンプル出力（[Text] のみ表示・内部ログ抑制）を検証します。"""
    # Arrange
    console, string_io = create_test_console()
    cfg = AppConfig()
    cfg.stream.streaming_log = False
    handler = create_progress_handler(console=console, cfg=cfg)

    # Act
    # 進捗・内部ログ（抑制されるべき）
    handler("extract", "抽出中...")
    handler("denoise", "ノイズ除去中...")
    handler("transcribe", "文字起こし中...")
    handler("vad_chunk_start", (1.0, 5.0))
    handler(
        "whisper_raw",
        {"start": 1.2, "end": 4.8, "duration": 3.6, "text": "生の音声認識テキスト"},
    )
    handler(
        "postprocess_replaced",
        {"start": 1.2, "end": 4.8, "old_text": "旧", "new_text": "新"},
    )
    handler("postprocess_drop_no_speech", "無音除外")
    handler("postprocess_overlap_prevented", "重複防止")
    handler("postprocess_summary", "サマリー情報")
    handler("done", "完了")

    # 確定テキスト（表示されるべき）
    handler(
        "text_confirmed",
        SubtitleSegment(start=1.2, end=4.5, text="最終確定テキスト"),
    )
    handler("text_confirmed", {"start": 5.0, "end": 6.0, "text": "辞書確定テキスト"})
    handler("text_confirmed", "文字列確定テキスト")

    output = string_io.getvalue()

    # Assert
    assert "[VAD]" not in output
    assert "[Whisper]" not in output
    assert "[テキスト置換]" not in output
    assert "[無音捏造除外]" not in output
    assert "[重複防止]" not in output
    assert "[postprocess_summary]" not in output
    assert "▶ [extract]" not in output
    assert "▶ [transcribe]" not in output
    assert "[Text] 00:00:01,200 --> 00:00:04,500 (3.30s) 最終確定テキスト" in output
    assert "[Text] 00:00:05,000 --> 00:00:06,000 (1.00s) 辞書確定テキスト" in output
    assert "[Text] 00:00:00,000 --> 00:00:00,000 (0.00s) 文字列確定テキスト" in output


def test_cli_ui_segment_handler() -> None:
    """create_segment_handler の呼び出しがエラーなく動作することを検証します。"""
    # Arrange
    console, string_io = create_test_console()
    cfg = AppConfig()
    cfg.stream.streaming_log = True
    seg_handler = create_segment_handler(console=console, cfg=cfg)

    # Act
    seg_handler({"start": 1.0, "end": 2.0, "text": "セグメント"})

    # Assert
    assert isinstance(string_io.getvalue(), str)
