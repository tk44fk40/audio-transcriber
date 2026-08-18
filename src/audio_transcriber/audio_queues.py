"""非同期音声チャンクキューモジュール。

音声データを保持するための非同期セーフなキュー
およびキューサイズ計算関数を提供します。
"""

from __future__ import annotations

import asyncio

DEFAULT_MAX_QUEUE_SIZE: int = 100
"""デフォルトの音声キュー最大容量。

メモリ消費を抑えつつ十分なバッファリングを
提供する防衛的な上限値です。
"""


class AudioChunkQueue:
    """非同期セーフな音声チャンクキュー。

    Backpressure制御に対応し、満杯時は
    一時的にブロックします。
    同一コルーチン間で安全に共有されます。

    Attributes:
        _queue (asyncio.Queue[tuple[bytes, bool] | None]):
            (音声バイトデータ, 発話フラグ)のタプル。
    """

    def __init__(self, maxsize: int = DEFAULT_MAX_QUEUE_SIZE) -> None:
        """AudioChunkQueue を初期化します。

        Args:
            maxsize (int): 最大許容サイズ（個数）。
        """
        self._queue: asyncio.Queue[tuple[bytes, bool] | None] = asyncio.Queue(
            maxsize=maxsize
        )
        """共有される非同期セーフキュー。"""

    async def put(self, item: tuple[bytes, bool] | None) -> None:
        """データをキューに非同期投入します。

        Args:
            item (tuple[bytes, bool] | None): 音声バイト列と
                発話検出フラグのタプル。または
                ストリーム終了を示す None。

        Returns:
            None

        Raises:
            asyncio.CancelledError: タスクがキャンセルされた場合。
        """
        await self._queue.put(item)

    async def get(self) -> tuple[bytes, bool] | None:
        """データをキューから非同期に取り出します。

        Returns:
            tuple[bytes, bool] | None: 音声バイト列と
                発話検出フラグ of タプル。または
                ストリーム終了を示す None。

        Raises:
            asyncio.CancelledError: タスクがキャンセルされた場合。
        """
        return await self._queue.get()

    def task_done(self) -> None:
        """キューから取り出したタスクの完了を通知します。

        Returns:
            None

        Raises:
            ValueError: 未処理残数が 0 未満のときに
                呼び出された場合。
        """
        self._queue.task_done()

    @property
    def qsize(self) -> int:
        """現在のキュー内の未処理アイテム数を返します。

        Returns:
            int: 未処理チャンク数。
        """
        return self._queue.qsize()

    @property
    def maxsize(self) -> int:
        """最大音声チャンク容量を返します。

        Returns:
            int: 最大容量。
        """
        return self._queue._maxsize  # type: ignore[attr-defined]

    @maxsize.setter
    def maxsize(self, value: int) -> None:
        """最大容量を動的に変更します。

        もし新しい容量が広がり、これまで容量制限で
        put() 待機していたプロデューサーがある場合は、
        それらを直ちに起床させます。
        """
        if value < 0:
            raise ValueError("maxsize must be >= 0")
        # asyncio.Queue の内部 maxsize 属性を動的に変更
        self._queue._maxsize = value  # type: ignore[attr-defined]

        # 待機中のputtersを起こす
        # （Ruff 88桁制限を遵守するため改行で整理）
        while (
            self._queue._putters  # type: ignore[attr-defined]
            and not self._queue.full()
        ):
            self._queue._wakeup_next(  # type: ignore[attr-defined]
                self._queue._putters  # type: ignore[attr-defined]
            )


def calculate_max_queue_size(buffer_seconds: float, chunk_size_ms: int) -> int:
    """動的なキューの最大容量を算出します。

    バッファ秒数と1チャンクのミリ秒長から算出します。

    Args:
        buffer_seconds (float): 総蓄積目標秒数。
        chunk_size_ms (int): 1チャンクあたりの時間長
            （ミリ秒）。

    Returns:
        int: 算出されたキューの最大容量。
            0以下の場合は1。
    """
    if buffer_seconds <= 0.0 or chunk_size_ms <= 0:
        return DEFAULT_MAX_QUEUE_SIZE
    maxsize = int((buffer_seconds * 1000.0) / chunk_size_ms)
    return max(maxsize, 1)
