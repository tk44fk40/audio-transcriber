# Milestone 1: テスト仕様・検証戦略詳細調査報告書 (Analysis)

本ドキュメントは、`audio-transcriber` の Milestone 1（`models.py`, `sanitizer.py`, `exporter.py`）における単体テスト仕様、エッジケース網羅基準、AAA（Arrange-Act-Assert）パターン構造、およびモック/フィクスチャ設計方針を定義したものです。

---

## 1. 概要 (Executive Summary)

Milestone 1 では、音声認識後の後処理パイプラインの基盤となる以下の3モジュールを導入します。

1. `models.py`: タイムスタンプ付き発言字幕データモデル (`SubtitleSegment`)
2. `sanitizer.py`: Whisper のハルシネーション・無音捏造・異常発話速度除去 (`SegmentSanitizer`)
3. `exporter.py`: DaVinci Resolve 互換 SRT / WebVTT / JSON の3形式同時出力 (`SubtitleExporter`)

各モジュールの責務を独立させ、高速・決定論的な単体テスト（`tests/test_models.py`, `tests/test_sanitizer.py`, `tests/test_exporter.py`）により、分岐網羅率 100% と厳格な型安全性を保証します。

---

## 2. テスト設計原則・規約 (Test Architecture & Principles)

### 2.1 AAA パターン (Arrange-Act-Assert) の徹底
すべてのテストケースにおいて以下の構成を厳格に維持し、テストロジック内での複雑なループや分岐を排除します。
- **Arrange (準備)**: テスト対象のインスタンス生成、入力データ（`SimpleNamespace`, `dict`, `SubtitleSegment`）のセットアップ。
- **Act (実行)**: テスト対象メソッドの単一呼び出し。
- **Assert (検証)**: 期待される戻り値、状態変更、ファイル出力内容、例外送出の明確なアサーション。

### 2.2 フィクスチャ方針 (Pytest Fixtures)
- **ファイル I/O 検証**: Pytest 標準の `tmp_path: Path` を利用し、一時ディレクトリ下でファイル作成・パーミッション・親ディレクトリ自動生成を安全に検証。
- **ログ検証**: Pytest 標準の `caplog: pytest.LogCaptureFixture` を利用し、進捗ログ (`total_duration > 0`) やハルシネーション検知ログの出力を検証。
- **共通データ定義**: `conftest.py` または各テストモジュール上部に、軽量なダミーオブジェクト生成ファクトリ/フィクスチャを配置。

### 2.3 型安全性と品質基準
- Python 3.11+ 厳格な型注釈を付与（`uv run basedpyright` でエラー 0 件）。
- Google スタイル日本語 Docstring を全テスト関数に記述。
- 1 ファイル最大 300 行以下（目標 200 行以下）を維持。

---

## 3. モジュール別テストケース仕様 (Test Case Specifications)

### 3.1 `models.py` (`tests/test_models.py`)

`SubtitleSegment` データモデルの生成、フィールドアクセス、辞書相互変換、同値性判定、型変換/デフォルト値フォールバックを網羅します。

| テスト関数名 | 種別 | 検証内容 | 期待結果 (Assert) |
|---|---|---|---|
| `test_subtitle_segment_init` | 正常系 | `start`, `end`, `text` を指定したインスタンス初期化 | 各フィールド値が正しく保持されること |
| `test_subtitle_segment_equality` | 正常系 | 同一フィールド値を持つ別インスタンス間の同値性 (`__eq__`) | `seg1 == seg2` が True、異なる値で False |
| `test_subtitle_segment_to_dict` | 正常系 | `to_dict()` による辞書へのシリアライズ | `{"start": 1.0, "end": 2.5, "text": "テスト"}` を返すこと |
| `test_subtitle_segment_from_dict_standard` | 正常系 | `from_dict()` による辞書からのデシリアライズ | フィールドが正しくパースされインスタンス化されること |
| `test_subtitle_segment_from_dict_type_coercion` | 境界値 | `start`/`end` に整数値や数値文字列、`text` に数値が渡された場合 | `float`, `str` への型変換が行われること |
| `test_subtitle_segment_from_dict_defaults` | 異常系/境界値 | キーが欠損した辞書 (`{}` や `{"text": "A"}`) の入力 | デフォルト値 (`start=0.0`, `end=0.0`, `text=""`) で安全に初期化されること |
| `test_subtitle_segment_roundtrip` | 正常系 | `from_dict(seg.to_dict())` の往復変換 | 元のインスタンスと等価であること |
| `test_subtitle_segment_unicode_and_special_chars` | 境界値 | 日本語、絵文字、改行コード、記号を含むテキストの保持 | 文字化けや欠損なくそのまま保持されること |

---

### 3.2 `sanitizer.py` (`tests/test_sanitizer.py`)

`SegmentSanitizer` による 5 大ハルシネーション除去機能と入出力形式の柔軟性を検証します。

| テスト関数名 | 機能/対象 | 検証内容 | 期待結果 (Assert) |
|---|---|---|---|
| `test_sanitizer_drops_high_no_speech_prob` | 無音捏造除外 | `no_speech_prob > no_speech_threshold` (0.8 > 0.6) のセグメント | 該当セグメントがドロップされ、正常セグメントのみ残る |
| `test_sanitizer_retains_low_no_speech_prob_boundary` | 境界値 | `no_speech_prob == 0.6` (境界値) および `< 0.6` のセグメント | 保持されること |
| `test_sanitizer_drops_excessive_speech_rate` | 発話速度制限 | `chars_per_sec > 12.0` かつ `len(text) > 4` (例: 0.3s に 10 文字 = 33.3 文字/秒) | 異常速度セグメントがドロップされること |
| `test_sanitizer_protects_short_utterances` | 短文保護 | 4文字以下の短文 (例: 0.1s に「はい」2文字 = 20文字/秒、0.2s に「了解です」4文字) | 速度超過でも保護されドロップされないこと |
| `test_sanitizer_speech_rate_boundary_5_chars` | 境界値 | 5文字以上の短文で速度超過 (例: 0.2s に「あいうえお」5文字 = 25文字/秒) | 4文字超のため正しくドロップされること |
| `test_sanitizer_reduces_intra_segment_repetition` | セグメント内重複短縮 | 前半と後半が完全一致し `no_speech_prob > 0.1` または `compression_ratio > 2.0` (例:「あいうえおあいうえお」) | 重複が解消され「あいうえお」に短縮されること |
| `test_sanitizer_preserves_natural_intra_repetition` | 正常系 | 自然な繰り返し (「もしもしもしもし」) で `no_speech_prob` / `compression_ratio` が正常値 | 短縮されずに元のテキストが維持されること |
| `test_sanitizer_drops_consecutive_loop_in_silence` | セグメント間ループ除外 | 直前と同一/部分一致テキストが連続し `no_speech_prob > 0.1` の場合 | 後続のループセグメントがドロップされること |
| `test_sanitizer_preserves_intentional_consecutive_repeat` | 正常系 | 話者が意図して連続発言 (`no_speech_prob <= 0.1`) した場合 | ループと判定されず両方保持されること |
| `test_sanitizer_adjusts_start_time_from_words` | 単語タイムスタンプ補正 | `words` リストが存在し文頭単語の `start` がセグメント `start` と異なる場合 | 文頭単語の `start` 時刻にセグメント開始時刻が補正されること |
| `test_sanitizer_handles_dict_and_object_segments` | 入力互換性 | `SimpleNamespace` (オブジェクト) と `dict` の混在/単独入力 | どちらも同一の `SubtitleSegment` リストとして変換・出力されること |
| `test_sanitizer_ignores_empty_and_whitespace_segments` | 異常系 | 空文字 `""` や空白 `"   \t\n"` のみのセグメント | 結果リストから安全に除外されること |
| `test_sanitizer_get_word_time_helper` | 内部関数単体 | `get_word_time` に `dict`, オブジェクト, 無効値, `None` を渡す | 数値のみ float で返り、不正値は `None` となること |
| `test_sanitizer_logging_with_total_duration` | ログ出力 | `total_duration > 0` を指定して実行 | 進捗率（%）を含むフォーマットログが出力されること |

---

### 3.3 `exporter.py` (`tests/test_exporter.py`)

`SubtitleExporter` による SRT, WebVTT, JSON の出力仕様（フォーマット、文字コード、改行コード、拡張子自動判定、エラー処理）を検証します。

| テスト関数名 | 機能/対象 | 検証内容 | 期待結果 (Assert) |
|---|---|---|---|
| `test_exporter_format_timestamp_srt` | タイムスタンプ | 秒数 (`0.0`, `12.345`, `3661.5`) を SRT 形式に変換 | `HH:MM:SS,mmm` (コンマ区切り) 形式で返ること |
| `test_exporter_format_timestamp_vtt` | タイムスタンプ | 秒数 (`0.0`, `12.345`, `3661.5`) を WebVTT 形式に変換 | `HH:MM:SS.mmm` (ドット区切り) 形式で返ること |
| `test_exporter_save_srt` | SRT 保存 | セグメントリストから `.srt` ファイルを出力 | インデックス連番 (1, 2..)、`HH:MM:SS,mmm --> HH:MM:SS,mmm`、LF改行、UTF-8 |
| `test_exporter_save_vtt` | WebVTT 保存 | セグメントリストから `.vtt` ファイルを出力 | 先頭 `WEBVTT\n`、`HH:MM:SS.mmm --> HH:MM:SS.mmm`、LF改行、UTF-8 |
| `test_exporter_save_json` | JSON 保存 | セグメントリストから `.json` ファイルを出力 | `indent=2`, `ensure_ascii=False`、UTF-8、有効な JSON パース可能配列 |
| `test_exporter_auto_detect_format` | フォーマット自動判定 | `save_subtitles` で `.srt`, `.vtt`, `.json`, 大文字 `.SRT`, `.VTT` を指定 | 拡張子に応じて適切な出力が行われること |
| `test_exporter_explicit_format` | 明示的フォーマット指定 | 拡張子が異なるファイルパスに対して `fmt="srt"`, `fmt="vtt"`, `fmt="json"` を指定 | 指定されたフォーマットで出力されること |
| `test_exporter_unsupported_extension_raises` | 異常系 | 未対応の拡張子 (`.txt`, `.csv` 等) を指定 | `ValueError` ("未対応の拡張子です") が送出されること |
| `test_exporter_unsupported_explicit_fmt_raises` | 異常系 | 未対応の `fmt="xml"` を指定 | `ValueError` ("未対応のフォーマットです") が送出されること |
| `test_exporter_empty_segments` | 境界値 | セグメントリストが空 `[]` の場合 | エラーにならず、空ファイルまたはヘッダーのみ/空配列 `[]` が出力されること |
| `test_exporter_creates_parent_directories` | ディレクトリ自動生成 | 存在しない深い階層のパス (`tmp_path / "a" / "b" / "out.srt"`) を指定 | 親ディレクトリが自動生成されファイルが保存されること |
| `test_exporter_unicode_and_multiline_text` | 境界値 | 絵文字、改行を含む複数行テキスト、引用符 `"` のエクスポート | 各フォーマットで破損せず正しく書き込まれること |

---

## 4. テストコード設計・実装ブループリント (Code Blueprints)

以下に、各テストモジュールの具象コード構成と AAA 実装例を示します。

### 4.1 `tests/test_models.py`
```python
"""Tests for SubtitleSegment data model."""

from audio_transcriber.models import SubtitleSegment


def test_subtitle_segment_init() -> None:
    """SubtitleSegment の基本属性の初期化を検証します。"""
    # Arrange & Act
    seg = SubtitleSegment(start=1.234, end=5.678, text="こんにちは")

    # Assert
    assert seg.start == 1.234
    assert seg.end == 5.678
    assert seg.text == "こんにちは"


def test_subtitle_segment_equality() -> None:
    """SubtitleSegment の同値性判定を検証します。"""
    # Arrange
    seg1 = SubtitleSegment(start=1.0, end=2.0, text="テスト")
    seg2 = SubtitleSegment(start=1.0, end=2.0, text="テスト")
    seg3 = SubtitleSegment(start=1.0, end=2.0, text="別テキスト")

    # Act & Assert
    assert seg1 == seg2
    assert seg1 != seg3


def test_subtitle_segment_dict_conversion() -> None:
    """SubtitleSegment の to_dict および from_dict 相互変換を検証します。"""
    # Arrange
    seg = SubtitleSegment(start=1.5, end=4.0, text="こんにちは")

    # Act
    d = seg.to_dict()
    reconstructed = SubtitleSegment.from_dict(d)

    # Assert
    assert d == {"start": 1.5, "end": 4.0, "text": "こんにちは"}
    assert reconstructed == seg


def test_subtitle_segment_from_dict_coercion_and_defaults() -> None:
    """from_dict における型変換および欠損キーのデフォルトフォールバックを検証します。"""
    # Arrange
    raw_int = {"start": 1, "end": 3, "text": "整数テスト"}
    raw_empty: dict[str, object] = {}

    # Act
    seg_int = SubtitleSegment.from_dict(raw_int)
    seg_empty = SubtitleSegment.from_dict(raw_empty)

    # Assert
    assert seg_int.start == 1.0
    assert seg_int.end == 3.0
    assert isinstance(seg_int.start, float)
    assert seg_empty.start == 0.0
    assert seg_empty.end == 0.0
    assert seg_empty.text == ""
```

---

### 4.2 `tests/test_sanitizer.py`
```python
"""Tests for SegmentSanitizer module."""

from types import SimpleNamespace
from typing import Any
import pytest
from audio_transcriber.models import SubtitleSegment
from audio_transcriber.sanitizer import SegmentSanitizer


def test_sanitizer_drops_high_no_speech_prob() -> None:
    """無音確率 (no_speech_prob) が閾値を超えるセグメントがドロップされることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer(no_speech_threshold=0.6)
    segments: list[Any] = [
        SimpleNamespace(start=0.0, end=2.0, text="正常発話", no_speech_prob=0.1),
        SimpleNamespace(start=2.5, end=4.0, text="無音捏造", no_speech_prob=0.8),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 1
    assert results[0].text == "正常発話"


def test_sanitizer_drops_excessive_speech_rate() -> None:
    """物理的限界を超える異常発話速度（12文字/秒超、4文字超）がドロップされることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer(max_chars_per_second=12.0)
    segments: list[Any] = [
        SimpleNamespace(start=0.0, end=2.0, text="こんにちは", no_speech_prob=0.1),
        SimpleNamespace(start=2.0, end=2.3, text="はいはいはいはいはいはい", no_speech_prob=0.1),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 1
    assert results[0].text == "こんにちは"


def test_sanitizer_protects_short_utterances() -> None:
    """4文字以下の短文は発話速度チェック対象外として安全に保護されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer(max_chars_per_second=12.0)
    segments: list[Any] = [
        SimpleNamespace(start=0.0, end=0.1, text="はい", no_speech_prob=0.1),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 1
    assert results[0].text == "はい"


def test_sanitizer_reduces_intra_segment_repetition() -> None:
    """セグメント内でのフレーズ重複が圧縮率判定により短縮されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    segments: list[Any] = [
        SimpleNamespace(
            start=0.0, end=2.0, text="あいうえおあいうえお", no_speech_prob=0.05, compression_ratio=2.5
        ),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 1
    assert results[0].text == "あいうえお"


def test_sanitizer_adjusts_start_time_with_word_timestamps() -> None:
    """単語タイムスタンプが存在する場合、文頭単語の開始時刻に補正されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    segments: list[Any] = [
        SimpleNamespace(
            start=0.0,
            end=2.0,
            text="テスト発言",
            no_speech_prob=0.05,
            words=[SimpleNamespace(start=0.45, end=1.8, word="テスト発言")],
        ),
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 1
    assert results[0].start == 0.45


def test_sanitizer_handles_dict_inputs() -> None:
    """辞書形式のセグメントおよび単語データが正しく処理されることを検証します。"""
    # Arrange
    sanitizer = SegmentSanitizer()
    segments: list[dict[str, Any]] = [
        {
            "start": 0.0,
            "end": 2.0,
            "text": "辞書セグメント",
            "no_speech_prob": 0.05,
            "words": [{"start": 0.2, "end": 1.8}],
        }
    ]

    # Act
    results: list[SubtitleSegment] = sanitizer.sanitize_segments(segments)

    # Assert
    assert len(results) == 1
    assert results[0].start == 0.2
    assert results[0].text == "辞書セグメント"
```

---

### 4.3 `tests/test_exporter.py`
```python
"""Tests for SubtitleExporter module."""

import json
from pathlib import Path
import pytest
from audio_transcriber.exporter import SubtitleExporter
from audio_transcriber.models import SubtitleSegment


def test_exporter_timestamp_formatting() -> None:
    """SRT および WebVTT 形式のタイムスタンプ文字列生成を検証します。"""
    # Arrange & Act
    srt_ts = SubtitleExporter.format_timestamp(3661.5)
    vtt_ts = SubtitleExporter.format_vtt_timestamp(3661.5)

    # Assert
    assert srt_ts == "01:01:01,500"
    assert vtt_ts == "01:01:01.500"


def test_exporter_save_srt(tmp_path: Path) -> None:
    """SRT フォーマットファイルが DaVinci Resolve 準拠で出力されることを検証します。"""
    # Arrange
    segments = [
        SubtitleSegment(start=1.0, end=3.5, text="こんにちは"),
        SubtitleSegment(start=4.0, end=6.2, text="さようなら"),
    ]
    out_file = tmp_path / "subtitles.srt"

    # Act
    SubtitleExporter.save_srt(segments, out_file)

    # Assert
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "1\n00:00:01,000 --> 00:00:03,500\nこんにちは" in content
    assert "2\n00:00:04,000 --> 00:00:06,200\nさようなら" in content


def test_exporter_save_vtt(tmp_path: Path) -> None:
    """WebVTT フォーマットファイルが出力されることを検証します。"""
    # Arrange
    segments = [SubtitleSegment(start=1.0, end=2.5, text="テスト")]
    out_file = tmp_path / "subtitles.vtt"

    # Act
    SubtitleExporter.save_vtt(segments, out_file)

    # Assert
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert content.startswith("WEBVTT\n")
    assert "00:00:01.000 --> 00:00:02.500" in content
    assert "テスト" in content


def test_exporter_save_json(tmp_path: Path) -> None:
    """JSON フォーマットファイルが正しく構造化されて出力されることを検証します。"""
    # Arrange
    segments = [SubtitleSegment(start=1.0, end=2.0, text="JSONテスト")]
    out_file = tmp_path / "subtitles.json"

    # Act
    SubtitleExporter.save_json(segments, out_file)

    # Assert
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0] == {"start": 1.0, "end": 2.0, "text": "JSONテスト"}


def test_exporter_save_subtitles_auto_detect_and_explicit(tmp_path: Path) -> None:
    """save_subtitles による拡張子自動判定および明示的フォーマット指定を検証します。"""
    # Arrange
    segments = [SubtitleSegment(start=0.0, end=1.0, text="自動判定")]

    # Act & Assert 1: .srt
    srt_p = tmp_path / "test.srt"
    SubtitleExporter.save_subtitles(segments, srt_p)
    assert "00:00:00,000 --> 00:00:01,000" in srt_p.read_text(encoding="utf-8")

    # Act & Assert 2: .vtt
    vtt_p = tmp_path / "test.vtt"
    SubtitleExporter.save_subtitles(segments, vtt_p)
    assert "WEBVTT" in vtt_p.read_text(encoding="utf-8")

    # Act & Assert 3: .json
    json_p = tmp_path / "test.json"
    SubtitleExporter.save_subtitles(segments, json_p)
    assert "自動判定" in json_p.read_text(encoding="utf-8")

    # Act & Assert 4: Explicit fmt override
    custom_p = tmp_path / "output.custom"
    SubtitleExporter.save_subtitles(segments, custom_p, fmt="srt")
    assert "00:00:00,000 --> 00:00:01,000" in custom_p.read_text(encoding="utf-8")


def test_exporter_unsupported_format_raises(tmp_path: Path) -> None:
    """未対応の拡張子または fmt で ValueError が発生することを検証します。"""
    # Arrange
    segments = [SubtitleSegment(start=0.0, end=1.0, text="エラーテスト")]

    # Act & Assert
    with pytest.raises(ValueError, match="未対応の拡張子です"):
        SubtitleExporter.save_subtitles(segments, tmp_path / "test.txt")

    with pytest.raises(ValueError, match="未対応のフォーマットです"):
        SubtitleExporter.save_subtitles(segments, tmp_path / "test.custom", fmt="unknown")
```

---

## 5. カバレッジと品質検証方針 (Coverage & Quality Assurance)

### 5.1 カバレッジ目標
- `models.py`: 100% (Line & Branch)
- `sanitizer.py`: 100% (Line & Branch)
- `exporter.py`: 100% (Line & Branch)

### 5.2 実行・検証コマンド
```bash
# テスト実行 & カバレッジ詳細レポート
uv run pytest tests/test_models.py tests/test_sanitizer.py tests/test_exporter.py --cov=audio_transcriber --cov-report=term-missing

# 静的型チェック (0 errors)
uv run basedpyright

# リント & フォーマット検証
uv run ruff check .
uv run ruff format --check .
```
