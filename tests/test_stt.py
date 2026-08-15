"""FasterWhisperProvider および STT 関連 Protocol の単体テスト。"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from audio_transcriber.stt import (
    FasterWhisperProvider,
    TranscriberProvider,
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
        words: list[Any] | None = None,
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
            vad_filter=True,
            model=mock_model,
        )
        assert transcriber.model_size == "small"
        assert transcriber.language == "ja"
        assert transcriber.vad_filter is True
        assert transcriber._model is mock_model

    def test_init_creates_default_model(self) -> None:
        """モデルが指定されない場合、内部で faster-whisper WhisperModel を生成することを確認します。"""
        with patch("audio_transcriber.stt.WhisperModel") as mock_cls:
            transcriber = FasterWhisperProvider(
                model_size="tiny", device="cpu", compute_type="int8"
            )
            mock_cls.assert_called_once_with("tiny", device="cpu", compute_type="int8")
            assert transcriber._model is mock_cls.return_value

    def test_transcribe_with_prompt_and_vad_parameters(self, tmp_path: Path) -> None:
        """initial_prompt および vad_parameters が正しく kwargs に渡されることを確認します。"""
        mock_model = MockWhisperModel()
        transcriber = FasterWhisperProvider(
            model=mock_model,
            initial_prompt="ゲーム実況用語",
            vad_parameters={"threshold": 0.5},
        )
        f = tmp_path / "t.wav"
        f.touch()
        transcriber.transcribe_file(f)

        assert mock_model.last_kwargs.get("initial_prompt") == "ゲーム実況用語"
        assert mock_model.last_kwargs.get("vad_parameters") == {"threshold": 0.5}

    def test_transcribe_file_success(self, tmp_path: Path) -> None:
        """音声ファイルパスからの文字起こしが正常に動作することを確認します。"""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy audio data")
        mock_model = MockWhisperModel()
        transcriber = FasterWhisperProvider(model=mock_model)

        results = transcriber.transcribe_file(audio_file)

        assert len(results) == 2
        assert results[0]["text"] == "こんにちは"
        assert mock_model.transcribe_called is True
        assert mock_model.last_audio == str(audio_file)

    def test_transcribe_file_not_found_raises_error(self, tmp_path: Path) -> None:
        """存在しないファイルパスを渡した場合に FileNotFoundError が発生することを確認します。"""
        non_existent = tmp_path / "non_existent.wav"
        mock_model = MockWhisperModel()
        transcriber = FasterWhisperProvider(model=mock_model)

        with pytest.raises(FileNotFoundError):
            transcriber.transcribe_file(non_existent)

    def test_transcribe_file_model_none_raises_error(self, tmp_path: Path) -> None:
        """unload 後に transcribe_file を呼んだ場合 RuntimeError が発生することを確認します。"""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy audio data")
        mock_model = MockWhisperModel()
        transcriber = FasterWhisperProvider(model=mock_model)
        transcriber.unload()

        with pytest.raises(RuntimeError, match="モデルがロードされていません"):
            transcriber.transcribe_file(audio_file)

    def test_unload_and_close_with_cuda(self) -> None:
        """unload() で CUDA empty_cache が安全に呼ばれることを確認します。"""
        mock_model = MockWhisperModel()
        transcriber = FasterWhisperProvider(model=mock_model)

        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.empty_cache") as mock_empty_cache,
        ):
            transcriber.unload()
            mock_empty_cache.assert_called_once()

        assert transcriber._model is None
