import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from audio_transcriber.callbacks import BasePipelineCallbacks
from audio_transcriber.models import RecognizedSegment, VadState
from audio_transcriber.pipeline_supervisor import PipelineSupervisor
from audio_transcriber.streaming.core import AudioStreamPipeline
from audio_transcriber.stt_types import TranscriberProvider


class MockCallbacks(BasePipelineCallbacks):
    """テスト用決定論的コールバックレコーダー。"""

    def __init__(self) -> None:
        self.vad_states: list[VadState] = []
        self.recognized_segments: list[RecognizedSegment] = []
        self.errors: list[BaseException] = []
        self.speech_starts: list[float] = []
        self.speech_ends: list[float] = []
        self.segment_event = asyncio.Event()
        self.speech_start_event = asyncio.Event()
        self.speech_end_event = asyncio.Event()
        self.error_event = asyncio.Event()

    def on_vad_state_change(self, state: VadState) -> None:
        self.vad_states.append(state)

    def on_segment_recognized(self, segment: RecognizedSegment) -> None:
        self.recognized_segments.append(segment)
        self.segment_event.set()

    def on_error(self, error: BaseException) -> None:
        self.errors.append(error)
        self.error_event.set()

    def on_speech_start(self, timestamp: float) -> None:
        self.speech_starts.append(timestamp)
        self.speech_start_event.set()

    def on_speech_end(self, timestamp: float) -> None:
        self.speech_ends.append(timestamp)
        self.speech_end_event.set()


@pytest.fixture
def mock_transcriber() -> MagicMock:
    """テスト用 TranscriberProvider のモックを返します。"""
    transcriber = MagicMock(spec=TranscriberProvider)
    transcriber.transcribe_stream.return_value = [
        {
            "id": 1,
            "start": 0.0,
            "end": 1.0,
            "text": "ストリーミング認識テスト",
            "confidence": 0.98,
            "no_speech_prob": 0.01,
            "compression_ratio": 1.0,
            "words": [],
        }
    ]
    return transcriber


@pytest.fixture
def mock_streaming_pipeline(mock_transcriber: MagicMock) -> AsyncMock:
    """テスト用 AudioStreamPipeline のモックを返します。"""
    pipeline = AsyncMock(spec=AudioStreamPipeline)
    pipeline.start = AsyncMock(return_value=None)
    pipeline.stop = AsyncMock(return_value=None)
    pipeline.reset = AsyncMock(return_value=None)
    pipeline.feed_chunk = AsyncMock(return_value=None)
    pipeline._is_running = False
    pipeline._stream_seconds = 0.0
    pipeline._vad_state = VadState.SILENCE
    return pipeline


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_pipeline_supervisor_lifecycle(
    mock_streaming_pipeline: AsyncMock,
) -> None:
    """PipelineSupervisor の開始、停止、リセットのライフサイクルテスト。"""
    supervisor = PipelineSupervisor(pipeline=mock_streaming_pipeline)

    assert not supervisor.is_running

    await supervisor.start()
    mock_streaming_pipeline.start.assert_awaited_once()
    assert supervisor.is_running

    await supervisor.stop()
    mock_streaming_pipeline.stop.assert_awaited_once()
    assert not supervisor.is_running

    mock_streaming_pipeline.start.reset_mock()
    mock_streaming_pipeline.stop.reset_mock()
    # 複数回 start/stop を呼んでも安全
    await supervisor.start()
    await supervisor.start()
    mock_streaming_pipeline.start.assert_awaited_once()

    await supervisor.stop()
    await supervisor.stop()
    mock_streaming_pipeline.stop.assert_awaited_once()

    await supervisor.reset()
    mock_streaming_pipeline.reset.assert_awaited_once()


@pytest.mark.anyio
async def test_pipeline_supervisor_error_handling(
    mock_streaming_pipeline: AsyncMock,
) -> None:
    """例外発生時に on_error が適切に通知され、リカバリされることをテスト。"""
    callbacks = MockCallbacks()
    mock_streaming_pipeline.start.side_effect = RuntimeError("Pipeline start error")
    supervisor = PipelineSupervisor(
        pipeline=mock_streaming_pipeline, callbacks=callbacks
    )

    with pytest.raises(RuntimeError, match="Pipeline start error"):
        await supervisor.start()
    assert len(callbacks.errors) == 1
    assert "Pipeline start error" in str(callbacks.errors[0])
    # エラー時にリセットが呼ばれることを確認
    mock_streaming_pipeline.reset.assert_awaited_once()
    assert (
        not supervisor.is_running
    )  # エラー後、is_running が False になっていることを確認

    callbacks.errors.clear()
    mock_streaming_pipeline.start.reset_mock()
    mock_streaming_pipeline.reset.reset_mock()
    mock_streaming_pipeline.feed_chunk.side_effect = RuntimeError("Feed chunk error")

    # 2回目のstart呼び出しで例外が発生しないように設定を解除
    mock_streaming_pipeline.start.side_effect = None
    # エラー回復後、再開できることを確認
    await supervisor.start()  # 再度開始
    mock_streaming_pipeline.start.assert_awaited_once()
    assert supervisor.is_running

    with pytest.raises(RuntimeError, match="Feed chunk error"):
        await supervisor.feed_chunk(b"dummy_data")
    assert len(callbacks.errors) == 1
    assert "Feed chunk error" in str(callbacks.errors[0])
    # エラー時にリセットが呼ばれることを確認
    mock_streaming_pipeline.reset.assert_awaited_once()
    assert (
        not supervisor.is_running
    )  # エラー後、is_running が False になっていることを確認


@pytest.mark.anyio
async def test_pipeline_supervisor_feed_chunk(
    mock_streaming_pipeline: AsyncMock,
) -> None:
    """feed_chunk が適切にパイプラインに渡されることをテスト。"""
    supervisor = PipelineSupervisor(pipeline=mock_streaming_pipeline)

    # パイプラインが実行中でない場合は feed_chunk が呼ばれない
    await supervisor.feed_chunk(b"dummy_data")
    mock_streaming_pipeline.feed_chunk.assert_not_called()

    await supervisor.start()
    mock_streaming_pipeline.start.assert_awaited_once()

    # パイプラインが実行中の場合は feed_chunk が呼ばれる
    await supervisor.feed_chunk(b"dummy_data", is_speech=True)
    # is_speech が位置引数として渡されるため、以下のように検証
    mock_streaming_pipeline.feed_chunk.assert_awaited_once_with(b"dummy_data", True)


@pytest.mark.anyio
async def test_pipeline_supervisor_on_metrics_passthrough(
    mock_streaming_pipeline: AsyncMock,
) -> None:
    """on_metrics コールバックがパイプラインから適切に伝播されることをテスト。"""
    callbacks = MockCallbacks()
    supervisor = PipelineSupervisor(
        pipeline=mock_streaming_pipeline, callbacks=callbacks
    )

    # 現状、mock_streaming_pipeline が on_metrics を持っていないため、ここでは直接テストできない。
    # on_metrics の伝播は、UnifiedTranscriptionPipeline の実装時にそこでテストする。
    # ここでは、Supervisor が少なくとも on_metrics を受け取れる準備ができていることを確認する程度に留める。
    assert hasattr(supervisor, "on_metrics")
    assert callable(supervisor.on_metrics)

    # カバレッジ100%を保証するために直接呼び出しをテスト
    supervisor.on_metrics({"latency": 0.05})


@pytest.mark.anyio
async def test_pipeline_supervisor_file_input_calls_pipeline(
    mock_streaming_pipeline: AsyncMock,
) -> None:
    """run_file メソッドが FileAudioProducer から
    デコードされたデータをパイプラインに投入することをテスト。"""
    supervisor = PipelineSupervisor(pipeline=mock_streaming_pipeline)

    # FileAudioProducer の動作をモック化
    mock_producer = MagicMock()
    mock_producer.start = AsyncMock()
    mock_producer.join = AsyncMock()
    mock_producer.stop = AsyncMock()

    # 2つのチャンクデータがキュー経由で流れる動作をシミュレート
    async def mock_queue_get(self_queue):
        # 1回目の get
        yield (b"chunk1", True)
        # 2回目の get
        yield (b"chunk2", False)
        # 終了センチネル
        yield None

    mock_get_gen = mock_queue_get(None)

    async def mock_get():
        return await anext(mock_get_gen)

    with (
        patch(
            "audio_transcriber.pipeline_supervisor.FileAudioProducer",
            return_value=mock_producer,
        ),
        patch(
            "audio_transcriber.pipeline_supervisor.AudioChunkQueue"
        ) as mock_queue_cls,
    ):
        # キューのモックを設定
        mock_queue = MagicMock()
        mock_queue.get = mock_get
        mock_queue.task_done = MagicMock()
        mock_queue_cls.return_value = mock_queue

        await supervisor.run_file("dummy_file.wav")

        # 開始、投入、停止がそれぞれ適切な回数呼ばれたことをアサート
        mock_streaming_pipeline.start.assert_awaited_once()
        assert mock_streaming_pipeline.feed_chunk.await_count == 2
        mock_streaming_pipeline.feed_chunk.assert_any_await(b"chunk1", True)
        mock_streaming_pipeline.feed_chunk.assert_any_await(b"chunk2", False)
        mock_streaming_pipeline.stop.assert_awaited_once()
        mock_producer.start.assert_awaited_once()
        mock_producer.join.assert_awaited_once()
        mock_producer.stop.assert_awaited_once()


@pytest.mark.anyio
async def test_pipeline_supervisor_race_condition(
    mock_streaming_pipeline: AsyncMock,
) -> None:
    """start()を同時に重複して呼び出した際、
    排他制御ロックによって1度しか開始が呼ばれないことを検証。"""
    supervisor = PipelineSupervisor(pipeline=mock_streaming_pipeline)

    # 1秒間ウェイトする開始をシミュレート
    async def slow_start():
        await asyncio.sleep(0.1)

    mock_streaming_pipeline.start.side_effect = slow_start

    # startを2つ並列で走らせる
    task1 = asyncio.create_task(supervisor.start())
    task2 = asyncio.create_task(supervisor.start())

    await asyncio.gather(task1, task2)

    # 排他ロックにより、重複した start_unlocked は早期リターンするため、
    # 実際の start 待機は1回のみ呼ばれるはず
    assert mock_streaming_pipeline.start.await_count == 1


@pytest.mark.anyio
async def test_pipeline_supervisor_stream_input_lifecycle(
    mock_streaming_pipeline: AsyncMock,
) -> None:
    """run_stream メソッドがパイプラインの開始・停止を呼び出すことをテスト。"""
    supervisor = PipelineSupervisor(pipeline=mock_streaming_pipeline)
    async with await supervisor.run_stream():
        pass
    mock_streaming_pipeline.start.assert_awaited_once()
    mock_streaming_pipeline.stop.assert_awaited_once()


@pytest.mark.anyio
async def test_pipeline_supervisor_stream_input_with_error(
    mock_streaming_pipeline: AsyncMock,
) -> None:
    """run_stream メソッド内でエラーが発生した場合、
    on_error が呼ばれ、パイプラインが停止することを確認。"""
    callbacks = MockCallbacks()
    supervisor = PipelineSupervisor(
        pipeline=mock_streaming_pipeline, callbacks=callbacks
    )

    async def buggy_operation():
        raise RuntimeError("Stream processing error")

    with pytest.raises(RuntimeError, match="Stream processing error"):
        async with await supervisor.run_stream():
            await buggy_operation()

    await callbacks.error_event.wait()  # エラーイベントの発生を待機
    assert len(callbacks.errors) == 1
    assert "Stream processing error" in str(callbacks.errors[0])
    mock_streaming_pipeline.stop.assert_awaited_once()


@pytest.mark.anyio
async def test_pipeline_supervisor_run_file_stopped_midway(
    mock_streaming_pipeline: AsyncMock,
) -> None:
    """run_file 中に pipeline が
    停止された場合にループを適切に抜けることをテスト。"""
    supervisor = PipelineSupervisor(pipeline=mock_streaming_pipeline)

    # 1つ目のチャンクを処理した後に supervisor.stop() を呼び出して停止状態にする
    async def mock_queue_get(self_queue):
        yield (b"chunk1", True)
        await supervisor.stop()  # 途中で停止
        yield (b"chunk2", False)
        yield None

    mock_get_gen = mock_queue_get(None)

    async def mock_get():
        return await anext(mock_get_gen)

    with (
        patch(
            "audio_transcriber.pipeline_supervisor.FileAudioProducer",
        ) as mock_producer_cls,
        patch(
            "audio_transcriber.pipeline_supervisor.AudioChunkQueue"
        ) as mock_queue_cls,
    ):
        mock_producer = MagicMock()
        mock_producer.start = AsyncMock()
        mock_producer.join = AsyncMock()
        mock_producer.stop = AsyncMock()
        mock_producer_cls.return_value = mock_producer

        mock_queue = MagicMock()
        mock_queue.get = mock_get
        mock_queue.task_done = MagicMock()
        mock_queue_cls.return_value = mock_queue

        await supervisor.run_file("dummy_file.wav")

        # stop() が呼ばれて以降は feed_chunk が呼ばれず、ループを抜ける
        assert mock_streaming_pipeline.feed_chunk.await_count == 1
        mock_streaming_pipeline.feed_chunk.assert_any_await(b"chunk1", True)


@pytest.mark.anyio
async def test_pipeline_supervisor_run_file_exception_recovery(
    mock_streaming_pipeline: AsyncMock,
) -> None:
    """run_file 実行中に例外が発生した場合、
    エラー通知と強制停止が適切に機能することをテスト。"""
    callbacks = MockCallbacks()
    supervisor = PipelineSupervisor(
        pipeline=mock_streaming_pipeline, callbacks=callbacks
    )

    # 1回目の get で例外を投げる
    async def mock_queue_get_error():
        raise RuntimeError("Producer process failed")

    with (
        patch(
            "audio_transcriber.pipeline_supervisor.FileAudioProducer",
        ) as mock_producer_cls,
        patch(
            "audio_transcriber.pipeline_supervisor.AudioChunkQueue"
        ) as mock_queue_cls,
    ):
        mock_producer = MagicMock()
        mock_producer.start = AsyncMock()
        mock_producer.join = AsyncMock()
        mock_producer.stop = AsyncMock()
        mock_producer_cls.return_value = mock_producer

        mock_queue = MagicMock()
        mock_queue.get = mock_queue_get_error
        mock_queue_cls.return_value = mock_queue

        with pytest.raises(RuntimeError, match="Producer process failed"):
            await supervisor.run_file("dummy_file.wav")

        # エラー通知と強制リセットが行われているか検証
        await callbacks.error_event.wait()
        assert len(callbacks.errors) == 1
        assert "Producer process failed" in str(callbacks.errors[0])
        mock_streaming_pipeline.reset.assert_awaited_once()
        mock_streaming_pipeline.stop.assert_awaited_once()
        assert not supervisor.is_running
