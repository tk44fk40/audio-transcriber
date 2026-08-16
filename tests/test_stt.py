"""FasterWhisperProvider および STT 関連 Protocol の単体テスト。"""

import builtins
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from audio_transcriber.stt import (
    FasterWhisperProvider,
    TranscriberProvider,
    VadProgressHandler,
    WhisperModelProtocol,
)


class MockWord:
    """単語モック。"""

    def __init__(
        self, word: str, start: float, end: float, probability: float = 0.95
    ) -> None:
        self.word = word
        self.start = start
        self.end = end
        self.probability = probability


class MockSegment:
    """faster-whisper のセグメントモック。"""

    def __init__(
        self,
        start: float,
        end: float,
        text: str,
        avg_logprob: float = -0.1,
        words: list[Any] | tuple[Any, ...] | None = None,
    ) -> None:
        self.start = start
        self.end = end
        self.text = text
        self.avg_logprob = avg_logprob
        self.words = words
        self.id = 1
        self.no_speech_prob = 0.0
        self.compression_ratio = 1.0


class MockWhisperModel:
    """WhisperModelProtocol に適合するモックモデル。"""

    def __init__(self) -> None:
        self.transcribe_called = False
        self.last_audio: Any = None
        self.last_kwargs: dict[str, Any] = {}
        self.custom_segments: list[MockSegment] | None = None

    def transcribe(
        self,
        audio: Any,
        **kwargs: Any,
    ) -> tuple[Iterator[MockSegment], MagicMock]:
        """推論モックメソッド。"""
        self.transcribe_called = True
        self.last_audio = audio
        self.last_kwargs = kwargs

        if self.custom_segments is not None:
            segments = self.custom_segments
        else:
            segments = [
                MockSegment(start=0.0, end=1.5, text=" こんにちは"),
                MockSegment(start=1.5, end=3.0, text=" 世界"),
            ]
        info = MagicMock()
        info.language = "ja"
        info.language_probability = 0.99
        return iter(segments), info


class TestProtocols:
    """Protocol 適合性のテスト。"""

    def test_whisper_model_protocol_check(self) -> None:
        """MockWhisperModel が WhisperModelProtocol を満たすことを確認します。"""
        model = MockWhisperModel()
        assert isinstance(model, WhisperModelProtocol)

    def test_speech_transcriber_protocol_check(self) -> None:
        """FasterWhisperProvider が TranscriberProvider を満たすことを確認します。"""
        mock_model = MockWhisperModel()
        transcriber = FasterWhisperProvider(model=mock_model)
        assert isinstance(transcriber, TranscriberProvider)


class TestFasterWhisperProvider:
    """FasterWhisperProvider クラスの機能テスト。"""

    def test_init_with_injected_model(self) -> None:
        """DI により外部からモデルを注入して初期化できることを確認します。"""
        mock_model = MockWhisperModel()
        transcriber = FasterWhisperProvider(
            model_size="small",
            language="ja",
            model=mock_model,
        )
        assert transcriber.model_size == "small"
        assert transcriber.language == "ja"
        assert transcriber._model is mock_model

    def test_init_cpu_device_fallback(self) -> None:
        """CPU デバイス時に float16 が int8 に自動変更されることを確認します。"""
        with patch("audio_transcriber.stt.WhisperModel") as mock_cls:
            transcriber = FasterWhisperProvider(
                model_size="tiny", device="cpu", compute_type="float16"
            )
            assert transcriber.compute_type == "int8"
            mock_cls.assert_called_once_with("tiny", device="cpu", compute_type="int8")

    def test_transcribe_file_success(self, tmp_path: Path) -> None:
        """音声ファイルパスからの文字起こしが正常に動作することを確認します。"""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy audio data")
        mock_model = MockWhisperModel()
        transcriber = FasterWhisperProvider(
            model=mock_model,
            initial_prompt="初期プロンプト",
            vad_parameters={"threshold": 0.5},
        )

        called_segs: list[dict[str, Any]] = []
        results = transcriber.transcribe_file(
            audio_file, on_segment=lambda s: called_segs.append(s)
        )
        assert len(results) == 2
        assert len(called_segs) == 2
        assert results[0]["text"] == "こんにちは"
        assert mock_model.transcribe_called is True
        assert mock_model.last_kwargs.get("vad_filter") is False
        assert mock_model.last_kwargs.get("initial_prompt") == "初期プロンプト"
        assert mock_model.last_kwargs.get("vad_parameters") == {"threshold": 0.5}

    def test_transcribe_file_with_words(self, tmp_path: Path) -> None:
        """単語タイムスタンプを含むファイル文字起こし結果が正しく変換されることを確認。"""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy")
        mock_model = MockWhisperModel()
        mock_model.custom_segments = [
            MockSegment(
                start=0.0,
                end=1.0,
                text="hello",
                words=(MockWord("hello", 0.0, 1.0, 0.98),),
            )
        ]
        transcriber = FasterWhisperProvider(model=mock_model)
        res = transcriber.transcribe_file(audio_file)
        assert len(res) == 1
        assert res[0]["words"][0]["word"] == "hello"
        assert res[0]["words"][0]["probability"] == 0.98

    def test_transcribe_file_not_found_raises_error(self, tmp_path: Path) -> None:
        """存在しないファイルパスで FileNotFoundError が発生することを確認。"""
        transcriber = FasterWhisperProvider(model=MockWhisperModel())
        with pytest.raises(FileNotFoundError):
            transcriber.transcribe_file(tmp_path / "non_existent.wav")

    def test_transcribe_file_model_none_raises_error(self, tmp_path: Path) -> None:
        """unload 後に transcribe_file を呼んだ場合 RuntimeError が発生することを確認。"""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy")
        transcriber = FasterWhisperProvider(model=MockWhisperModel())
        transcriber.unload()
        with pytest.raises(RuntimeError, match="モデルがロードされていません"):
            transcriber.transcribe_file(audio_file)

    def test_transcribe_stream_success(self) -> None:
        """音声波形データからのストリーミング文字起こしが正常に動作することを確認。"""
        audio_arr = np.zeros(16000, dtype=np.float32)
        mock_model = MockWhisperModel()
        transcriber = FasterWhisperProvider(model=mock_model)

        called_segs: list[dict[str, Any]] = []
        results = transcriber.transcribe_stream(
            audio_arr,
            initial_prompt="初期文脈",
            on_segment=lambda s: called_segs.append(s),
        )
        assert len(results) == 2
        assert len(called_segs) == 2
        assert results[0]["text"] == "こんにちは"
        assert mock_model.transcribe_called is True
        assert mock_model.last_kwargs.get("initial_prompt") == "初期文脈"

    def test_transcribe_stream_stereo_and_multidim(self) -> None:
        """2次元ステレオ配列の平均モノラル化および3次元以上の配列例外を検証。"""
        mock_model = MockWhisperModel()
        transcriber = FasterWhisperProvider(model=mock_model)

        stereo_audio = np.array([[0.4, 0.8], [0.2, 0.6]], dtype=np.float32)
        transcriber.transcribe_stream(stereo_audio)
        np.testing.assert_allclose(
            mock_model.last_audio, np.array([0.6, 0.4], dtype=np.float32)
        )

        with pytest.raises(ValueError, match="1次元または2次元配列"):
            transcriber.transcribe_stream(np.zeros((2, 2, 2), dtype=np.float32))

    def test_transcribe_stream_int16_conversion(self) -> None:
        """int16 配列が float32 に正規化されて WhisperModel に渡されることを確認。"""
        audio_int16 = np.array([16384, -16384], dtype=np.int16)
        mock_model = MockWhisperModel()
        transcriber = FasterWhisperProvider(model=mock_model)

        transcriber.transcribe_stream(audio_int16)
        assert mock_model.last_audio.dtype == np.float32
        np.testing.assert_allclose(
            mock_model.last_audio, np.array([0.5, -0.5], dtype=np.float32)
        )

    def test_transcribe_stream_float64_conversion(self) -> None:
        """float64 等の配列が float32 にキャストされて WhisperModel に渡されることを確認。"""
        audio_f64 = np.array([0.25, -0.75], dtype=np.float64)
        mock_model = MockWhisperModel()
        transcriber = FasterWhisperProvider(model=mock_model)

        transcriber.transcribe_stream(audio_f64)
        assert mock_model.last_audio.dtype == np.float32
        np.testing.assert_allclose(
            mock_model.last_audio, np.array([0.25, -0.75], dtype=np.float32)
        )

    def test_transcribe_stream_empty_and_unloaded_raises(self) -> None:
        """空配列および unload 状態での例外送出を検証。"""
        transcriber = FasterWhisperProvider(model=MockWhisperModel())
        with pytest.raises(ValueError, match="入力音声データが空です"):
            transcriber.transcribe_stream(np.array([], dtype=np.float32))

        transcriber.unload()
        with pytest.raises(RuntimeError, match="モデルがロードされていません"):
            transcriber.transcribe_stream(np.zeros(1600, dtype=np.float32))

    def test_unload_and_cuda_cleanup(self) -> None:
        """unload() で CUDA empty_cache が安全に呼ばれることを確認。"""
        transcriber = FasterWhisperProvider(model=MockWhisperModel())
        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.empty_cache") as mock_empty_cache,
        ):
            transcriber.unload()
            mock_empty_cache.assert_called_once()
        assert transcriber._model is None

    def test_unload_import_error_safe(self) -> None:
        """unload() で torch インポートエラーが発生しても例外とならないことを確認。"""
        orig_import = builtins.__import__

        def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "torch":
                raise ImportError("torch not installed")
            return orig_import(name, *args, **kwargs)

        transcriber = FasterWhisperProvider(model=MockWhisperModel())
        with patch("builtins.__import__", side_effect=fake_import):
            transcriber.unload()
        assert transcriber._model is None


def test_vad_progress_handler() -> None:
    """VadProgressHandler のログメッセージパースおよび on_progress=None を検証。"""
    # 1. on_progress is None
    handler_none = VadProgressHandler(on_progress=None)
    mock_log = MagicMock()
    mock_log.getMessage.return_value = (
        "VAD filter kept the following audio segments: 1.000s - 2.500s"
    )
    handler_none.emit(mock_log)

    # 2. normal parsing
    chunks: list[tuple[float, float]] = []
    handler = VadProgressHandler(on_progress=lambda stage, msg: chunks.extend(msg))
    handler.emit(mock_log)
    assert chunks == [(1.0, 2.5)]

    # 3. other log
    mock_log.getMessage.return_value = "other log"
    handler.emit(mock_log)
    assert chunks == [(1.0, 2.5)]

    # 4. timestamp > 10000 normalization
    mock_log.getMessage.return_value = (
        "VAD filter kept the following audio segments: 16000.000s - 32000.000s"
    )
    handler.emit(mock_log)
    assert chunks[-1] == (1.0, 2.0)
