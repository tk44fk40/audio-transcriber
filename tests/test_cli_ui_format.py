"""CLI UI の STREAMING_LOG=true 時の詳細フォーマットおよびイベント出力テスト。"""

import io

from rich.console import Console

from audio_transcriber.cli_ui import create_progress_handler
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


def test_cli_ui_streaming_log_true_event_formats() -> None:
    """STREAMING_LOG=true 時のインデントログフォーマットおよび各種イベント出力を検証します。"""
    # Arrange
    console, string_io = create_test_console()
    cfg = AppConfig()
    cfg.stream.streaming_log = True
    handler = create_progress_handler(console=console, cfg=cfg)

    # Act
    # 1. VAD chunk (tuple & fallback str)
    handler("vad_chunk_start", (1.0, 5.0))
    handler("vad_chunk_start", "invalid chunk format")

    # 2. Whisper 生認識 (dict & fallback str)
    handler(
        "whisper_raw",
        {"start": 1.2, "end": 4.8, "duration": 3.6, "text": "生の音声認識テキスト"},
    )
    handler("whisper_raw", "raw str msg")

    # 3. テキスト置換 (dict & fallback str)
    handler(
        "postprocess_replaced",
        {"start": 1.2, "end": 4.8, "old_text": "旧", "new_text": "新"},
    )
    handler("postprocess_replaced", "replaced string")

    # 4. リピート短縮 (dict & fallback str)
    handler(
        "postprocess_repeat",
        {"start": 1.2, "end": 4.8, "old_text": "テストテスト", "new_text": "テスト"},
    )
    handler("postprocess_repeat", "repeat string")

    # 5. 除外イベント各種
    handler("postprocess_drop_no_speech", "'無音' (no_speech_prob=0.85)")
    handler("postprocess_drop_speed", "'異常速度' (15.0 chars/s)")
    handler("postprocess_drop_loop", "'ループ' (直前='ループ', no_speech_prob=0.30)")
    handler("postprocess_drop_empty", "'' (空文字)")
    handler("postprocess_dropped", "汎用除外メッセージ")

    # 6. 重複防止
    handler(
        "postprocess_overlap_prevented",
        "終了時刻 00:00:04,800 ➔ 00:00:04,500 (次発話との重複を回避)",
    )

    # 7. 確定テキスト (SubtitleSegment & dict & str)
    handler(
        "text_confirmed",
        SubtitleSegment(start=1.2, end=4.5, text="最終確定テキスト"),
    )
    handler("text_confirmed", {"start": 5.0, "end": 6.0, "text": "辞書テキスト"})
    handler("text_confirmed", "単純文字列テキスト")

    # 8. サマリー表示 & VAD & その他
    handler("postprocess_summary", "サマリー: 10件中 2件除外、1件置換、1件重複防止")
    handler("vad", "VAD検出中...")
    handler("extract", "音声抽出中...")
    handler("vad_chunks", [(1.0, 5.0)])

    output = string_io.getvalue()

    # Assert
    assert "[VAD] 00:00:01,000 --> 00:00:05,000 (4.00s)" in output
    assert "[VAD] invalid chunk format" in output
    assert (
        "  [Whisper] 00:00:01,200 --> 00:00:04,800 (3.60s) 生の音声認識テキスト"
        in output
    )
    assert "  [Whisper] raw str msg" in output
    assert "  [テキスト置換] '旧' ➔ '新'" in output
    assert "  [テキスト置換] replaced string" in output
    assert "  [リピート短縮] 'テストテスト' ➔ 'テスト'" in output
    assert "  [リピート短縮] repeat string" in output
    assert "  [無音捏造除外] '無音' (no_speech_prob=0.85)" in output
    assert "  [異常発話速度除外] '異常速度' (15.0 chars/s)" in output
    assert "  [ループ重複除外] 'ループ' (直前='ループ', no_speech_prob=0.30)" in output
    assert "  [空文字除外] '' (空文字)" in output
    assert "  [無音捏造等除外] 汎用除外メッセージ" in output
    assert (
        "  [重複防止] 終了時刻 00:00:04,800 ➔ 00:00:04,500 (次発話との重複を回避)"
        in output
    )
    assert "  [Text] 00:00:01,200 --> 00:00:04,500 (3.30s) 最終確定テキスト" in output
    assert "  [Text] 00:00:05,000 --> 00:00:06,000 (1.00s) 辞書テキスト" in output
    assert "  [Text] 00:00:00,000 --> 00:00:00,000 (0.00s) 単純文字列テキスト" in output
    assert (
        "▶ [postprocess_summary] サマリー: 10件中 2件除外、1件置換、1件重複防止"
        in output
    )
    assert "▶ [vad] VAD検出中..." in output
    assert "▶ [extract] 音声抽出中..." in output


def test_cli_ui_streaming_log_postprocess_summary() -> None:
    """STREAMING_LOG=true 時に ▶ [postprocess_summary] が付与されてサマリーが出力されることを検証します。"""
    # Arrange
    console, string_io = create_test_console()
    cfg = AppConfig()
    cfg.stream.streaming_log = True
    handler = create_progress_handler(console=console, cfg=cfg)

    # Act
    summary_message = "10件中 2件除外、1件置換、1件重複防止"
    handler("postprocess_summary", summary_message)
    output = string_io.getvalue()

    # Assert
    assert f"▶ [postprocess_summary] {summary_message}" in output
