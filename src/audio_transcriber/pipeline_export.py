"""パイプライン字幕ファイル出力ヘルパーモジュール。"""

from __future__ import annotations

import logging
from pathlib import Path

from audio_transcriber.exporter import SubtitleExporter
from audio_transcriber.models import SubtitleSegment

logger = logging.getLogger(__name__)


def export_pipeline_subtitles(
    final_segments: list[SubtitleSegment],
    formats: list[str],
    out_dir: Path,
    stem: str,
) -> tuple[Path | None, Path | None, Path | None, str]:
    """設定されたフォーマットに従って字幕ファイルを出力しテキストトランスクリプトを生成します。

    Args:
        final_segments: 出力する字幕セグメントのリスト。
        formats: 出力フォーマット形式のリスト（srt, vtt, json）。
        out_dir: 出力先ディレクトリ。
        stem: ベースファイル名（拡張子なし）。

    Returns:
        tuple[Path | None, Path | None, Path | None, str]: (srt_path, vtt_path, json_path, transcript_text) のタプル。
    """
    srt_path: Path | None = None
    vtt_path: Path | None = None
    json_path: Path | None = None

    if "srt" in formats:
        srt_path = out_dir / f"{stem}.srt"
        SubtitleExporter.save_srt(final_segments, srt_path)
        logger.info("SRT を出力しました: %s", srt_path)
    if "vtt" in formats:
        vtt_path = out_dir / f"{stem}.vtt"
        SubtitleExporter.save_vtt(final_segments, vtt_path)
        logger.info("VTT を出力しました: %s", vtt_path)
    if "json" in formats:
        json_path = out_dir / f"{stem}.json"
        SubtitleExporter.save_json(final_segments, json_path)
        logger.info("JSON を出力しました: %s", json_path)

    transcript = "\n\n".join(
        f"{i}\n{SubtitleExporter.format_timestamp(getattr(s, 'start', 0.0))} --> "
        f"{SubtitleExporter.format_timestamp(getattr(s, 'end', 0.0))}\n{getattr(s, 'text', '')}"
        for i, s in enumerate(final_segments, start=1)
    )
    return srt_path, vtt_path, json_path, transcript
