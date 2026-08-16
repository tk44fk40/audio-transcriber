"""Audio track extraction and video remuxing using ffmpeg."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from audio_transcriber.media_probe import get_audio_tracks

logger = logging.getLogger(__name__)

__all__ = ["extract_audio_track", "remux_video"]


def extract_audio_track(
    media_path: Path,
    track_number: int,
    output_wav: Path,
    sample_rate: int = 48000,
) -> Path:
    """Extract a specific audio track from a media file as a WAV file."""
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
    """Remux video by replacing the specified mic audio track with clean audio."""
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
