"""音声プロデューサーとキューの定義。

音声をファイルやストリーミングソースといった様々な入力元から抽象化し、
デノイズなどの前処理を適用した上で、非同期セーフなキュー（AudioChunkQueue）へ
データを供給するプロデューサー層です。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from audio_transcriber.audio_queues import (
    AudioChunkQueue,
)
from audio_transcriber.config import AppConfig
from audio_transcriber.denoise import create_denoiser

logger = logging.getLogger(__name__)


# Constants for audio processing and async timeout control
FFMPEG_TERMINATE_TIMEOUT_SEC: float = 0.5
"""FFmpegプロセス終了時の最大待機秒数。

ハングした場合はゾンビプロセス化を防ぐためSIGKILLで強制キルします。
"""

BYTES_PER_SAMPLE_16BIT: int = 2
"""1サンプルあたりのバイト幅。

16-bitリニアPCMの1サンプルあたりのバイト幅（バイト）。2バイト固定です。
"""

MS_PER_SECOND: float = 1000.0
"""1秒あたりのミリ秒数。

単位変換用の固定スケールです。
"""

FFMPEG_MONO_CHANNELS: str = "1"
"""FFmpeg要求用のモノラルチャンネル数。

FFmpegにデコードを要求するモノラル音声トラックのチャンネル数です。
"""

SENTINEL_PUT_TIMEOUT_SEC: float = 1.0
"""終了センチネルの最大待機秒数。

キュー満杯によるプロデューサーのハングを防ぎます。
"""


class StreamAudioProducer:
    """ストリーミング音声用プロデューサー。

    マイク入力やストリーミング接続から音声（チャンク）を
    そのまま AudioChunkQueue へパススルー投入（仲介）します。

    Attributes:
        _queue (AudioChunkQueue): 投入先となる非同期セーフな共有キュー。
    """

    def __init__(self, queue: AudioChunkQueue) -> None:
        """StreamAudioProducer を初期化します。

        Args:
            queue (AudioChunkQueue): 供給対象 of AudioChunkQueue。
        """
        self._queue = queue
        """投入先となる非同期セーフな共有キュー。"""

    async def feed_chunk(self, chunk: bytes, is_speech: bool = False) -> None:
        """音声チャンクをキューに投入します。

        Args:
            chunk (bytes): 音声データの生バイト列。
            is_speech (bool): 発話区間フラグ。
        """
        await self._queue.put((chunk, is_speech))

    async def stop(self) -> None:
        """ストリーム終了センチネルを投入します。

        Returns:
            None
        """
        await self._queue.put(None)


class FileAudioProducer:
    """ファイル音声用プロデューサー。

    指定された動画または音声ファイルを読み込み、ノイズ除去前処理を実行し、
    FFmpeg非同期デコードを用いて、正確に100ms単位などの
    一定時間間隔に分割しながら AudioChunkQueue に非同期投入します。

    Attributes:
        _file_path (Path):
            入力ソースファイルの絶対パス。
        _queue (AudioChunkQueue):
            前処理された音声データを流し込む共有キュー。
        _app_config (AppConfig):
            アプリケーション全体の設定。
        _sample_rate (int):
            デコードを要求するサンプリング周波数（Hz）。
        _chunk_size_ms (int):
            キューに投入する1チャンクあたりの時間長（ミリ秒単位）。
        _temp_files (list[Path]):
            一時ファイルのパス一覧。終了時に消去されます。
        _ffmpeg_process (asyncio.subprocess.Process | None):
            非同期で動作するFFmpegのサブプロセス参照。
        _run_task (asyncio.Task[None] | None):
            ファイル処理ループを実行するバックグラウンドタスク。
        _cleanup_lock (asyncio.Lock):
            多重クリーンアップを防ぐための非同期排他ロック。
    """

    def __init__(
        self,
        file_path: str | Path,
        queue: AudioChunkQueue,
        app_config: AppConfig,
        sample_rate: int | None = None,
        chunk_size_ms: int | None = None,
    ) -> None:
        """FileAudioProducer を初期化します。

        Args:
            file_path (str | Path): 入力ソースファイルのパス。
            queue (AudioChunkQueue): 供給対象 of AudioChunkQueue。
            app_config (AppConfig): 全体設定。
            sample_rate (int | None): サンプリング周波数（Hz）。
            chunk_size_ms (int | None): チャンク時間長(ms)。
        """
        self._file_path = Path(file_path).resolve()
        """入力ソースファイルの絶対パス。"""
        self._queue = queue
        """共有される非同期セーフキュー。"""
        self._app_config = app_config
        """アプリケーション全体の統合設定。"""
        self._sample_rate = sample_rate or app_config.stream.sample_rate
        """デコードを要求するサンプリング周波数（Hz）。"""
        self._chunk_size_ms = chunk_size_ms or app_config.stream.chunk_size_ms
        """キューに投入する1チャンクあたりの時間長（ミリ秒単位）。"""
        self._temp_files: list[Path] = []
        """一時ファイルのパス一覧。"""
        self._ffmpeg_process: asyncio.subprocess.Process | None = None
        """非同期で動作するFFmpegのサブプロセス参照。"""
        self._run_task: asyncio.Task[None] | None = None
        """ファイル処理ループを実行するバックグラウンドタスク。"""
        self._cleanup_lock = asyncio.Lock()
        """多重クリーンアップを防ぐための非同期排他ロック。"""

    async def start(self) -> None:
        """ファイルのデコードとキュー投入を開始します。"""
        if self._run_task and not self._run_task.done():
            raise RuntimeError("FileAudioProducer is already running.")
        self._run_task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """処理を途中で停止し、リソースを解放します。"""
        if self._run_task:
            self._run_task.cancel()
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass
            self._run_task = None

        await self._cleanup()

    async def join(self) -> None:
        """ファイルデコード処理の完了まで待機します。"""
        if self._run_task:
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass

    @property
    def denoised_audio_path(self) -> Path | None:
        """ノイズ除去済みの一時ファイルのパスを返します。

        デノイズが無効、または未生成の場合は None を返します。
        """
        if not self._temp_files:
            return None
        return self._temp_files[0]

    async def _cleanup(self) -> None:
        """FFmpegプロセスと一時ファイルのクリーンアップ。

        動画リマックスで使用するため、ノイズ除去済み一時ファイルは
        ここでは自動削除せず、プロセスのクリーンアップのみを実施します。
        """
        async with self._cleanup_lock:
            if self._ffmpeg_process:
                try:
                    self._ffmpeg_process.terminate()
                    # 正常終了を待機。ハング時は強制キル。
                    try:
                        await asyncio.wait_for(
                            self._ffmpeg_process.wait(),
                            timeout=FFMPEG_TERMINATE_TIMEOUT_SEC,
                        )
                    except TimeoutError:
                        logger.warning(
                            "FFmpeg process terminate timeout. Sending SIGKILL."
                        )
                        self._ffmpeg_process.kill()
                        await self._ffmpeg_process.wait()
                except Exception as e:
                    logger.warning("Error terminating ffmpeg process: %s", e)
                finally:
                    self._ffmpeg_process = None

    async def _run(self) -> None:
        """ファイルのデコードループ処理。"""
        try:
            target_path = self._file_path

            # RNNoise 等によるノイズ除去前処理
            if self._app_config.denoise.enabled:
                unique_id = uuid.uuid4().hex
                denoised_path = (
                    self._app_config.paths.output_dir
                    / f"{self._file_path.stem}_clean_{unique_id}.wav"
                )
                self._app_config.paths.output_dir.mkdir(parents=True, exist_ok=True)
                self._temp_files.append(denoised_path)

                # デノイザーの同期的な呼び出しを実行
                denoiser = create_denoiser(self._app_config.denoise)
                # ブロッキング処理を避けるため、別スレッドで実行
                await asyncio.to_thread(
                    denoiser.denoise, self._file_path, denoised_path
                )
                target_path = denoised_path

            # 100ms（あるいは指定ms）あたりのサンプル数・バイト数の計算
            sample_rate = self._sample_rate
            chunk_size_ms = self._chunk_size_ms
            bytes_per_sample = BYTES_PER_SAMPLE_16BIT
            samples_per_chunk = int(sample_rate * (chunk_size_ms / MS_PER_SECOND))
            chunk_bytes_size = samples_per_chunk * bytes_per_sample

            # FFmpeg 非同期サブプロセスの構築
            cmd = [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(target_path),
                "-f",
                "s16le",
                "-acodec",
                "pcm_s16le",
                "-ar",
                str(sample_rate),
                "-ac",
                FFMPEG_MONO_CHANNELS,
                "-",
            ]

            # 起動処理中の CancelledError による
            # FFmpeg ゾンビ化を完全に防ぐため、
            # サブプロセスの生成とメンバ変数への格納処理を
            # asyncio.shield で非同期保護してアトミックに行います。
            async def launch_ffmpeg() -> asyncio.subprocess.Process:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                self._ffmpeg_process = proc
                return proc

            try:
                proc = await asyncio.shield(launch_ffmpeg())
            except BaseException:
                # 起動処理自体に何かしら致命的な失敗があった場合のセーフティキル
                if self._ffmpeg_process:
                    try:
                        self._ffmpeg_process.kill()
                    except Exception:
                        pass
                    self._ffmpeg_process = None
                raise

            stdout = proc.stdout
            stderr = proc.stderr
            if stdout is None or stderr is None:
                raise RuntimeError("Failed to open stdout/stderr of ffmpeg subprocess.")

            # stderrパイプがログで満杯になり、OSレベルで
            # デッドロック（ハング）するのを防ぐため、
            # 非同期でバックグラウンド読み込みタスクを走らせて常時ドレインします。
            stderr_task = asyncio.create_task(stderr.read())

            while True:
                try:
                    # 設定された 1 チャンクあたりの正確な
                    # バイトサイズを厳密に同期読み込み
                    chunk = await stdout.readexactly(chunk_bytes_size)
                    await self._queue.put((chunk, False))
                except asyncio.IncompleteReadError as e:
                    # ファイル末尾に達し、規定バイト数（100ms分）に満たない
                    # 残余バッファがある場合の最終処理
                    if e.partial:
                        await self._queue.put((e.partial, False))
                    break

            # プロセスの終了ステータス検証（異常終了時は stderr ログを詳細に投げる）
            if self._ffmpeg_process is None:
                raise RuntimeError("FFmpeg process is not running.")
            exit_code = await self._ffmpeg_process.wait()
            err_log_bytes = await stderr_task
            if exit_code != 0:
                err_log = err_log_bytes.decode(errors="replace").strip()
                raise RuntimeError(
                    f"FFmpeg process exited with non-zero code {exit_code}. "
                    f"stderr: {err_log}"
                )

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Error in FileAudioProducer processing: %s", e)
            raise
        finally:
            # 正常終了、異常終了、キャンセルに関わらず、
            # 終了を示すセンチネルをキューに流します。
            # キャンセルによる呼び出し中でも確実に完遂させるため、
            # shieldで保護します。
            async def safe_final_cleanup() -> None:
                try:
                    # キューがフルの際にプロデューサーがセンチネル投入で
                    # 永続ハングアップするのを防ぐため、タイムアウト付き。
                    await asyncio.wait_for(
                        self._queue.put(None), timeout=SENTINEL_PUT_TIMEOUT_SEC
                    )
                except TimeoutError:
                    logger.warning(
                        "Timeout putting sentinel into queue. "
                        "Consumer might have stopped."
                    )
                except Exception as ex:
                    logger.warning("Failed to put sentinel into queue: %s", ex)
                await self._cleanup()

            await asyncio.shield(safe_final_cleanup())
