"""設定パースおよびバリデーションにおける境界値エラー・独立性のストレステスト。"""

from __future__ import annotations

import pytest

from audio_transcriber.config import (
    MasteringConfig,
    MediaConfig,
    PostProcessConfig,
    StreamConfig,
    StreamContextConfig,
    SubtitleConfig,
    TranscribeConfig,
    VadConfig,
    parse_config_dict,
)


def test_validation_errors_on_invalid_boundaries() -> None:
    """無効な境界値を与えた場合に ValueError が正しく送出されることを網羅的に検証する。"""
    # 1. VadConfig
    with pytest.raises(ValueError, match="min_silence_duration_ms"):
        VadConfig(min_silence_duration_ms=0)
    with pytest.raises(ValueError, match="vad_threshold"):
        VadConfig(vad_threshold=-0.1)
    with pytest.raises(ValueError, match="vad_threshold"):
        VadConfig(vad_threshold=1.1)

    # 2. TranscribeConfig
    with pytest.raises(ValueError, match="beam_size"):
        TranscribeConfig(beam_size=0)
    with pytest.raises(ValueError, match="no_speech_threshold"):
        TranscribeConfig(no_speech_threshold=-0.1)
    with pytest.raises(ValueError, match="no_speech_threshold"):
        TranscribeConfig(no_speech_threshold=1.5)

    # 3. PostProcessConfig
    with pytest.raises(ValueError, match="no_speech_threshold"):
        PostProcessConfig(no_speech_threshold=-0.1)
    with pytest.raises(ValueError, match="max_chars_per_second"):
        PostProcessConfig(max_chars_per_second=0.0)

    # 4. SubtitleConfig
    with pytest.raises(ValueError, match="end_padding"):
        SubtitleConfig(end_padding=-0.1)
    with pytest.raises(ValueError, match="min_duration"):
        SubtitleConfig(min_duration=0.0)
    with pytest.raises(ValueError, match="min_gap"):
        SubtitleConfig(min_gap=-0.1)

    # 5. MediaConfig
    with pytest.raises(ValueError, match="mic_track"):
        MediaConfig(mic_track=0)
    with pytest.raises(ValueError, match="sample_rate"):
        MediaConfig(sample_rate=0)

    # 6. MasteringConfig
    with pytest.raises(ValueError, match="noise_gate_threshold"):
        MasteringConfig(noise_gate_threshold=-0.1)

    # 7. StreamContextConfig
    with pytest.raises(ValueError, match="context_max_length"):
        StreamContextConfig(context_max_length=0)
    with pytest.raises(ValueError, match="context_timeout_seconds"):
        StreamContextConfig(context_timeout_seconds=0.0)

    # 8. StreamConfig
    with pytest.raises(ValueError, match="chunk_size_ms"):
        StreamConfig(chunk_size_ms=0)
    with pytest.raises(ValueError, match="buffer_size_seconds"):
        StreamConfig(buffer_size_seconds=0.0)
    with pytest.raises(ValueError, match="sample_rate"):
        StreamConfig(sample_rate=0)
    with pytest.raises(ValueError, match="flush_timeout_ms"):
        StreamConfig(flush_timeout_ms=0)
    with pytest.raises(ValueError, match="word_gap_split_threshold"):
        StreamConfig(word_gap_split_threshold=-0.1)
    with pytest.raises(ValueError, match="chunk_min_seconds"):
        StreamConfig(chunk_min_seconds=0.0)
    with pytest.raises(ValueError, match="chunk_max_seconds"):
        StreamConfig(chunk_min_seconds=5.0, chunk_max_seconds=2.0)


def test_transcribe_and_post_process_thresholds_are_independent() -> None:
    """transcribe と post_process の no_speech_threshold が互いに干渉せず独立して設定されることを検証する。"""
    cfg1 = parse_config_dict(
        {
            "transcribe": {"no_speech_threshold": 0.4},
            "post_process": {"no_speech_threshold": 0.9},
        }
    )
    assert cfg1.transcribe.no_speech_threshold == 0.4
    assert cfg1.post_process.no_speech_threshold == 0.9

    cfg2 = parse_config_dict(
        {
            "transcribe": {"no_speech_threshold": 0.85},
        }
    )
    assert cfg2.transcribe.no_speech_threshold == 0.85
    assert cfg2.post_process.no_speech_threshold == 0.6
