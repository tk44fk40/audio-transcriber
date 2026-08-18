"""パイプラインを統括する監視モジュール。

音声入力元（ファイル、ストリームなど）の違いを吸収し、バックエンドの
推論パイプライン（AudioStreamPipeline）へのデータ供給を統括する最上位マネージャです。
"""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Any

from audio_transcriber.audio_producers import AudioChunkQueue, FileAudioProducer
from audio_transcriber.callbacks import BasePipelineCallbacks, PipelineCallbacks
from audio_transcriber.config import AppConfig, StreamConfig
from audio_transcriber.streaming.core import AudioStreamPipeline


class PipelineSupervisor:
    """パイプラインのオーケストレーター。

    入力元（ファイル/ストリーム）を統一されたインターフェースで統括し、
    すべての開始・停止などのライフサイクル、非同期エラーハンドリング、
    および二重起動（競合状態）を安全に制御します。

    Attributes:
        _pipeline (AudioStreamPipeline):
            実際に音声活動検出(VAD)や音声認識(Whisper等)を
            直列に回すコンシューマーとしてのパイプラインインスタンス。
        _callbacks (PipelineCallbacks):
            認識結果の確定セグメント、エラー、VADイベントなどを
            外部（呼び出し元）に通知するコールバックインターフェース。
        _config (StreamConfig):
            サンプリングレート、1チャンク時間長(ms)など、
            ストリーミング・再生を制御する各種パラメータ。
        _app_config (AppConfig):
            RNNoiseの有効化設定や出力先パスなど、
            アプリケーション全体の統合コンフィグ。
        _is_running (bool):
            パイプラインが現在アクティブに動作（音声受付可能）
            しているかどうかを示す状態フラグ。
        _lock (asyncio.Lock):
            多重起動、競合状態、および制御操作 of デッドロックを
            防止するためのライフサイクル非同期排他ロック（非同期安全）。
    """

    def __init__(
        self,
        pipeline: AudioStreamPipeline,
        callbacks: PipelineCallbacks | None = None,
        config: StreamConfig | None = None,
        app_config: AppConfig | None = None,
    ) -> None:
        """PipelineSupervisorを初期化します。

        Args:
            pipeline (AudioStreamPipeline): 推論やVADを直列に回すパイプライン。
            callbacks (PipelineCallbacks | None): イベント通知用コールバック。
            config (StreamConfig | None): ストリーミングやデコード再生の設定。
            app_config (AppConfig | None): システム全体の統合コンフィグ。
        """
        self._pipeline = pipeline
        """推論やVADを直列に回すパイプラインインスタンス。"""
        self._callbacks = (
            callbacks if callbacks is not None else BasePipelineCallbacks()
        )
        """外部（呼び出し元）に各種イベントを通知する
        コールバックインターフェース。"""
        self._config = config if config is not None else StreamConfig()
        """サンプリングレートなどの再生・デコード制御コンフィグ。"""
        self._app_config = app_config if app_config is not None else AppConfig()
        """RNNoiseの有効化や一時ディレクトリなどを制御する全体コンフィグ。"""
        self._is_running = False
        """パイプラインが現在稼働中であるかどうかを示す状態フラグ。"""
        self._lock = asyncio.Lock()
        """多重起動や競合を安全に防止するためのライフサイクル非同期排他ロック。"""

    @property
    def is_running(self) -> bool:
        """パイプラインが現在実行中かどうかを返します。

        Returns:
            bool: 実行中であれば True、停止中または異常終了時は False。
        """
        return self._is_running

    async def start(self) -> None:
        """パイプラインを非同期起動します。

        内部ロックを確保して状態遷移を保護します。すでに起動している場合は何もしません。

        Returns:
            None

        Raises:
            Exception: 下位の pipeline.start() 起動に失敗した場合。
        """
        async with self._lock:
            await self._start_unlocked()

    async def _start_unlocked(self) -> None:
        """ロック保持下での非同期起動ヘルパー。

        二重起動を防ぎつつ、下位パイプラインの初期化を行います。
        初期化中に例外が発生した場合は、確実にリセット処理を実行し、
        コールバックに例外を通知した上で再送出します。
        """
        if self._is_running:
            return
        try:
            await self._pipeline.start()
            self._is_running = True
        except Exception as e:
            self._callbacks.on_error(e)
            await self._reset_unlocked()
            self._is_running = False
            raise

    async def stop(self) -> None:
        """パイプラインを非同期に停止します。

        内部ロックを確保して状態遷移を保護します。すでに停止している場合は何もしません。

        Returns:
            None
        """
        async with self._lock:
            await self._stop_unlocked()

    async def _stop_unlocked(self) -> None:
        """ロック保持下での非同期停止ヘルパー。

        下位のパイプラインの終了処理を呼び出し、実行フラグを安全に False に更新します。
        """
        if not self._is_running:
            return
        await self._pipeline.stop()
        self._is_running = False

    async def reset(self) -> None:
        """パイプラインの状態を強制リセットします。

        内部ロックを確保して安全に行われます。

        Returns:
            None
        """
        async with self._lock:
            await self._reset_unlocked()

    async def _reset_unlocked(self) -> None:
        """ロック保持下での強制リセットヘルパー。

        下位パイプラインの状態リセットを呼び出し、実行状態を False にします。
        """
        await self._pipeline.reset()
        self._is_running = False

    async def feed_chunk(self, chunk: bytes, is_speech: bool = False) -> None:
        """リアルタイム音声データをパイプラインに供給します。

        内部的に排他ロックを確保し、停止中の場合はデータを破棄します。
        供給処理中に例外が発生した場合、エラーコールバックを呼び出し、パイプラインを
        安全に自動停止・リセットした上で例外を再送出します。

        Args:
            chunk (bytes): 供給する音声生バイトデータ（1ch Mono、
                通常 16kHz 16bit PCM）。
            is_speech (bool): 外部または前段のVADで音声検出されているか
                どうかのフラグ。デフォルトは False。

        Returns:
            None

        Raises:
            Exception: パイプライン処理中または供給中に予期せぬエラーが発生した場合。
        """
        async with self._lock:
            if not self._is_running:
                return
            try:
                await self._pipeline.feed_chunk(chunk, is_speech)
            except Exception as e:
                self._callbacks.on_error(e)
                await self._reset_unlocked()
                await self._pipeline.stop()
                self._is_running = False
                raise

    async def run_file(self, file_path: str) -> None:
        """指定ファイルを読み込み文字起こしをバッチ実行します。

        FileAudioProducerおよびAudioChunkQueueをバックグラウンドで起動し、
        ファイル内の全データをデコードして、本パイプラインへ順次非同期に投入します。

        Args:
            file_path (str): 読み込み対象となるソースメディアファイルの
                パス（相対または絶対）。

        Returns:
            None

        Raises:
            Exception: デコードやパイプライン処理中にエラーが発生した場合。
        """
        # 開始前に非同期起動
        async with self._lock:
            await self._start_unlocked()

        # デコード中の中継用バッファとして、Backpressure制御が
        # 効くキューを最大100チャンクで初期化
        queue = AudioChunkQueue(maxsize=100)
        producer = FileAudioProducer(
            file_path=file_path,
            queue=queue,
            app_config=self._app_config,
            sample_rate=self._config.sample_rate,
            chunk_size_ms=self._config.chunk_size_ms,
        )

        try:
            # プロデューサーのバックグラウンドタスク（FFmpegデコード等）を開始
            await producer.start()

            while True:
                # キューからデコード済みの音声チャンクを順次引き出す
                # （Noneが来るまでループ）
                item = await queue.get()
                if item is None:
                    # 終了センチネルを検知
                    queue.task_done()
                    break

                chunk, is_speech = item
                # 非同期操作の競合を防ぐため、ロックを確保してパイプラインへ供給
                async with self._lock:
                    if not self._is_running:
                        queue.task_done()
                        break
                    await self._pipeline.feed_chunk(chunk, is_speech)
                queue.task_done()

            # プロデューサーの残りのクリーンアップや完了処理を非同期待機
            await producer.join()

        except Exception as e:
            # エラー発生時は即座にコールバックを叩き、
            # パイプラインを安全な状態へリセット
            self._callbacks.on_error(e)
            async with self._lock:
                await self._reset_unlocked()
                await self._pipeline.stop()
                self._is_running = False
            raise
        finally:
            # プロセスの終了や一時ファイルの削除を、いかなる場合も確実に実行
            await producer.stop()
            async with self._lock:
                await self._stop_unlocked()

    async def run_stream(self) -> PipelineSupervisor:
        """ストリーミング入力の開始前に実行状態をリセットします。

        主にコンテキストマネージャ等と組み合わせて使用されるための
        非同期インターフェースです。

        Returns:
            PipelineSupervisor: 自身のインスタンス。
        """
        self._is_running = False  # コンテキストに入る前に確実に false にリセット
        return self

    async def __aenter__(self) -> PipelineSupervisor:
        """非同期コンテキストマネージャの開始。

        ブロックに入ると同時に、自動的にパイプラインを起動（start）させます。

        Returns:
            PipelineSupervisor: 起動後の自身のインスタンス。
        """
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """非同期コンテキストマネージャの終了。

        例外が発生していた場合は、エラーをコールバックへ通知した上で、
        安全にリセット処理（reset_unlocked）と
        停止（_pipeline.stop()）を実行して、
        状態を確実に False に保ち、例外を外に伝播させます。
        正常終了時は、通常の停止（stop）を実行します。

        Args:
            exc_type (type[BaseException] | None): 発生した例外の型。
            exc_val (BaseException | None): 発生した例外のインスタンス。
            exc_tb (TracebackType | None): 例外のトレースバック情報。

        Returns:
            bool: 例外を握りつぶす場合は True。
                通常は例外を伝播させるため False を返します。
        """
        if exc_val:
            self._callbacks.on_error(exc_val)
            async with self._lock:
                await self._reset_unlocked()  # エラー時は強制リセット
                await self._pipeline.stop()  # バックエンドも確実に停止
                self._is_running = False  # 状態フラグの完全なクリア
            return False  # 例外を外に伝播
        await self.stop()
        return False

    def on_metrics(self, *args: Any, **kwargs: Any) -> None:
        """リアルタイムメトリクス通知を受け取ります。

        Args:
            *args (Any): 可変長引数。
            **kwargs (Any): キーワード引数。
        """
        pass
