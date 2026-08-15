"""モデル常駐型音声認識コアモジュール。

本モジュールは、Faster-Whisper モデルおよび Silero-VAD をメモリ上に保持し、
低遅延な音声認識処理とライフサイクル管理を提供する SpeechTranscriber クラスを定義します。
"""

from __future__ import annotations

import gc
import logging
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, BinaryIO, Protocol, runtime_checkable

import numpy as np
from faster_whisper import WhisperModel

import audio_transcriber.compat  # noqa: F401

logger = logging.getLogger(__name__)


@runtime_checkable
class WhisperModelProtocol(Protocol):
    """Whisper モデルバックエンドの Protocol。"""

    def transcribe(
        self,
        audio: str | BinaryIO | np.ndarray,
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
        """音声推論を実行します。"""
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
        """音声ファイルパスから文字起こしを実行し、セグメント辞書のリストを返します。"""
        ...


class VadProgressHandler(logging.Handler):
    """Faster-Whisper の内部ロガーから VAD チャンク出力を横取りして通知するハンドラ"""

    def __init__(self, on_progress: Callable[[str, Any], None] | None):
        """初期化します。"""
        super().__init__()
        self.on_progress = on_progress
        self.setLevel(logging.DEBUG)

    def emit(self, record: logging.LogRecord) -> None:
        """ログレコードを受け取り、VAD出力があればコールバックに送ります。"""
        if not self.on_progress:
            return
        msg = record.getMessage()
        if "VAD filter kept the following audio segments:" in msg:
            chunks_str = msg.replace(
                "VAD filter kept the following audio segments:", ""
            ).strip()

            import re

            pattern = re.compile(r"([\d\.]+)s\s*-\s*([\d\.]+)s")
            vad_chunks = [
                (float(m.group(1)), float(m.group(2)))
                for m in pattern.finditer(chunks_str)
            ]

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
        vad_filter: bool = True,
        vad_parameters: dict[str, Any] | None = None,
        beam_size: int = 5,
        condition_on_previous_text: bool = True,
        no_speech_threshold: float = 0.6,
        model: WhisperModelProtocol | None = None,
    ) -> None:
        """プロバイダーを初期化します。"""
        self.model_size = model_size
        self.device = device
        resolved_compute = compute_type
        if device.lower() == "cpu" and compute_type.lower() in (
            "float16",
            "int8_float16",
        ):
            logger.info(
                "CPU デバイスでは %s が非サポートのため、compute_type を 'int8' に自動変更しました。",
                compute_type,
            )
            resolved_compute = "int8"

        self.compute_type = resolved_compute
        self.language = language
        self.initial_prompt = initial_prompt
        self.vad_filter = vad_filter
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
        """推論用キーワード引数を生成します。"""
        kwargs: dict[str, Any] = {
            "language": self.language,
            "vad_filter": self.vad_filter,
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

    def transcribe_file(
        self,
        file_path: Path | str,
        on_segment: Callable[[dict[str, Any]], None] | None = None,
        on_progress: Callable[[str, Any], None] | None = None,
    ) -> list[dict[str, Any]]:
        """音声ファイルパスから文字起こしを実行し、セグメント辞書のリストを返します。"""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"音声ファイルが見つかりません: {path}")
        if self._model is None:
            raise RuntimeError("モデルがロードされていません")

        # VADログフックの準備の代わりに、事前にVADチャンクを取得する
        if on_progress and self.vad_filter:
            try:
                from faster_whisper.audio import decode_audio
                from faster_whisper.vad import VadOptions, get_speech_timestamps

                raw_audio = decode_audio(str(path))
                if isinstance(raw_audio, tuple):
                    audio_arr = raw_audio[0]
                else:
                    audio_arr = raw_audio
                vad_opts = VadOptions(**(self.vad_parameters or {}))
                clip_timestamps = get_speech_timestamps(audio_arr, vad_opts)
                vad_chunks = [
                    (float(c["start"]), float(c["end"])) for c in clip_timestamps
                ]
                on_progress("vad_chunks", vad_chunks)
            except Exception as e:
                logging.getLogger(__name__).warning(
                    "VAD情報の事前取得に失敗しました: %s", e
                )

        segments_gen, _info = self._model.transcribe(str(path), **self._build_kwargs())

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

    def unload(self) -> None:
        """モデルをアンロードします。"""
        self._model = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
