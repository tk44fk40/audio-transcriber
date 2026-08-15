"""End-to-End configuration loading and parameter validation tests.

設定ファイル読み込み、後処理・字幕パラメータ、および MAX_SEGMENT_CHARS 廃止の検証を行います。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from audio_transcriber.config import (
    AppConfig,
    PostProcessConfig,
    SubtitleConfig,
    load_config,
    parse_config_dict,
)


def test_config_max_segment_chars_completely_removed() -> None:
    """MAX_SEGMENT_CHARS パラメータが各設定クラスから完全に除外されていることを検証する。"""
    # Arrange & Act
    app_cfg = AppConfig()
    post_cfg = PostProcessConfig()
    sub_cfg = SubtitleConfig()

    # Assert
    assert not hasattr(app_cfg, "max_segment_chars")
    assert not hasattr(app_cfg, "MAX_SEGMENT_CHARS")
    assert not hasattr(post_cfg, "max_segment_chars")
    assert not hasattr(sub_cfg, "max_segment_chars")


def test_config_legacy_toml_with_max_segment_chars_ignored() -> None:
    """旧バージョンの MAX_SEGMENT_CHARS を含む TOML が
    エラーなく解釈され無視されることを検証する。
    """
    # Arrange
    legacy_toml_data = {
        "MAX_SEGMENT_CHARS": 30,
        "POST_PROCESS": {
            "MAX_SEGMENT_CHARS": 30,
        },
    }

    # Act
    cfg = parse_config_dict(legacy_toml_data)

    # Assert
    assert not hasattr(cfg, "max_segment_chars")
    assert not hasattr(cfg.post_process, "max_segment_chars")


def test_config_post_process_parameters_parsing() -> None:
    """後処理パラメータ群(サニタイズ・置換・正規化)が正しくパースされることを検証する。"""
    # Arrange
    raw_data = {
        "PATH": {
            "CUSTOM_DICT_PATH": "/path/to/custom_dict.toml",
        },
        "POST_PROCESS": {
            "REPLACE_TERMS": False,
            "LOWER": True,
            "REMOVE_PUNCT": True,
            "NO_SPEECH_THRESHOLD": 0.75,
            "MAX_CHARS_PER_SECOND": 15.5,
        },
    }

    # Act
    cfg = parse_config_dict(raw_data)
    post_cfg = cfg.post_process

    # Assert
    assert cfg.paths.custom_dict_path == Path("/path/to/custom_dict.toml")
    assert cfg.custom_dict_path == Path("/path/to/custom_dict.toml")
    assert post_cfg.replace_terms is False
    assert post_cfg.lower is True
    assert post_cfg.remove_punct is True
    assert post_cfg.no_speech_threshold == 0.75
    assert post_cfg.max_chars_per_second == 15.5


def test_config_subtitle_parameters_parsing() -> None:
    """字幕タイミング補正およびフォーマットリストが正しくパースされることを検証する。"""
    # Arrange
    raw_data = {
        "SUBTITLE": {
            "END_PADDING": 2.0,
            "MIN_DURATION": 2.5,
            "MIN_GAP": 0.1,
            "FORMATS": ["srt", "vtt", "json"],
        }
    }

    # Act
    cfg = parse_config_dict(raw_data)
    sub_cfg = cfg.subtitle

    # Assert
    assert sub_cfg.end_padding == 2.0
    assert sub_cfg.min_duration == 2.5
    assert sub_cfg.min_gap == 0.1
    assert sub_cfg.formats == ["srt", "vtt", "json"]


def test_config_formats_comma_string_parsing() -> None:
    """字幕フォーマットがカンマ区切り文字列で指定された場合にリストへ変換されることを検証する。"""
    # Arrange
    raw_data = {
        "subtitle": {
            "formats": "srt, vtt, json",
        }
    }

    # Act
    cfg = parse_config_dict(raw_data)

    # Assert
    assert cfg.subtitle.formats == ["srt", "vtt", "json"]


def test_config_case_insensitivity_and_aliases() -> None:
    """大文字小文字の違いやエイリアスセクション名が柔軟に解決されることを検証する。"""
    # Arrange
    raw_data = {
        "postprocess": {
            "replace_terms": False,
            "no_speech_threshold": 0.8,
        },
        "subtitles": {
            "end_padding": 0.5,
            "min_duration": 1.2,
        },
    }

    # Act
    cfg = parse_config_dict(raw_data)

    # Assert
    assert cfg.post_process.replace_terms is False
    assert cfg.post_process.no_speech_threshold == 0.8
    assert cfg.subtitle.end_padding == 0.5
    assert cfg.subtitle.min_duration == 1.2


def test_config_file_not_found_raises_error(tmp_path: Path) -> None:
    """指定された設定ファイルが存在しない場合に FileNotFoundError を送出することを検証する。"""
    # Arrange
    missing_file = tmp_path / "nonexistent_config.toml"

    # Act & Assert
    with pytest.raises(FileNotFoundError) as exc_info:
        load_config(missing_file)
    assert "Configuration file not found" in str(exc_info.value)


def test_config_invalid_toml_syntax_raises_error(tmp_path: Path) -> None:
    """構文が不正な TOML ファイルが指定された場合に ValueError を送出することを検証する。"""
    # Arrange
    corrupt_file = tmp_path / "broken_config.toml"
    corrupt_file.write_text("THIS IS NOT A VALID TOML [[[ ]", encoding="utf-8")

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        load_config(corrupt_file)
    assert "Failed to parse TOML configuration" in str(exc_info.value)


def test_config_boundary_numeric_values() -> None:
    """境界値となる数値パラメータが正しく float / int へ型変換されることを検証する。"""
    # Arrange
    raw_data = {
        "post_process": {
            "no_speech_threshold": "0.0",
            "max_chars_per_second": 0.0,
        },
        "subtitle": {
            "end_padding": 0,
            "min_duration": "0.0",
            "min_gap": 0.001,
        },
    }

    # Act
    cfg = parse_config_dict(raw_data)

    # Assert
    assert cfg.post_process.no_speech_threshold == 0.0
    assert cfg.post_process.max_chars_per_second == 0.0
    assert cfg.subtitle.end_padding == 0.0
    assert cfg.subtitle.min_duration == 0.0
    assert cfg.subtitle.min_gap == 0.001
