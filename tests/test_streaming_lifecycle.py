"""AudioStreamPipeline のライフサイクル・キュー管理・キャンセル・例外処理の単体テスト。"""

import asyncio
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from audio_transcriber.callbacks import BasePipelineCallbacks
from audio_transcriber.config import StreamConfig
from audio_transcriber.models import RecognizedSegment, VadState
from audio_transcriber.streaming import AudioStreamPipeline
from audio_transcriber.stt import TranscriberProvider


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
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_audio_stream_pipeline_lifecycle(mock_transcriber: MagicMock) -> None:
    """パイプラインの開始、停止、リセットのライフサイクルテスト。"""
    config = StreamConfig()
    callbacks = MockCallbacks()
    pipeline = AudioStreamPipeline(
        transcriber=mock_transcriber, callbacks=callbacks, config=config
    )

    assert pipeline._is_running is False

    await pipeline.start()
    assert pipeline._is_running is True

    # 複数回 start を呼んでも安全
    await pipeline.start()

    await pipeline.reset()
    assert pipeline._stream_seconds == 0.0
    assert pipeline._vad_state == VadState.SILENCE
    assert callbacks.vad_states[-1] == VadState.SILENCE

    await pipeline.stop()
    assert pipeline._is_running is False

    # 複数回 stop を呼んでも安全
    await pipeline.stop()


@pytest.mark.anyio
async def test_audio_stream_pipeline_error_handling(
    mock_transcriber: MagicMock,
) -> None:
    """例外発生時に on_error が適切に通知されることをテスト。"""
    config = StreamConfig()
    callbacks = MockCallbacks()
    mock_transcriber.transcribe_stream.side_effect = RuntimeError(
        "Whisper inference error"
    )

    pipeline = AudioStreamPipeline(
        transcriber=mock_transcriber, callbacks=callbacks, config=config
    )

    await pipeline.start()
    await pipeline.feed_chunk(np.zeros(16000, dtype=np.float32), is_speech=True)
    await pipeline.feed_chunk(np.zeros(16000, dtype=np.float32), is_speech=False)

    await asyncio.wait_for(callbacks.error_event.wait(), timeout=1.0)
    await pipeline.stop()

    assert len(callbacks.errors) > 0
    assert "Whisper inference error" in str(callbacks.errors[0])


@pytest.mark.anyio
async def test_audio_stream_pipeline_feed_chunk_not_running(
    mock_transcriber: MagicMock,
) -> None:
    """未実行状態での feed_chunk が安全に無視されることをテスト。"""
    pipeline = AudioStreamPipeline(transcriber=mock_transcriber)
    await pipeline.feed_chunk(b"data")
    assert pipeline._queue.empty()


@pytest.mark.anyio
async def test_audio_stream_pipeline_reset_and_drain_queue(
    mock_transcriber: MagicMock,
) -> None:
    """キューにアイテムが残っている状態で reset を呼び出し安全にクリアされることをテスト。"""
    config = StreamConfig()
    callbacks = MockCallbacks()
    pipeline = AudioStreamPipeline(
        transcriber=mock_transcriber, callbacks=callbacks, config=config
    )
    pipeline._is_running = True
    await pipeline.feed_chunk(b"chunk1", is_speech=True)
    await pipeline.feed_chunk(b"chunk2", is_speech=False)
    assert not pipeline._queue.empty()

    await pipeline.reset()
    assert pipeline._queue.empty()
    assert pipeline._stream_seconds == 0.0
    assert pipeline._vad_state == VadState.SILENCE


@pytest.mark.anyio
async def test_audio_stream_pipeline_process_loop_cancellation(
    mock_transcriber: MagicMock,
) -> None:
    """プロセスループがタスクキャンセルされた際に安全に終了することをテスト。"""
    callbacks = MockCallbacks()
    pipeline = AudioStreamPipeline(transcriber=mock_transcriber, callbacks=callbacks)

    loop_started = asyncio.Event()
    orig_get = pipeline._queue.get

    async def tracking_get() -> tuple[Any, bool] | None:
        loop_started.set()
        return await orig_get()

    pipeline._queue.get = tracking_get  # type: ignore[method-assign]
    pipeline._is_running = True
    pipeline._loop_task = asyncio.create_task(pipeline._process_loop())
    await loop_started.wait()

    pipeline._loop_task.cancel()
    try:
        await pipeline._loop_task
    except asyncio.CancelledError:
        pass
    assert len(callbacks.errors) == 0
