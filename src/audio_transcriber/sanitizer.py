"""音声セグメントのハルシネーション検出およびサニタイズモジュール。

Whisper による無音捏造や異常な発話速度のセグメントを検出し、
除外・正規化を行います。
"""

import logging
from collections.abc import Iterable

from audio_transcriber.models import SubtitleSegment

logger = logging.getLogger(__name__)


class SegmentSanitizer:
    """Whisper 認識結果のハルシネーション検出およびフィルタリングを行うクラス。"""

    def __init__(
        self,
        no_speech_threshold: float = 0.6,
        max_chars_per_second: float = 12.0,
    ) -> None:
        """SegmentSanitizer を初期化します。

        Args:
            no_speech_threshold (float): 無音判定閾値。デフォルト 0.6。
            max_chars_per_second (float): 物理的発話速度の許容上限 (文字/秒)。デフォルト 12.0。
        """
        self.no_speech_threshold = no_speech_threshold
        self.max_chars_per_second = max_chars_per_second
        self.last_valid_text = ""

    @staticmethod
    def get_word_time(word_obj: object, attr_name: str) -> float | None:
        """単語オブジェクト (dict または Word オブジェクト) から指定された時刻属性を取得します。

        Args:
            word_obj (object): 単語情報を含むオブジェクトまたは辞書。
            attr_name (str): 取得対象の属性名 (例: "start", "end")。

        Returns:
            float | None: 取得された時刻 (秒)。取得できない場合は None。
        """
        if isinstance(word_obj, dict):
            val = word_obj.get(attr_name)
            if isinstance(val, int | float):
                return float(val)
        else:
            val = getattr(word_obj, attr_name, None)
            if isinstance(val, int | float):
                return float(val)
        return None

    def sanitize_segment(
        self, segment: object, total_duration: float = 0.0
    ) -> SubtitleSegment | None:
        """単一セグメントに対してハルシネーションを判定し、除外・正規化を行います。

        無効と判定された場合は None を返し、有効な場合は補正済みの SubtitleSegment を返します。
        """
        if isinstance(segment, dict):
            text = str(segment.get("text", "")).strip()
        else:
            text = str(getattr(segment, "text", "")).strip()

        if not text:
            return None

        if isinstance(segment, dict):
            no_speech_prob = float(segment.get("no_speech_prob", 0.0))
            compression_ratio = float(segment.get("compression_ratio", 0.0))
            start = float(segment.get("start", 0.0))
            end = float(segment.get("end", 0.0))
            words = segment.get("words", None)
        else:
            no_speech_prob = float(getattr(segment, "no_speech_prob", 0.0))
            compression_ratio = float(getattr(segment, "compression_ratio", 0.0))
            start = float(getattr(segment, "start", 0.0))
            end = float(getattr(segment, "end", 0.0))
            words = getattr(segment, "words", None)

        half_len = len(text) // 2
        if len(text) >= 4 and text[:half_len] == text[half_len:]:
            if no_speech_prob > 0.1 or compression_ratio > 2.0:
                logger.info(
                    "ハルシネーションとみられるセグメント内リピートを検出・短縮: "
                    "'%s' -> '%s' (no_speech_prob=%.2f, comp_ratio=%.2f)",
                    text,
                    text[:half_len],
                    no_speech_prob,
                    compression_ratio,
                )
                text = text[:half_len]

        if words:
            words_list = words if isinstance(words, (list, tuple)) else list(words)
            if words_list:
                first_word_start = self.get_word_time(words_list[0], "start")
                if first_word_start is not None:
                    start = first_word_start

                last_word_end = self.get_word_time(words_list[-1], "end")
                if last_word_end is not None:
                    end = last_word_end

        duration = max(end - start, 0.1)
        chars_per_sec = len(text) / duration

        if self.last_valid_text and no_speech_prob > 0.1:
            if text == self.last_valid_text or text in self.last_valid_text:
                logger.info(
                    "ループ重複を自動ドロップ: 直前='%s', ドロップ対象='%s' "
                    "(no_speech_prob=%.2f)",
                    self.last_valid_text,
                    text,
                    no_speech_prob,
                )
                return None

        if no_speech_prob > self.no_speech_threshold:
            logger.debug(
                "無音捏造セグメントを自動ドロップ: %s (no_speech_prob=%.2f)",
                text,
                no_speech_prob,
            )
            return None

        if chars_per_sec > self.max_chars_per_second and len(text) > 4:
            logger.debug(
                "異常発話速度の捏造セグメントを自動ドロップ: %s (%.1f文字/秒)",
                text,
                chars_per_sec,
            )
            return None

        clean_seg = SubtitleSegment(
            start=round(start, 3),
            end=round(end, 3),
            text=text,
        )

        self.last_valid_text = text

        if total_duration > 0:
            progress = min(100.0, (clean_seg.end / total_duration) * 100)
            logger.info(
                "発言検出 [%5.1fs / %5.1fs (%3.0f%%)] [%.2fs -> %.2fs]: %s",
                clean_seg.end,
                total_duration,
                progress,
                clean_seg.start,
                clean_seg.end,
                clean_seg.text,
            )
        else:
            logger.info(
                "発言検出 [%.2fs -> %.2fs]: %s",
                clean_seg.start,
                clean_seg.end,
                clean_seg.text,
            )

        return clean_seg

    def sanitize_segments(
        self,
        segments: Iterable[object],
        total_duration: float = 0.0,
    ) -> list[SubtitleSegment]:
        """Whisper 認識結果からハルシネーションを自動判定し除外・正規化します。

        無音捏造、異常発話速度、重複発話を除外・短縮し、単語レベルのタイムスタンプ (words) が
        存在する場合は文頭単語の発声開始位置へ補正します。

        Args:
            segments (Iterable[object]): Segment オブジェクトまたは辞書のイテラブル。
            total_duration (float): 音声の全再生時間 (秒)。進捗出力用。

        Returns:
            list[SubtitleSegment]: フィルタリングおよび発声位置補正済みの字幕セグメントリスト。
        """
        results: list[SubtitleSegment] = []
        self.last_valid_text = ""

        for segment in segments:
            clean_seg = self.sanitize_segment(segment, total_duration)
            if clean_seg is not None:
                results.append(clean_seg)

        return results
