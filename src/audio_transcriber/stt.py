"""モデル常駐型音声認識コアモジュール。

本モジュールは、Faster-Whisper モデルおよび Silero-VAD をメモリ上に保持し、
低遅延な音声認識処理とライフサイクル管理を提供する SpeechTranscriber クラスを定義します。
"""

import gc
from collections.abc import Iterable
from pathlib import Path
from typing import Any, BinaryIO, Protocol, Self, runtime_checkable

import numpy as np
from faster_whisper import WhisperModel

from audio_transcriber.models import RecognizedSegment


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
    ) -> tuple[Iterable[Any], Any]:
        """音声推論を実行します。

        Args:
            audio: 音声ファイルパス、バイナリストリーム、または波形データ配列。
            language: 言語コード。
            task: タスク名。
            beam_size: ビーム探索幅。
            vad_filter: VAD フィルタ有効化。
            vad_parameters: VAD パラメータ。
            initial_prompt: 初期プロンプト。
            condition_on_previous_text: 前後コンテキスト考慮。

        Returns:
            tuple[Iterable[Any], Any]: セグメント反復子と推論メタ情報。
        """
        ...


@runtime_checkable
class TranscriberProtocol(Protocol):
    """音声認識プロバイダーの共通インターフェース Protocol。"""

    def transcribe_waveform(
        self,
        waveform: np.ndarray,
        sample_rate: int = 16000,
    ) -> list[RecognizedSegment]:
        """波形データから認識を実行します。

        Args:
            waveform (np.ndarray): 音声波形データ。
            sample_rate (int): サンプリングレート (Hz)。

        Returns:
            list[RecognizedSegment]: 認識結果セグメントのリスト。
        """
        ...

    def transcribe_file(
        self,
        file_path: Path | str,
    ) -> list[RecognizedSegment]:
        """音声ファイルから認識を実行します。

        Args:
            file_path (Path | str): 音声ファイルのパス。

        Returns:
            list[RecognizedSegment]: 認識結果セグメントのリスト。
        """
        ...

    def unload(self) -> None:
        """リソースを解放します。"""
        ...

    def close(self) -> None:
        """インスタンスをクローズしてリソースを解放します。"""
        ...


class SpeechTranscriber:
    """Faster-Whisper モデル常駐型の音声認識コアクラス（TranscriberProtocol 準拠）。"""

    def __init__(
        self,
        model_name: str = "large-v3",
        device: str = "auto",
        compute_type: str = "default",
        vad_filter: bool = True,
        beam_size: int = 5,
        language: str = "ja",
        condition_on_previous_text: bool = False,
        initial_prompt: str | None = None,
        vad_parameters: dict[str, object] | None = None,
        model: WhisperModelProtocol | None = None,
    ) -> None:
        """Faster-Whisper モデルを初期化または注入します。

        Args:
            model_name (str): Whisper モデル名。
            device (str): 実行デバイス ("cuda", "cpu", "auto")。
            compute_type (str): 量子化/精度 ("float16", "int8", 等)。
            vad_filter (bool): Silero-VAD 有効化。
            beam_size (int): ビーム探索サイズ。
            language (str): 認識対象言語コード。
            condition_on_previous_text (bool): 前後コンテキスト考慮。
            initial_prompt (str | None): 初期プロンプト。
            vad_parameters (dict[str, object] | None): VAD パラメータ。
            model (WhisperModelProtocol | None): 外部注入する Whisper モデルインスタンス。
        """
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.vad_filter = vad_filter
        self.beam_size = beam_size
        self.language = language
        self.condition_on_previous_text = condition_on_previous_text
        self.initial_prompt = initial_prompt
        self.vad_parameters = vad_parameters

        if model is not None:
            self._model: WhisperModelProtocol | None = model
        else:
            self._model = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
            )

    def transcribe_waveform(
        self,
        waveform: np.ndarray,
        sample_rate: int = 16000,
    ) -> list[RecognizedSegment]:
        """メモリ上の音声波形（16kHz Float32）から文字起こしを実行します。

        Args:
            waveform (np.ndarray): 音声波形データ（1D float32 配列）。
            sample_rate (int): サンプリングレート (Hz, デフォルト 16000)。

        Returns:
            list[RecognizedSegment]: 認識結果セグメントのリスト。

        Raises:
            ValueError: 波形データが無効または空の場合。
            RuntimeError: モデルがロードされていない場合。
        """
        if waveform.size == 0:
            raise ValueError("波形データが空です")

        if self._model is None:
            raise RuntimeError("モデルがロードされていません")

        # faster-whisper は float32 の波形 (16kHz) を直接受け入れ可能
        audio_input = (
            waveform.astype(np.float32) if waveform.dtype != np.float32 else waveform
        )

        kwargs: dict[str, Any] = {
            "beam_size": self.beam_size,
            "language": self.language,
            "vad_filter": self.vad_filter,
            "condition_on_previous_text": self.condition_on_previous_text,
        }
        if self.initial_prompt is not None:
            kwargs["initial_prompt"] = self.initial_prompt
        if self.vad_parameters is not None:
            kwargs["vad_parameters"] = self.vad_parameters

        segments_iter, _ = self._model.transcribe(audio_input, **kwargs)
        return self._format_segments(segments_iter)

    def transcribe_file(
        self,
        file_path: Path | str,
    ) -> list[RecognizedSegment]:
        """音声ファイルパスから文字起こしを実行します。

        Args:
            file_path (Path | str): 音声ファイルのパス。

        Returns:
            list[RecognizedSegment]: 認識結果セグメントのリスト。

        Raises:
            FileNotFoundError: 音声ファイルが存在しない場合。
            RuntimeError: モデルがロードされていない場合。
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"音声ファイルが見つかりません: {path}")

        if self._model is None:
            raise RuntimeError("モデルがロードされていません")

        kwargs: dict[str, Any] = {
            "beam_size": self.beam_size,
            "language": self.language,
            "vad_filter": self.vad_filter,
            "condition_on_previous_text": self.condition_on_previous_text,
        }
        if self.initial_prompt is not None:
            kwargs["initial_prompt"] = self.initial_prompt
        if self.vad_parameters is not None:
            kwargs["vad_parameters"] = self.vad_parameters

        segments_iter, _ = self._model.transcribe(str(path), **kwargs)
        return self._format_segments(segments_iter)

    def _format_segments(self, segments_iter: Iterable[Any]) -> list[RecognizedSegment]:
        """推論結果のセグメント反復子を RecognizedSegment リストへ整形します。

        Args:
            segments_iter (Iterable[Any]): faster-whisper のセグメント反復子。

        Returns:
            list[RecognizedSegment]: 整形後の認識セグメントリスト。
        """
        results: list[RecognizedSegment] = []
        for s in segments_iter:
            text = getattr(s, "text", "").strip()
            if not text:
                continue

            start = float(getattr(s, "start", 0.0))
            end = float(getattr(s, "end", 0.0))
            avg_logprob = float(getattr(s, "avg_logprob", 0.0))
            # 対数確率 (<= 0.0) を [0.0, 1.0] 近似に変換 (np.exp)
            confidence = float(np.clip(np.exp(avg_logprob), 0.0, 1.0))

            words_data: list[dict[str, object]] | None = None
            raw_words = getattr(s, "words", None)
            if raw_words is not None:
                words_data = [
                    {
                        "word": getattr(w, "word", ""),
                        "start": float(getattr(w, "start", 0.0)),
                        "end": float(getattr(w, "end", 0.0)),
                        "probability": float(getattr(w, "probability", 0.0)),
                    }
                    for w in raw_words
                ]

            results.append(
                RecognizedSegment(
                    start=start,
                    end=end,
                    text=text,
                    confidence=confidence,
                    words=words_data,
                )
            )
        return results

    def unload(self) -> None:
        """ロードされた Whisper モデルをアンロードし、リソースを解放します。"""
        self._model = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    def close(self) -> None:
        """リソースを解放してインスタンスをクローズします。"""
        self.unload()

    def __enter__(self) -> Self:
        """コンテキストマネージャー開始。

        Returns:
            Self: 自身のインスタンス。
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """コンテキストマネージャー終了時にリソースを解放します。

        Args:
            exc_type: 例外の型。
            exc_val: 例外のインスタンス。
            exc_tb: トレースバック。
        """
        self.close()
