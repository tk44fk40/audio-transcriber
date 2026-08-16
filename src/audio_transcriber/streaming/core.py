"""リアルタイム音声ストリーミング処理モジュール。"""

import asyncio
import logging
from typing import Any

import numpy as np

from audio_transcriber.callbacks import BasePipelineCallbacks, PipelineCallbacks
from audio_transcriber.config import StreamConfig
from audio_transcriber.models import RecognizedSegment, VadState
from audio_transcriber.stt import TranscriberProvider

logger = logging.getLogger(__name__)


class AudioStreamPipeline:
    """リアルタイム音声ストリーミングパイプライン。"""

    def __init__(
        self,
        transcriber: TranscriberProvider,
        callbacks: PipelineCallbacks | None = None,
        config: StreamConfig | None = None,
    ) -> None:
        """初期化します。"""
        self.transcriber = transcriber
        self.callbacks = callbacks or BasePipelineCallbacks()
        self.config = config or StreamConfig()

        self._buffer: bytearray = bytearray()
        self._is_running = False
        self._vad_state = VadState.SILENCE
        self._loop_task: asyncio.Task[None] | None = None
        self._queue: asyncio.Queue[bytes | np.ndarray[Any, Any] | None] = (
            asyncio.Queue()
        )

    async def start(self) -> None:
        """パイプラインを開始します。"""
        if self._is_running:
            return
        self._is_running = True
        self._loop_task = asyncio.create_task(self._process_loop())
        logger.info("Audio stream pipeline started.")

    async def stop(self) -> None:
        """パイプラインを停止し、残りのバッファを処理します。"""
        if not self._is_running:
            return
        self._is_running = False
        await self._queue.put(None)  # Sentinel for stop
        if self._loop_task:
            await self._loop_task
            self._loop_task = None
        logger.info("Audio stream pipeline stopped.")

    async def feed_chunk(self, chunk: np.ndarray[Any, Any] | bytes) -> None:
        """非ブロッキングで音声チャンクを投入します。"""
        if not self._is_running:
            return
        await self._queue.put(chunk)

    async def reset(self) -> None:
        """内部バッファと状態をリセットします。"""
        self._buffer.clear()
        self._vad_state = VadState.SILENCE
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break
        self.callbacks.on_vad_state_change(self._vad_state)

    async def _process_loop(self) -> None:
        """バックグラウンドで音声キューを処理するループ。"""
        try:
            while True:
                chunk = await self._queue.get()
                if chunk is None:
                    self._queue.task_done()
                    break

                try:
                    self._process_chunk(chunk)
                except Exception as e:
                    self.callbacks.on_error(e)
                    logger.error("Error processing chunk: %s", e)
                finally:
                    self._queue.task_done()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.callbacks.on_error(e)

    def _process_chunk(self, chunk: np.ndarray[Any, Any] | bytes) -> None:
        """音声チャンクのVAD判定・推論呼び出しなどを行います。"""
        if isinstance(chunk, bytes):
            self._buffer.extend(chunk)
        else:
            self._buffer.extend(chunk.tobytes())

        # バッファサイズに基づく簡易的なVADエミュレーションと推論呼び出し
        bytes_per_sample = 2
        chunk_size_bytes = (
            self.config.sample_rate
            * bytes_per_sample
            * int(self.config.buffer_size_seconds)
        )

        if len(self._buffer) >= chunk_size_bytes:
            if self._vad_state == VadState.SILENCE:
                self._vad_state = VadState.SPEECH_START
                self.callbacks.on_vad_state_change(self._vad_state)
                self.callbacks.on_speech_start(0.0)
                self._vad_state = VadState.SPEECH
                self.callbacks.on_vad_state_change(self._vad_state)

            # バッファが十分に溜まったら推論をエミュレートしてクリア
            _ = (
                np.frombuffer(self._buffer[:chunk_size_bytes], dtype=np.int16).astype(
                    np.float32
                )
                / 32768.0
            )

            # NOTE: 実際のシステムでは self.transcriber のストリーミング用APIを呼び出す

            self._vad_state = VadState.SPEECH_END
            self.callbacks.on_vad_state_change(self._vad_state)
            self.callbacks.on_speech_end(self.config.buffer_size_seconds)

            seg = RecognizedSegment(
                start=0.0,
                end=self.config.buffer_size_seconds,
                text="Transcribed stream text",
                confidence=0.99,
            )
            self.callbacks.on_segment_recognized(seg)

            self._vad_state = VadState.SILENCE
            self.callbacks.on_vad_state_change(self._vad_state)

            del self._buffer[:chunk_size_bytes]
