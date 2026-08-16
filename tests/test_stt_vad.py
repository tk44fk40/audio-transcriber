"""FasterWhisperProvider における VAD 検出連携およびログハンドラの単体テスト。"""

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from audio_transcriber.stt import FasterWhisperProvider, VadProgressHandler


class DummyWhisperModel:
    """テスト用ダミーモデル。"""

    def transcribe(self, audio: Any, **kwargs: Any) -> tuple[list[Any], MagicMock]:
        """ダミー推論結果を返します。"""
        _ = (audio, kwargs)
        info = MagicMock()
        info.language = "ja"
        return [], info


def test_stt_transcribe_file_vad_chunk_detection(tmp_path: Path) -> None:
    """transcribe_file で VAD 検出が実行され vad_chunks が通知されることを検証。"""
    # Arrange
    audio_file = tmp_path / "test.wav"
    audio_file.write_bytes(b"dummy wav data")
    transcriber = FasterWhisperProvider(
        model=DummyWhisperModel(), vad_parameters={"threshold": 0.5}
    )

    progress_events: list[tuple[str, Any]] = []

    mock_timestamps = [{"start": 16000, "end": 48000}]
    with (
        patch(
            "faster_whisper.audio.decode_audio",
            return_value=np.zeros(48000, dtype=np.float32),
        ),
        patch("faster_whisper.vad.get_vad_model"),
        patch("faster_whisper.vad.get_speech_timestamps", return_value=mock_timestamps),
    ):
        # Act
        transcriber.transcribe_file(
            audio_file,
            on_progress=lambda stage, msg: progress_events.append((stage, msg)),
        )

    # Assert
    assert len(progress_events) == 1
    assert progress_events[0][0] == "vad_chunks"
    assert progress_events[0][1] == [(1.0, 3.0)]


def test_stt_transcribe_file_vad_tuple_audio(tmp_path: Path) -> None:
    """decode_audio が tuple を返した場合の VAD 検出処理を検証。"""
    # Arrange
    audio_file = tmp_path / "test.wav"
    audio_file.write_bytes(b"dummy wav data")
    transcriber = FasterWhisperProvider(model=DummyWhisperModel(), vad_parameters=None)

    progress_events: list[tuple[str, Any]] = []

    with (
        patch(
            "faster_whisper.audio.decode_audio",
            return_value=(np.zeros(16000), np.zeros(16000)),
        ),
        patch("faster_whisper.vad.get_vad_model"),
        patch(
            "faster_whisper.vad.get_speech_timestamps",
            return_value=[{"start": 0, "end": 16000}],
        ),
    ):
        transcriber.transcribe_file(
            audio_file,
            on_progress=lambda stage, msg: progress_events.append((stage, msg)),
        )
    assert len(progress_events) == 1
    assert progress_events[0][1] == [(0.0, 1.0)]


def test_stt_transcribe_file_vad_failure_logs_error_and_yields_no_chunks(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """VAD 検出処理で例外が発生した際に error ログが記録され vad_chunks が通知されないことを検証。"""
    # Arrange
    audio_file = tmp_path / "test.wav"
    audio_file.write_bytes(b"dummy wav data")
    transcriber = FasterWhisperProvider(model=DummyWhisperModel(), vad_parameters=None)

    # Act
    with (
        patch(
            "faster_whisper.audio.decode_audio", side_effect=RuntimeError("VAD failed")
        ),
        caplog.at_level(logging.ERROR),
    ):
        transcriber.transcribe_file(
            audio_file,
            on_progress=lambda stage, msg: None,
        )

    # Assert
    assert "VAD チャンク検出処理に失敗しました: VAD failed" in caplog.text


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
