"""テスト: ストリーミングパイプライン"""

import asyncio
from unittest.mock import MagicMock

import numpy as np
import pytest

from audio_transcriber.callbacks import BasePipelineCallbacks
from audio_transcriber.config import StreamConfig
from audio_transcriber.models import RecognizedSegment, VadState
from audio_transcriber.streaming import AudioStreamPipeline
from audio_transcriber.stt import TranscriberProvider


class MockCallbacks(BasePipelineCallbacks):
    def __init__(self):
        self.vad_states = []
        self.recognized_segments = []
        self.errors = []
        self.speech_starts = []
        self.speech_ends = []

    def on_vad_state_change(self, state: VadState) -> None:
        self.vad_states.append(state)

    def on_segment_recognized(self, segment: RecognizedSegment) -> None:
        self.recognized_segments.append(segment)

    def on_error(self, error: Exception) -> None:
        self.errors.append(error)

    def on_speech_start(self, timestamp: float) -> None:
        self.speech_starts.append(timestamp)

    def on_speech_end(self, timestamp: float) -> None:
        self.speech_ends.append(timestamp)


@pytest.fixture
def mock_transcriber():
    transcriber = MagicMock(spec=TranscriberProvider)
    return transcriber


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_audio_stream_pipeline_lifecycle(mock_transcriber):
    """パイプラインの開始、停止、リセットのライフサイクルテスト。"""
    config = StreamConfig()
    callbacks = MockCallbacks()
    pipeline = AudioStreamPipeline(
        transcriber=mock_transcriber, callbacks=callbacks, config=config
    )

    assert pipeline._is_running is False

    await pipeline.start()
    assert pipeline._is_running is True

    # 複数回startを呼んでも問題ないこと
    await pipeline.start()

    await pipeline.reset()
    assert len(pipeline._buffer) == 0
    assert pipeline._vad_state == VadState.SILENCE
    assert callbacks.vad_states[-1] == VadState.SILENCE

    await pipeline.stop()
    assert pipeline._is_running is False

    # 複数回stopを呼んでも問題ないこと
    await pipeline.stop()


@pytest.mark.anyio
async def test_audio_stream_pipeline_processing(mock_transcriber):
    """音声チャンクの投入とコールバック発火のテスト。"""
    config = StreamConfig(sample_rate=16000, buffer_size_seconds=1.0)
    callbacks = MockCallbacks()
    pipeline = AudioStreamPipeline(
        transcriber=mock_transcriber, callbacks=callbacks, config=config
    )

    await pipeline.start()

    # 0.5秒分(8000サンプル)の音声データを送信（バッファが満たされないためコールバックはまだ呼ばれないはず）
    half_audio = np.zeros(8000, dtype=np.int16).tobytes()
    await pipeline.feed_chunk(half_audio)

    # キュー処理待ち
    await asyncio.sleep(0.05)

    assert len(callbacks.vad_states) == 0
    assert len(callbacks.recognized_segments) == 0

    # 残りの0.5秒分を送信
    await pipeline.feed_chunk(half_audio)

    # キュー処理待ち
    await asyncio.sleep(0.1)

    await pipeline.stop()

    # VAD状態が順序通りに遷移したか厳密に確認
    assert callbacks.vad_states == [
        VadState.SPEECH_START,
        VadState.SPEECH,
        VadState.SPEECH_END,
        VadState.SILENCE,
    ]

    # 発話開始・終了が正しいタイムスタンプで発火したか
    assert callbacks.speech_starts == [0.0]
    assert callbacks.speech_ends == [1.0]

    # 認識セグメントが正しく渡されたか
    assert len(callbacks.recognized_segments) == 1
    assert callbacks.recognized_segments[0].text == "Transcribed stream text"
    assert len(callbacks.errors) == 0


@pytest.mark.anyio
async def test_audio_stream_pipeline_error_handling(mock_transcriber):
    """例外処理のテスト。"""
    config = StreamConfig()
    callbacks = MockCallbacks()
    pipeline = AudioStreamPipeline(
        transcriber=mock_transcriber, callbacks=callbacks, config=config
    )

    await pipeline.start()

    # 不正なデータを送ってエラーを起こさせる（例として、無効な型）
    await pipeline.feed_chunk("invalid data")  # type: ignore

    await asyncio.sleep(0.1)
    await pipeline.stop()

    # on_error が発火したか確認
    assert len(callbacks.errors) > 0
    assert isinstance(callbacks.errors[0], Exception)
