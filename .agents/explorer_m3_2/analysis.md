# Milestone 3 Config Architecture & Parameter Updates Analysis

## 1. Executive Summary

本ドキュメントは、Milestone 3（Config Cleanup & Parameter Updates）における `src/audio_transcriber/config.py`、`config.toml`、`config.example.toml`、および `tests/test_config.py` の構造設計と実装仕様をまとめた調査・分析レポートです。

リファレンス実装（`lumi_companion`）のパラメータ仕様および本プロジェクト（`audio-transcriber`）の設計思想に基づき、廃止対象である `MAX_SEGMENT_CHARS` / `max_segment_chars` を完全に除去し、新設される `PostProcessConfig`（8フィールド）および `SubtitleConfig`（4フィールド）の型安全な定義と、大文字・小文字・エイリアスに対応した堅牢な TOML パーサー仕様を策定しました。

---

## 2. Reference Implementation Analysis (`lumi_companion`)

`lumi_companion` における設定およびパラメータの構造と、`audio-transcriber` への移植マッピングは以下の通りです。

| lumi_companion 設定項目 | デフォルト値 | audio-transcriber 設計項目 | audio-transcriber デフォルト値 | 備考 |
|---|---|---|---|---|
| `custom_dictionary_path` | `data/custom_dictionary.yaml` | `post_process.custom_dict_path` / `custom_dictionary_path` | `None` (TOMLで指定可) | YAML/JSON/TOML 対応 |
| (なし/暗黙有効) | - | `post_process.replace_terms` | `True` | 辞書置換フラグ |
| `whisper_post_process_normalize_nums` | `True` | `post_process.normalize_nums` | `True` | 漢数字・ローマ数字の正規化 |
| `whisper_post_process_to_hankaku` | `False` | `post_process.to_hankaku` | `False` | NFKC半角化 |
| `whisper_post_process_lower` | `False` | `post_process.lower` | `False` | 英小文字化 |
| `whisper_post_process_remove_punct` | `False` | `post_process.remove_punct` | `False` | 句読点・記号削除 |
| `no_speech_threshold` | `0.6` | `post_process.no_speech_threshold` | `0.6` | サニタイザー無音閾値 |
| `max_chars_per_second` | `12.0` | `post_process.max_chars_per_second` | `12.0` | 発話速度上限フィルタ |
| `subtitle_end_padding` | `0.8` | `subtitle.end_padding` | `1.0` | 余韻パディング秒数 |
| `subtitle_min_duration` | `1.2` | `subtitle.min_duration` | `1.5` | 最小表示秒数 |
| `subtitle_min_gap` | `0.05` | `subtitle.min_gap` | `0.05` | 重複防止最小ギャップ |
| (SRT/VTT/JSON 固定出力) | - | `subtitle.formats` | `["srt", "vtt", "json"]` | 出力フォーマットリスト |
| `whisper_max_segment_chars` | `25` | **完全廃止** | **なし** | 文節分割廃止に伴い完全削除 |

---

## 3. Detailed Class & Field Specifications (`config.py`)

### 3.1 `PostProcessConfig`
テキスト後処理・サニタイズ用の設定クラス。

```python
@dataclass
class PostProcessConfig:
    """Text post-processing and sanitization configuration."""

    custom_dict_path: Path | None = None
    replace_terms: bool = True
    normalize_nums: bool = True
    to_hankaku: bool = False
    lower: bool = False
    remove_punct: bool = False
    no_speech_threshold: float = 0.6
    max_chars_per_second: float = 12.0
```

- **フィールド構成**:
  1. `custom_dict_path: Path | None = None`
     - カスタム辞書ファイル（TOML/YAML/JSON）のパス。ルートの `custom_dictionary_path` と相互フォールバック。
  2. `replace_terms: bool = True`
     - 辞書置換（最長一致）を実行するかどうか。
  3. `normalize_nums: bool = True`
     - `NumberNormalizer` による漢数字・ローマ数字等の正規化を実行するかどうか。
  4. `to_hankaku: bool = False`
     - `unicodedata.normalize("NFKC", ...)` による全角英数の半角化を実行するかどうか。
  5. `lower: bool = False`
     - 英字を小文字化するかどうか。
  6. `remove_punct: bool = False`
     - 句読点・記号（`、。！？!?` 等）を削除するかどうか。
  7. `no_speech_threshold: float = 0.6`
     - `SegmentSanitizer` で無音捏造セグメントを除外する確率閾値。
  8. `max_chars_per_second: float = 12.0`
     - `SegmentSanitizer` で異常発話速度セグメントを除外する文字数/秒上限値。

### 3.2 `SubtitleConfig`
字幕タイミング補正および出力フォーマット用の設定クラス。

```python
@dataclass
class SubtitleConfig:
    """Subtitle timing adjustment and output format configuration."""

    end_padding: float = 1.0
    min_duration: float = 1.5
    min_gap: float = 0.05
    formats: list[str] = field(default_factory=lambda: ["srt", "vtt", "json"])
```

- **フィールド構成**:
  1. `end_padding: float = 1.0`
     - 発話終了後の余韻パディング秒数。
  2. `min_duration: float = 1.5`
     - 字幕の最小表示秒数。
  3. `min_gap: float = 0.05`
     - 連続する字幕間の最小隙間秒数（重複防止）。
  4. `formats: list[str] = field(default_factory=lambda: ["srt", "vtt", "json"])`
     - 出力する字幕形式のリスト。

### 3.3 `AppConfig`
ルート設定クラス。

```python
@dataclass
class AppConfig:
    """Root application configuration."""

    output_dir: Path = field(default_factory=lambda: Path("./output"))
    default_video_path: Path | None = None
    debug_output_dir: Path | None = None
    custom_dictionary_path: Path | None = None
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    media: MediaConfig = field(default_factory=MediaConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    transcribe: TranscribeConfig = field(default_factory=TranscribeConfig)
    post_process: PostProcessConfig = field(default_factory=PostProcessConfig)
    subtitle: SubtitleConfig = field(default_factory=SubtitleConfig)
```

---

## 4. TOML Parsing & Section Mapping Architecture

### 4.1 セクション名およびキーの柔軟な解決

TOML ファイルでは、以下のような命名揺れや大文字・小文字、プレフィックスの有無が存在します。パーサーはこれらすべてを透過的に吸収します。

| セクション | 対象エイリアス | キー候補（大文字・小文字両対応） |
|---|---|---|
| ルート | N/A | `OUTPUT_DIR`, `DEFAULT_VIDEO_PATH`, `DEBUG_OUTPUT_DIR`, `CUSTOM_DICTIONARY_PATH` |
| `[pipeline]` | `pipeline` | `REMUX` / `remux` |
| `[media]` | `media` | `MIC_TRACK` / `mic_track`, `SAMPLE_RATE` / `sample_rate` |
| `[model]` | `model` | `MODEL_SIZE` / `model_size`, `DEVICE` / `device`, `COMPUTE_TYPE` / `compute_type` |
| `[transcribe]` | `transcribe` | `LANGUAGE`, `BEAM_SIZE`, `CONDITION_ON_PREVIOUS_TEXT`, `NO_SPEECH_THRESHOLD`, `INITIAL_PROMPT` |
| `[transcribe.vad]` | `vad` / `transcribe.vad` | `VAD_FILTER`, `MIN_SILENCE_DURATION_MS`, `VAD_THRESHOLD` |
| `[post_process]` | `post_process`, `postprocess`, `post_processing` | `CUSTOM_DICT_PATH`, `REPLACE_TERMS` / `POST_PROCESS_REPLACE_TERMS`, `NORMALIZE_NUMS` / `POST_PROCESS_NORMALIZE_NUMS`, `TO_HANKAKU` / `POST_PROCESS_TO_HANKAKU`, `LOWER` / `POST_PROCESS_LOWER`, `REMOVE_PUNCT` / `POST_PROCESS_REMOVE_PUNCT`, `NO_SPEECH_THRESHOLD` / `POST_PROCESS_NO_SPEECH_THRESHOLD`, `MAX_CHARS_PER_SECOND` / `POST_PROCESS_MAX_CHARS_PER_SECOND` |
| `[subtitle]` | `subtitle`, `subtitles` | `END_PADDING` / `SUBTITLE_END_PADDING`, `MIN_DURATION` / `SUBTITLE_MIN_DURATION`, `MIN_GAP` / `SUBTITLE_MIN_GAP`, `FORMATS` / `SUBTITLE_FORMATS` / `OUTPUT_FORMATS` |

### 4.2 パーサーヘルパー設計

コードの可読性と保守性を高め、ネストした `get()` の乱立を防ぐため、以下の軽量ヘルパー関数を導入します：

```python
def _normalize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize dictionary keys to lowercase recursively."""
    normalized: dict[str, Any] = {}
    for k, v in data.items():
        lower_k = k.lower()
        if isinstance(v, dict):
            normalized[lower_k] = _normalize_dict(v)
        else:
            normalized[lower_k] = v
    return normalized


def _get_val(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first matching key value from dictionary or default."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default
```

### 4.3 `formats` リストのパース処理
TOML 上で `SUBTITLE_FORMATS = ["srt", "vtt", "json"]` のような配列だけでなく、`SUBTITLE_FORMATS = "srt, vtt, json"` のようなカンマ区切り文字列が渡された場合でも安全に `list[str]` に正規化します。

```python
raw_formats = _get_val(sub_data, "formats", "subtitle_formats", "output_formats", default=["srt", "vtt", "json"])
if isinstance(raw_formats, str):
    parsed_formats = [f.strip().lower() for f in raw_formats.split(",") if f.strip()]
elif isinstance(raw_formats, list):
    parsed_formats = [str(f).strip().lower() for f in raw_formats if str(f).strip()]
else:
    parsed_formats = ["srt", "vtt", "json"]
```

---

## 5. Complete Proposed `src/audio_transcriber/config.py` Implementation

以下は、Google Python スタイルガイド・PEP 8 に完全準拠し、約 220 行（目標 200 行前後、上限 300 行以内）で厳格な型注釈を備えた `config.py` の完全な設計コードです。

```python
"""Configuration management and TOML loading for audio-transcriber."""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_FILENAME = "config.toml"


def _normalize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize dictionary keys to lowercase recursively.

    Args:
        data: Input dictionary with arbitrary key casing.

    Returns:
        New dictionary with all keys converted to lowercase recursively.
    """
    normalized: dict[str, Any] = {}
    for k, v in data.items():
        lower_k = k.lower()
        if isinstance(v, dict):
            normalized[lower_k] = _normalize_dict(v)
        else:
            normalized[lower_k] = v
    return normalized


def _get_val(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first existing non-None key value from a dictionary or default.

    Args:
        d: Dictionary to look up keys from.
        *keys: Candidate key names in priority order.
        default: Fallback value if none of the keys exist.

    Returns:
        First matching value, or default if no match.
    """
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


@dataclass
class MediaConfig:
    """Media extraction and remuxing configuration."""

    mic_track: int = 2
    sample_rate: int = 48000


@dataclass
class ModelConfig:
    """Whisper inference model configuration."""

    model_size: str = "small"
    device: str = "cuda"
    compute_type: str = "float16"


@dataclass
class VadConfig:
    """Voice Activity Detection (Silero-VAD) configuration."""

    vad_filter: bool = True
    min_silence_duration_ms: int = 500
    vad_threshold: float = 0.5


@dataclass
class TranscribeConfig:
    """Transcription and Whisper inference configuration."""

    language: str = "ja"
    beam_size: int = 5
    condition_on_previous_text: bool = True
    no_speech_threshold: float = 0.6
    initial_prompt: str | None = None
    vad: VadConfig = field(default_factory=VadConfig)


@dataclass
class PostProcessConfig:
    """Text post-processing and sanitization configuration."""

    custom_dict_path: Path | None = None
    replace_terms: bool = True
    normalize_nums: bool = True
    to_hankaku: bool = False
    lower: bool = False
    remove_punct: bool = False
    no_speech_threshold: float = 0.6
    max_chars_per_second: float = 12.0


@dataclass
class SubtitleConfig:
    """Subtitle timing adjustment and output format configuration."""

    end_padding: float = 1.0
    min_duration: float = 1.5
    min_gap: float = 0.05
    formats: list[str] = field(default_factory=lambda: ["srt", "vtt", "json"])


@dataclass
class PipelineConfig:
    """Pipeline orchestration configuration."""

    remux: bool = True


@dataclass
class AppConfig:
    """Root application configuration."""

    output_dir: Path = field(default_factory=lambda: Path("./output"))
    default_video_path: Path | None = None
    debug_output_dir: Path | None = None
    custom_dictionary_path: Path | None = None
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    media: MediaConfig = field(default_factory=MediaConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    transcribe: TranscribeConfig = field(default_factory=TranscribeConfig)
    post_process: PostProcessConfig = field(default_factory=PostProcessConfig)
    subtitle: SubtitleConfig = field(default_factory=SubtitleConfig)


def parse_config_dict(data: dict[str, Any]) -> AppConfig:
    """Parse a dictionary (e.g. from TOML) into an AppConfig instance.

    Supports uppercase, lowercase, and mixed-case keys as well as section aliases.

    Args:
        data: Dictionary loaded from TOML configuration.

    Returns:
        Populated AppConfig instance with defaults applied for omitted fields.
    """
    norm = _normalize_dict(data)

    # Root / Path settings
    output_dir_val = _get_val(norm, "output_dir", default="./output")
    output_dir = Path(output_dir_val)
    default_video_val = _get_val(norm, "default_video_path", "default_video")
    default_video = Path(default_video_val) if default_video_val is not None else None
    debug_output_val = _get_val(norm, "debug_output_dir", "debug_dir")
    debug_output = Path(debug_output_val) if debug_output_val is not None else None
    custom_dict_val = _get_val(
        norm, "custom_dictionary_path", "custom_dict_path", "dictionary_path"
    )
    custom_dict = Path(custom_dict_val) if custom_dict_val is not None else None

    # Pipeline section
    pipeline_data = norm.get("pipeline", {})
    pipeline = PipelineConfig(
        remux=bool(_get_val(pipeline_data, "remux", default=True)),
    )

    # Media section
    media_data = norm.get("media", {})
    media = MediaConfig(
        mic_track=int(_get_val(media_data, "mic_track", default=2)),
        sample_rate=int(_get_val(media_data, "sample_rate", default=48000)),
    )

    # Model section
    model_data = norm.get("model", {})
    model = ModelConfig(
        model_size=str(_get_val(model_data, "model_size", default="small")),
        device=str(_get_val(model_data, "device", default="cuda")),
        compute_type=str(_get_val(model_data, "compute_type", default="float16")),
    )

    # Transcribe & VAD section
    transcribe_data = norm.get("transcribe", {})
    vad_data = transcribe_data.get("vad") or norm.get("vad", {})
    vad = VadConfig(
        vad_filter=bool(_get_val(vad_data, "vad_filter", default=True)),
        min_silence_duration_ms=int(_get_val(vad_data, "min_silence_duration_ms", default=500)),
        vad_threshold=float(_get_val(vad_data, "vad_threshold", default=0.5)),
    )
    raw_prompt = _get_val(transcribe_data, "initial_prompt", "prompt")
    initial_prompt = str(raw_prompt).strip() if raw_prompt is not None else None

    transcribe = TranscribeConfig(
        language=str(_get_val(transcribe_data, "language", default="ja")),
        beam_size=int(_get_val(transcribe_data, "beam_size", default=5)),
        condition_on_previous_text=bool(
            _get_val(transcribe_data, "condition_on_previous_text", default=True)
        ),
        no_speech_threshold=float(_get_val(transcribe_data, "no_speech_threshold", default=0.6)),
        initial_prompt=initial_prompt,
        vad=vad,
    )

    # Post process section
    post_data = norm.get("post_process") or norm.get("postprocess") or norm.get("post_processing", {})
    post_dict_raw = _get_val(
        post_data,
        "custom_dict_path",
        "custom_dictionary_path",
        "dictionary_path",
        "post_process_custom_dict_path",
        default=custom_dict,
    )
    post_dict_path = Path(post_dict_raw) if post_dict_raw is not None else None
    if custom_dict is None and post_dict_path is not None:
        custom_dict = post_dict_path

    post_process = PostProcessConfig(
        custom_dict_path=post_dict_path,
        replace_terms=bool(
            _get_val(
                post_data,
                "replace_terms",
                "post_process_replace_terms",
                "post_convert_terms",
                default=True,
            )
        ),
        normalize_nums=bool(
            _get_val(
                post_data, "normalize_nums", "post_process_normalize_nums", default=True
            )
        ),
        to_hankaku=bool(
            _get_val(post_data, "to_hankaku", "post_process_to_hankaku", default=False)
        ),
        lower=bool(_get_val(post_data, "lower", "post_process_lower", default=False)),
        remove_punct=bool(
            _get_val(post_data, "remove_punct", "post_process_remove_punct", default=False)
        ),
        no_speech_threshold=float(
            _get_val(
                post_data,
                "no_speech_threshold",
                "post_process_no_speech_threshold",
                default=0.6,
            )
        ),
        max_chars_per_second=float(
            _get_val(
                post_data,
                "max_chars_per_second",
                "post_process_max_chars_per_second",
                default=12.0,
            )
        ),
    )

    # Subtitle section
    sub_data = norm.get("subtitle") or norm.get("subtitles", {})
    raw_formats = _get_val(
        sub_data, "formats", "subtitle_formats", "output_formats", default=["srt", "vtt", "json"]
    )
    if isinstance(raw_formats, str):
        parsed_formats = [f.strip().lower() for f in raw_formats.split(",") if f.strip()]
    elif isinstance(raw_formats, list):
        parsed_formats = [str(f).strip().lower() for f in raw_formats if str(f).strip()]
    else:
        parsed_formats = ["srt", "vtt", "json"]

    subtitle = SubtitleConfig(
        end_padding=float(
            _get_val(sub_data, "end_padding", "subtitle_end_padding", default=1.0)
        ),
        min_duration=float(
            _get_val(sub_data, "min_duration", "subtitle_min_duration", default=1.5)
        ),
        min_gap=float(_get_val(sub_data, "min_gap", "subtitle_min_gap", default=0.05)),
        formats=parsed_formats,
    )

    return AppConfig(
        output_dir=output_dir,
        pipeline=pipeline,
        default_video_path=default_video,
        debug_output_dir=debug_output,
        custom_dictionary_path=custom_dict,
        media=media,
        model=model,
        transcribe=transcribe,
        post_process=post_process,
        subtitle=subtitle,
    )


def load_config(config_path: Path | str | None = None) -> AppConfig:
    """Load configuration from a TOML file, falling back to default config if none found.

    Args:
        config_path: Explicit path to the TOML configuration file. If None,
            checks for './config.toml' in current directory.

    Returns:
        AppConfig populated from the file or with defaults if no file is present.

    Raises:
        FileNotFoundError: If an explicit config_path was given but does not exist.
        ValueError: If TOML file is malformed or invalid.
    """
    target_path: Path | None = None
    if config_path is not None:
        p = Path(config_path)
        if not p.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        target_path = p
    else:
        default_file = Path(DEFAULT_CONFIG_FILENAME)
        if default_file.exists() and default_file.is_file():
            target_path = default_file

    if target_path is None:
        logger.debug("No configuration file found; using default configuration.")
        return AppConfig()

    logger.info(f"Loading configuration from {target_path}")
    try:
        with open(target_path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"Failed to parse TOML configuration '{target_path}': {e}") from e

    return parse_config_dict(data)
```

---

## 6. TOML Configuration File Updates (`config.toml` & `config.example.toml`)

### 6.1 `[post_process]` セクション（完全版）

```toml
# ==============================================================================
# テキスト後処理設定
# ==============================================================================
[post_process]
# カスタム辞書（表記揺れ・ユーザー指定用語）のパス (省略時はルートの CUSTOM_DICTIONARY_PATH を参照)
# POST_PROCESS_CUSTOM_DICT_PATH = "data/custom_dictionary.toml"

# カスタム辞書による用語置換を行うか
POST_PROCESS_REPLACE_TERMS = true

# 全角英数字を半角に統一するか (NFKC正規化)
POST_PROCESS_TO_HANKAKU = false

# 漢数字等をアラビア数字に正規化するか
POST_PROCESS_NORMALIZE_NUMS = true

# 英字を小文字化するか
POST_PROCESS_LOWER = false

# 句読点等の記号を削除するか
POST_PROCESS_REMOVE_PUNCT = false

# ハルシネーション（無音捏造）判定の無音確率閾値 (0.0〜1.0)
POST_PROCESS_NO_SPEECH_THRESHOLD = 0.6

# 異常発話速度判定の上限文字数/秒 (人間の解剖学的限界に基づくフィルタ)
POST_PROCESS_MAX_CHARS_PER_SECOND = 12.0
```

### 6.2 `[subtitle]` セクション（完全版）

```toml
# ==============================================================================
# 字幕表示タイミング調整・出力フォーマット設定
# ==============================================================================
[subtitle]
# 発話終了後の余韻表示秒数 (発声終了後に字幕を残す時間)
SUBTITLE_END_PADDING = 1.0

# 字幕の最小表示秒数 (短い発言でも読み取れる最低時間)
SUBTITLE_MIN_DURATION = 1.5

# 連続する字幕セグメント間の最小隙間秒数 (次セグメントとの重複防止)
SUBTITLE_MIN_GAP = 0.05

# 出力字幕フォーマットリスト ("srt", "vtt", "json")
SUBTITLE_FORMATS = ["srt", "vtt", "json"]
```

---

## 7. Recommended Test Suite Additions (`tests/test_config.py`)

1. **`test_default_config_instance`**:
   - `PostProcessConfig` の全8フィールドのデフォルト値検証
   - `SubtitleConfig` の全4フィールド（`formats` 含む）のデフォルト値検証
   - `hasattr(cfg.post_process, "max_segment_chars") is False` の検証
2. **`test_load_config_uppercase_toml`**:
   - 全セクション（UPPER_CASE キー）のパース結果検証
   - `POST_PROCESS_NO_SPEECH_THRESHOLD = 0.75` / `POST_PROCESS_MAX_CHARS_PER_SECOND = 15.0`
   - `SUBTITLE_FORMATS = ["srt", "vtt"]`
3. **`test_load_config_lowercase_and_aliases`**:
   - lowercase キーおよび `[postprocess]` / `[subtitles]` セクション名のパース検証
   - `SUBTITLE_FORMATS = "srt, vtt"` の文字列パース検証
4. **`test_custom_dict_path_resolution`**:
   - ルート `CUSTOM_DICTIONARY_PATH` と `[post_process]` 内のパスの優先順位とフォールバック検証
5. **`test_max_segment_chars_completely_ignored`**:
   - TOML や辞書に `MAX_SEGMENT_CHARS` が混入していても、例外なく無視され属性として保持されないことの検証
