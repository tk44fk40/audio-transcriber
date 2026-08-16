"""メディアファイルの検証、トラック情報取得、音声抽出、タイムコードオフセットの単体テスト。"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audio_transcriber.media import (
    extract_audio_track,
    get_audio_tracks,
    get_timecode_offset,
    is_video_file,
)


def test_is_video_file() -> None:
    """動画ファイル拡張子の判定を検証する。"""
    assert is_video_file(Path("gameplay.mp4")) is True
    assert is_video_file(Path("stream.MKV")) is True
    assert is_video_file(Path("clip.mov")) is True
    assert is_video_file(Path("audio.wav")) is False
    assert is_video_file(Path("voice.mp3")) is False


def test_get_audio_tracks_success() -> None:
    """ffprobe 出力モックによる音声トラック情報の取得を検証する。"""
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


def test_get_audio_tracks_no_streams() -> None:
    """音声ストリームが存在しない場合に RuntimeError が発生することを検証する。"""
    mock_stdout = json.dumps({"streams": []})
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_stdout, returncode=0)
        with pytest.raises(RuntimeError, match="No audio streams found"):
            get_audio_tracks(Path("silent.mp4"))


def test_get_audio_tracks_called_process_error() -> None:
    """ffprobe 失敗時に RuntimeError が発生することを検証する。"""
    with patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(
            1, "ffprobe", stderr="Corrupt file header"
        ),
    ):
        with pytest.raises(RuntimeError, match="Failed to inspect media file"):
            get_audio_tracks(Path("corrupt.mp4"))


def test_extract_audio_track_invalid_track() -> None:
    """範囲外のトラック番号で extract_audio_track を呼んだ場合に ValueError が発生することを検証する。"""
    with patch("audio_transcriber.media_ffmpeg.get_audio_tracks") as mock_get_tracks:
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


def test_extract_audio_track_called_process_error() -> None:
    """ffmpeg 失敗時に RuntimeError が発生することを検証する。"""
    with patch(
        "audio_transcriber.media_ffmpeg.get_audio_tracks",
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


def test_get_timecode_offset_with_valid_timecode() -> None:
    """SMPTE タイムコードと fps からタイムコードオフセットが正しく計算されることを検証する。"""
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


def test_get_timecode_offset_without_timecode() -> None:
    """タイムコードメタデータが存在しない場合に 0.0 が返されることを検証する。"""
    mock_stdout = json.dumps(
        {"streams": [{"r_frame_rate": "30/1"}], "format": {"tags": {}}}
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_stdout, returncode=0)
        offset = get_timecode_offset(Path("no_timecode.mp4"))

    assert offset == 0.0


def test_get_timecode_offset_format_tags() -> None:
    """streams ではなく format tags からタイムコードがパースされることを検証する。"""
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


def test_get_timecode_offset_framerate_errors() -> None:
    """不正なフレームレート形式の場合にデフォルト fps (30.0) でフォールバックされることを検証する。"""
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

        # default fps is 30.0, 15 frames / 30 = 0.5s -> 1.5s
        assert pytest.approx(offset, 0.001) == 1.5


def test_get_timecode_offset_invalid_parts() -> None:
    """タイムコードの要素数が4つでない場合に 0.0 が返されることを検証する。"""
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


def test_get_timecode_offset_invalid_values() -> None:
    """タイムコードの要素が整数でない場合に 0.0 が返されることを検証する。"""
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
