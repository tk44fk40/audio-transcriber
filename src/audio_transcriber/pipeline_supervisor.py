"""オーケストレーター、エラーハンドリング、ライフサイクル管理を担うパイプライン監視モジュール。"""

from types import TracebackType
from typing import Any

from audio_transcriber.callbacks import BasePipelineCallbacks, PipelineCallbacks
from audio_transcriber.config import StreamConfig
from audio_transcriber.streaming.core import AudioStreamPipeline


class PipelineSupervisor:
    """統合パイプラインアーキテクチャのオーケストレーター/Facadeクラス。"""

    def __init__(
        self,
        pipeline: AudioStreamPipeline,
        callbacks: PipelineCallbacks | None = None,
        config: StreamConfig | None = None,
    ) -> None:
        """PipelineSupervisorを初期化します。"""
        self._pipeline = pipeline
        self._callbacks = (
            callbacks if callbacks is not None else BasePipelineCallbacks()
        )
        self._config = config if config is not None else StreamConfig()
        self._is_running = False

    @property
    def is_running(self) -> bool:
        """パイプラインが現在実行中かどうかを返します。"""
        return self._is_running

    async def start(self) -> None:
        """パイプラインを開始します。"""
        if self._is_running:
            return
        try:
            await self._pipeline.start()
            self._is_running = True
        except Exception as e:
            self._callbacks.on_error(e)
            await self.reset()
            self._is_running = False  # エラー発生時は状態を確実にFalseにする
            raise

    async def stop(self) -> None:
        """パイプラインを停止します。"""
        if not self._is_running:
            return
        await self._pipeline.stop()
        self._is_running = False

    async def reset(self) -> None:
        """パイプラインの状態をリセットします。"""
        await self._pipeline.reset()
        self._is_running = False  # リセット時も状態を確実にFalseにする

    async def feed_chunk(self, chunk: bytes, is_speech: bool = False) -> None:
        """音声データをパイプラインに供給します。"""
        if not self._is_running:
            return
        try:
            await self._pipeline.feed_chunk(chunk, is_speech)
        except Exception as e:
            self._callbacks.on_error(e)
            await self.reset()
            await (
                self._pipeline.stop()
            )  # 例外発生時もバックグラウンドループを確実に停止
            raise

    async def run_file(self, file_path: str) -> None:
        """ファイル入力用のファサード。"""
        await self.start()
        try:
            # FileAudioProducer の実装はまだなので、ここでは単に開始と停止を行うだけ
            pass
        finally:
            await self.stop()

    async def run_stream(self):
        """ストリーミング入力用のコンテキストマネージャ。"""
        self._is_running = False  # コンテキストに入る前に false にリセット
        return self

    async def __aenter__(self) -> "PipelineSupervisor":
        """非同期コンテキストマネージャの開始。"""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """非同期コンテキストマネージャの終了。"""
        if exc_val:
            self._callbacks.on_error(exc_val)
            await self.reset()  # エラー時はresetも呼ぶ
            await (
                self._pipeline.stop()
            )  # エラーが発生した場合でも _pipeline.stop() は確実に呼ぶ
            self._is_running = False  # 状態を確実にFalseにする
            # ここでTrueを返すと例外が抑制されるため、raise True を利用者がハンドリングできるように False または何も返さない
            return False
        await self.stop()
        return False

    def on_metrics(self, *args: Any, **kwargs: Any) -> None:
        """パイプラインからのメトリクス通知を受け取ります（パススルー）。"""
        # 現状、そのままコールバックに伝播するだけ
        # 将来的にはここでメトリクスを収集・集約するロジックが入る可能性もある
        pass
