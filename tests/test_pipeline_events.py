"""TranscriptionPipelineCollector のイベント処理および後処理の単体テスト。"""

from typing import Any

from audio_transcriber.config import AppConfig
from audio_transcriber.pipeline_events import TranscriptionPipelineCollector


def test_pipeline_collector_all_drop_reasons_and_repeats() -> None:
    """Collector で各種除外理由（無音・異常速度・ループ・空文字）およびリピート短縮が通知されることを検証。"""
    # Arrange
    cfg = AppConfig()
    cfg.post_process.no_speech_threshold = 0.5
    cfg.post_process.max_chars_per_second = 10.0
    cfg.post_process.replace_terms = True

    events_progress: list[tuple[str, Any]] = []
    segments_received: list[dict[str, Any]] = []

    collector = TranscriptionPipelineCollector(
        cfg=cfg,
        timecode_offset=1.0,
        on_progress=lambda stage, msg: events_progress.append((stage, msg)),
        on_segment=lambda seg: segments_received.append(seg),
    )

    # VADチャンクの受信
    collector.handle_progress("vad_chunks", [(0.0, 5.0), (10.0, 15.0)])
    collector.handle_progress("other_stage", "message")

    # 1. 正常セグメント + リピート短縮
    collector.handle_segment(
        {
            "start": 0.5,
            "end": 2.5,
            "text": "テストテスト",
            "no_speech_prob": 0.2,
            "compression_ratio": 1.5,
        }
    )

    # 2. ループ重複除外
    collector.handle_segment(
        {
            "start": 2.6,
            "end": 4.0,
            "text": "テスト",
            "no_speech_prob": 0.3,
        }
    )

    # 3. 無音捏造除外
    collector.handle_segment(
        {
            "start": 4.1,
            "end": 5.5,
            "text": "無音捏造発話テキスト",
            "no_speech_prob": 0.95,
        }
    )

    # 4. 異常発話速度除外 (0.2秒に15文字)
    collector.handle_segment(
        {
            "start": 5.6,
            "end": 5.8,
            "text": "非常に高速な捏造テキストです",
            "no_speech_prob": 0.05,
        }
    )

    # 5. 空文字除外
    collector.handle_segment(
        {
            "start": 6.0,
            "end": 7.0,
            "text": "   \t\n  ",
            "no_speech_prob": 0.0,
        }
    )

    # 最終セグメント確定
    collector.finalize_timing_and_summary(cfg.subtitle)

    # Assert
    stages = [p[0] for p in events_progress]
    assert "vad_chunks" in stages
    assert "vad_chunk_start" in stages
    assert "whisper_raw" in stages
    assert "postprocess_repeat" in stages
    assert "postprocess_drop_loop" in stages
    assert "postprocess_drop_no_speech" in stages
    assert "postprocess_drop_speed" in stages
    assert "postprocess_drop_empty" in stages
    assert "text_confirmed" in stages

    assert len(segments_received) == 1
    assert segments_received[0]["text"] == "テスト"


def test_pipeline_collector_streaming_timing_and_overlap_order() -> None:
    """セグメントごとに重複防止・確定テキストがリアルタイムに順序正しく通知されることを検証。"""
    # Arrange
    cfg = AppConfig()
    cfg.subtitle.end_padding = 1.0
    cfg.subtitle.min_duration = 1.0
    cfg.subtitle.min_gap = 0.1

    events_progress: list[tuple[str, Any]] = []
    segments_received: list[dict[str, Any]] = []

    collector = TranscriptionPipelineCollector(
        cfg=cfg,
        timecode_offset=0.0,
        on_progress=lambda stage, msg: events_progress.append((stage, msg)),
        on_segment=lambda seg: segments_received.append(seg),
    )

    # Act 1: 1件目のセグメント (0.0s - 2.0s) -> 保留される
    collector.handle_segment({"start": 0.0, "end": 2.0, "text": "1件目の発話"})
    assert len(segments_received) == 0
    stages_after_seg1 = [p[0] for p in events_progress]
    assert "whisper_raw" in stages_after_seg1
    assert "text_confirmed" not in stages_after_seg1

    # Act 2: 2件目のセグメント (2.5s - 4.0s) -> 1件目の余韻(2.0+1.0=3.0s)と重複するため重複防止発生し1件目が確定
    collector.handle_segment({"start": 2.5, "end": 4.0, "text": "2件目の発話"})
    assert len(segments_received) == 1
    assert segments_received[0]["text"] == "1件目の発話"
    # 1件目の終了時刻は 2.5 - 0.1 = 2.4s に短縮されているはず
    assert segments_received[0]["end"] == 2.4

    stages_after_seg2 = [p[0] for p in events_progress]
    assert "postprocess_overlap_prevented" in stages_after_seg2
    assert "text_confirmed" in stages_after_seg2

    # 重複防止通知が text_confirmed より前に発生していることを検証
    overlap_idx = stages_after_seg2.index("postprocess_overlap_prevented")
    confirmed_idx = stages_after_seg2.index("text_confirmed")
    assert overlap_idx < confirmed_idx

    # Act 3: 完了処理 -> 2件目が確定
    final_segs = collector.finalize_timing_and_summary(cfg.subtitle)
    assert len(final_segs) == 2
    assert len(segments_received) == 2
    assert segments_received[1]["text"] == "2件目の発話"
    # 2件目は次セグメントがないので 4.0 + 1.0 = 5.0s
    assert segments_received[1]["end"] == 5.0

    final_stages = [p[0] for p in events_progress]
    assert "postprocess_summary" in final_stages


def test_pipeline_collector_without_callbacks() -> None:
    """コールバックが None の場合でも例外なく正常に処理が完了することを検証。"""
    # Arrange
    cfg = AppConfig()
    collector = TranscriptionPipelineCollector(
        cfg=cfg,
        on_progress=None,
        on_segment=None,
    )

    # Act
    collector.handle_progress("stage", "msg")
    collector.handle_segment({"start": 0.0, "end": 1.0, "text": "test"})
    final_segs = collector.finalize_timing_and_summary(cfg.subtitle)

    # Assert
    assert len(final_segs) == 1
    assert final_segs[0].text == "test"


def test_pipeline_collector_all_segments_dropped_edge_case() -> None:
    """全セグメントが無音捏造等で除外された場合でも、サマリーが正しく通知され空リストが返ることを検証。"""
    # Arrange
    cfg = AppConfig()
    events_progress: list[tuple[str, Any]] = []
    collector = TranscriptionPipelineCollector(
        cfg=cfg,
        on_progress=lambda stage, msg: events_progress.append((stage, msg)),
    )

    # Act
    collector.handle_segment(
        {"start": 0.0, "end": 1.0, "text": "無音捏造", "no_speech_prob": 0.99}
    )
    collector.handle_segment(
        {"start": 1.5, "end": 1.6, "text": "超高速捏造テキスト", "no_speech_prob": 0.05}
    )
    final_segs = collector.finalize_timing_and_summary(cfg.subtitle)

    # Assert
    assert len(final_segs) == 0
    assert collector.raw_count == 2
    assert collector.dropped_count == 2
    assert collector.replaced_count == 0
    assert collector.overlap_prevented_count == 0
    summary_msg = next(p[1] for p in events_progress if p[0] == "postprocess_summary")
    assert "2件中 2件除外" in summary_msg
    assert "確定字幕: 0件" in summary_msg
