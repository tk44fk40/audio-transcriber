"""リアルタイム音声ストリーミング処理。

このモジュールは、マイク入力やストリーミングソースからの音声データを
リアルタイムにバッファリングし、VAD（音声活動検出）を用いて発話区間を検出し、
Whisper等の音声認識プロバイダーを非同期に呼び出して
テキスト化するパイプラインを提供します。
"""

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
    """リアルタイム音声ストリーミングパイプライン。

    本クラスは、入力される音声のチャンク(bytesまたはnumpy配列)を、
    非同期セーフなキューを中継して
    バックグラウンドのイベントループタスクで逐次処理します。
    VADによる発話検出・区間切り出しを行い、認識エンジンによる推論を実行、
    サニタイズ（ハルシネーション対策）や
    用語置換などのテキスト後処理を適用して、
    確定したテキスト（および単語単位アライメント）を
    各種コールバックへディスパッチします。

    Attributes:
        transcriber (TranscriberProvider):
            音声認識（Whisper等）推論プロバイダーインスタンス。
        callbacks (PipelineCallbacks):
            各種イベント発生（VAD開始/終了、状態遷移、文字認識確定、
            エラー等）時に外部へ通知を行うコールバック群。
        app_config (AppConfig):
            アプリケーション全体のコンフィギュレーション
            （デノイズ、VAD、ポストプロセス設定など）。
        config (StreamConfig):
            ストリーミング処理専用の設定パラメータ
            （サンプリングレート、バッファ秒数など）。
        timecode_offset (float):
            ストリーム全体の開始時刻に対するオフセット値（秒）。
        vad_manager (StreamingVadManager):
            無音区間や発話継続秒数のルールに基づき、
            音声波形から発話区間を
            セグメンテーション（切り出し）するバッファ管理機構。
        context_manager (ContextManager):
            Whisperでの認識精度向上のため、
            過去の認識確定テキスト履歴（履歴プロンプト）を保持・管理する機構。
        sanitizer (SegmentSanitizer):
            推論結果セグメントのハルシネーション、
            異常な繰り返しテキストなどを
            フィルタリング・サニタイズする機構。
        processor (TextPostProcessor):
            専門用語・固有名詞などの辞書置換、小文字化、
            不要な句読点除去などを施すテキスト後処理加工エンジン。
        _is_running (bool):
            パイプラインが現在アクティブに動作しているかどうかを示す状態フラグ。
            start()/stop() 等のライフサイクルメソッドから
            アトミックに変更され、非同期安全です。
        _vad_state (VadState):
            現在のVAD内部状態（SILENCE, SPEECH_START, SPEECH, SPEECH_END）。
            単一のバックグラウンドループ（_process_loop）からのみ
            参照・更新されるため、競合が起きず非同期安全です。
        _loop_task (asyncio.Task[None] | None):
            バックグラウンドで音声キュー（_queue）からデータを非同期に引き出し、
            逐次処理を実行し続ける専用の非同期イベントループタスク。
        _queue (asyncio.Queue[tuple[np.ndarray[Any, Any] | bytes, bool] | None]):
            外部（マイク、ファイル、ストリーム）から
            feed_chunk された音声データおよび
            発話有無フラグ of タプル（または終了を通知する
            None センチネル）を非同期安全に一時保持するキュー。
            複数コルーチンからの多重投入・取り出しに対しても
            完全に非同期安全です。
        _stream_seconds (float):
            ストリーム開始時点からの累積経過時間（秒）。
            サンプル数にサンプリングレートを割った値をベースに、
            誤差なく厳密にインクリメント更新されます。
        _current_speech_start (float | None):
            現在検出・処理中である発話区間の、
            ストリーム開始を基準とした開始タイムスタンプ（秒）。
        _continuous_silence (float):
            現在続いている連続無音（非発話）区間の合計秒数（秒）。
            一定時間無音が継続した際、ContextManagerの
            履歴プロンプト寿命を
            タイムアウトさせる判定に使用されます。
    """

    def __init__(
        self,
        transcriber: TranscriberProvider,
        callbacks: PipelineCallbacks | None = None,
        config: StreamConfig | None = None,
        app_config: AppConfig | None = None,
        timecode_offset: float = 0.0,
    ) -> None:
        """AudioStreamPipeline を初期化します。

        Args:
            transcriber (TranscriberProvider): 音声認識プロバイダー。
            callbacks (PipelineCallbacks | None): イベント通知用コールバック。
            config (StreamConfig | None): ストリーミング用のしきい値やサイズ設定。
            app_config (AppConfig | None): システム全体の統合設定オブジェクト。
            timecode_offset (float): タイムコードの開始秒数オフセット（秒）。
        """
        self.transcriber = transcriber
        self.callbacks = callbacks or BasePipelineCallbacks()
        self.app_config = app_config or AppConfig()
        self.config = config or self.app_config.stream
        self.timecode_offset = timecode_offset

        # ミリ秒単位の設定値を秒単位にスケール変換
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

        self._is_running: bool = False
        """パイプラインが現在アクティブに動作しているかどうかの稼働フラグ。"""
        self._vad_state: VadState = VadState.SILENCE
        """現在のVAD内部状態（SILENCE, SPEECHなど）。"""
        self._loop_task: asyncio.Task[None] | None = None
        """キューからデータを引き出し処理を回し続けるバックグラウンドタスク。"""
        self._queue: asyncio.Queue[tuple[np.ndarray[Any, Any] | bytes, bool] | None] = (
            asyncio.Queue()
        )
        """外部から feed_chunk された音声データを
        非同期安全に一時保持するキュー。"""
        self._stream_seconds: float = 0.0
        """ストリーム開始時点からの累積経過時間（秒）。"""
        self._current_speech_start: float | None = None
        """現在検出・処理中である発話区間の、
        ストリーム開始を基準とした開始タイムスタンプ（秒）。"""
        self._continuous_silence: float = 0.0
        """現在続いている連続無音（非発話）区間の合計秒数（秒）。"""

    async def start(self) -> None:
        """パイプラインを非同期起動します。

        バックグラウンド処理用のループタスク（_process_loop）を走らせます。
        すでに起動している場合は、二重起動を防ぐために何もせず即座に復帰します。

        Returns:
            None
        """
        if self._is_running:
            return
        self._is_running = True
        self._loop_task = asyncio.create_task(self._process_loop())
        logger.info("Audio stream pipeline started.")

    async def stop(self) -> None:
        """パイプラインを安全に停止します。

        バックグラウンドループの終了を待ち、
        残存する全音声データを即時デコード・強制フラッシュします。
        すでに停止している場合は何も行いません。

        Returns:
            None

        Raises:
            asyncio.CancelledError: ループタスクの待機中にキャンセルが発生した場合。
        """
        if not self._is_running:
            return
        self._is_running = False
        # ループタスクに対して終了センチネル(None)を投入
        await self._queue.put(None)
        if self._loop_task:
            await self._loop_task
            self._loop_task = None
        # VADバッファ内に残されている最後の音声波形を引き出して強制的に推論・出力
        self._flush_internal()
        logger.info("Audio stream pipeline stopped.")

    async def feed_chunk(
        self, chunk: np.ndarray[Any, Any] | bytes, is_speech: bool = True
    ) -> None:
        """音声チャンクを中継キューに非同期投入します。

        パイプラインが現在稼働中でない（停止中である）場合は、
        データは安全に破棄（無視）されます。

        Args:
            chunk (np.ndarray[Any, Any] | bytes): 1次元の float32
                または int16 numpy配列、あるいは
                16bit モノラル PCM バイトデータ。
            is_speech (bool): 前段（例えば WebRTC VAD などの
                マイクキャプチャ層）で発話が検出されたかどうかの
                真偽フラグ。デフォルトは True。

        Returns:
            None
        """
        if not self._is_running:
            return
        await self._queue.put((chunk, is_speech))

    async def reset(self) -> None:
        """パイプラインの内部状態をリセットします。

        すべての内部バッファ、キューの残余、文脈プロンプト、累積時間、
        VAD状態を初期状態へリセットします。
        呼び出し元のコールバックに対しても
        VADState.SILENCE を通知します。

        Returns:
            None
        """
        self.vad_manager.flush()
        self.context_manager.clear()
        self._stream_seconds = 0.0
        self._current_speech_start = None
        self._continuous_silence = 0.0
        self._vad_state = VadState.SILENCE

        # 中継キューの残存データをすべて引き出して破棄
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break
        self.callbacks.on_vad_state_change(self._vad_state)

    async def _process_loop(self) -> None:
        """処理用バックグラウンド無限ループ。

        非同期セーフキューからアイテムを1件ずつ `await` で待ち受け、
        取り出して順次デコード処理へディスパッチします。
        None (センチネル) を検知した場合は、ループを正常終了させます。

        Returns:
            None
        """
        try:
            while True:
                item = await self._queue.get()
                if item is None:
                    # 終了シグナル
                    self._queue.task_done()
                    break

                chunk, is_speech = item
                try:
                    self._process_chunk(chunk, is_speech)
                except Exception as e:
                    # 1チャンクの処理失敗が全体の無限ループを落とさないよう
                    # 防衛的にキャッチしてコールバックへ委譲
                    self.callbacks.on_error(e)
                    logger.error("Error processing chunk: %s", e)
                finally:
                    self._queue.task_done()
        except asyncio.CancelledError:
            # 外部タスクキャンセルは正常な終了パターンとしてパス
            pass

    def _process_chunk(
        self, chunk: np.ndarray[Any, Any] | bytes, is_speech: bool
    ) -> None:
        """単一音声チャンクのVAD遷移判定や処理。

        Args:
            chunk (np.ndarray[Any, Any] | bytes): 入力音声チャンク。
                bytes の場合は自動で 16bit PCM と解釈し、
                float32 [-1.0, 1.0] にスケーリングします。
            is_speech (bool): 該当チャンクが発話状態にあるかどうか。

        Returns:
            None
        """
        # 音声データの型スケーリング (常に 16kHz float32 に標準化)
        if isinstance(chunk, bytes):
            audio_arr = (
                np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            )
        elif chunk.dtype == np.int16:
            audio_arr = chunk.astype(np.float32) / 32768.0
        else:
            audio_arr = chunk.astype(np.float32)

        # チャンクの再生時間長 (秒) をサンプリング周波数から高精度に計算
        chunk_duration = len(audio_arr) / self.config.sample_rate
        chunk_start_ts = self.timecode_offset + self._stream_seconds
        # 累積経過時間を加算
        self._stream_seconds += chunk_duration

        # VAD状態機械（State Machine）の更新制御フロー
        if is_speech:
            self._continuous_silence = (
                0.0  # 発話が再開されたため、無音継続カウントをリセット
            )
            if self._vad_state == VadState.SILENCE:
                # 無音状態から「発話開始（SPEECH_START）」へ遷移
                self._vad_state = VadState.SPEECH_START
                self.callbacks.on_vad_state_change(self._vad_state)

                # このチャンクが始まった時点のタイムコードを発話開始位置としてマーク
                self._current_speech_start = chunk_start_ts
                self.callbacks.on_speech_start(chunk_start_ts)

                # 直ちに「発話中（SPEECH）」へ遷移
                self._vad_state = VadState.SPEECH
                self.callbacks.on_vad_state_change(self._vad_state)
        else:
            # 無音が継続している場合、そのミリ秒/秒数を蓄積
            self._continuous_silence += chunk_duration
            # 一定の無音期間を超えていた場合、ContextManager の
            # 文脈履歴バッファを自動消去
            self.context_manager.check_timeout(self._continuous_silence)

        # 切り出し管理機構(StreamingVadManager)へ波形を投入。
        # 切り出すべき意味のある発話音声区間が確定した場合のみ、
        # speech_audio 配列が返ってきます。
        speech_audio = self.vad_manager.process_audio(audio_arr, is_speech=is_speech)
        if speech_audio is not None:
            speech_end_ts = self.timecode_offset + self._stream_seconds
            # 発話が一旦完了したため「発話終了（SPEECH_END）」へ遷移
            self._vad_state = VadState.SPEECH_END
            self.callbacks.on_vad_state_change(self._vad_state)
            self.callbacks.on_speech_end(speech_end_ts)

            # 開始位置タイムスタンプを安全に算出（万が一 None の場合は
            # 現在のチャンク開始を採用）
            start_ts = (
                self._current_speech_start
                if self._current_speech_start is not None
                else chunk_start_ts
            )
            # 認識エンジンの呼び出しと、結果のアライメント、コールバック通知を実行
            self._transcribe_and_dispatch(speech_audio, start_ts, speech_end_ts)

            # VADマネージャがIDLE状態に戻った場合、パイプライン側も
            # 「無音（SILENCE）」へ戻して次の発話を待ちます。
            if self.vad_manager.state == State.IDLE:
                self._vad_state = VadState.SILENCE
                self.callbacks.on_vad_state_change(self._vad_state)
                self._current_speech_start = None

    def _flush_internal(self) -> None:
        """バッファ内の残存音声を強制推論・出力します。

        Returns:
            None
        """
        remaining = self.vad_manager.flush()
        if remaining is not None and len(remaining) > 0:
            # 発話中だった場合は、強制的に発話終了(SPEECH_END)の
            # ステート更新とイベント送出を行います
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
            # 残余データで音声認識を実行
            self._transcribe_and_dispatch(
                remaining, start_ts, self.timecode_offset + self._stream_seconds
            )

            # 初期状態へ戻す
            self._vad_state = VadState.SILENCE
            self.callbacks.on_vad_state_change(self._vad_state)
            self._current_speech_start = None

    def _transcribe_and_dispatch(
        self, speech_audio: np.ndarray[Any, Any], start_offset: float, end_offset: float
    ) -> None:
        """発話ブロックのモデル推論と結果送信を行います。

        Args:
            speech_audio (np.ndarray[Any, Any]): 切り出された音声波形の
                numpy 配列（float32）。
            start_offset (float): ストリーム開始（秒）に対する、
                この発話開始点の相対タイムコード（秒）。
            end_offset (float): ストリーム開始（秒）に対する、
                この発話終了点の相対タイムコード（秒）。

        Returns:
            None
        """
        # Whisper などの精度向上のための先行コンテキスト（プロンプト）を取得
        prompt = self.context_manager.get_prompt(separator=" ")
        initial_prompt = prompt if prompt else None

        # 実際の推論プロバイダー（TranscriberProvider）を同期呼び出し
        # （ストリーム処理内の各発話は直列実行されます）
        segments = self.transcriber.transcribe_stream(
            speech_audio, initial_prompt=initial_prompt
        )

        for seg in segments:
            # ハルシネーション対策
            # （高すぎる文字密度や、特定パターンの繰り返しを検出し除外・整形）
            clean_seg = self.sanitizer.sanitize_segment(seg)
            if clean_seg is None:
                continue

            # 固有名詞や業界専門用語のカスタム辞書置換、
            # 不要な記号トリムなどのテキスト後処理を適用
            processed_text = self.processor.apply_to_text(clean_seg.text)
            if not processed_text:
                continue

            # 次回以降の推論コンテキストに利用するため、この認識確定テキストを追加
            self.context_manager.add_text(processed_text)

            # 発話全体の中でのこのセグメントの絶対タイムコードを計算
            seg_start = start_offset + clean_seg.start
            seg_end = start_offset + clean_seg.end
            # 終了が開始以下になってしまった場合のセーフガード（0.1秒以上の幅を確保）
            if seg_end <= seg_start:
                seg_end = seg_start + 0.1

            # 認識結果オブジェクトを構築し、外部の確定通知コールバックをトリガー
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
