"""Adversarial stress and edge-case tests for configuration parsing and validation.

設定管理・パラメータ変換・境界値バリデーション・MAX_SEGMENT_CHARS完全撤廃の
ストレステストおよびエッジケース検証を提供します。
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from audio_transcriber.config import (
    AppConfig,
    MasteringConfig,
    MediaConfig,
    ModelConfig,
    PipelineConfig,
    PostProcessConfig,
    StreamConfig,
    StreamContextConfig,
    SubtitleConfig,
    TranscribeConfig,
    VadConfig,
    parse_config_dict,
)


def test_dict_path_omitted() -> None:
    """辞書パスが未指定の場合、None になることを検証する。"""
    cfg = parse_config_dict({})
    assert cfg.paths.custom_dict_path is None
    assert cfg.custom_dict_path is None


def test_dict_path_in_path_section() -> None:
    """[path] セクションの custom_dict_path が正しくパースされることを検証する。"""
    cfg = parse_config_dict({"path": {"custom_dict_path": "data/root_dict.toml"}})
    assert cfg.paths.custom_dict_path == Path("data/root_dict.toml")
    assert cfg.custom_dict_path == Path("data/root_dict.toml")


def test_dict_path_aliases_in_path_section() -> None:
    """[path] セクションのエイリアスキー（custom_dictionary_path, dictionary_path）が解決されることを検証する。"""
    cfg1 = parse_config_dict({"path": {"custom_dictionary_path": "data/alias1.toml"}})
    assert cfg1.paths.custom_dict_path == Path("data/alias1.toml")
    assert cfg1.custom_dict_path == Path("data/alias1.toml")

    cfg2 = parse_config_dict({"path": {"dictionary_path": "data/alias2.toml"}})
    assert cfg2.paths.custom_dict_path == Path("data/alias2.toml")
    assert cfg2.custom_dict_path == Path("data/alias2.toml")


def test_dict_path_section_alias_paths() -> None:
    """セクション名エイリアス [paths] でも辞書パスが解決されることを検証する。"""
    cfg = parse_config_dict({"paths": {"custom_dict_path": "data/section_dict.toml"}})
    assert cfg.paths.custom_dict_path == Path("data/section_dict.toml")
    assert cfg.custom_dict_path == Path("data/section_dict.toml")


def test_dict_path_special_characters_and_paths(tmp_path: Path) -> None:
    """スペースや日本語を含む特殊パス、相対・絶対パスが正しく Path オブジェクトに変換されることを検証する。"""
    special_rel = "data/カスタム 辞書/dict (v1.0).toml"
    special_abs = str(tmp_path / "辞書 ディレクトリ" / "custom.toml")

    cfg_rel = parse_config_dict({"path": {"custom_dict_path": special_rel}})
    assert cfg_rel.paths.custom_dict_path == Path(special_rel)
    assert cfg_rel.custom_dict_path == Path(special_rel)

    cfg_abs = parse_config_dict({"path": {"custom_dict_path": special_abs}})
    assert cfg_abs.paths.custom_dict_path == Path(special_abs)
    assert cfg_abs.custom_dict_path == Path(special_abs)


def test_float_zero_values_preserved() -> None:
    """0.0 が許容される浮動小数点値がデフォルト値にフォールバックせず 0.0 として維持されることを検証する。"""
    raw_data = {
        "transcribe": {
            "no_speech_threshold": 0.0,
            "vad": {"vad_threshold": 0.0},
        },
        "post_process": {
            "no_speech_threshold": 0.0,
        },
        "subtitle": {
            "end_padding": 0.0,
            "min_gap": 0.0,
        },
    }
    cfg = parse_config_dict(raw_data)

    assert cfg.transcribe.no_speech_threshold == 0.0
    assert cfg.transcribe.vad.vad_threshold == 0.0
    assert cfg.post_process.no_speech_threshold == 0.0
    assert cfg.subtitle.end_padding == 0.0
    assert cfg.subtitle.min_gap == 0.0


def test_float_integer_inputs_converted_to_float() -> None:
    """整数で渡された数値が正しく float に変換されることを検証する。"""
    raw_data = {
        "transcribe": {
            "no_speech_threshold": 1,
            "vad": {"vad_threshold": 0},
        },
        "post_process": {
            "no_speech_threshold": 1,
            "max_chars_per_second": 15,
        },
        "subtitle": {
            "end_padding": 2,
            "min_duration": 3,
            "min_gap": 0,
        },
    }
    cfg = parse_config_dict(raw_data)

    assert isinstance(cfg.transcribe.no_speech_threshold, float)
    assert cfg.transcribe.no_speech_threshold == 1.0
    assert isinstance(cfg.transcribe.vad.vad_threshold, float)
    assert cfg.transcribe.vad.vad_threshold == 0.0
    assert isinstance(cfg.post_process.no_speech_threshold, float)
    assert cfg.post_process.no_speech_threshold == 1.0
    assert isinstance(cfg.post_process.max_chars_per_second, float)
    assert cfg.post_process.max_chars_per_second == 15.0
    assert isinstance(cfg.subtitle.end_padding, float)
    assert cfg.subtitle.end_padding == 2.0
    assert isinstance(cfg.subtitle.min_duration, float)
    assert cfg.subtitle.min_duration == 3.0
    assert isinstance(cfg.subtitle.min_gap, float)
    assert cfg.subtitle.min_gap == 0.0


def test_float_string_representations() -> None:
    """文字列形式の浮動小数点数値が正しく float に変換されることを検証する。"""
    raw_data = {
        "transcribe": {"no_speech_threshold": "0.75"},
        "post_process": {
            "no_speech_threshold": "0.85",
            "max_chars_per_second": "20.5",
        },
        "subtitle": {
            "end_padding": "1.25",
            "min_duration": "2.75",
            "min_gap": "0.025",
        },
    }
    cfg = parse_config_dict(raw_data)

    assert cfg.transcribe.no_speech_threshold == 0.75
    assert cfg.post_process.no_speech_threshold == 0.85
    assert cfg.post_process.max_chars_per_second == 20.5
    assert cfg.subtitle.end_padding == 1.25
    assert cfg.subtitle.min_duration == 2.75
    assert cfg.subtitle.min_gap == 0.025


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


def test_all_boolean_flags_true_and_false() -> None:
    """全ブールフラグが明示的な True / False に正しく解釈されることを検証する。"""
    cfg_true = parse_config_dict(
        {
            "pipeline": {"remux": True},
            "transcribe": {
                "condition_on_previous_text": True,
            },
            "post_process": {
                "replace_terms": True,
                "lower": True,
                "remove_punct": True,
            },
        }
    )
    assert cfg_true.pipeline.remux is True
    assert cfg_true.transcribe.condition_on_previous_text is True
    assert (
        cfg_true.post_process.replace_terms,
        cfg_true.post_process.lower,
        cfg_true.post_process.remove_punct,
    ) == (True, True, True)

    cfg_false = parse_config_dict(
        {
            "pipeline": {"remux": False},
            "transcribe": {
                "condition_on_previous_text": False,
            },
            "post_process": {
                "replace_terms": False,
                "lower": False,
                "remove_punct": False,
            },
        }
    )
    assert cfg_false.pipeline.remux is False
    assert cfg_false.transcribe.condition_on_previous_text is False
    assert (
        cfg_false.post_process.replace_terms,
        cfg_false.post_process.lower,
        cfg_false.post_process.remove_punct,
    ) == (False, False, False)


def test_boolean_flags_from_integers() -> None:
    """整数 1 / 0 がそれぞれ True / False に評価されることを検証する。"""
    cfg = parse_config_dict(
        {
            "pipeline": {"remux": 0},
            "transcribe": {
                "condition_on_previous_text": 0,
            },
            "post_process": {
                "replace_terms": 0,
                "lower": 1,
                "remove_punct": 1,
            },
        }
    )
    assert cfg.pipeline.remux is False
    assert cfg.transcribe.condition_on_previous_text is False
    assert (
        cfg.post_process.replace_terms,
        cfg.post_process.lower,
        cfg.post_process.remove_punct,
    ) == (False, True, True)


def test_subtitle_formats_permutations() -> None:
    """formats パラメータの多様な入力形式（リスト、空白付き、大文字、カンマ区切り文字列）の解釈を検証する。"""
    cfg1 = parse_config_dict({"subtitle": {"formats": [" SRT ", "VTT", " JSON "]}})
    assert cfg1.subtitle.formats == ["srt", "vtt", "json"]

    cfg2 = parse_config_dict({"subtitle": {"formats": " SRT, vtt , JSON "}})
    assert cfg2.subtitle.formats == ["srt", "vtt", "json"]

    cfg3 = parse_config_dict({"subtitle": {"formats": "srt"}})
    assert cfg3.subtitle.formats == ["srt"]

    cfg4 = parse_config_dict({"subtitle": {"formats": "srt, , , vtt, "}})
    assert cfg4.subtitle.formats == ["srt", "vtt"]

    cfg5 = parse_config_dict({"subtitle": {"formats": None}})
    assert cfg5.subtitle.formats == ["srt", "vtt", "json"]

    cfg6 = parse_config_dict({"subtitle": {"formats": 999}})
    assert cfg6.subtitle.formats == ["srt", "vtt", "json"]


def test_max_segment_chars_cannot_be_instantiated_on_dataclasses() -> None:
    """全データクラスに max_segment_chars 引数を渡すと TypeError が発生することを検証する。"""
    classes_to_test = [
        PostProcessConfig,
        SubtitleConfig,
        AppConfig,
        TranscribeConfig,
        PipelineConfig,
        MediaConfig,
        ModelConfig,
        VadConfig,
    ]

    for cls in classes_to_test:
        field_names = [f.name for f in dataclasses.fields(cls)]
        assert "max_segment_chars" not in field_names
        assert "MAX_SEGMENT_CHARS" not in field_names

        with pytest.raises(TypeError, match="unexpected keyword argument"):
            cls(max_segment_chars=30)  # type: ignore[call-arg]


def test_max_segment_chars_in_dict_is_safely_ignored_everywhere() -> None:
    """TOML/辞書のルートおよび各セクションに max_segment_chars が含まれていても無視されることを検証する。"""
    raw_data = {
        "MAX_SEGMENT_CHARS": 30,
        "max_segment_chars": 30,
        "pipeline": {"max_segment_chars": 30},
        "media": {"max_segment_chars": 30},
        "model": {"max_segment_chars": 30},
        "transcribe": {"max_segment_chars": 30},
        "post_process": {"max_segment_chars": 30, "MAX_SEGMENT_CHARS": 30},
        "subtitle": {"max_segment_chars": 30},
    }

    cfg = parse_config_dict(raw_data)

    assert not hasattr(cfg, "max_segment_chars")
    assert not hasattr(cfg.pipeline, "max_segment_chars")
    assert not hasattr(cfg.media, "max_segment_chars")
    assert not hasattr(cfg.model, "max_segment_chars")
    assert not hasattr(cfg.transcribe, "max_segment_chars")
    assert not hasattr(cfg.post_process, "max_segment_chars")
    assert not hasattr(cfg.subtitle, "max_segment_chars")
