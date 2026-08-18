"""AudioChunkQueue および関連関数のテスト。

AAA (Arrange-Act-Assert) パターンを徹底し、
キューの基本機能、Backpressure制御、
および動的サイズ調整を検証します。
"""

from __future__ import annotations

import asyncio

import pytest

from audio_transcriber.audio_queues import (
    DEFAULT_MAX_QUEUE_SIZE,
    AudioChunkQueue,
    calculate_max_queue_size,
)


@pytest.fixture
def anyio_backend() -> str:
    """AnyIOのバックエンド。"""
    return "asyncio"


@pytest.mark.anyio
async def test_audio_chunk_queue_basic() -> None:
    """正常系: キューの基本的なデータ投入・取得とqsizeを検証。"""
    queue = AudioChunkQueue(maxsize=5)
    assert queue.qsize == 0

    await queue.put((b"data1", True))
    await queue.put((b"data2", False))
    await queue.put(None)

    assert queue.qsize == 3

    item1 = await queue.get()
    assert item1 == (b"data1", True)
    queue.task_done()

    item2 = await queue.get()
    assert item2 == (b"data2", False)
    queue.task_done()

    item3 = await queue.get()
    assert item3 is None
    queue.task_done()

    assert queue.qsize == 0


@pytest.mark.anyio
async def test_audio_chunk_queue_backpressure() -> None:
    """正常系: キュー満杯時のブロック（Backpressure）を検証。"""
    queue = AudioChunkQueue(maxsize=2)
    await queue.put((b"1", False))
    await queue.put((b"2", False))

    assert queue.qsize == 2

    # 3つ目のputはブロックされるため、
    # タイムアウト付きタスクで検証
    put_task = asyncio.create_task(queue.put((b"3", False)))

    # 少し待ってタスクが完了していない
    # （ブロック中）ことを確認
    await asyncio.sleep(0.05)
    assert not put_task.done()

    # 1つ取り出す
    item = await queue.get()
    assert item == (b"1", False)
    queue.task_done()

    # 取り出されたことでputが再開・完了
    # することを確認
    await asyncio.wait_for(put_task, timeout=0.5)
    assert queue.qsize == 2

    item2 = await queue.get()
    assert item2 == (b"2", False)
    item3 = await queue.get()
    assert item3 == (b"3", False)


@pytest.mark.anyio
async def test_audio_chunk_queue_dynamic_maxsize() -> None:
    """正常系: キューのmaxsize動的変更を検証。"""
    queue = AudioChunkQueue(maxsize=10)
    assert queue.maxsize == 10
    queue.maxsize = 20
    assert queue.maxsize == 20

    with pytest.raises(ValueError):
        queue.maxsize = -5


@pytest.mark.anyio
async def test_audio_chunk_queue_dynamic_maxsize_wake_putters() -> None:
    """正常系: maxsize増加時に、put待ちタスクが起床するか検証。"""
    queue = AudioChunkQueue(maxsize=1)
    await queue.put((b"data1", False))

    # 2つ目のputはブロックされる
    put_task = asyncio.create_task(queue.put((b"data2", False)))
    await asyncio.sleep(0.05)
    assert not put_task.done()

    # maxsizeを動的に増やす
    queue.maxsize = 2

    # これによりputタスクが
    # ウェイクアップして完了するはず
    await asyncio.wait_for(put_task, timeout=0.5)
    assert queue.qsize == 2


@pytest.mark.anyio
async def test_calculate_max_queue_size() -> None:
    """正常系/異常系: 動的キュー最大容量の計算ロジックを検証。"""
    # 標準的な値
    assert calculate_max_queue_size(buffer_seconds=10.0, chunk_size_ms=100) == 100

    # バッファ秒数を変更
    assert calculate_max_queue_size(buffer_seconds=5.5, chunk_size_ms=100) == 55

    # チャンクミリ秒を変更
    assert calculate_max_queue_size(buffer_seconds=10.0, chunk_size_ms=200) == 50

    # 蓄積秒数が小、最小値 1 に制限
    assert calculate_max_queue_size(buffer_seconds=0.05, chunk_size_ms=100) == 1

    # 異常値入力のときはデフォルト値
    assert (
        calculate_max_queue_size(buffer_seconds=0.0, chunk_size_ms=100)
        == DEFAULT_MAX_QUEUE_SIZE
    )
    assert (
        calculate_max_queue_size(buffer_seconds=10.0, chunk_size_ms=0)
        == DEFAULT_MAX_QUEUE_SIZE
    )
    assert (
        calculate_max_queue_size(buffer_seconds=-5.0, chunk_size_ms=100)
        == DEFAULT_MAX_QUEUE_SIZE
    )
    assert (
        calculate_max_queue_size(buffer_seconds=10.0, chunk_size_ms=-50)
        == DEFAULT_MAX_QUEUE_SIZE
    )
