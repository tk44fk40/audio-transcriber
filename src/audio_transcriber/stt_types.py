"""音声認識モジュールの共通型定義および Protocol 定義。"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, BinaryIO, Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class WhisperModelProtocol(Protocol):
    """Whisper モデルバックエンドの Protocol。"""

    def transcribe(
        self,
        audio: str | BinaryIO | np.ndarray[Any, Any],
        *,
        language: str | None = ...,
        task: str = ...,
        beam_size: int = ...,
        vad_filter: bool = ...,
        vad_parameters: Any = ...,
        initial_prompt: str | Iterable[int] | None = ...,
        condition_on_previous_text: bool = ...,
        word_timestamps: bool = ...,
        no_speech_threshold: float = ...,
    ) -> tuple[Iterable[Any], Any]:
        """音声推論を実行します。

        Args:
            audio: 音声ファイルパス、バイナリIO、または音声波形配列。
            language: 言語コード（'ja' 等）。
            task: タスク種別（'transcribe' 等）。
            beam_size: ビームサーチ幅。
            vad_filter: 内部 VAD フィルタの有効フラグ。
            vad_parameters: VAD パラメータ辞書。
            initial_prompt: 初期文脈プロンプト。
            condition_on_previous_text: 前のテキストに依存するかどうかのフラグ。
            word_timestamps: 単語レベルタイムスタンプを算出するかどうかのフラグ。
            no_speech_threshold: 無音判定確率の閾値。

        Returns:
            tuple[Iterable[Any], Any]: セグメントのイテレータと推論情報メタデータ。
        """
        ...


@runtime_checkable
class TranscriberProvider(Protocol):
    """音声文字起こしプロバイダーの共通インターフェース Protocol。"""

    def transcribe_file(
        self,
        file_path: Path | str,
        on_segment: Callable[[dict[str, Any]], None] | None = None,
        on_progress: Callable[[str, Any], None] | None = None,
    ) -> list[dict[str, Any]]:
        """音声ファイルパスから文字起こしを実行し、セグメント辞書のリストを返します。

        Args:
            file_path: 音声ファイルのパス。
            on_segment: 各セグメント認識時の通知コールバック。
            on_progress: 進捗通知コールバック。

        Returns:
            list[dict[str, Any]]: 認識されたセグメント辞書のリスト。

        Raises:
            FileNotFoundError: 対象ファイルが存在しない場合。
            RuntimeError: モデルが未ロードまたは推論に失敗した場合。
        """
        ...

    def transcribe_stream(
        self,
        audio: np.ndarray[Any, Any],
        initial_prompt: str | None = None,
        on_segment: Callable[[dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        """音声波形データ（numpy配列）から文字起こしを実行し、セグメント辞書のリストを返します。

        Args:
            audio: 1次元または2次元の音声波形 numpy 配列。
            initial_prompt: 文脈誘導のための初期プロンプトテキスト。
            on_segment: 各セグメント認識時の通知コールバック。

        Returns:
            list[dict[str, Any]]: 認識されたセグメント辞書のリスト。

        Raises:
            ValueError: 入力波形データが空または無効な形状の場合。
            RuntimeError: モデルが未ロードまたは推論に失敗した場合。
        """
        ...
