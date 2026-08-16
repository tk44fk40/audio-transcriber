"""字幕セグメントの表示タイミング補正モジュール。

Whisper が検出した物理的な発声終了時刻に対し、視聴者の読みやすさを
向上させるための余韻パディング、最小表示時間の確保、および次発話セグメントと
の重複防止（ギャップ制御）を行います。
"""

from __future__ import annotations

import logging
from typing import Any

from audio_transcriber.models import SubtitleSegment

__all__ = ["SubtitleTimingAdjuster", "split_segments_by_word_gap"]

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


class SubtitleTimingAdjuster:
    """字幕セグメントの表示タイミング（余韻・最小表示時間・重複防止）を補正するクラス。"""

    def __init__(
        self,
        end_padding: float,
        min_duration: float,
        min_gap: float,
    ) -> None:
        """SubtitleTimingAdjuster を初期化します。

        Args:
            end_padding: 発話終了後の余韻表示秒数。
            min_duration: 字幕の最小表示秒数。
            min_gap: 連続するセグメント間の最小隙間秒数。
        """
        self.end_padding = end_padding
        self.min_duration = min_duration
        self.min_gap = min_gap

    def adjust_single_segment(
        self,
        seg: SubtitleSegment,
        next_start: float | None = None,
        total_duration: float | None = None,
    ) -> tuple[SubtitleSegment, bool, float]:
        """単一の字幕セグメントのタイミングを補正します。

        Args:
            seg: 補正対象の字幕セグメント。
            next_start: 次の字幕セグメントの開始時刻（秒）。存在しない場合は None。
            total_duration: メディアの総再生時間（秒）。

        Returns:
            tuple[SubtitleSegment, bool, float]:
                - 補正済みの字幕セグメント
                - 重複防止（ギャップ制御）による短縮が発生したかどうかのフラグ
                - 重複防止前の目標終了時刻（秒）
        """
        padded_end = seg.end + self.end_padding
        min_required_end = seg.start + self.min_duration
        raw_target_end = max(padded_end, min_required_end)
        target_end = raw_target_end

        overlap_prevented = False
        if next_start is not None:
            max_allowed_end = round(next_start - self.min_gap, 3)
            if max_allowed_end > seg.start:
                if round(target_end, 3) > max_allowed_end:
                    target_end = max_allowed_end
                    overlap_prevented = True
            else:
                if round(target_end, 3) > round(next_start, 3):
                    target_end = next_start
                    overlap_prevented = True

        if total_duration is not None and total_duration > 0:
            target_end = min(target_end, total_duration)

        final_end = max(seg.start, target_end)

        adjusted_seg = SubtitleSegment(
            start=round(seg.start, 3),
            end=round(final_end, 3),
            text=seg.text,
        )
        return adjusted_seg, overlap_prevented, raw_target_end

    def adjust_segments(
        self,
        segments: list[SubtitleSegment],
        total_duration: float | None = None,
    ) -> list[SubtitleSegment]:
        """字幕セグメントリストの終了時刻を自然な表示時間へ補正します。

        各セグメントに対して以下の補正を順に適用します:
        1. 余韻パディングの追加: 発話終了直後に字幕が消えるのを防ぐため、終了時刻を延長。
        2. 最小表示時間の確保: 短い発言でも視聴者が読めるよう最低表示秒数を下限に。
        3. 次セグメントとの重複防止: 余韻延長によって次セグメントと被らないよう制限。
        4. 総再生時間の制限: total_duration が指定されている場合、動画全体の長さを超えない。

        Args:
            segments: 補正対象の字幕セグメントリスト。
            total_duration: メディアの総再生時間（秒）。

        Returns:
            list[SubtitleSegment]: タイミング補正済みの新しい字幕セグメントリスト。
        """
        if not segments:
            return []

        adjusted: list[SubtitleSegment] = []
        count = len(segments)

        for i, seg in enumerate(segments):
            next_start = segments[i + 1].start if i + 1 < count else None
            adj_seg, _, _ = self.adjust_single_segment(
                seg=seg,
                next_start=next_start,
                total_duration=total_duration,
            )
            adjusted.append(adj_seg)

        logger.debug(
            "字幕タイミング補正完了: %d 件を処理 (padding=%.2fs, min_duration=%.2fs, gap=%.2fs)",
            len(adjusted),
            self.end_padding,
            self.min_duration,
            self.min_gap,
        )

        return adjusted
