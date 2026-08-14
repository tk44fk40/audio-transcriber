"""SpeechTranscriber および STT 関連 Protocol の単体テスト。"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from audio_transcriber.stt import (
    SpeechTranscriber,
    TranscriberProtocol,
    WhisperModelProtocol,
)


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


class MockWhisperModel:
    """WhisperModelProtocol に適合するモックモデル。"""

    def __init__(self) -> None:
        self.transcribe_called = False
        self.last_audio: Any = None
        self.last_kwargs: dict[str, Any] = {}

    def transcribe(
        self,
        audio: Any,
        **kwargs: Any,
    ) -> tuple[Iterator[MockSegment], MagicMock]:
        """推論モックメソッド。"""
        self.transcribe_called = True
        self.last_audio = audio
        self.last_kwargs = kwargs

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
        # Arrange
        model = MockWhisperModel()

        # Act & Assert
        assert isinstance(model, WhisperModelProtocol)

    def test_speech_transcriber_protocol_check(self) -> None:
        """SpeechTranscriber が TranscriberProtocol を満たすことを確認します。"""
        # Arrange
        mock_model = MockWhisperModel()
        transcriber = SpeechTranscriber(model=mock_model)

        # Act & Assert
        assert isinstance(transcriber, TranscriberProtocol)


class TestSpeechTranscriber:
    """SpeechTranscriber クラスの機能テスト。"""

    def test_init_with_injected_model(self) -> None:
        """DI により外部からモデルを注入して初期化できることを確認します。"""
        # Arrange
        mock_model = MockWhisperModel()

        # Act
        transcriber = SpeechTranscriber(
            model_name="small",
            language="ja",
            vad_filter=True,
            model=mock_model,
        )

        # Assert
        assert transcriber.model_name == "small"
        assert transcriber.language == "ja"
        assert transcriber.vad_filter is True
        assert transcriber._model is mock_model

    def test_init_creates_default_model(self) -> None:
        """モデルが指定されない場合、内部で faster-whisper WhisperModel を生成することを確認します。"""
        # Arrange & Act
        with patch("audio_transcriber.stt.WhisperModel") as mock_cls:
            transcriber = SpeechTranscriber(model_name="tiny", device="cpu")

            # Assert
            mock_cls.assert_called_once_with(
                "tiny", device="cpu", compute_type="default"
            )
            assert transcriber._model is mock_cls.return_value

    def test_transcribe_waveform_success(self) -> None:
        """波形データからの文字起こしが正常に RecognizedSegment リストを返すことを確認します。"""
        # Arrange
        mock_model = MockWhisperModel()
        transcriber = SpeechTranscriber(model=mock_model)
        waveform = np.zeros(16000, dtype=np.float32)

        # Act
        results = transcriber.transcribe_waveform(waveform, sample_rate=16000)

        # Assert
        assert len(results) == 2
        assert results[0].start == 0.0
        assert results[0].end == 1.5
        assert results[0].text == "こんにちは"
        assert results[1].start == 1.5
        assert results[1].end == 3.0
        assert results[1].text == "世界"
        assert mock_model.transcribe_called is True
        assert mock_model.last_kwargs.get("language") == "ja"

    def test_transcribe_waveform_empty_raises_value_error(self) -> None:
        """空の波形を渡した際に ValueError が発生することを確認します。"""
        # Arrange
        mock_model = MockWhisperModel()
        transcriber = SpeechTranscriber(model=mock_model)
        empty_waveform = np.array([], dtype=np.float32)

        # Act & Assert
        with pytest.raises(ValueError, match="波形データが空です"):
            transcriber.transcribe_waveform(empty_waveform)

    def test_transcribe_file_success(self, tmp_path: Path) -> None:
        """音声ファイルパスからの文字起こしが正常に動作することを確認します。"""
        # Arrange
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"dummy audio data")
        mock_model = MockWhisperModel()
        transcriber = SpeechTranscriber(model=mock_model)

        # Act
        results = transcriber.transcribe_file(audio_file)

        # Assert
        assert len(results) == 2
        assert results[0].text == "こんにちは"
        assert mock_model.transcribe_called is True
        assert mock_model.last_audio == str(audio_file)

    def test_transcribe_file_not_found_raises_error(self, tmp_path: Path) -> None:
        """存在しないファイルパスを渡した場合に FileNotFoundError が発生することを確認します。"""
        # Arrange
        non_existent = tmp_path / "non_existent.wav"
        mock_model = MockWhisperModel()
        transcriber = SpeechTranscriber(model=mock_model)

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            transcriber.transcribe_file(non_existent)

    def test_unload_and_close(self) -> None:
        """unload() および close() でモデルが解放され、その後の推論でエラーになることを確認します。"""
        # Arrange
        mock_model = MockWhisperModel()
        transcriber = SpeechTranscriber(model=mock_model)

        # Act
        transcriber.unload()

        # Assert
        assert transcriber._model is None
        with pytest.raises(RuntimeError, match="モデルがロードされていません"):
            transcriber.transcribe_waveform(np.zeros(16000, dtype=np.float32))

        # close() を再度呼んでも安全（二重解放防止）
        transcriber.close()

    def test_context_manager(self) -> None:
        """with 構文で安全にライフサイクル管理され自動解放されることを確認します。"""
        # Arrange
        mock_model = MockWhisperModel()

        # Act & Assert
        with SpeechTranscriber(model=mock_model) as transcriber:
            assert transcriber._model is mock_model
            results = transcriber.transcribe_waveform(np.zeros(16000, dtype=np.float32))
            assert len(results) == 2

        assert transcriber._model is None
