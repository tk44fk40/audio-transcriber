"""動画ファイルの再多重化（remux_video）および ffmpeg 連携の統合テスト。"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audio_transcriber.media import (
    extract_audio_track,
    get_audio_tracks,
    remux_video,
)


def test_remux_video_invalid_track() -> None:
    """範囲外のトラック番号で remux_video を呼んだ場合に ValueError が発生することを検証する。"""
    with patch(
        "audio_transcriber.media.get_audio_tracks",
        return_value=[MagicMock(index=0)],
    ):
        with pytest.raises(ValueError, match="Invalid audio track number"):
            remux_video(
                original_video=Path("dummy.mp4"),
                mic_track_number=0,
                clean_audio=Path("clean.wav"),
                output_video=Path("out.mp4"),
            )

        with pytest.raises(ValueError, match="Invalid audio track number"):
            remux_video(
                original_video=Path("dummy.mp4"),
                mic_track_number=2,
                clean_audio=Path("clean.wav"),
                output_video=Path("out.mp4"),
            )


def test_remux_video_called_process_error() -> None:
    """ffmpeg 失敗時に RuntimeError が発生することを検証する。"""
    with patch(
        "audio_transcriber.media.get_audio_tracks",
        return_value=[MagicMock(index=0, codec_name="aac")],
    ):
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(
                1, "ffmpeg", stderr="Muxing error"
            ),
        ):
            with pytest.raises(RuntimeError, match="Failed to remux video"):
                remux_video(
                    original_video=Path("dummy.mp4"),
                    mic_track_number=1,
                    clean_audio=Path("clean.wav"),
                    output_video=Path("out.mp4"),
                )


def test_remux_video_unknown_codec_fallback() -> None:
    """未知のコーデックの場合に pcm_s16le にフォールバックすることを検証する。"""
    with patch(
        "audio_transcriber.media.get_audio_tracks",
        return_value=[MagicMock(index=0, codec_name="unknown")],
    ):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            remux_video(
                original_video=Path("dummy.mp4"),
                mic_track_number=1,
                clean_audio=Path("clean.wav"),
                output_video=Path("out.mp4"),
            )
            called_args = mock_run.call_args[0][0]
            assert "-c:a:0" in called_args
            idx = called_args.index("-c:a:0")
            assert called_args[idx + 1] == "pcm_s16le"


def test_ffmpeg_real_multitrack_workflow(tmp_path: Path) -> None:
    """2トラック動画を実際に ffmpeg で生成・分離・再多重化する統合テスト。"""
    # 1. Create a 1-second video with 2 audio tracks using ffmpeg
    test_video = tmp_path / "input_multitrack.mp4"
    create_cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=1:size=320x240:rate=30",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=880:duration=1",
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-map",
        "2:a",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        str(test_video),
    ]
    subprocess.run(create_cmd, capture_output=True, text=True, check=True)

    # 2. Inspect audio tracks
    tracks = get_audio_tracks(test_video)
    assert len(tracks) == 2

    # 3. Extract track 2 (mic track)
    extracted_wav = tmp_path / "extracted_track2.wav"
    extract_audio_track(test_video, track_number=2, output_wav=extracted_wav)
    assert extracted_wav.exists()
    assert extracted_wav.stat().st_size > 0

    # 4. Create dummy replacement audio (e.g. 1-second sine 1000Hz WAV)
    clean_wav = tmp_path / "clean_mic.wav"
    sine_cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=1000:duration=1",
        "-c:a",
        "pcm_s16le",
        str(clean_wav),
    ]
    subprocess.run(sine_cmd, capture_output=True, text=True, check=True)

    # 5. Remux video replacing track 2
    remuxed_video = tmp_path / "output_clean.mp4"
    remux_video(
        original_video=test_video,
        mic_track_number=2,
        clean_audio=clean_wav,
        output_video=remuxed_video,
    )
    assert remuxed_video.exists()

    # 6. Verify remuxed video tracks
    new_tracks = get_audio_tracks(remuxed_video)
    assert len(new_tracks) == 2
