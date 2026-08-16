"""Media file inspection, audio track extraction, and video remuxing using ffmpeg/ffprobe."""

from __future__ import annotations

from audio_transcriber.media_ffmpeg import (
    extract_audio_track,
    remux_video,
)
from audio_transcriber.media_probe import (
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    AudioTrackInfo,
    get_audio_tracks,
    get_timecode_offset,
    is_video_file,
)

__all__ = [
    "AUDIO_EXTENSIONS",
    "VIDEO_EXTENSIONS",
    "AudioTrackInfo",
    "extract_audio_track",
    "get_audio_tracks",
    "get_timecode_offset",
    "is_video_file",
    "remux_video",
]
