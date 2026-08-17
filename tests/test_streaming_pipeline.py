"""AudioStreamPipeline の音声処理・サニタイズ・タイミング・文脈プロンプトの単体テスト。"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from audio_transcriber.callbacks import BasePipelineCallbacks
from audio_transcriber.config import AppConfig, StreamConfig
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
async def test_audio_stream_pipeline_speech_processing_and_callbacks(
    mock_transcriber: MagicMock,
) -> None:
    """音声チャンクの投入とVAD切り出し・推論コールバック発火の決定論的テスト。"""
    config = StreamConfig(
        sample_rate=16000,
        chunk_min_seconds=1.0,
        chunk_max_seconds=5.0,
    )
    callbacks = MockCallbacks()
    pipeline = AudioStreamPipeline(
        transcriber=mock_transcriber,
        callbacks=callbacks,
        config=config,
        timecode_offset=10.0,
    )

    await pipeline.start()

    # 1.0秒分の発話チャンク (is_speech=True)
    audio_chunk = np.zeros(16000, dtype=np.int16).tobytes()
    await pipeline.feed_chunk(audio_chunk, is_speech=True)

    await asyncio.wait_for(callbacks.speech_start_event.wait(), timeout=1.0)
    assert callbacks.speech_starts == [10.0]
    assert VadState.SPEECH_START in callbacks.vad_states
    assert VadState.SPEECH in callbacks.vad_states
    assert len(callbacks.recognized_segments) == 0

    # 1.0秒分の無音チャンク (is_speech=False) -> min_silence (0.5s) を超えて確定
    silence_chunk = np.zeros(16000, dtype=np.float32)
    await pipeline.feed_chunk(silence_chunk, is_speech=False)

    await asyncio.wait_for(callbacks.segment_event.wait(), timeout=1.0)
    await pipeline.stop()

    assert len(callbacks.speech_ends) >= 1
    assert len(callbacks.recognized_segments) == 1
    rec = callbacks.recognized_segments[0]
    assert rec.text == "ストリーミング認識テスト"
    assert rec.start == 10.0
    assert rec.end == 11.0
    assert len(callbacks.errors) == 0


@pytest.mark.anyio
async def test_audio_stream_pipeline_feed_int16_ndarray(
    mock_transcriber: MagicMock,
) -> None:
    """int16 型の numpy 配列チャンクを直接投入して正常に処理されることをテスト。"""
    config = StreamConfig(sample_rate=16000, chunk_min_seconds=0.5)
    callbacks = MockCallbacks()
    pipeline = AudioStreamPipeline(
        transcriber=mock_transcriber, callbacks=callbacks, config=config
    )

    await pipeline.start()
    int16_audio = np.zeros(8000, dtype=np.int16)
    await pipeline.feed_chunk(int16_audio, is_speech=True)
    await pipeline.feed_chunk(np.zeros(8000, dtype=np.int16), is_speech=False)

    await asyncio.wait_for(callbacks.segment_event.wait(), timeout=1.0)
    await pipeline.stop()

    assert len(callbacks.recognized_segments) == 1


@pytest.mark.anyio
async def test_audio_stream_pipeline_context_and_dictionary(
    tmp_path: Path, mock_transcriber: MagicMock
) -> None:
    """カスタム辞書置換および文脈プロンプトの維持を検証するテスト。"""
    dict_file = tmp_path / "custom_dict.toml"
    dict_file.write_text('AI = "人工知能"\n', encoding="utf-8")

    app_cfg = AppConfig()
    app_cfg.paths.custom_dict_path = dict_file
    app_cfg.stream.chunk_min_seconds = 0.5
    app_cfg.transcribe.vad.min_silence_duration_ms = 200

    mock_transcriber.transcribe_stream.return_value = [
        {
            "start": 0.0,
            "end": 1.5,
            "text": "最新の AI 技術",
            "no_speech_prob": 0.0,
        }
    ]

    callbacks = MockCallbacks()
    pipeline = AudioStreamPipeline(
        transcriber=mock_transcriber,
        callbacks=callbacks,
        app_config=app_cfg,
    )

    await pipeline.start()

    # 1.5秒発話 + 0.3秒無音
    await pipeline.feed_chunk(np.zeros(24000, dtype=np.float32), is_speech=True)
    await pipeline.feed_chunk(np.zeros(4800, dtype=np.float32), is_speech=False)

    await asyncio.wait_for(callbacks.segment_event.wait(), timeout=1.0)
    await pipeline.stop()

    assert len(callbacks.recognized_segments) == 1
    assert callbacks.recognized_segments[0].text == "最新の 人工知能 技術"
    assert "人工知能" in pipeline.context_manager.get_prompt()


@pytest.mark.anyio
async def test_audio_stream_pipeline_sanitizer_drops_and_empty_text(
    mock_transcriber: MagicMock,
) -> None:
    """サニタイザーによる無音ドロップおよびテキスト処理後の空文字スキップをテスト。"""
    config = StreamConfig(sample_rate=16000, chunk_min_seconds=0.5)
    callbacks = MockCallbacks()
    pipeline = AudioStreamPipeline(
        transcriber=mock_transcriber, callbacks=callbacks, config=config
    )
    pipeline.processor.remove_punct = True

    # 1件目は無音捏造（no_speech_prob=0.99）、2件目は記号のみで処理後空文字、3件目は正常
    mock_transcriber.transcribe_stream.return_value = [
        {"start": 0.0, "end": 1.0, "text": "幻覚テキスト", "no_speech_prob": 0.99},
        {"start": 0.0, "end": 1.0, "text": "！？！？", "no_speech_prob": 0.0},
        {"start": 1.0, "end": 2.0, "text": "正常テキスト", "no_speech_prob": 0.0},
    ]

    await pipeline.start()
    await pipeline.feed_chunk(np.zeros(32000, dtype=np.float32), is_speech=True)
    await pipeline.feed_chunk(np.zeros(16000, dtype=np.float32), is_speech=False)

    await asyncio.wait_for(callbacks.segment_event.wait(), timeout=1.0)
    await pipeline.stop()

    assert len(callbacks.recognized_segments) == 1
    assert callbacks.recognized_segments[0].text == "正常テキスト"


@pytest.mark.anyio
async def test_audio_stream_pipeline_segment_timing_edge_cases(
    mock_transcriber: MagicMock,
) -> None:
    """セグメント終了時刻が開始時刻以下の場合に 0.1s 加算補正されることを厳密にテスト。"""
    config = StreamConfig(sample_rate=16000, chunk_min_seconds=0.5)
    callbacks = MockCallbacks()
    pipeline = AudioStreamPipeline(
        transcriber=mock_transcriber,
        callbacks=callbacks,
        config=config,
        timecode_offset=5.0,
    )

    # start と end が同じ (1.0, 1.0) -> start_offset(5.0) + 1.0 = 6.0, seg_end = 6.1
    mock_transcriber.transcribe_stream.return_value = [
        {"start": 1.0, "end": 1.0, "text": "あ", "no_speech_prob": 0.0}
    ]

    await pipeline.start()
    await pipeline.feed_chunk(np.zeros(8000, dtype=np.float32), is_speech=True)
    await pipeline.feed_chunk(np.zeros(8000, dtype=np.float32), is_speech=False)

    await asyncio.wait_for(callbacks.segment_event.wait(), timeout=1.0)
    await pipeline.stop()

    assert len(callbacks.recognized_segments) == 1
    seg = callbacks.recognized_segments[0]
    assert seg.start == 6.0
    assert seg.end == pytest.approx(6.1, rel=1e-3)


@pytest.mark.anyio
async def test_audio_stream_pipeline_flush_on_stop(
    mock_transcriber: MagicMock,
) -> None:
    """stop 時に保留中だった音声が flush されて推論されることをテスト。"""
    config = StreamConfig(sample_rate=16000, chunk_min_seconds=5.0)
    callbacks = MockCallbacks()
    pipeline = AudioStreamPipeline(
        transcriber=mock_transcriber, callbacks=callbacks, config=config
    )

    await pipeline.start()
    # 1.0秒発話のみ送信（最小5.0秒に未達のため通常時は保留）
    await pipeline.feed_chunk(np.zeros(16000, dtype=np.float32), is_speech=True)

    await pipeline.stop()

    assert len(callbacks.recognized_segments) == 1
    assert callbacks.recognized_segments[0].text == "ストリーミング認識テスト"
