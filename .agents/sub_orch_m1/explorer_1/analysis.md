# Milestone 1 リファレンス実装調査・設計分析レポート

## 概要
本レポートは、`lumi_companion` における音声認識後処理モジュール（`segment_sanitizer.py` および `srt_exporter.py`）の実装仕様、アルゴリズムの詳細、DaVinci Resolve / WebVTT / JSON 各フォーマットの出力仕様、および `audio-transcriber` プロジェクト（Milestone 1）への移植・適合方針をまとめた調査分析書である。

---

## 1. `SegmentSanitizer` アルゴリズム詳細分析

### 1.1 役割と責務
Whisper (faster-whisper) の音声認識結果から、以下のハルシネーション（無音区間の捏造、異常発話速度、同一フレーズの繰り返しループ等）を自動検知して除外・短縮し、単語レベルタイムスタンプに基づき文頭発声開始位置を補正して `list[SubtitleSegment]` を生成する。

### 1.2 アルゴリズムの各ステップ詳細

```
[入力セグメント群 (Iterable[Any])]
   │
   ├─ 1. テキスト抽出 & 空白チェック (text.strip() が空ならスキップ)
   │
   ├─ 2. セグメント内リピート判定・短縮 (Intra-Segment Repetition)
   │      - 条件: len(text) >= 4 かつ 前半 == 後半
   │      - トリガー: no_speech_prob > 0.1 または compression_ratio > 2.0
   │      - 処理: text = text[:half_len] に短縮
   │
   ├─ 3. 単語タイムスタンプによる開始時刻補正 (Word Timestamp Alignment)
   │      - words が存在する場合、words[0].start をセグメント start に適用
   │
   ├─ 4. セグメント間ループ重複判定 (Inter-Segment Loop Repetition)
   │      - 条件: last_valid_text が存在 かつ no_speech_prob > 0.1
   │      - 判定: text == last_valid_text または text in last_valid_text
   │      - 処理: セグメントを破棄 (ドロップ)
   │
   ├─ 5. 無音捏造判定 (No-Speech Hallucination)
   │      - 条件: no_speech_prob > no_speech_threshold (デフォルト 0.6)
   │      - 処理: セグメントを破棄 (ドロップ)
   │
   ├─ 6. 異常発話速度判定 (Speech Rate Anomaly)
   │      - 計算: duration = max(end - start, 0.1)
   │             chars_per_sec = len(text) / duration
   │      - 条件: chars_per_sec > max_chars_per_second (デフォルト 12.0) かつ len(text) > 4
   │      - 処理: セグメントを破棄 (ドロップ)
   │      - 短文保護: len(text) <= 4 の短文（「はい」「うん」等）は速度制限チェックを除外
   │
   └─ 7. 有効セグメントの構築と登録
          - SubtitleSegment(start=round(start, 3), end=round(end, 3), text=text)
          - last_valid_text を更新
          - 進行状況ログ出力 (total_duration > 0 の場合は進捗%付き)
```

### 1.3 パラメータと閾値一覧

| パラメータ / 閾値 | デフォルト値 | 役割・判定条件 | ログレベル |
|---|---|---|---|
| `no_speech_threshold` | `0.6` | セグメントの無音確率がこれを超える場合は無音捏造としてドロップ | `DEBUG` |
| `max_chars_per_second` | `12.0` | 1秒あたりの最大文字数。物理的人間発話限界（約10〜12文字/秒）を超過した場合にドロップ | `DEBUG` |
| 短文保護閾値 | `len(text) <= 4` | 0.1〜0.3秒で発声される短い相槌（「はい」「うん」等）が異常速度判定で誤爆ドロップされるのを防止 | - |
| リピート判定無音閾値 | `no_speech_prob > 0.1` | ループ重複やセグメント内重複がハルシネーションであるかを判定するゲート | `INFO` |
| 圧縮率閾値 (`compression_ratio`) | `> 2.0` | Whisperのトークン圧縮率が高い（繰り返し文字列が多発している）場合のセグメント内リピート短縮トリガー | `INFO` |
| 最小継続秒数 (`duration`) | `max(end - start, 0.1)` | ゼロ除算防止のための下限クランプ | - |
| タイムスタンプ丸め | `round(val, 3)` | ミリ秒精度（小数点以下3桁）への丸め | - |

### 1.4 オブジェクトおよび辞書入力への対応
faster-whisper の出力オブジェクト（`Segment`, `Word`）だけでなく、辞書型データ（`dict`）や `SimpleNamespace` など多様な形式が渡された場合でも安全にフィールドを抽出できるようにする。

- `get_word_time(word_obj, attr_name)`:
  - `isinstance(word_obj, dict)` ➔ `word_obj.get(attr_name)`
  - その他 ➔ `getattr(word_obj, attr_name, None)`
  - 数値型（`int | float`）であることを確認して `float` を返す。
- セグメントフィールド抽出:
  - `getattr(segment, "text", "")` または `segment.get("text", "")` (辞書対応)
  - `getattr(segment, "no_speech_prob", 0.0)`
  - `getattr(segment, "compression_ratio", 0.0)`
  - `getattr(segment, "start", 0.0)`
  - `getattr(segment, "end", 0.0)`
  - `getattr(segment, "words", None)`

---

## 2. `SubtitleExporter` 実装および各フォーマット仕様分析

### 2.1 概要
抽出・サニタイズ・タイミング調整された字幕セグメントリスト（`Sequence[SubtitleSegment]`）を、用途に応じた3つの標準ファイル形式（SRT, WebVTT, JSON）へ出力する。

### 2.2 出力フォーマット比較

| 項目 | SRT (`.srt`) | WebVTT (`.vtt`) | JSON (`.json`) |
|---|---|---|---|
| **ヘッダー** | なし | `WEBVTT\n\n` | なし |
| **タイムスタンプ形式** | `HH:MM:SS,mmm` (カンマ区切り) | `HH:MM:SS.mmm` (ドット区切り) | 数値 (`float`: 1.234) |
| **シーケンス番号** | 1から始まる連番 | 1から始まる連番 | なし（配列順） |
| **エントリ区切り** | `\n\n` (空行) | `\n\n` (空行) | カンマ区切り |
| **文字コード** | UTF-8 (BOMなし) | UTF-8 | UTF-8 (`ensure_ascii=False`) |
| **改行コード** | LF (`\n`) | LF (`\n`) | LF (`\n`), `indent=2` |
| **主な用途** | DaVinci Resolve, Premiere 等 | Web動画プレイヤー, ブラウザ | プログラム連携, デバッグ, 後続API |

### 2.3 DaVinci Resolve 互換性要件
DaVinci Resolve の字幕インポート（SRT）仕様を満たすため、以下の条件を厳格に順守する：
1. **ミリ秒区切り文字**: 必ずカンマ `,` を使用（例: `00:01:23,456`）。ドット `.` ではインポートエラーやタイムコード不一致となる場合がある。
2. **2桁ゼロ埋め**: 時・分・秒は2桁 `02d`、ミリ秒は3桁 `03d`。
3. **文字エンコーディング**: UTF-8。
4. **改行コード**: LF (`\n`)。
5. **シーケンス連番**: 各ブロックの1行目に 1-indexed の連番整数。

### 2.4 クラス設計とメソッド一覧
- `format_timestamp(seconds: float) -> str`: 秒数を `HH:MM:SS,mmm` にフォーマット。
- `format_vtt_timestamp(seconds: float) -> str`: 秒数を `HH:MM:SS.mmm` にフォーマット。
- `save_srt(segments: Sequence[SubtitleSegment], output_path: Path) -> None`: SRT ファイル出力。
- `save_vtt(segments: Sequence[SubtitleSegment], output_path: Path) -> None`: WebVTT ファイル出力。
- `save_json(segments: Sequence[SubtitleSegment], output_path: Path) -> None`: JSON ファイル出力。
- `save_subtitles(segments: Sequence[SubtitleSegment], output_path: Path, fmt: str | None = None) -> None`:
  - `fmt` が None の場合は `output_path.suffix.lower()`（`.srt`, `.vtt`, `.json`）から自動判別。
  - 大文字拡張子（`.SRT`, `.VTT`, `.JSON`）や大文字 `fmt`（`"SRT"` 等）に対応。
  - 未対応の拡張子/フォーマットの場合は `ValueError` を送出。
  - 親ディレクトリが存在しない場合は自動作成（`output_path.parent.mkdir(parents=True, exist_ok=True)`）。

---

## 3. `audio-transcriber` への移植・適合方針

### 3.1 外部依存ライブラリの排除（Pure Python 実装）
- `lumi_companion` では `srt` サードパーティライブラリ（`import srt`）を使用していた。
- しかし `audio-transcriber` の `pyproject.toml` には `srt` パッケージが含まれておらず、標準ライブラリのみで完全に DaVinci Resolve 準拠の SRT 生成が可能である。
- `save_srt` を自前の `format_timestamp` と文字列結合で実装することにより、不要な外部依存を排除し、LF 改行コードやフォーマットの一貫性を確実に担保できる。

### 3.2 モジュール分割方針（KISS原則・行数制限遵守）
プロジェクト規約（1ファイル最大300行以下、目標200行以下）に従い、以下の3ファイルに分割して配置する：

1. `src/audio_transcriber/models.py` (~40行):
   - `SubtitleSegment(start: float, end: float, text: str)`
   - `to_dict() -> dict[str, Any]`
   - `from_dict(cls, data: dict[str, Any]) -> SubtitleSegment`
2. `src/audio_transcriber/sanitizer.py` (~150行):
   - `SegmentSanitizer(no_speech_threshold: float = 0.6, max_chars_per_second: float = 12.0)`
   - `sanitize_segments(segments: Iterable[Any], total_duration: float = 0.0) -> list[SubtitleSegment]`
   - `get_word_time(word_obj: object, attr_name: str) -> float | None`
3. `src/audio_transcriber/exporter.py` (~140行):
   - `SubtitleExporter`
   - `format_timestamp`, `format_vtt_timestamp`
   - `save_srt`, `save_vtt`, `save_json`, `save_subtitles`

### 3.3 型安全性・品質基準
- Python 3.11+ 厳格な型注釈（`from collections.abc import Iterable, Sequence` 等）。
- `basedpyright` エラー 0 件を達成。
- Google スタイル日本語 Docstring（概要, `Args`, `Returns`, `Raises`）。
- AAA パターンによるユニットテスト作成：
  - `tests/test_models.py`
  - `tests/test_sanitizer.py`
  - `tests/test_exporter.py`
