"""Unit tests for AudioChunkQueue, StreamAudioProducer, and FileAudioProducer."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from audio_transcriber.audio_producers import (
    AudioChunkQueue,
    FileAudioProducer,
    StreamAudioProducer,
)
from audio_transcriber.config import AppConfig


@pytest.fixture
def anyio_backend() -> str:
    """AnyIO backend."""
    return "asyncio"


@pytest.mark.anyio
async def test_audio_chunk_queue_basic() -> None:
    """AudioChunkQueueの基本的なデータ投入・取得とqsizeを検証。"""
    queue = AudioChunkQueue(maxsize=5)
    assert queue.qsize == 0

    await queue.put((b"data1", True))
    await queue.put((b"data2", False))
    await queue.put(None)

    assert queue.qsize == 3

    item1 = await queue.get()
    assert item1 == (b"data1", True)
    queue.task_done()

    item2 = await queue.get()
    assert item2 == (b"data2", False)
    queue.task_done()

    item3 = await queue.get()
    assert item3 is None
    queue.task_done()

    assert queue.qsize == 0


@pytest.mark.anyio
async def test_audio_chunk_queue_backpressure() -> None:
    """AudioChunkQueueのBackpressure（満杯時のブロック）制御を検証。"""
    queue = AudioChunkQueue(maxsize=2)
    await queue.put((b"1", False))
    await queue.put((b"2", False))

    assert queue.qsize == 2

    # 3つ目のputはブロックされるため、タイムアウト付きタスクで検証
    put_task = asyncio.create_task(queue.put((b"3", False)))

    # 少し待ってタスクが完了していない（ブロック中）ことを確認
    await asyncio.sleep(0.05)
    assert not put_task.done()

    # 1つ取り出す
    item = await queue.get()
    assert item == (b"1", False)
    queue.task_done()

    # 取り出されたことでputが再開・完了することを確認
    await asyncio.wait_for(put_task, timeout=0.5)
    assert queue.qsize == 2

    item2 = await queue.get()
    assert item2 == (b"2", False)
    item3 = await queue.get()
    assert item3 == (b"3", False)


@pytest.mark.anyio
async def test_stream_audio_producer() -> None:
    """StreamAudioProducerによるパススルー投入と終了通知を検証。"""
    queue = AudioChunkQueue()
    producer = StreamAudioProducer(queue)

    await producer.feed_chunk(b"stream_data_1", is_speech=True)
    await producer.feed_chunk(b"stream_data_2", is_speech=False)
    await producer.stop()

    assert queue.qsize == 3
    assert await queue.get() == (b"stream_data_1", True)
    assert await queue.get() == (b"stream_data_2", False)
    assert await queue.get() is None


@pytest.mark.anyio
async def test_file_audio_producer_without_denoise(tmp_path: Path) -> None:
    """FileAudioProducerのFFmpeg非同期デコーダー読み込みと
    キュー投入を検証（ノイズ除去無効時）。"""
    # ダミーの音声ファイルを準備
    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"A" * 10000)

    queue = AudioChunkQueue()
    app_config = AppConfig()
    app_config.denoise.enabled = False
    app_config.stream.sample_rate = 16000
    app_config.stream.chunk_size_ms = 100  # 100ms

    # 100ms分のバイト数 = 16000 * 0.1 * 2bytes = 3200 bytes
    expected_chunk_bytes = 3200

    # FFmpegプロセスおよびstdoutをモック化
    from unittest.mock import AsyncMock

    mock_process = MagicMock()
    mock_stdout = asyncio.StreamReader()
    # 2回分のチャンクと、最後にEOFを返すようにデータを供給
    mock_stdout.feed_data(b"B" * expected_chunk_bytes)
    mock_stdout.feed_data(b"C" * 1000)  # 不完全チャンク（1000バイト）
    mock_stdout.feed_eof()

    mock_process.stdout = mock_stdout
    mock_process.stderr = asyncio.StreamReader()
    mock_process.stderr.feed_eof()
    mock_process.terminate = MagicMock()
    # wait() が 0 (正常終了) を返す非同期モック
    mock_process.wait = AsyncMock(return_value=0)

    producer = FileAudioProducer(dummy_wav, queue, app_config)

    with patch(
        "asyncio.create_subprocess_exec", return_value=mock_process
    ) as mock_exec:
        await producer.start()
        await producer.join()

        # 呼び出しパラメータの検証
        mock_exec.assert_called_once()
        args = mock_exec.call_args[0]
        assert args[0] == "ffmpeg"
        assert "-loglevel" in args
        assert "error" in args
        assert "-i" in args
        assert str(dummy_wav) in args

        # キュー内容の検証
        assert queue.qsize == 3  # 完全チャンク, 不完全チャンク, センチネルNone

        chunk1 = await queue.get()
        assert chunk1 == (b"B" * expected_chunk_bytes, False)

        chunk2 = await queue.get()
        assert chunk2 == (b"C" * 1000, False)

        chunk3 = await queue.get()
        assert chunk3 is None


@pytest.mark.anyio
async def test_file_audio_producer_with_denoise(tmp_path: Path) -> None:
    """FileAudioProducerがRNNoise前処理を実行した上で
    デコード処理へ進むかを検証。"""
    dummy_input = tmp_path / "input.wav"
    dummy_input.write_bytes(b"raw_bytes")

    queue = AudioChunkQueue()
    app_config = AppConfig()
    app_config.denoise.enabled = True
    app_config.paths.output_dir = tmp_path / "output"

    from unittest.mock import AsyncMock

    # デノイザーとFFmpegのモック
    mock_denoiser = MagicMock()
    mock_denoiser.denoise = MagicMock()

    mock_process = MagicMock()
    mock_stdout = asyncio.StreamReader()
    mock_stdout.feed_eof()
    mock_process.stdout = mock_stdout
    mock_process.stderr = asyncio.StreamReader()
    mock_process.stderr.feed_eof()
    mock_process.terminate = MagicMock()
    mock_process.wait = AsyncMock(return_value=0)

    producer = FileAudioProducer(dummy_input, queue, app_config)

    with (
        patch(
            "audio_transcriber.audio_producers.create_denoiser",
            return_value=mock_denoiser,
        ) as mock_create_denoiser,
        patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec,
    ):
        await producer.start()
        await producer.join()

        # ノイズ除去器が生成され実行されたか
        mock_create_denoiser.assert_called_once_with(app_config.denoise)
        # 一時クリーニングファイルに対してノイズ除去が実行されたか
        assert mock_denoiser.denoise.call_count == 1
        call_args = mock_denoiser.denoise.call_args[0]
        assert call_args[0] == dummy_input
        actual_temp_path = call_args[1]
        assert actual_temp_path.parent == app_config.paths.output_dir
        assert actual_temp_path.stem.startswith("input_clean_")
        assert len(actual_temp_path.stem) == len("input_clean_") + 32

        # FFmpegがデノイズ済み一時ファイルをインプットとして起動されたか
        mock_exec.assert_called_once()
        args = mock_exec.call_args[0]
        assert str(actual_temp_path) in args
        assert "-loglevel" in args
        assert "error" in args

        # センチネルNoneが投入されたことを確認
        assert queue.qsize == 1
        assert await queue.get() is None


@pytest.mark.anyio
async def test_audio_chunk_queue_dynamic_maxsize() -> None:
    """AudioChunkQueueのmaxsize動的変更メソッドを検証。"""
    queue = AudioChunkQueue(maxsize=10)
    assert queue.maxsize == 10
    queue.maxsize = 20
    assert queue.maxsize == 20

    with pytest.raises(ValueError):
        queue.maxsize = -5


@pytest.mark.anyio
async def test_file_audio_producer_custom_sampling_rate(tmp_path: Path) -> None:
    """FileAudioProducerが要求サンプリングレートと
    カスタムチャンク時間長を適切に引き回すか検証。"""
    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"A" * 10000)

    queue = AudioChunkQueue()
    app_config = AppConfig()
    app_config.denoise.enabled = False

    from unittest.mock import AsyncMock

    mock_process = MagicMock()
    mock_stdout = asyncio.StreamReader()
    mock_stdout.feed_eof()
    mock_process.stdout = mock_stdout
    mock_process.stderr = asyncio.StreamReader()
    mock_process.stderr.feed_eof()
    mock_process.terminate = MagicMock()
    mock_process.wait = AsyncMock(return_value=0)

    # 24000Hz, 50ms = 24000 * 0.05 * 2bytes = 2400 bytes チャンクを期待
    producer = FileAudioProducer(
        dummy_wav, queue, app_config, sample_rate=24000, chunk_size_ms=50
    )

    with patch(
        "asyncio.create_subprocess_exec", return_value=mock_process
    ) as mock_exec:
        await producer.start()
        await producer.join()

        mock_exec.assert_called_once()
        args = mock_exec.call_args[0]
        # FFmpegの起動引数に指定レート 24000 が含まれること
        assert "-ar" in args
        assert "24000" in args


@pytest.mark.anyio
async def test_file_audio_producer_ffmpeg_error(tmp_path: Path) -> None:
    """FFmpegが異常終了した際に
    エラーログ詳細を含んだ RuntimeError が送出されるか検証。"""
    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"A" * 1000)

    queue = AudioChunkQueue()
    app_config = AppConfig()
    app_config.denoise.enabled = False

    from unittest.mock import AsyncMock

    mock_process = MagicMock()
    mock_stdout = asyncio.StreamReader()
    mock_stdout.feed_eof()
    mock_process.stdout = mock_stdout

    # stderr にダミーエラーを供給
    mock_stderr = asyncio.StreamReader()
    mock_stderr.feed_data(b"ffmpeg dec error: sample corrupted")
    mock_stderr.feed_eof()
    mock_process.stderr = mock_stderr

    mock_process.terminate = MagicMock()
    # exit code = 1 (異常終了)
    mock_process.wait = AsyncMock(return_value=1)

    producer = FileAudioProducer(dummy_wav, queue, app_config)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        await producer.start()
        # 非同期タスクがバックグラウンドでコルーチンとして実行されているため、
        # join() でエラーが発生することを確認する。
        with pytest.raises(RuntimeError) as exc_info:
            await producer.join()

        assert "FFmpeg process exited with non-zero code 1" in str(exc_info.value)
        assert "ffmpeg dec error: sample corrupted" in str(exc_info.value)


@pytest.mark.anyio
async def test_file_audio_producer_cleanup_timeout(tmp_path: Path) -> None:
    """_cleanup時にterminateがハングした場合、SIGKILLが送出されるか検証。"""
    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"A" * 1000)

    queue = AudioChunkQueue()
    app_config = AppConfig()
    app_config.denoise.enabled = False

    mock_process = MagicMock()
    mock_stdout = asyncio.StreamReader()
    mock_stdout.feed_eof()
    mock_process.stdout = mock_stdout
    mock_process.stderr = asyncio.StreamReader()
    mock_process.stderr.feed_eof()

    mock_process.terminate = MagicMock()
    mock_process.kill = MagicMock()

    # 待機コルーチン。1回目はタイムアウトを引き起こすために意図的に遅延させる
    async def slow_wait():
        await asyncio.sleep(2.0)
        return 0

    mock_process.wait = slow_wait

    producer = FileAudioProducer(dummy_wav, queue, app_config)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        await producer.start()
        await asyncio.sleep(0.05)  # 起動を少し待つ

        # タイムアウトを引き起こすため、意図的にタイムアウトを極小値に落としたモック環境下にするか、
        # または直接 _cleanup() の処理を検証。
        # 0.5秒のタイムアウトを検証するため、スリープ待機してstopを呼び出す
        with patch("audio_transcriber.audio_producers.logger"):
            # タイムアウト時間が0.5秒なので、stop() 呼び出しが非同期に SIGKILL を呼ぶことを期待
            # pytest の実行速度向上のため、一時的に asyncio.wait_for のタイムアウト値を落とすなどしてもよいが、
            # wait_for がタイムアウト例外を投げ、kill() が呼ばれることをアサート
            await producer.stop()
            mock_process.kill.assert_called_once()


@pytest.mark.anyio
async def test_file_audio_producer_duplicate_start(tmp_path: Path) -> None:
    """すでに起動しているFileAudioProducerに対してstartを
    重複して呼んだらRuntimeErrorが送出されるか検証。"""
    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"A" * 1000)

    queue = AudioChunkQueue()
    app_config = AppConfig()
    app_config.denoise.enabled = False

    from unittest.mock import AsyncMock

    mock_process = MagicMock()
    mock_stdout = asyncio.StreamReader()
    mock_stdout.feed_eof()
    mock_process.stdout = mock_stdout
    mock_process.stderr = asyncio.StreamReader()
    mock_process.stderr.feed_eof()
    mock_process.terminate = MagicMock()
    mock_process.wait = AsyncMock(return_value=0)

    producer = FileAudioProducer(dummy_wav, queue, app_config)

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        await producer.start()
        with pytest.raises(RuntimeError) as exc_info:
            await producer.start()
        assert "FileAudioProducer is already running." in str(exc_info.value)
        await producer.stop()


@pytest.mark.anyio
async def test_audio_chunk_queue_dynamic_maxsize_wake_putters() -> None:
    """maxsizeを増やしたときに、put待ちのタスクが正しく起こされるか検証。"""
    queue = AudioChunkQueue(maxsize=1)
    await queue.put((b"data1", False))

    # 2つ目のputはブロックされる
    put_task = asyncio.create_task(queue.put((b"data2", False)))
    await asyncio.sleep(0.05)
    assert not put_task.done()

    # maxsizeを動的に増やす
    queue.maxsize = 2

    # これによりputタスクがウェイクアップして完了するはず
    await asyncio.wait_for(put_task, timeout=0.5)
    assert queue.qsize == 2


def test_audio_producers_constants() -> None:
    """定数値が正しく定義されていることを検証。"""
    from audio_transcriber.audio_producers import (
        BYTES_PER_SAMPLE_16BIT,
        DEFAULT_MAX_QUEUE_SIZE,
        FFMPEG_MONO_CHANNELS,
        FFMPEG_TERMINATE_TIMEOUT_SEC,
        MS_PER_SECOND,
        SENTINEL_PUT_TIMEOUT_SEC,
    )

    assert DEFAULT_MAX_QUEUE_SIZE == 100
    assert FFMPEG_TERMINATE_TIMEOUT_SEC == 0.5
    assert BYTES_PER_SAMPLE_16BIT == 2
    assert MS_PER_SECOND == 1000.0
    assert FFMPEG_MONO_CHANNELS == "1"
    assert SENTINEL_PUT_TIMEOUT_SEC == 1.0


@pytest.mark.anyio
async def test_file_audio_producer_join_cancelled(tmp_path: Path) -> None:
    """joinメソッドがCancelledErrorを適切に捕捉して正常終了するか検証。"""
    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"A" * 1000)

    queue = AudioChunkQueue()
    app_config = AppConfig()
    app_config.denoise.enabled = False

    producer = FileAudioProducer(dummy_wav, queue, app_config)

    # _run_task に、CancelledErrorを投げるタスクをモック
    async def cancelled_task():
        raise asyncio.CancelledError()

    producer._run_task = asyncio.create_task(cancelled_task())

    # joinを呼び出しても、CancelledErrorは外に出ない（passされる）
    await producer.join()


@pytest.mark.anyio
async def test_file_audio_producer_cleanup_terminate_exception(tmp_path: Path) -> None:
    """_cleanup実行時にFFmpegプロセスのterminate呼び出しが
    例外を投げた場合、適切に処理されるか検証。"""
    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"A" * 1000)

    queue = AudioChunkQueue()
    app_config = AppConfig()
    app_config.denoise.enabled = False

    producer = FileAudioProducer(dummy_wav, queue, app_config)

    mock_process = MagicMock()
    # terminateメソッドが例外を発生させるように設定
    mock_process.terminate = MagicMock(side_effect=Exception("Terminate error"))

    producer._ffmpeg_process = mock_process

    # _cleanup() を直接実行。例外がログ出力され、エラーでクラッシュせずに正常終了することを確認
    with patch("audio_transcriber.audio_producers.logger") as mock_logger:
        await producer._cleanup()
        mock_logger.warning.assert_any_call(
            "Error terminating ffmpeg process: %s", mock_process.terminate.side_effect
        )
        assert producer._ffmpeg_process is None


@pytest.mark.anyio
async def test_file_audio_producer_cleanup_temp_file_exception(tmp_path: Path) -> None:
    """_cleanup実行時に一時ファイルの削除(unlink)が
    例外を投げた場合、適切に処理されるか検証。"""
    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"A" * 1000)

    queue = AudioChunkQueue()
    app_config = AppConfig()
    app_config.denoise.enabled = False

    producer = FileAudioProducer(dummy_wav, queue, app_config)

    mock_temp_file = MagicMock()
    mock_temp_file.unlink = MagicMock(side_effect=OSError("Permission denied"))
    producer._temp_files.append(mock_temp_file)

    with patch("audio_transcriber.audio_producers.logger") as mock_logger:
        await producer._cleanup()
        mock_logger.warning.assert_called_with(
            "Error deleting temporary file %s: %s",
            mock_temp_file,
            mock_temp_file.unlink.side_effect,
        )
        assert len(producer._temp_files) == 0


@pytest.mark.anyio
async def test_file_audio_producer_launch_ffmpeg_exception(tmp_path: Path) -> None:
    """FFmpegの起動に失敗してBaseExceptionが発生した際、
    プロセスが安全にkillされ、例外が再送されるか検証。"""
    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"A" * 1000)

    queue = AudioChunkQueue()
    app_config = AppConfig()
    app_config.denoise.enabled = False

    producer = FileAudioProducer(dummy_wav, queue, app_config)

    mock_process = MagicMock()
    mock_process.kill = MagicMock(side_effect=Exception("Kill failure"))

    class MockBaseException(BaseException):
        pass

    def side_effect(*args, **kwargs):
        producer._ffmpeg_process = mock_process
        raise MockBaseException("Simulated BaseException during launch")

    with (
        patch("asyncio.create_subprocess_exec", side_effect=side_effect),
        pytest.raises(MockBaseException),
    ):
        await producer._run()

    mock_process.kill.assert_called_once()
    assert producer._ffmpeg_process is None


@pytest.mark.anyio
async def test_file_audio_producer_stdout_stderr_none(tmp_path: Path) -> None:
    """FFmpegプロセスのstdout/stderrがNoneの場合に
    RuntimeErrorが送出されるか検証。"""
    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"A" * 1000)

    queue = AudioChunkQueue()
    app_config = AppConfig()
    app_config.denoise.enabled = False

    producer = FileAudioProducer(dummy_wav, queue, app_config)

    mock_process = MagicMock()
    mock_process.stdout = None  # stdoutをNoneに設定
    mock_process.stderr = asyncio.StreamReader()

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        await producer.start()
        with pytest.raises(RuntimeError) as exc_info:
            await producer.join()
        assert "Failed to open stdout/stderr of ffmpeg subprocess." in str(
            exc_info.value
        )


@pytest.mark.anyio
async def test_file_audio_producer_ffmpeg_process_none_before_wait(
    tmp_path: Path,
) -> None:
    """ループ終了後にself._ffmpeg_processがNoneになっていた場合に
    RuntimeErrorが送出されるか検証。"""
    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"A" * 1000)

    queue = AudioChunkQueue()
    app_config = AppConfig()
    app_config.denoise.enabled = False

    producer = FileAudioProducer(dummy_wav, queue, app_config)

    mock_process = MagicMock()
    mock_stdout = asyncio.StreamReader()
    mock_stdout.feed_eof()  # すぐにループを抜けるように
    mock_process.stdout = mock_stdout
    mock_process.stderr = asyncio.StreamReader()
    mock_process.stderr.feed_eof()

    async def mock_readexactly(n):
        producer._ffmpeg_process = None
        raise asyncio.IncompleteReadError(b"", n)

    mock_stdout.readexactly = mock_readexactly

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        await producer.start()
        with pytest.raises(RuntimeError) as exc_info:
            await producer.join()
        assert "FFmpeg process is not running." in str(exc_info.value)


@pytest.mark.anyio
async def test_file_audio_producer_sentinel_put_timeout(tmp_path: Path) -> None:
    """センチネル(None)投入時にタイムアウトした場合に警告がログ出力されるか検証。"""
    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"A" * 1000)

    queue = AudioChunkQueue()
    app_config = AppConfig()
    app_config.denoise.enabled = False

    producer = FileAudioProducer(dummy_wav, queue, app_config)

    mock_process = MagicMock()
    mock_stdout = asyncio.StreamReader()
    mock_stdout.feed_eof()
    mock_process.stdout = mock_stdout
    mock_process.stderr = asyncio.StreamReader()
    mock_process.stderr.feed_eof()
    mock_process.wait = AsyncMock(return_value=0)

    async def mock_put_timeout(item):
        raise TimeoutError()

    queue.put = mock_put_timeout

    with (
        patch("asyncio.create_subprocess_exec", return_value=mock_process),
        patch("audio_transcriber.audio_producers.logger") as mock_logger,
    ):
        await producer.start()
        await producer.join()
        mock_logger.warning.assert_any_call(
            "Timeout putting sentinel into queue. Consumer might have stopped."
        )


@pytest.mark.anyio
async def test_file_audio_producer_sentinel_put_exception(tmp_path: Path) -> None:
    """センチネル(None)投入時に一般的な例外が発生した場合に
    警告がログ出力されるか検証。"""
    dummy_wav = tmp_path / "dummy.wav"
    dummy_wav.write_bytes(b"A" * 1000)

    queue = AudioChunkQueue()
    app_config = AppConfig()
    app_config.denoise.enabled = False

    producer = FileAudioProducer(dummy_wav, queue, app_config)

    mock_process = MagicMock()
    mock_stdout = asyncio.StreamReader()
    mock_stdout.feed_eof()
    mock_process.stdout = mock_stdout
    mock_process.stderr = asyncio.StreamReader()
    mock_process.stderr.feed_eof()
    mock_process.wait = AsyncMock(return_value=0)

    test_ex = Exception("Simulated queue put error")

    async def mock_put_exception(item):
        raise test_ex

    queue.put = mock_put_exception

    with (
        patch("asyncio.create_subprocess_exec", return_value=mock_process),
        patch("audio_transcriber.audio_producers.logger") as mock_logger,
    ):
        await producer.start()
        await producer.join()
        mock_logger.warning.assert_any_call(
            "Failed to put sentinel into queue: %s", test_ex
        )
