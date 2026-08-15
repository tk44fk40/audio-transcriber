"""Unit and integration tests for media inspection, audio extraction, and remuxing."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audio_transcriber.media import (
    extract_audio_track,
    get_audio_tracks,
    is_video_file,
    remux_video,
)


def test_is_video_file():
    """Test video file extension detection."""
    assert is_video_file(Path("gameplay.mp4")) is True
    assert is_video_file(Path("stream.MKV")) is True
    assert is_video_file(Path("clip.mov")) is True
    assert is_video_file(Path("audio.wav")) is False
    assert is_video_file(Path("voice.mp3")) is False


def test_get_audio_tracks_success():
    """Test getting audio track information with mocked ffprobe output."""
    mock_stdout = json.dumps(
        {
            "streams": [
                {
                    "index": 1,
                    "codec_name": "aac",
                    "channels": 2,
                    "sample_rate": "48000",
                    "tags": {"title": "Game Audio"},
                },
                {
                    "index": 2,
                    "codec_name": "aac",
                    "channels": 1,
                    "sample_rate": "48000",
                    "tags": {"title": "Mic Audio"},
                },
            ]
        }
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_stdout, returncode=0)
        tracks = get_audio_tracks(Path("dummy.mp4"))

    assert len(tracks) == 2
    assert tracks[0].index == 0
    assert tracks[0].stream_index == 1
    assert tracks[0].codec_name == "aac"
    assert tracks[0].channels == 2
    assert tracks[0].title == "Game Audio"

    assert tracks[1].index == 1
    assert tracks[1].stream_index == 2
    assert tracks[1].channels == 1
    assert tracks[1].title == "Mic Audio"


def test_get_audio_tracks_no_streams():
    """Test get_audio_tracks raises error when no audio streams exist."""
    mock_stdout = json.dumps({"streams": []})
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_stdout, returncode=0)
        with pytest.raises(RuntimeError, match="No audio streams found"):
            get_audio_tracks(Path("silent.mp4"))


def test_get_audio_tracks_called_process_error():
    """Test get_audio_tracks raises RuntimeError on ffprobe failure."""
    with patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(
            1, "ffprobe", stderr="Corrupt file header"
        ),
    ):
        with pytest.raises(RuntimeError, match="Failed to inspect media file"):
            get_audio_tracks(Path("corrupt.mp4"))


def test_extract_audio_track_invalid_track():
    """Test extract_audio_track with out-of-range track numbers."""
    with patch("audio_transcriber.media.get_audio_tracks") as mock_get_tracks:
        mock_get_tracks.return_value = [
            MagicMock(index=0),
            MagicMock(index=1),
        ]
        with pytest.raises(ValueError, match="Invalid audio track number"):
            extract_audio_track(
                Path("dummy.mp4"), track_number=0, output_wav=Path("out.wav")
            )

        with pytest.raises(ValueError, match="Invalid audio track number"):
            extract_audio_track(
                Path("dummy.mp4"), track_number=3, output_wav=Path("out.wav")
            )


def test_extract_audio_track_called_process_error():
    """Test extract_audio_track raises RuntimeError on ffmpeg failure."""
    with patch(
        "audio_transcriber.media.get_audio_tracks",
        return_value=[MagicMock(index=0)],
    ):
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(
                1, "ffmpeg", stderr="Codec error"
            ),
        ):
            with pytest.raises(RuntimeError, match="Failed to extract audio track 1"):
                extract_audio_track(
                    Path("dummy.mp4"), track_number=1, output_wav=Path("out.wav")
                )


def test_remux_video_invalid_track():
    """Test remux_video with invalid track numbers."""
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


def test_remux_video_called_process_error():
    """Test remux_video raises RuntimeError on ffmpeg failure."""
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


def test_remux_video_unknown_codec_fallback():
    """Test remux_video falls back to pcm_s16le when codec is unknown."""
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
            # Check if pcm_s16le was used in the ffmpeg command
            called_args = mock_run.call_args[0][0]
            assert "-c:a:0" in called_args
            idx = called_args.index("-c:a:0")
            assert called_args[idx + 1] == "pcm_s16le"


def test_ffmpeg_real_multitrack_workflow(tmp_path: Path):
    """End-to-end integration test creating a 2-track video and remuxing it with ffmpeg."""
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


def test_get_timecode_offset_with_valid_timecode():
    """Test get_timecode_offset parses SMPTE timecode correctly with fps."""
    from audio_transcriber.media import get_timecode_offset

    mock_stdout = json.dumps(
        {
            "streams": [
                {
                    "r_frame_rate": "60/1",
                    "tags": {"timecode": "00:08:38:40"},
                }
            ],
            "format": {"tags": {}},
        }
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_stdout, returncode=0)
        offset = get_timecode_offset(Path("sample.mov"))

    # 8min + 38sec + 40/60sec = 480 + 38 + 0.6666... = 518.6666...
    assert pytest.approx(offset, 0.001) == 518.6667


def test_get_timecode_offset_without_timecode():
    """Test get_timecode_offset returns 0.0 when no timecode metadata exists."""
    from audio_transcriber.media import get_timecode_offset

    mock_stdout = json.dumps(
        {"streams": [{"r_frame_rate": "30/1"}], "format": {"tags": {}}}
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_stdout, returncode=0)
        offset = get_timecode_offset(Path("no_timecode.mp4"))

    assert offset == 0.0


def test_get_timecode_offset_format_tags():
    """Test get_timecode_offset parses from format tags instead of streams."""
    from audio_transcriber.media import get_timecode_offset

    mock_stdout = json.dumps(
        {
            "streams": [],
            "format": {"tags": {"timecode": "01:00:00:00"}},
        }
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_stdout, returncode=0)
        offset = get_timecode_offset(Path("sample.mov"))
    assert offset == 3600.0


def test_get_timecode_offset_framerate_errors():
    """Test get_timecode_offset ignores invalid frame rates."""
    from audio_transcriber.media import get_timecode_offset

    # "invalid/fps" throws ValueError, "30/0" throws ZeroDivisionError
    for r_fps in ["invalid/fps", "30/0"]:
        mock_stdout = json.dumps(
            {
                "streams": [
                    {
                        "r_frame_rate": r_fps,
                        "tags": {"timecode": "00:00:01:15"},
                    }
                ],
                "format": {"tags": {}},
            }
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=mock_stdout, returncode=0)
            offset = get_timecode_offset(Path("sample.mov"))

        # default fps is 30.0, 15 frames / 30 = 0.5s
        assert pytest.approx(offset, 0.001) == 1.5


def test_get_timecode_offset_invalid_parts():
    """Test get_timecode_offset returns 0.0 if timecode parts != 4."""
    from audio_transcriber.media import get_timecode_offset

    mock_stdout = json.dumps(
        {
            "streams": [
                {
                    "tags": {"timecode": "01:00"},
                }
            ],
            "format": {"tags": {}},
        }
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_stdout, returncode=0)
        offset = get_timecode_offset(Path("sample.mov"))
    assert offset == 0.0


def test_get_timecode_offset_invalid_values():
    """Test get_timecode_offset returns 0.0 if timecode parts are not ints."""
    from audio_transcriber.media import get_timecode_offset

    mock_stdout = json.dumps(
        {
            "streams": [
                {
                    "tags": {"timecode": "01:00:00:AA"},
                }
            ],
            "format": {"tags": {}},
        }
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_stdout, returncode=0)
        offset = get_timecode_offset(Path("sample.mov"))
    assert offset == 0.0
