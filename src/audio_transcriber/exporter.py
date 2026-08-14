"""字幕エクスポートモジュール。

本モジュールは、抽出された発言字幕データモデル (SubtitleSegment) から
DaVinci Resolve 互換 SRT、WebVTT、JSON フォーマットへの書き出し処理を提供します。
"""

import json
from collections.abc import Sequence
from pathlib import Path

from audio_transcriber.models import SubtitleSegment


class SubtitleExporter:
    """字幕 JSON, SRT および WebVTT ファイルのエクスポートクラス。"""

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """秒数を SRT 形式のタイムスタンプ文字列 (HH:MM:SS,mmm) に変換します。

        Args:
            seconds (float): 変換対象の秒数。

        Returns:
            str: 形式化されたタイムスタンプ文字列 (例: '00:01:23,456')。
        """
        seconds = max(0.0, seconds)
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        millis = round((seconds - total_seconds) * 1000)
        if millis >= 1000:
            millis -= 1000
            secs += 1
            if secs >= 60:
                secs -= 60
                minutes += 1
                if minutes >= 60:
                    minutes -= 60
                    hours += 1
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def format_vtt_timestamp(seconds: float) -> str:
        """秒数を WebVTT 形式のタイムスタンプ文字列 (HH:MM:SS.mmm) に変換します。

        Args:
            seconds (float): 変換対象の秒数。

        Returns:
            str: 形式化されたタイムスタンプ文字列 (例: '00:01:23.456')。
        """
        seconds = max(0.0, seconds)
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        millis = round((seconds - total_seconds) * 1000)
        if millis >= 1000:
            millis -= 1000
            secs += 1
            if secs >= 60:
                secs -= 60
                minutes += 1
                if minutes >= 60:
                    minutes -= 60
                    hours += 1
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    @classmethod
    def save_json(cls, segments: Sequence[SubtitleSegment], output_path: Path) -> None:
        """字幕セグメントリストを JSON ファイルとして保存します。

        Args:
            segments (Sequence[SubtitleSegment]): 字幕セグメントのリスト。
            output_path (Path): 保存先 JSON パス。
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = [seg.to_dict() for seg in segments]
        with open(output_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    @classmethod
    def save_srt(cls, segments: Sequence[SubtitleSegment], output_path: Path) -> None:
        """字幕セグメントリストを標準 .srt 字幕ファイルとして保存します。

        DaVinci Resolve インポート仕様 (ミリ秒表記 00:00:00,000、UTF-8、LF改行) に準拠します。

        Args:
            segments (Sequence[SubtitleSegment]): 字幕セグメントのリスト。
            output_path (Path): 保存先 SRT パス。
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        blocks = [
            f"{index}\n{cls.format_timestamp(seg.start)} --> "
            f"{cls.format_timestamp(seg.end)}\n{seg.text}"
            for index, seg in enumerate(segments, start=1)
        ]
        content = "\n\n".join(blocks) + ("\n" if blocks else "")
        with open(output_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

    @classmethod
    def save_vtt(cls, segments: Sequence[SubtitleSegment], output_path: Path) -> None:
        """字幕セグメントリストを WebVTT (.vtt) 字幕ファイルとして保存します。

        Args:
            segments (Sequence[SubtitleSegment]): 字幕セグメントのリスト。
            output_path (Path): 保存先 VTT パス。
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        blocks = [
            f"{index}\n{cls.format_vtt_timestamp(seg.start)} --> "
            f"{cls.format_vtt_timestamp(seg.end)}\n{seg.text}"
            for index, seg in enumerate(segments, start=1)
        ]
        content = (
            "WEBVTT\n" if not blocks else "WEBVTT\n\n" + "\n\n".join(blocks) + "\n"
        )
        with open(output_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

    @classmethod
    def save_subtitles(
        cls,
        segments: Sequence[SubtitleSegment],
        output_path: Path,
        fmt: str | None = None,
    ) -> None:
        """字幕セグメントリストを指定フォーマットまたは拡張子自動判定でファイルとして保存します。

        Args:
            segments (Sequence[SubtitleSegment]): 字幕セグメントのリスト。
            output_path (Path): 保存先ファイルパス。
            fmt (str | None): 明示的なフォーマット指定 ("srt", "vtt", "json")。
                省略時は拡張子から自動判定。

        Raises:
            ValueError: サポートされていないフォーマットまたは拡張子の場合。
        """
        if fmt is None:
            ext = output_path.suffix.lower()
            if ext == ".vtt":
                target_fmt = "vtt"
            elif ext == ".srt":
                target_fmt = "srt"
            elif ext == ".json":
                target_fmt = "json"
            else:
                msg = f"未対応の拡張子です: '{ext}' (対応拡張子: .srt, .vtt, .json)"
                raise ValueError(msg)
        else:
            target_fmt = fmt.lower()

        if target_fmt == "vtt":
            cls.save_vtt(segments, output_path)
        elif target_fmt == "srt":
            cls.save_srt(segments, output_path)
        elif target_fmt == "json":
            cls.save_json(segments, output_path)
        else:
            msg = (
                f"未対応のフォーマットです: '{fmt}' (対応フォーマット: srt, vtt, json)"
            )
            raise ValueError(msg)
