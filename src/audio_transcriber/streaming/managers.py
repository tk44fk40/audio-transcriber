"""ストリーミング処理の状態管理・文脈管理マネージャー。"""

from __future__ import annotations

from enum import Enum, auto
from typing import Any

import numpy as np


class State(Enum):
    """StreamingVadManagerの内部状態。"""

    IDLE = auto()
    SPEECH_ACTIVE = auto()
    TRAILING_SILENCE = auto()
    HOLDING_SHORT_CHUNK = auto()


class ContextManager:
    """Whisperに渡す初期プロンプト(文脈履歴)を管理するクラス。"""

    def __init__(self, max_length: int, timeout_seconds: float) -> None:
        """初期化します。

        Args:
            max_length: プロンプトの最大文字数
            timeout_seconds: クリアまでの無音時間(秒)
        """
        self.max_length = max_length
        self.timeout_seconds = timeout_seconds
        self.segments: list[str] = []

    def add_text(self, text: str) -> None:
        """テキストセグメントを追加します。

        Args:
            text: 追加するテキスト
        """
        text = text.strip()
        if not text:
            return
        if len(text) > self.max_length:
            text = text[-self.max_length :]
        self.segments.append(text)
        self._trim_over_limit()

    def get_prompt(self, separator: str = "") -> str:
        """現在のプロンプト文字列を取得します。

        Args:
            separator: セグメント間の区切り文字

        Returns:
            結合されたプロンプト文字列
        """
        return separator.join(self.segments)

    def _trim_over_limit(self) -> None:
        """最大文字数を超えた古いセグメントを破棄します。"""
        while self.segments:
            # 区切り文字（スペース）込みでの長さを評価
            total_len = sum(len(s) for s in self.segments) + (len(self.segments) - 1)
            if total_len <= self.max_length:
                break
            self.segments.pop(0)

    def check_timeout(self, silence_duration: float) -> None:
        """タイムアウト判定を行い、必要に応じてクリアします。

        Args:
            silence_duration: 現在の無音時間(秒)
        """
        if silence_duration >= self.timeout_seconds:
            self.clear()

    def clear(self) -> None:
        """プロンプトを強制的にクリアします。"""
        self.segments.clear()


class StreamingVadManager:
    """音声チャンクの蓄積、無音による切り出し、短チャンク保留等を管理するクラス。"""

    def __init__(
        self,
        sample_rate: int,
        min_silence_duration: float,
        chunk_min_seconds: float,
        chunk_max_seconds: float,
    ) -> None:
        """初期化します。

        Args:
            sample_rate: サンプリングレート
            min_silence_duration: チャンクを切り出す最小無音時間(秒)
            chunk_min_seconds: 最小チャンク長(秒)
            chunk_max_seconds: 最大チャンク長(秒)
        """
        self.sample_rate = sample_rate
        self.min_silence_duration = min_silence_duration
        self.chunk_min_seconds = chunk_min_seconds
        self.chunk_max_seconds = chunk_max_seconds
        self.state = State.IDLE
        self.buffer: list[np.ndarray[Any, Any]] = []
        self.accumulated_seconds = 0.0
        self.silence_timer = 0.0

    def process_audio(
        self, audio_chunk: np.ndarray[Any, Any], is_speech: bool
    ) -> np.ndarray[Any, Any] | None:
        """音声チャンクとVAD判定を受け取り、確定した音声チャンクがあれば返します。

        Args:
            audio_chunk: 音声データチャンク
            is_speech: チャンクが発話区間かどうか
        """
        chunk_duration = len(audio_chunk) / self.sample_rate

        if self.state == State.IDLE:
            if is_speech:
                self.state = State.SPEECH_ACTIVE
                self.buffer.append(audio_chunk)
                self.accumulated_seconds += chunk_duration
                self.silence_timer = 0.0

        elif self.state == State.SPEECH_ACTIVE:
            self.buffer.append(audio_chunk)
            self.accumulated_seconds += chunk_duration
            if not is_speech:
                self.state = State.TRAILING_SILENCE
                self.silence_timer = chunk_duration
            else:
                self.silence_timer = 0.0

        elif self.state == State.TRAILING_SILENCE:
            self.buffer.append(audio_chunk)
            self.accumulated_seconds += chunk_duration
            if is_speech:
                self.state = State.SPEECH_ACTIVE
                self.silence_timer = 0.0
            else:
                self.silence_timer += chunk_duration

        elif self.state == State.HOLDING_SHORT_CHUNK:
            if is_speech:
                self.state = State.SPEECH_ACTIVE
                self.silence_timer = 0.0
            else:
                self.silence_timer += chunk_duration
            self.buffer.append(audio_chunk)
            self.accumulated_seconds += chunk_duration

        # 無音判定による確定
        if self.state == State.TRAILING_SILENCE:
            if self.silence_timer >= self.min_silence_duration:
                if (
                    self.accumulated_seconds - self.silence_timer
                ) >= self.chunk_min_seconds:
                    self.state = State.IDLE
                    return self.flush()
                else:
                    self.state = State.HOLDING_SHORT_CHUNK

        # 短チャンク保留中に無音が長時間（min_silenceの3倍以上）継続した場合のフォールバック切り出し
        if self.state == State.HOLDING_SHORT_CHUNK:
            if self.silence_timer >= self.min_silence_duration * 3:
                self.state = State.IDLE
                return self.flush()

        # 最大チャンク長到達時の強制切り出し
        if (
            self.state != State.IDLE
            and self.accumulated_seconds >= self.chunk_max_seconds
        ):
            old_state = self.state
            result = self.flush()
            if old_state == State.SPEECH_ACTIVE:
                self.state = State.SPEECH_ACTIVE
            return result

        return None

    def flush(self) -> np.ndarray[Any, Any] | None:
        """保持しているバッファを強制的に切り出して返します。

        Returns:
            バッファの音声データ、なければNone
        """
        if not self.buffer:
            return None
        out = np.concatenate(self.buffer)
        self.buffer.clear()
        self.accumulated_seconds = 0.0
        self.silence_timer = 0.0
        self.state = State.IDLE
        return out
