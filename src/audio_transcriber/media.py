"""Media file inspection, audio track extraction, and video remuxing using ffmpeg/ffprobe."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".ts"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}


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
    """Check if the given file is likely a video container based on extension.

    Args:
        path: Path to the media file.

    Returns:
        True if the file extension corresponds to a video container, False otherwise.
    """
    return path.suffix.lower() in VIDEO_EXTENSIONS


def get_audio_tracks(media_path: Path) -> list[AudioTrackInfo]:
    """Retrieve audio track information from a media file using ffprobe.

    Args:
        media_path: Path to the media file.

    Returns:
        List of AudioTrackInfo for each audio track found.

    Raises:
        RuntimeError: If ffprobe command fails or media has no audio streams.
    """
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


def extract_audio_track(
    media_path: Path,
    track_number: int,
    output_wav: Path,
    sample_rate: int = 48000,
) -> Path:
    """Extract a specific audio track from a media file as a WAV file.

    Args:
        media_path: Path to the source media file.
        track_number: 1-indexed audio track number (e.g. 1 for 1st audio, 2 for 2nd).
        output_wav: Output WAV file path.
        sample_rate: Output audio sampling rate in Hz (default: 48000).

    Returns:
        Path to the extracted WAV file.

    Raises:
        ValueError: If the specified track number is invalid.
        RuntimeError: If ffmpeg fails during extraction.
    """
    tracks = get_audio_tracks(media_path)
    if track_number < 1 or track_number > len(tracks):
        raise ValueError(
            f"Invalid audio track number {track_number}. "
            f"File '{media_path.name}' has {len(tracks)} audio track(s)."
        )

    audio_stream_idx = track_number - 1
    output_wav.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(media_path),
        "-map",
        f"0:a:{audio_stream_idx}",
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(sample_rate),
        str(output_wav),
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error("ffmpeg extraction failed: %s", e.stderr)
        raise RuntimeError(
            f"Failed to extract audio track {track_number} from '{media_path}': {e.stderr.strip()}"
        ) from e

    return output_wav


def remux_video(
    original_video: Path,
    mic_track_number: int,
    clean_audio: Path,
    output_video: Path,
) -> Path:
    """Remux video by replacing the specified mic audio track with clean audio.

    Args:
        original_video: Path to the original video file.
        mic_track_number: 1-indexed audio track number to replace (e.g. 2 for 2nd track).
        clean_audio: Path to the clean/denoised audio WAV file.
        output_video: Path to the output remuxed video file.

    Returns:
        Path to the remuxed video file.

    Raises:
        ValueError: If the specified track number is invalid.
        RuntimeError: If ffmpeg fails during remuxing.
    """
    tracks = get_audio_tracks(original_video)
    if mic_track_number < 1 or mic_track_number > len(tracks):
        raise ValueError(
            f"Invalid audio track number {mic_track_number}. "
            f"File '{original_video.name}' has {len(tracks)} audio track(s)."
        )

    replace_idx = mic_track_number - 1
    output_video.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(original_video),
        "-i",
        str(clean_audio),
        "-map",
        "0:v",
    ]

    for idx in range(len(tracks)):
        if idx == replace_idx:
            cmd.extend(["-map", "1:a:0"])
        else:
            cmd.extend(["-map", f"0:a:{idx}"])

    cmd.extend(["-c:v", "copy"])

    for out_a_idx, in_a_idx in enumerate(range(len(tracks))):
        if in_a_idx == replace_idx:
            target_codec = tracks[replace_idx].codec_name
            if target_codec == "unknown":
                target_codec = "pcm_s16le"
            cmd.extend([f"-c:a:{out_a_idx}", target_codec])
        else:
            cmd.extend([f"-c:a:{out_a_idx}", "copy"])

    cmd.append(str(output_video))

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error("ffmpeg remux failed: %s", e.stderr)
        raise RuntimeError(
            f"Failed to remux video '{original_video}': {e.stderr.strip()}"
        ) from e

    return output_video


def get_timecode_offset(media_path: Path) -> float:
    """動画メタデータ内のタイムコード (SMPTE timecode) を検出し開始秒数を算出します。

    Args:
        media_path: 対象の動画またはメディアファイルパス。

    Returns:
        float: タイムコードの開始秒数 (タイムコードが存在しない場合は 0.0)。
    """
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
