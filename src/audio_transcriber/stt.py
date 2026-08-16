"""モデル常駐型音声認識コアモジュール。

本モジュールは、Faster-Whisper モデルをメモリ上に保持し、
低遅延な音声認識処理とライフサイクル管理を提供するプロバイダーを定義します。
"""

from __future__ import annotations

import gc
import logging
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import numpy as np
from faster_whisper import WhisperModel

import audio_transcriber.compat  # noqa: F401
from audio_transcriber.stt_types import (
    TranscriberProvider,
    WhisperModelProtocol,
)

__all__ = [
    "FasterWhisperProvider",
    "TranscriberProvider",
    "VadProgressHandler",
    "WhisperModelProtocol",
]

logger = logging.getLogger(__name__)


class VadProgressHandler(logging.Handler):
    """Faster-Whisper の内部ロガーから VAD チャンク出力を横取りして通知するハンドラ。"""

    def __init__(self, on_progress: Callable[[str, Any], None] | None) -> None:
        """初期化します。

        Args:
            on_progress: 進捗通知を受け取るコールバック関数。
        """
        super().__init__()
        self.on_progress = on_progress
        self.setLevel(logging.DEBUG)

    def emit(self, record: logging.LogRecord) -> None:
        """ログレコードを受け取り、VAD出力があればコールバックに送ります。

        Args:
            record: ログレコードオブジェクト。
        """
        if not self.on_progress:
            return
        msg = record.getMessage()
        if "VAD filter kept the following audio segments:" in msg:
            import re

            chunks_str = msg.replace(
                "VAD filter kept the following audio segments:", ""
            ).strip()
            pattern = re.compile(r"([\d\.]+)s\s*-\s*([\d\.]+)s")
            vad_chunks = []
            for m in pattern.finditer(chunks_str):
                start = float(m.group(1))
                end = float(m.group(2))
                if start > 10000 or end > 10000:
                    start /= 16000.0
                    end /= 16000.0
                vad_chunks.append((start, end))
            self.on_progress("vad_chunks", vad_chunks)


class FasterWhisperProvider:
    """Faster-Whisper をバックエンドとする音声認識プロバイダー。"""

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cuda",
        compute_type: str = "float16",
        language: str = "ja",
        initial_prompt: str | None = None,
        vad_parameters: dict[str, Any] | None = None,
        beam_size: int = 5,
        condition_on_previous_text: bool = True,
        no_speech_threshold: float = 0.6,
        model: WhisperModelProtocol | None = None,
    ) -> None:
        """プロバイダーを初期化します。

        Args:
            model_size: Whisper モデルサイズ ('tiny', 'base', 'small', 'medium', 'large-v3')。
            device: 推論デバイス ('cuda' または 'cpu')。
            compute_type: 量子化計算タイプ ('float16', 'int8' 等)。
            language: 音声認識言語コード。
            initial_prompt: 初期文脈プロンプト。
            vad_parameters: VAD パラメータ辞書。
            beam_size: ビームサーチ幅。
            condition_on_previous_text: 前のテキストに依存するかどうかのフラグ。
            no_speech_threshold: 無音判定確率閾値。
            model: 外部注入可能な WhisperModelProtocol インスタンス（モック用）。
        """
        self.model_size = model_size
        self.device = device
        resolved_compute = compute_type
        if device.lower() == "cpu" and compute_type.lower() in (
            "float16",
            "int8_float16",
        ):
            logger.info(
                "CPU では %s 非サポートのため 'int8' に自動変更しました。",
                compute_type,
            )
            resolved_compute = "int8"

        self.compute_type = resolved_compute
        self.language = language
        self.initial_prompt = initial_prompt
        self.vad_parameters = vad_parameters
        self.beam_size = beam_size
        self.condition_on_previous_text = condition_on_previous_text
        self.no_speech_threshold = no_speech_threshold

        if model is not None:
            self._model: WhisperModelProtocol | None = model
        else:
            self._model = WhisperModel(
                model_size, device=device, compute_type=resolved_compute
            )

    def _build_kwargs(self) -> dict[str, Any]:
        """推論用キーワード引数を生成します。

        Returns:
            dict[str, Any]: model.transcribe へ渡すキーワード引数辞書。
        """
        kwargs: dict[str, Any] = {
            "language": self.language,
            "vad_filter": False,
            "word_timestamps": True,
            "beam_size": self.beam_size,
            "condition_on_previous_text": self.condition_on_previous_text,
            "no_speech_threshold": self.no_speech_threshold,
        }
        if self.initial_prompt is not None:
            kwargs["initial_prompt"] = self.initial_prompt
        if self.vad_parameters is not None:
            kwargs["vad_parameters"] = self.vad_parameters
        return kwargs

    def _extract_segments(
        self,
        segments_gen: Iterable[Any],
        on_segment: Callable[[dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        """セグメントジェネレータから辞書リストを生成します。

        Args:
            segments_gen: WhisperModel.transcribe から返されるセグメントイテレータ。
            on_segment: 各セグメント生成時のコールバック。

        Returns:
            list[dict[str, Any]]: 整形されたセグメント辞書のリスト。
        """
        segment_dicts: list[dict[str, Any]] = []
        for i, s in enumerate(segments_gen, start=1):
            words_list = []
            words_attr = getattr(s, "words", None)
            if words_attr is not None:
                for w in words_attr:
                    words_list.append(
                        {
                            "start": float(getattr(w, "start", 0.0)),
                            "end": float(getattr(w, "end", 0.0)),
                            "word": getattr(w, "word", ""),
                            "probability": float(getattr(w, "probability", 0.0)),
                        }
                    )

            seg_dict = {
                "id": getattr(s, "id", i),
                "start": float(getattr(s, "start", 0.0)),
                "end": float(getattr(s, "end", 0.0)),
                "text": getattr(s, "text", "").strip(),
                "no_speech_prob": float(getattr(s, "no_speech_prob", 0.0)),
                "compression_ratio": float(getattr(s, "compression_ratio", 0.0)),
                "words": words_list,
            }
            segment_dicts.append(seg_dict)
            if on_segment is not None:
                on_segment(seg_dict)
        return segment_dicts

    def transcribe_file(
        self,
        file_path: Path | str,
        on_segment: Callable[[dict[str, Any]], None] | None = None,
        on_progress: Callable[[str, Any], None] | None = None,
    ) -> list[dict[str, Any]]:
        """音声ファイルパスから文字起こしを実行し、セグメント辞書のリストを返します。

        Args:
            file_path: 音声ファイルパス。
            on_segment: セグメント認識時の通知コールバック。
            on_progress: 進捗通知コールバック。

        Returns:
            list[dict[str, Any]]: 認識されたセグメント辞書のリスト。

        Raises:
            FileNotFoundError: 音声ファイルが存在しない場合。
            RuntimeError: モデルがアンロードされている場合。
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"音声ファイルが見つかりません: {path}")
        if self._model is None:
            raise RuntimeError("モデルがロードされていません")

        segments_gen, _info = self._model.transcribe(str(path), **self._build_kwargs())
        return self._extract_segments(segments_gen, on_segment=on_segment)

    def transcribe_stream(
        self,
        audio: np.ndarray[Any, Any],
        initial_prompt: str | None = None,
        on_segment: Callable[[dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        """音声波形データ（numpy配列）から文字起こしを実行し、セグメント辞書のリストを返します。

        Args:
            audio: 音声波形 numpy 配列。
            initial_prompt: 文脈誘導のためのプロンプト文字列。
            on_segment: セグメント認識時の通知コールバック。

        Returns:
            list[dict[str, Any]]: 認識されたセグメント辞書のリスト。

        Raises:
            RuntimeError: モデルがロードされていない場合。
            ValueError: 入力音声配列が空または3次元以上の場合。
        """
        if self._model is None:
            raise RuntimeError("モデルがロードされていません")
        if len(audio) == 0:
            raise ValueError("入力音声データが空です")

        if audio.ndim > 1:
            if audio.ndim == 2:
                audio = np.mean(audio, axis=-1)
            else:
                raise ValueError("入力音声は1次元または2次元配列である必要があります")

        if audio.dtype == np.int16:
            audio_arr = audio.astype(np.float32) / 32768.0
        elif audio.dtype != np.float32:
            audio_arr = audio.astype(np.float32)
        else:
            audio_arr = audio

        kwargs = self._build_kwargs()
        kwargs["vad_filter"] = False
        if initial_prompt is not None:
            kwargs["initial_prompt"] = initial_prompt

        segments_gen, _info = self._model.transcribe(audio_arr, **kwargs)
        return self._extract_segments(segments_gen, on_segment=on_segment)

    def unload(self) -> None:
        """モデルをアンロードしメモリを解放します。"""
        self._model = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
