"""パイプライン処理における文字起こしイベント・後処理ヘルパーモジュール。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from audio_transcriber.config import AppConfig, SubtitleConfig
from audio_transcriber.exporter import SubtitleExporter
from audio_transcriber.models import SubtitleSegment
from audio_transcriber.pipeline_export import export_pipeline_subtitles
from audio_transcriber.postprocess import TextPostProcessor
from audio_transcriber.sanitizer import DropReason, SegmentSanitizer
from audio_transcriber.timing import SubtitleTimingAdjuster, split_segments_by_word_gap

__all__ = [
    "TranscriptionPipelineCollector",
    "export_pipeline_subtitles",
    "split_segments_by_word_gap",
]

logger = logging.getLogger(__name__)


class TranscriptionPipelineCollector:
    """文字起こしパイプラインのコールバックイベント集約および後処理管理クラス。"""

    def __init__(
        self,
        cfg: AppConfig,
        timecode_offset: float = 0.0,
        on_progress: Callable[[str, Any], None] | None = None,
        on_segment: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """初期化します。

        Args:
            cfg: アプリケーション設定オブジェクト。
            timecode_offset: 動画タイムコードオフセット（秒）。
            on_progress: 進捗通知コールバック関数。
            on_segment: 認識セグメント通知コールバック関数。
        """
        self.cfg = cfg
        self.timecode_offset = timecode_offset
        self.on_progress = on_progress
        self.on_segment = on_segment

        self.vad_chunks_collected: list[tuple[float, float]] = []
        self.processing_events: list[dict[str, Any]] = []
        self.offset_segment_dicts: list[dict[str, Any]] = []
        self.sanitized_segments: list[SubtitleSegment] = []
        self.processed_segments: list[SubtitleSegment] = []
        self.final_segments: list[SubtitleSegment] = []

        self._pending_item: tuple[SubtitleSegment, dict[str, Any]] | None = None
        self._current_vad_idx = -1
        self.raw_count = 0
        self.dropped_count = 0
        self.replaced_count = 0
        self.overlap_prevented_count = 0

        self.adjuster = SubtitleTimingAdjuster(
            end_padding=cfg.subtitle.end_padding,
            min_duration=cfg.subtitle.min_duration,
            min_gap=cfg.subtitle.min_gap,
        )
        self.sanitizer = SegmentSanitizer(
            no_speech_threshold=cfg.post_process.no_speech_threshold,
            max_chars_per_second=cfg.post_process.max_chars_per_second,
        )
        self.processor = TextPostProcessor(
            dictionary_path=cfg.paths.custom_dict_path
            if cfg.post_process.replace_terms
            else None,
            lower=cfg.post_process.lower,
            remove_punct=cfg.post_process.remove_punct,
        )

    def _flush_pending_segment(self, next_start: float | None = None) -> None:
        """保留中の未確定セグメントに対してタイミング調整を実施し、重複防止・確定テキストを通知します。

        Args:
            next_start: 次の発話セグメントの開始時刻（秒）。存在しない場合は None。
        """
        if self._pending_item is None:
            return

        clean_seg, sub_seg = self._pending_item
        (
            adj_seg,
            overlap_prevented,
            raw_target_end,
        ) = self.adjuster.adjust_single_segment(
            seg=clean_seg,
            next_start=next_start,
        )

        if overlap_prevented and next_start is not None:
            self.overlap_prevented_count += 1
            self.processing_events.append(
                {
                    "start": clean_seg.start,
                    "type": "重複防止",
                    "message": f"終了時刻 {SubtitleExporter.format_timestamp(raw_target_end)} ➔ {SubtitleExporter.format_timestamp(adj_seg.end)} (次発話との重複を回避)",
                }
            )
            if self.on_progress:
                self.on_progress(
                    "postprocess_overlap_prevented",
                    f"終了時刻 {SubtitleExporter.format_timestamp(raw_target_end)} ➔ {SubtitleExporter.format_timestamp(adj_seg.end)} (次発話 {SubtitleExporter.format_timestamp(next_start)} との重複を回避)",
                )

        self.final_segments.append(adj_seg)
        if self.on_progress:
            self.on_progress("text_confirmed", adj_seg)

        if self.on_segment is not None:
            out_dict = dict(sub_seg)
            out_dict["start"] = adj_seg.start
            out_dict["end"] = adj_seg.end
            out_dict["text"] = adj_seg.text
            self.on_segment(out_dict)

        self._pending_item = None

    def handle_progress(self, stage: str, message: Any) -> None:
        """VADや処理進捗イベントを受け取り、タイムコードオフセットを加味して集約・通知します。

        Args:
            stage: 進捗ステージ名。
            message: 進捗メッセージまたはデータ。
        """
        if stage == "vad_chunks":
            for chunk in message:
                v_start, v_end = chunk
                self.vad_chunks_collected.append(
                    (v_start + self.timecode_offset, v_end + self.timecode_offset)
                )
            if self.on_progress:
                self.on_progress("vad_chunks", self.vad_chunks_collected)
        else:
            if self.on_progress:
                self.on_progress(stage, message)

    def handle_segment(self, seg_dict: dict[str, Any]) -> None:
        """Whisperから通知されたセグメントを受け取り、単語間分割・サニタイズ・テキスト置換を実施します。

        Args:
            seg_dict: Whisperの認識セグメント辞書。
        """
        gap_threshold = self.cfg.stream.word_gap_split_threshold
        sub_segments = split_segments_by_word_gap(
            seg_dict=seg_dict,
            timecode_offset=self.timecode_offset,
            gap_threshold=gap_threshold,
        )

        for sub_seg in sub_segments:
            self.offset_segment_dicts.append(sub_seg)
            self.raw_count += 1
            s_start = float(sub_seg["start"])
            s_end = float(sub_seg["end"])
            dur = max(0.0, s_end - s_start)
            raw_text = str(sub_seg.get("text", "")).strip()

            while self._current_vad_idx + 1 < len(self.vad_chunks_collected):
                next_vad = self.vad_chunks_collected[self._current_vad_idx + 1]
                if s_start >= next_vad[0]:
                    self._current_vad_idx += 1
                    if self.on_progress:
                        self.on_progress("vad_chunk_start", next_vad)
                else:
                    break

            if self.on_progress:
                self.on_progress(
                    "whisper_raw",
                    {
                        "start": s_start,
                        "end": s_end,
                        "duration": dur,
                        "text": raw_text,
                    },
                )

            res = self.sanitizer.sanitize_with_result(sub_seg)
            if res.repeat_shortened:
                self.processing_events.append(
                    {
                        "start": s_start,
                        "type": "リピート短縮",
                        "message": f"'{res.original_text}' ➔ '{res.cleaned_text}'",
                    }
                )
                if self.on_progress:
                    self.on_progress(
                        "postprocess_repeat",
                        {
                            "start": s_start,
                            "end": s_end,
                            "old_text": res.original_text,
                            "new_text": res.cleaned_text,
                        },
                    )

            if res.segment is None:
                self.dropped_count += 1
                detail = res.drop_detail or ""
                stage = "postprocess_dropped"
                type_name = "除外"
                if res.drop_reason == DropReason.NO_SPEECH:
                    stage = "postprocess_drop_no_speech"
                    type_name = "無音捏造除外"
                    msg = f"'{raw_text}' ({detail})"
                elif res.drop_reason == DropReason.SPEED:
                    stage = "postprocess_drop_speed"
                    type_name = "異常発話速度除外"
                    msg = f"'{raw_text}' ({detail})"
                elif res.drop_reason == DropReason.LOOP:
                    stage = "postprocess_drop_loop"
                    type_name = "ループ重複除外"
                    msg = f"'{raw_text}' (直前='{self.sanitizer.last_valid_text}', {detail})"
                else:
                    stage = "postprocess_drop_empty"
                    type_name = "空文字除外"
                    msg = f"'{raw_text}' (空文字)"

                self.processing_events.append(
                    {"start": s_start, "type": type_name, "message": msg}
                )
                if self.on_progress:
                    self.on_progress(stage, msg)
                continue

            clean_seg = res.segment
            self._flush_pending_segment(next_start=clean_seg.start)
            self.sanitized_segments.append(clean_seg)
            old_text = clean_seg.text
            new_text = self.processor.apply_to_text(old_text)

            if new_text != old_text:
                self.replaced_count += 1
                clean_seg.text = new_text
                self.processing_events.append(
                    {
                        "start": clean_seg.start,
                        "type": "テキスト置換",
                        "message": f"'{old_text}' ➔ '{new_text}'",
                    }
                )
                if self.on_progress:
                    self.on_progress(
                        "postprocess_replaced",
                        {
                            "start": clean_seg.start,
                            "end": clean_seg.end,
                            "old_text": old_text,
                            "new_text": new_text,
                        },
                    )

            self.processed_segments.append(clean_seg)
            self._pending_item = (clean_seg, sub_seg)

    def finalize_timing_and_summary(
        self, sub_cfg: SubtitleConfig | None = None
    ) -> list[SubtitleSegment]:
        """保留中の最終セグメントを確定し、処理結果サマリーを通知します。

        Args:
            sub_cfg: 字幕設定オブジェクト。省略時は初期化時の設定を使用。

        Returns:
            list[SubtitleSegment]: 確定した字幕セグメントのリスト。
        """
        if sub_cfg is not None:
            self.adjuster.end_padding = sub_cfg.end_padding
            self.adjuster.min_duration = sub_cfg.min_duration
            self.adjuster.min_gap = sub_cfg.min_gap

        self._flush_pending_segment(next_start=None)

        if self.on_progress:
            self.on_progress(
                "postprocess_summary",
                f"サマリー: {self.raw_count}件中 {self.dropped_count}件除外、{self.replaced_count}件置換、{self.overlap_prevented_count}件重複防止 (確定字幕: {len(self.final_segments)}件)",
            )
        return self.final_segments
