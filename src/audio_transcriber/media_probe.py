"""Media file inspection using ffprobe."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".ts"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}

__all__ = [
    "AUDIO_EXTENSIONS",
    "VIDEO_EXTENSIONS",
    "AudioTrackInfo",
    "get_audio_tracks",
    "get_timecode_offset",
    "is_video_file",
]


@dataclass
class AudioTrackInfo:
    """Information about an audio track in a media file."""

    index: int  # 0-indexed across audio streams
    stream_index: int  # ffmpeg global stream index
    codec_name: str
    channels: int
    sample_rate: int
    title: str | None = None


def is_video_file(path: Path) -> bool:
    """Check if the given file is likely a video container based on extension."""
    return path.suffix.lower() in VIDEO_EXTENSIONS


def get_audio_tracks(media_path: Path) -> list[AudioTrackInfo]:
    """Retrieve audio track information from a media file using ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index,codec_name,channels,sample_rate:stream_tags=title",
        "-of",
        "json",
        str(media_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error("ffprobe failed: %s", e.stderr)
        raise RuntimeError(
            f"Failed to inspect media file '{media_path}': {e.stderr.strip()}"
        ) from e

    data = json.loads(proc.stdout)
    streams = data.get("streams", [])
    if not streams:
        raise RuntimeError(f"No audio streams found in '{media_path}'.")

    tracks: list[AudioTrackInfo] = []
    for audio_idx, s in enumerate(streams):
        title = s.get("tags", {}).get("title")
        tracks.append(
            AudioTrackInfo(
                index=audio_idx,
                stream_index=int(s["index"]),
                codec_name=s.get("codec_name", "unknown"),
                channels=int(s.get("channels", 2)),
                sample_rate=int(s.get("sample_rate", 48000)),
                title=title,
            )
        )
    return tracks


def get_timecode_offset(media_path: Path) -> float:
    """動画メタデータ内のタイムコードを検出し開始秒数を算出します。"""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=r_frame_rate,avg_frame_rate:stream_tags=timecode:format_tags=timecode",
        "-of",
        "json",
        str(media_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)
    except Exception as e:
        logger.debug("タイムコード取得の ffprobe 実行をスキップ/失敗: %s", e)
        return 0.0

    tc_str: str | None = None
    fps: float = 30.0

    fmt_tags = data.get("format", {}).get("tags", {})
    if "timecode" in fmt_tags:
        tc_str = fmt_tags["timecode"]

    streams = data.get("streams", [])
    for s in streams:
        tags = s.get("tags", {})
        if not tc_str and "timecode" in tags:
            tc_str = tags["timecode"]
        r_fps = s.get("r_frame_rate", "")
        if r_fps and "/" in r_fps:
            try:
                num, den = r_fps.split("/")
                val = float(num) / float(den)
                if val > 0:
                    fps = val
            except (ValueError, ZeroDivisionError):
                pass

    if not tc_str:
        return 0.0

    sep = ";" if ";" in tc_str else ":"
    parts = tc_str.strip().split(sep)
    if len(parts) != 4:
        return 0.0

    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        frames = int(parts[3])
        return hours * 3600.0 + minutes * 60.0 + seconds + (frames / fps)
    except ValueError:
        return 0.0
