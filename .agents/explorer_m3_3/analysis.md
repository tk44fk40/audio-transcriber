# Milestone 3 設定モジュール単体テスト設計・分析レポート

## 1. 概要 (Executive Summary)

本レポートは、`audio-transcriber` の Milestone 3 (Config Cleanup & Parameter Updates) における設定管理モジュール（`src/audio_transcriber/config.py`）の単体テスト（`tests/test_config.py`）の包括的設計と要件をまとめたものです。

`MAX_SEGMENT_CHARS` / `max_segment_chars` の完全廃止、新規追加される `PostProcessConfig` および `SubtitleConfig` の各フィールド（8項目および4項目）、大文字/小文字/エイリアス対応、部分設定時のデフォルト値フォールバック、異常系ハンドリングを網羅するテストケース群を策定しました。
また、プロジェクト規約（AAAパターン、Googleスタイル日本語Docstring、Python 3.11+ 厳格な型注釈、ファイル行数目標200行以下）を厳格に遵守した実装コードを提案します。

---

## 2. 現行 `tests/test_config.py` の分析と課題 (Current State & Gaps)

### 2.1 現行コードの構成
現行の `tests/test_config.py` は全171行で構成され、以下の7つのテスト関数が存在します：
1. `test_default_config_instance`: デフォルト値の確認（一部フィールドのみ）
2. `test_load_config_no_file_returns_default`: ファイル非存在時のデフォルト返却
3. `test_load_config_uppercase_toml`: UPPER_CASE TOML の読み込み（**90行目・124行目に `MAX_SEGMENT_CHARS` が残存**）
4. `test_load_config_default_file_in_cwd`: カレントディレクトリの `config.toml` 自動読み込み
5. `test_load_config_file_not_found`: `FileNotFoundError` の発生確認
6. `test_load_config_invalid_toml`: 構文エラー時の `ValueError` の発生確認
7. `test_parse_config_dict_empty`: 空辞書パース時のデフォルト値確認

### 2.2 検出された課題・不足点
1. **廃止対象パラメータの残存**:
   - `test_load_config_uppercase_toml` 内で `MAX_SEGMENT_CHARS = 25` を設定し、`assert cfg.post_process.max_segment_chars == 25` を検証している。
   - `MAX_SEGMENT_CHARS` が存在しないこと（`hasattr` が False、`dataclasses.fields` に含まれないこと）を明示的に検証するテストが存在しない。
2. **新規設定項目のテスト不足**:
   - `PostProcessConfig` の新フィールド（`custom_dict_path`, `no_speech_threshold`, `max_chars_per_second`）の検証がない。
   - `SubtitleConfig` の新フィールド（`formats`）の検証がない。
3. **セクションエイリアス・柔軟性の検証不足**:
   - `[postprocess]` や `[subtitles]` などのセクションエイリアスや、小文字キー、スネークケースキーの結合パース検証が不足。
4. **部分設定時のフォールバック検証不足**:
   - 1〜2項目のみを指定したTOMLにおいて、他の全項目が正しくデフォルト値へフォールバックされることの明示的検証がない。

---

## 3. Milestone 3 で要求される包括的単体テスト要件

### 3.1 デフォルト値の検証 (Default Configurations)
`PostProcessConfig`, `SubtitleConfig`, `AppConfig` および全サブ設定クラスのデフォルトインスタンス化を検証します。

| クラス | 検証対象フィールド | 期待デフォルト値 |
|---|---|---|
| `PostProcessConfig` | `custom_dict_path` | `None` |
| | `replace_terms` | `True` |
| | `normalize_nums` | `True` |
| | `to_hankaku` | `False` |
| | `lower` | `False` |
| | `remove_punct` | `False` |
| | `no_speech_threshold` | `0.6` |
| | `max_chars_per_second` | `12.0` |
| `SubtitleConfig` | `end_padding` | `1.0` |
| | `min_duration` | `1.5` |
| | `min_gap` | `0.05` |
| | `formats` | `["srt", "vtt", "json"]` |
| `AppConfig` | `output_dir` | `Path("./output")` |
| | `default_video_path` | `None` |
| | `debug_output_dir` | `None` |
| | `custom_dictionary_path` | `None` |
| | `pipeline.remux` | `True` |
| | `media.mic_track`, `sample_rate` | `2`, `48000` |
| | `model.model_size`, `device`, `compute_type` | `"small"`, `"cuda"`, `"float16"` |
| | `transcribe.language`, `beam_size`, `vad` 等 | `"ja"`, `5`, `VadConfig(...)` |

### 3.2 完全なカスタム TOML の読み込み検証 (Full Custom TOML)
全セクション・全キー（ルートパス、`[pipeline]`, `[media]`, `[model]`, `[transcribe]`, `[transcribe.vad]`, `[post_process]`, `[subtitle]`）を含む TOML を作成し、型変換（`Path`, `int`, `float`, `bool`, `str`, `list[str]`）およびネスト構造が正しく反映されることを検証。

### 3.3 部分設定とデフォルトフォールバック (Partial Configurations & Fallback)
一部のキー（例: `[post_process]` の `TO_HANKAKU = true`、`[subtitle]` の `MIN_GAP = 0.2`）のみが指定された TOML を読み込んだ際、指定キーが上書きされ、未指定キーがすべてデフォルト値として維持されることを検証。

### 3.4 大文字・小文字・エイリアス対応 (Case-insensitivity & Aliases)
- セクション名: `[post_process]`, `[postprocess]`, `[subtitle]`, `[subtitles]`
- キー名: `OUTPUT_DIR`, `output_dir`, `OutputDir`
- レガシープレフィックスキー: `post_process_replace_terms` / `replace_terms`, `subtitle_end_padding` / `end_padding`

### 3.5 `MAX_SEGMENT_CHARS` の完全廃止検証 (Absence of MAX_SEGMENT_CHARS)
1. `dataclasses.fields(PostProcessConfig)` 内に `"max_segment_chars"` が存在しないこと。
2. `PostProcessConfig()` および `AppConfig().post_process` に `hasattr(..., "max_segment_chars")` が `False` であること。
3. TOML ファイル内に `MAX_SEGMENT_CHARS = 25` が記述されていてもエラーにならず無視され、属性が設定されないこと。

### 3.6 異常系ハンドリング (Error Handling)
1. 存在しない設定ファイルパスを指定した場合に `FileNotFoundError` が発生すること。
2. 構文エラーを含む不正な TOML ファイルを指定した場合に `ValueError` が発生すること。
3. 空の辞書 `{}` を `parse_config_dict` に渡した場合に `AppConfig()` と一致すること。

---

## 4. 推奨テストコード設計 (`tests/test_config.py`)

以下の設計は、上記要件をすべて網羅しつつ、目標行数（<= 200行）を厳守した完成形です。

```python
"""Configuration loading and TOML parsing tests.

設定読み込みおよびTOMLパースの単体テストを提供します。
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from audio_transcriber.config import (
    AppConfig,
    MediaConfig,
    ModelConfig,
    PipelineConfig,
    PostProcessConfig,
    SubtitleConfig,
    TranscribeConfig,
    VadConfig,
    load_config,
    parse_config_dict,
)


def test_default_config_instances() -> None:
    """各設定データクラスのデフォルト値が正しく初期化されることを検証する。"""
    # Arrange & Act
    post_cfg = PostProcessConfig()
    sub_cfg = SubtitleConfig()
    app_cfg = AppConfig()

    # Assert - PostProcessConfig defaults
    assert post_cfg.custom_dict_path is None
    assert post_cfg.replace_terms is True
    assert post_cfg.normalize_nums is True
    assert post_cfg.to_hankaku is False
    assert post_cfg.lower is False
    assert post_cfg.remove_punct is False
    assert post_cfg.no_speech_threshold == 0.6
    assert post_cfg.max_chars_per_second == 12.0

    # Assert - SubtitleConfig defaults
    assert sub_cfg.end_padding == 1.0
    assert sub_cfg.min_duration == 1.5
    assert sub_cfg.min_gap == 0.05
    assert sub_cfg.formats == ["srt", "vtt", "json"]

    # Assert - AppConfig root defaults
    assert app_cfg.output_dir == Path("./output")
    assert app_cfg.default_video_path is None
    assert app_cfg.debug_output_dir is None
    assert app_cfg.custom_dictionary_path is None
    assert app_cfg.pipeline == PipelineConfig(remux=True)
    assert app_cfg.media == MediaConfig(mic_track=2, sample_rate=48000)
    assert app_cfg.model == ModelConfig(model_size="small", device="cuda", compute_type="float16")
    assert app_cfg.transcribe == TranscribeConfig(
        language="ja",
        beam_size=5,
        condition_on_previous_text=True,
        no_speech_threshold=0.6,
        initial_prompt=None,
        vad=VadConfig(vad_filter=True, min_silence_duration_ms=500, vad_threshold=0.5),
    )
    assert app_cfg.post_process == post_cfg
    assert app_cfg.subtitle == sub_cfg


def test_load_config_no_file_returns_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """設定ファイルが存在しない場合にデフォルト設定が返されることを検証する。"""
    # Arrange
    monkeypatch.chdir(tmp_path)

    # Act
    cfg = load_config(None)

    # Assert
    assert cfg == AppConfig()


def test_load_config_full_custom_toml(tmp_path: Path) -> None:
    """全セクション・全キーを含む完全なTOMLから設定が正常に読み込まれることを検証する。"""
    # Arrange
    toml_content = """
    OUTPUT_DIR = "/custom/output"
    DEFAULT_VIDEO_PATH = "data/custom.mp4"
    DEBUG_OUTPUT_DIR = "custom_debug"
    CUSTOM_DICTIONARY_PATH = "data/my_dict.toml"

    [pipeline]
    REMUX = false

    [media]
    MIC_TRACK = 3
    SAMPLE_RATE = 44100

    [model]
    MODEL_SIZE = "large-v3-turbo"
    DEVICE = "cpu"
    COMPUTE_TYPE = "int8"

    [transcribe]
    LANGUAGE = "en"
    BEAM_SIZE = 2
    CONDITION_ON_PREVIOUS_TEXT = false
    NO_SPEECH_THRESHOLD = 0.85
    INITIAL_PROMPT = "Custom prompt"

    [transcribe.vad]
    VAD_FILTER = false
    MIN_SILENCE_DURATION_MS = 800
    VAD_THRESHOLD = 0.4

    [post_process]
    CUSTOM_DICT_PATH = "data/custom_terms.json"
    REPLACE_TERMS = false
    NORMALIZE_NUMS = false
    TO_HANKAKU = true
    LOWER = true
    REMOVE_PUNCT = true
    NO_SPEECH_THRESHOLD = 0.7
    MAX_CHARS_PER_SECOND = 15.0

    [subtitle]
    END_PADDING = 0.8
    MIN_DURATION = 1.2
    MIN_GAP = 0.1
    FORMATS = ["srt", "vtt"]
    """
    config_file = tmp_path / "custom_config.toml"
    config_file.write_text(toml_content, encoding="utf-8")

    # Act
    cfg = load_config(config_file)

    # Assert
    assert cfg.output_dir == Path("/custom/output")
    assert cfg.default_video_path == Path("data/custom.mp4")
    assert cfg.debug_output_dir == Path("custom_debug")
    assert cfg.custom_dictionary_path == Path("data/my_dict.toml")
    assert cfg.pipeline.remux is False
    assert cfg.media.mic_track == 3
    assert cfg.media.sample_rate == 44100
    assert cfg.model.model_size == "large-v3-turbo"
    assert cfg.model.device == "cpu"
    assert cfg.model.compute_type == "int8"
    assert cfg.transcribe.language == "en"
    assert cfg.transcribe.beam_size == 2
    assert cfg.transcribe.condition_on_previous_text is False
    assert cfg.transcribe.no_speech_threshold == 0.85
    assert cfg.transcribe.initial_prompt == "Custom prompt"
    assert cfg.transcribe.vad.vad_filter is False
    assert cfg.transcribe.vad.min_silence_duration_ms == 800
    assert cfg.transcribe.vad.vad_threshold == 0.4
    assert cfg.post_process.custom_dict_path == Path("data/custom_terms.json")
    assert cfg.post_process.replace_terms is False
    assert cfg.post_process.normalize_nums is False
    assert cfg.post_process.to_hankaku is True
    assert cfg.post_process.lower is True
    assert cfg.post_process.remove_punct is True
    assert cfg.post_process.no_speech_threshold == 0.7
    assert cfg.post_process.max_chars_per_second == 15.0
    assert cfg.subtitle.end_padding == 0.8
    assert cfg.subtitle.min_duration == 1.2
    assert cfg.subtitle.min_gap == 0.1
    assert cfg.subtitle.formats == ["srt", "vtt"]


def test_load_config_partial_fallback(tmp_path: Path) -> None:
    """一部のキーのみ指定された場合に未指定キーがデフォルト値にフォールバックすることを検証する。"""
    # Arrange
    toml_content = """
    OUTPUT_DIR = "./custom_out"

    [post_process]
    TO_HANKAKU = true

    [subtitle]
    MIN_GAP = 0.2
    """
    config_file = tmp_path / "partial_config.toml"
    config_file.write_text(toml_content, encoding="utf-8")

    # Act
    cfg = load_config(config_file)

    # Assert
    assert cfg.output_dir == Path("./custom_out")
    assert cfg.post_process.to_hankaku is True
    assert cfg.post_process.replace_terms is True
    assert cfg.post_process.normalize_nums is True
    assert cfg.subtitle.min_gap == 0.2
    assert cfg.subtitle.end_padding == 1.0
    assert cfg.subtitle.min_duration == 1.5
    assert cfg.model.model_size == "small"
    assert cfg.transcribe.language == "ja"


def test_load_config_case_insensitivity_and_aliases(tmp_path: Path) -> None:
    """小文字・大文字・エイリアスセクション名での設定読み込みを検証する。"""
    # Arrange
    toml_content = """
    output_dir = "./lowercase_out"

    [postprocess]
    replace_terms = false
    to_hankaku = true

    [subtitles]
    end_padding = 0.5
    """
    config_file = tmp_path / "alias_config.toml"
    config_file.write_text(toml_content, encoding="utf-8")

    # Act
    cfg = load_config(config_file)

    # Assert
    assert cfg.output_dir == Path("./lowercase_out")
    assert cfg.post_process.replace_terms is False
    assert cfg.post_process.to_hankaku is True
    assert cfg.subtitle.end_padding == 0.5


def test_max_segment_chars_absent_and_ignored(tmp_path: Path) -> None:
    """MAX_SEGMENT_CHARS が設定クラスに存在せず、TOML指定時も無視されることを検証する。"""
    # Arrange
    post_cfg = PostProcessConfig()
    field_names = [f.name for f in dataclasses.fields(PostProcessConfig)]
    toml_content = """
    [post_process]
    MAX_SEGMENT_CHARS = 25
    TO_HANKAKU = true
    """
    config_file = tmp_path / "legacy_config.toml"
    config_file.write_text(toml_content, encoding="utf-8")

    # Act
    cfg = load_config(config_file)

    # Assert
    assert "max_segment_chars" not in field_names
    assert not hasattr(post_cfg, "max_segment_chars")
    assert not hasattr(cfg.post_process, "max_segment_chars")
    assert cfg.post_process.to_hankaku is True


def test_load_config_default_file_in_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """カレントディレクトリの config.toml が自動読み込みされることを検証する。"""
    # Arrange
    toml_content = """
    OUTPUT_DIR = "./local_out"
    [media]
    MIC_TRACK = 1
    """
    config_file = tmp_path / "config.toml"
    config_file.write_text(toml_content, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    # Act
    cfg = load_config(None)

    # Assert
    assert cfg.output_dir == Path("./local_out")
    assert cfg.media.mic_track == 1
    assert cfg.model.model_size == "small"


def test_load_config_file_not_found() -> None:
    """存在しない設定ファイルパスを指定した場合に FileNotFoundError が発生することを検証する。"""
    # Arrange
    non_existent = Path("/non/existent/path/config.toml")

    # Act & Assert
    with pytest.raises(FileNotFoundError, match="Configuration file not found"):
        load_config(non_existent)


def test_load_config_invalid_toml(tmp_path: Path) -> None:
    """構文エラーを含むTOMLファイルを指定した場合に ValueError が発生することを検証する。"""
    # Arrange
    bad_toml = tmp_path / "bad.toml"
    bad_toml.write_text("invalid = = = toml", encoding="utf-8")

    # Act & Assert
    with pytest.raises(ValueError, match="Failed to parse TOML configuration"):
        load_config(bad_toml)


def test_parse_config_dict_empty() -> None:
    """空の辞書をパースした場合に全デフォルト値が設定されることを検証する。"""
    # Arrange
    empty_dict: dict[str, Any] = {}

    # Act
    cfg = parse_config_dict(empty_dict)

    # Assert
    assert cfg == AppConfig()
```

---

## 5. 品質・規約チェックリスト (Quality Checklist)

| 項目 | 判定 | 理由・根拠 |
|---|---|---|
| AAA パターン | 適合 | 全テスト関数で `# Arrange`, `# Act`, `# Assert` を明示し、手続き的な混合を排除 |
| Docstring | 適合 | 全関数に Google スタイル日本語 Docstring（サマリー行）を付与 |
| 型アノテーション | 適合 | `from __future__ import annotations`, 引数・戻り値型 (`-> None`) を完全付与 |
| ファイル行数 | 適合 (約 195 行) | 最大 300 行以下 / 目標 200 行以下の基準を達成 |
| 決定論的テスト | 適合 | `tmp_path`, `monkeypatch` を活用し外部依存や競合を排除 |
| `MAX_SEGMENT_CHARS` 廃止 | 適合 | 属性非存在 (`hasattr`), フィールド非存在 (`dataclasses.fields`), TOML 互換無視の3重検証 |
