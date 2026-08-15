import logging
from unittest.mock import MagicMock, patch

from audio_transcriber.stt import (
    FasterWhisperProvider,
    VadProgressHandler,
)


def test_vad_progress_handler():
    handler = VadProgressHandler(on_progress=None)

    mock_log = MagicMock()
    mock_log.getMessage.return_value = (
        "VAD filter kept the following audio segments: 1.000s - 2.500s"
    )
    handler.emit(mock_log)  # doesn't do anything because on_progress is None

    chunks = []
    handler = VadProgressHandler(on_progress=lambda stage, msg: chunks.extend(msg))
    handler.emit(mock_log)
    assert chunks == [(1.0, 2.5)]

    mock_log.getMessage.return_value = "other log"
    handler.emit(mock_log)
    assert chunks == [(1.0, 2.5)]

    # Test timestamp > 10000 normalization (divided by 16000.0)
    mock_log.getMessage.return_value = (
        "VAD filter kept the following audio segments: 16000.000s - 40000.000s"
    )
    handler.emit(mock_log)
    assert chunks == [(1.0, 2.5), (1.0, 2.5)]


def test_faster_whisper_provider_cpu_fallback():

    # It should convert int8_float16 to int8 on cpu
    provider = FasterWhisperProvider(
        model_size="tiny", device="cpu", compute_type="int8_float16"
    )
    assert provider.compute_type == "int8"


@patch("faster_whisper.audio.decode_audio")
@patch("faster_whisper.vad.get_speech_timestamps")
def test_faster_whisper_provider_vad_precalc(mock_get_speech, mock_decode, tmp_path):
    mock_decode.return_value = ([0.0, 0.0], 16000)
    mock_get_speech.return_value = [{"start": 0.0, "end": 24000.0}]

    mock_model = MagicMock()

    class DummyWord:
        start = 0.0
        end = 1.0
        word = "test"
        probability = 0.99

    class DummySegment:
        id = 1
        start = 0.0
        end = 1.0
        text = "test"
        no_speech_prob = 0.01
        compression_ratio = 1.0
        words = (DummyWord(),)

    mock_model.transcribe.return_value = ([DummySegment()], {})
    provider = FasterWhisperProvider(model=mock_model)
    audio_file = tmp_path / "test.wav"
    audio_file.write_text("dummy")

    called_progress = None
    called_segment = None

    def on_prog(stage, msg):
        nonlocal called_progress
        if stage == "vad_chunks":
            called_progress = msg

    def on_seg(seg):
        nonlocal called_segment
        called_segment = seg

    res = provider.transcribe_file(audio_file, on_progress=on_prog, on_segment=on_seg)
    assert called_progress == [(0.0, 1.5)]
    assert called_segment is not None
    assert res[0]["words"][0]["word"] == "test"


@patch("faster_whisper.audio.decode_audio")
@patch("faster_whisper.vad.get_speech_timestamps")
def test_faster_whisper_provider_vad_precalc_error(
    mock_get_speech, mock_decode, tmp_path, caplog
):
    mock_decode.return_value = ([0.0, 0.0], 16000)
    mock_get_speech.side_effect = Exception("test error")

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], {})
    provider = FasterWhisperProvider(model=mock_model)
    audio_file = tmp_path / "test.wav"
    audio_file.write_text("dummy")

    with caplog.at_level(logging.WARNING):
        provider.transcribe_file(audio_file, on_progress=lambda s, m: None)

    assert "VAD情報の事前取得に失敗しました: test error" in caplog.text


def test_faster_whisper_provider_unload():
    mock_model = MagicMock()
    provider = FasterWhisperProvider(model=mock_model)
    with (
        patch("torch.cuda.is_available", return_value=True),
        patch("torch.cuda.empty_cache") as mock_empty,
    ):
        provider.unload()
        mock_empty.assert_called_once()
    assert provider._model is None


def test_faster_whisper_provider_unload_import_error():
    import builtins

    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "torch":
            raise ImportError("mock error")
        return original_import(name, *args, **kwargs)

    mock_model = MagicMock()
    provider = FasterWhisperProvider(model=mock_model)
    with patch("builtins.__import__", side_effect=mock_import):
        provider.unload()
    assert provider._model is None


@patch("faster_whisper.audio.decode_audio")
@patch("faster_whisper.vad.get_speech_timestamps")
def test_faster_whisper_provider_vad_precalc_no_tuple(
    mock_get_speech, mock_decode, tmp_path
):
    mock_decode.return_value = [0.0, 0.0]  # not a tuple
    mock_get_speech.return_value = [{"start": 0.0, "end": 24000.0}]

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], {})
    provider = FasterWhisperProvider(model=mock_model)
    audio_file = tmp_path / "test.wav"
    audio_file.write_text("dummy")

    called_progress = None

    def on_prog(stage, msg):
        nonlocal called_progress
        if stage == "vad_chunks":
            called_progress = msg

    provider.transcribe_file(audio_file, on_progress=on_prog)
    assert called_progress == [(0.0, 1.5)]


def test_transcriber_properties():
    mock_model = MagicMock()
    provider = FasterWhisperProvider(
        model=mock_model, language="en", condition_on_previous_text=False
    )
    assert provider.language == "en"
    assert provider.condition_on_previous_text is False
