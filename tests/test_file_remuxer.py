"""FileRemuxer のテスト。

AAA（Arrange-Act-Assert）パターンを徹底。
FFmpegをモック化し、ハングや異常終了時の
堅牢性を検証します。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from audio_transcriber.file_remuxer import FileRemuxer


@pytest.fixture
def anyio_backend() -> str:
    """AnyIOのバックエンド。"""
    return "asyncio"


@pytest.mark.anyio
async def test_remux_success(tmp_path: Path) -> None:
    """正常系: FFmpeg が正常終了し、ファイルが生成されることを検証。"""
    # Arrange
    video_file = tmp_path / "input.mp4"
    audio_file = tmp_path / "denoised.wav"
    output_file = tmp_path / "output.mp4"

    video_file.write_text("dummy video")
    audio_file.write_text("dummy audio")

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.wait.return_value = 0

    remuxer = FileRemuxer()

    # Act
    with patch(
        "asyncio.create_subprocess_exec", return_value=mock_process
    ) as mock_exec:
        await remuxer.remux(video_file, audio_file, output_file)

    # Assert
    mock_exec.assert_called_once()
    args = mock_exec.call_args[0]
    assert "ffmpeg" in args
    assert "-shortest" in args


@pytest.mark.anyio
async def test_remux_file_not_found() -> None:
    """異常系: 入力不在時に FileNotFoundError が発生することを検証。"""
    # Arrange
    remuxer = FileRemuxer()

    # Act & Assert
    with pytest.raises(FileNotFoundError):
        await remuxer.remux("non_existent_video.mp4", "audio.wav", "out.mp4")


@pytest.mark.anyio
async def test_remux_ffmpeg_error(tmp_path: Path) -> None:
    """異常系: FFmpeg 異常終了時に RuntimeError が発生することを検証。"""
    # Arrange
    video_file = tmp_path / "input.mp4"
    audio_file = tmp_path / "denoised.wav"
    output_file = tmp_path / "output.mp4"

    video_file.write_text("dummy video")
    audio_file.write_text("dummy audio")

    mock_stderr = AsyncMock()
    mock_stderr.read.return_value = b"Some ffmpeg conversion error"

    mock_process = AsyncMock()
    mock_process.returncode = 1
    mock_process.wait.return_value = 1
    mock_process.stderr = mock_stderr

    remuxer = FileRemuxer()

    # Act & Assert
    with (
        patch("asyncio.create_subprocess_exec", return_value=mock_process),
        pytest.raises(RuntimeError) as exc_info,
    ):
        await remuxer.remux(video_file, audio_file, output_file)

    assert "exited with code 1" in str(exc_info.value)
    assert "Some ffmpeg conversion error" in str(exc_info.value)


@pytest.mark.anyio
async def test_remux_timeout(tmp_path: Path) -> None:
    """異常系: タイムアウト時に SIGKILL が送信されることを検証。"""
    # Arrange
    video_file = tmp_path / "input.mp4"
    audio_file = tmp_path / "denoised.wav"
    output_file = tmp_path / "output.mp4"

    video_file.write_text("dummy")
    audio_file.write_text("dummy")

    mock_process = MagicMock()

    # asyncio.wait_for が TimeoutError を送出するように
    # シミュレートするため、wait のモックに asyncio.sleep を
    # 挟んでタイムアウトを誘発する。
    async def slow_wait() -> int:
        await asyncio.sleep(2.0)
        return 0

    mock_process.wait = slow_wait
    mock_process.kill = MagicMock()

    remuxer = FileRemuxer()

    # Act & Assert
    with (
        patch("asyncio.create_subprocess_exec", return_value=mock_process),
        patch("audio_transcriber.file_remuxer.FFMPEG_TIMEOUT_SEC", 0.05),
        pytest.raises(RuntimeError) as exc_info,
    ):
        await remuxer.remux(video_file, audio_file, output_file)

    assert "timed out after" in str(exc_info.value)
    mock_process.kill.assert_called_once()
