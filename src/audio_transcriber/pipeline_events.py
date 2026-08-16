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
from audio_transcriber.sanitizer import SegmentSanitizer
from audio_transcriber.timing import SubtitleTimingAdjuster

__all__ = [
    "TranscriptionPipelineCollector",
    "export_pipeline_subtitles",
    "split_segments_by_word_gap",
]

logger = logging.getLogger(__name__)


def split_segments_by_word_gap(
    seg_dict: dict[str, Any],
    timecode_offset: float,
    gap_threshold: float,
) -> list[dict[str, Any]]:
    """単語間ギャップに基づいてセグメントを分割し、タイムコードオフセットを適用します。

    Args:
        seg_dict: Whisperからの生セグメント辞書。
        timecode_offset: 適用するタイムコードオフセット（秒）。
        gap_threshold: 単語間ギャップによる分割閾値（秒）。

    Returns:
        list[dict[str, Any]]: 分割・オフセット調整済みのセグメント辞書リスト。
    """
    mapped = dict(seg_dict)
    mapped["start"] = float(seg_dict.get("start", 0.0)) + timecode_offset
    mapped["end"] = float(seg_dict.get("end", 0.0)) + timecode_offset

    words = mapped.get("words", [])
    if not words:
        return [mapped]

    new_words: list[dict[str, Any]] = []
    for w in words:
        if isinstance(w, dict):
            new_w = dict(w)
            new_w["start"] = float(w.get("start", 0.0)) + timecode_offset
            new_w["end"] = float(w.get("end", 0.0)) + timecode_offset
            new_words.append(new_w)

    sub_segments: list[dict[str, Any]] = []
    current_chunk: list[dict[str, Any]] = []
    current_start = float(new_words[0].get("start", 0.0))

    for i, w in enumerate(new_words):
        current_chunk.append(w)
        if i < len(new_words) - 1:
            next_start = float(new_words[i + 1].get("start", 0.0))
            gap = next_start - w["end"]
            if gap >= gap_threshold:
                new_seg = dict(mapped)
                new_seg["words"] = current_chunk
                new_seg["start"] = current_start
                new_seg["end"] = w["end"]
                new_seg["text"] = "".join(
                    x.get("word", "") for x in current_chunk
                ).strip()
                sub_segments.append(new_seg)
                current_chunk = []
                current_start = next_start

    if current_chunk:
        new_seg = dict(mapped)
        new_seg["words"] = current_chunk
        new_seg["start"] = current_start
        new_seg["end"] = current_chunk[-1]["end"]
        new_seg["text"] = "".join(x.get("word", "") for x in current_chunk).strip()
        sub_segments.append(new_seg)

    return sub_segments


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

        self._current_vad_idx = -1
        self.raw_count = 0
        self.dropped_count = 0
        self.replaced_count = 0

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

            while self._current_vad_idx + 1 < len(self.vad_chunks_collected):
                next_vad = self.vad_chunks_collected[self._current_vad_idx + 1]
                if s_start >= next_vad[0]:
                    self._current_vad_idx += 1
                    if self.on_progress:
                        self.on_progress("vad_chunk_start", next_vad)
                else:
                    break

            clean_seg = self.sanitizer.sanitize_segment(sub_seg)
            if clean_seg is None:
                self.dropped_count += 1
                prob = float(sub_seg.get("no_speech_prob", 0.0))
                self.processing_events.append(
                    {
                        "start": s_start,
                        "type": "無音捏造等除外",
                        "message": f"no_speech_prob: {prob:.2f}",
                    }
                )
                if self.on_progress:
                    s_str = SubtitleExporter.format_timestamp(s_start)
                    dur = float(sub_seg["end"]) - s_start
                    self.on_progress(
                        "postprocess_dropped",
                        f"[除外] {s_str} ({dur:.1f}s) '{sub_seg.get('text', '')}' (無音捏造/高速ループ)",
                    )
                continue

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
                        "message": f'"{old_text}" ➔ "{new_text}"',
                    }
                )
                if self.on_progress:
                    s_str = SubtitleExporter.format_timestamp(clean_seg.start)
                    self.on_progress(
                        "postprocess_replaced",
                        f"[置換・正規化] {s_str}: '{old_text}' ➔ '{new_text}'",
                    )

            self.processed_segments.append(clean_seg)

            if self.on_segment is not None:
                out_dict = dict(sub_seg)
                out_dict["start"] = clean_seg.start
                out_dict["end"] = clean_seg.end
                out_dict["text"] = clean_seg.text
                self.on_segment(out_dict)

    def finalize_timing_and_summary(
        self, sub_cfg: SubtitleConfig
    ) -> list[SubtitleSegment]:
        """タイミング調整（パディング・最小長・ギャップ・重複防止）を行いサマリーを通知します。

        Args:
            sub_cfg: 字幕設定オブジェクト。

        Returns:
            list[SubtitleSegment]: 確定した字幕セグメントのリスト。
        """
        adjuster = SubtitleTimingAdjuster(
            end_padding=sub_cfg.end_padding,
            min_duration=sub_cfg.min_duration,
            min_gap=sub_cfg.min_gap,
        )
        final_segments = adjuster.adjust_segments(self.processed_segments)
        overlap_prevented_count = 0

        if self.on_progress:
            for i, (p_seg, f_seg) in enumerate(
                zip(self.processed_segments, final_segments, strict=False)
            ):
                if i + 1 < len(self.processed_segments):
                    next_start = getattr(self.processed_segments[i + 1], "start", 0.0)
                    p_end = getattr(p_seg, "end", 0.0)
                    p_start = getattr(p_seg, "start", 0.0)
                    raw_target_end = max(
                        p_end + sub_cfg.end_padding, p_start + sub_cfg.min_duration
                    )
                    f_end = getattr(f_seg, "end", 0.0)
                    if raw_target_end > f_end and (
                        raw_target_end > next_start - sub_cfg.min_gap
                    ):
                        overlap_prevented_count += 1
                        txt = getattr(f_seg, "text", "")
                        self.processing_events.append(
                            {
                                "start": p_start,
                                "type": "重複防止",
                                "message": f"終了時刻 {SubtitleExporter.format_timestamp(raw_target_end)} ➔ {SubtitleExporter.format_timestamp(f_end)} (次発話との重複を回避)",
                            }
                        )
                        self.on_progress(
                            "postprocess_overlap_prevented",
                            f"[重複防止] '{txt}': 終了時刻 {SubtitleExporter.format_timestamp(raw_target_end)} ➔ {SubtitleExporter.format_timestamp(f_end)} (次発話 {SubtitleExporter.format_timestamp(next_start)} との重複を回避)",
                        )
            self.on_progress(
                "postprocess_summary",
                f"サマリー: {self.raw_count}件中 {self.dropped_count}件除外、{self.replaced_count}件置換、{overlap_prevented_count}件重複防止 (確定字幕: {len(final_segments)}件)",
            )
        return final_segments
