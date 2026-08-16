"""リアルタイム音声ストリーミング処理モジュール。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import numpy as np

from audio_transcriber.callbacks import BasePipelineCallbacks, PipelineCallbacks
from audio_transcriber.config import AppConfig, StreamConfig
from audio_transcriber.models import RecognizedSegment, VadState
from audio_transcriber.postprocess import TextPostProcessor
from audio_transcriber.sanitizer import SegmentSanitizer
from audio_transcriber.streaming.managers import (
    ContextManager,
    State,
    StreamingVadManager,
)
from audio_transcriber.stt import TranscriberProvider

logger = logging.getLogger(__name__)


class AudioStreamPipeline:
    """リアルタイム音声ストリーミングパイプライン。"""

    def __init__(
        self,
        transcriber: TranscriberProvider,
        callbacks: PipelineCallbacks | None = None,
        config: StreamConfig | None = None,
        app_config: AppConfig | None = None,
        timecode_offset: float = 0.0,
    ) -> None:
        """初期化します。

        Args:
            transcriber: 音声認識プロバイダーインスタンス。
            callbacks: イベント通知を受け取るコールバックインスタンス。
            config: ストリーミング設定オブジェクト。
            app_config: 全体アプリケーション設定オブジェクト。
            timecode_offset: タイムコード開始オフセット秒数。
        """
        self.transcriber = transcriber
        self.callbacks = callbacks or BasePipelineCallbacks()
        self.app_config = app_config or AppConfig()
        self.config = config or self.app_config.stream
        self.timecode_offset = timecode_offset

        min_silence_sec = (
            float(self.app_config.transcribe.vad.min_silence_duration_ms) / 1000.0
        )
        self.vad_manager = StreamingVadManager(
            sample_rate=self.config.sample_rate,
            min_silence_duration=min_silence_sec,
            chunk_min_seconds=self.config.chunk_min_seconds,
            chunk_max_seconds=self.config.chunk_max_seconds,
        )
        self.context_manager = ContextManager(
            max_length=self.config.context.context_max_length,
            timeout_seconds=self.config.context.context_timeout_seconds,
        )
        self.sanitizer = SegmentSanitizer(
            no_speech_threshold=self.app_config.post_process.no_speech_threshold,
            max_chars_per_second=self.app_config.post_process.max_chars_per_second,
        )
        self.processor = TextPostProcessor(
            dictionary_path=self.app_config.paths.custom_dict_path,
            lower=self.app_config.post_process.lower,
            remove_punct=self.app_config.post_process.remove_punct,
        )

        self._is_running = False
        self._vad_state = VadState.SILENCE
        self._loop_task: asyncio.Task[None] | None = None
        self._queue: asyncio.Queue[tuple[np.ndarray[Any, Any] | bytes, bool] | None] = (
            asyncio.Queue()
        )
        self._stream_seconds = 0.0
        self._current_speech_start: float | None = None
        self._continuous_silence = 0.0

    async def start(self) -> None:
        """パイプラインを開始し、バックグラウンド処理ループを起動します。"""
        if self._is_running:
            return
        self._is_running = True
        self._loop_task = asyncio.create_task(self._process_loop())
        logger.info("Audio stream pipeline started.")

    async def stop(self) -> None:
        """パイプラインを停止し、残りのバッファを強制フラッシュして処理します。"""
        if not self._is_running:
            return
        self._is_running = False
        await self._queue.put(None)
        if self._loop_task:
            await self._loop_task
            self._loop_task = None
        self._flush_internal()
        logger.info("Audio stream pipeline stopped.")

    async def feed_chunk(
        self, chunk: np.ndarray[Any, Any] | bytes, is_speech: bool = True
    ) -> None:
        """非ブロッキングで音声チャンクを内部キューに投入します。

        Args:
            chunk: 音声データ（numpy配列または16bit PCMバイト列）。
            is_speech: 該当チャンクが発話区間かどうかのフラグ。
        """
        if not self._is_running:
            return
        await self._queue.put((chunk, is_speech))

    async def reset(self) -> None:
        """内部バッファと状態（VAD状態、文脈、待機キュー）をリセットします。"""
        self.vad_manager.flush()
        self.context_manager.clear()
        self._stream_seconds = 0.0
        self._current_speech_start = None
        self._continuous_silence = 0.0
        self._vad_state = VadState.SILENCE

        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break
        self.callbacks.on_vad_state_change(self._vad_state)

    async def _process_loop(self) -> None:
        """バックグラウンドで音声キューからチャンクを取り出し逐次処理します。"""
        try:
            while True:
                item = await self._queue.get()
                if item is None:
                    self._queue.task_done()
                    break

                chunk, is_speech = item
                try:
                    self._process_chunk(chunk, is_speech)
                except Exception as e:
                    self.callbacks.on_error(e)
                    logger.error("Error processing chunk: %s", e)
                finally:
                    self._queue.task_done()
        except asyncio.CancelledError:
            pass

    def _process_chunk(
        self, chunk: np.ndarray[Any, Any] | bytes, is_speech: bool
    ) -> None:
        """音声チャンクのVAD判定、発話区間の蓄積、および推論呼び出しを行います。

        Args:
            chunk: 音声データ（numpy配列またはPCMバイト列）。
            is_speech: 発話フラグ。
        """
        if isinstance(chunk, bytes):
            audio_arr = (
                np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            )
        elif chunk.dtype == np.int16:
            audio_arr = chunk.astype(np.float32) / 32768.0
        else:
            audio_arr = chunk.astype(np.float32)

        chunk_duration = len(audio_arr) / self.config.sample_rate
        chunk_start_ts = self.timecode_offset + self._stream_seconds
        self._stream_seconds += chunk_duration

        if is_speech:
            self._continuous_silence = 0.0
            if self._vad_state == VadState.SILENCE:
                self._vad_state = VadState.SPEECH_START
                self.callbacks.on_vad_state_change(self._vad_state)
                self._current_speech_start = chunk_start_ts
                self.callbacks.on_speech_start(chunk_start_ts)
                self._vad_state = VadState.SPEECH
                self.callbacks.on_vad_state_change(self._vad_state)
        else:
            self._continuous_silence += chunk_duration
            self.context_manager.check_timeout(self._continuous_silence)

        speech_audio = self.vad_manager.process_audio(audio_arr, is_speech=is_speech)
        if speech_audio is not None:
            speech_end_ts = self.timecode_offset + self._stream_seconds
            self._vad_state = VadState.SPEECH_END
            self.callbacks.on_vad_state_change(self._vad_state)
            self.callbacks.on_speech_end(speech_end_ts)

            start_ts = (
                self._current_speech_start
                if self._current_speech_start is not None
                else chunk_start_ts
            )
            self._transcribe_and_dispatch(speech_audio, start_ts, speech_end_ts)

            if self.vad_manager.state == State.IDLE:
                self._vad_state = VadState.SILENCE
                self.callbacks.on_vad_state_change(self._vad_state)
                self._current_speech_start = None

    def _flush_internal(self) -> None:
        """内部バッファの残りを強制フラッシュして推論および後処理を実行します。"""
        remaining = self.vad_manager.flush()
        if remaining is not None and len(remaining) > 0:
            if self._vad_state in (VadState.SPEECH, VadState.SPEECH_START):
                self._vad_state = VadState.SPEECH_END
                self.callbacks.on_vad_state_change(self._vad_state)
                self.callbacks.on_speech_end(
                    self.timecode_offset + self._stream_seconds
                )

            start_ts = (
                self._current_speech_start
                if self._current_speech_start is not None
                else self.timecode_offset
            )
            self._transcribe_and_dispatch(
                remaining, start_ts, self.timecode_offset + self._stream_seconds
            )

            self._vad_state = VadState.SILENCE
            self.callbacks.on_vad_state_change(self._vad_state)
            self._current_speech_start = None

    def _transcribe_and_dispatch(
        self, speech_audio: np.ndarray[Any, Any], start_offset: float, end_offset: float
    ) -> None:
        """音声推論、サニタイズ、テキスト置換、文脈更新、コールバック通知を実行します。

        Args:
            speech_audio: 発話音声の波形 numpy 配列。
            start_offset: 発話開始オフセット時刻（秒）。
            end_offset: 発話終了オフセット時刻（秒）。
        """
        prompt = self.context_manager.get_prompt(separator=" ")
        initial_prompt = prompt if prompt else None

        segments = self.transcriber.transcribe_stream(
            speech_audio, initial_prompt=initial_prompt
        )

        for seg in segments:
            clean_seg = self.sanitizer.sanitize_segment(seg)
            if clean_seg is None:
                continue

            processed_text = self.processor.apply_to_text(clean_seg.text)
            if not processed_text:
                continue

            self.context_manager.add_text(processed_text)
            seg_start = start_offset + clean_seg.start
            seg_end = start_offset + clean_seg.end
            if seg_end <= seg_start:
                seg_end = seg_start + 0.1

            rec = RecognizedSegment(
                start=seg_start,
                end=seg_end,
                text=processed_text,
                confidence=float(seg.get("confidence", 0.99))
                if "confidence" in seg
                else 0.99,
                words=seg.get("words") if isinstance(seg.get("words"), list) else None,
            )
            self.callbacks.on_segment_recognized(rec)
