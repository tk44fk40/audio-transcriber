# 技術調査レポート: lumi_companion 音声後処理パイプラインの構造と移植要件

- **調査日時**: 2026-08-15
- **調査対象**: `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/`
- **目的**: `lumi_companion` の後処理機能（サニタイズ・数字正規化・タイミング補正・字幕エクスポート・辞書置換）の仕様を精査し、`audio-transcriber` への移植に必要な設計・依存関係・アルゴリズム・注意事項を体系化する。

---

## 1. モジュール別詳細調査結果

### 1.1 `number_normalizer.py` (数字正規化)

#### 概要
漢数字、ローマ数字、丸数字、全角/半角数字の表記揺れを統一正規化するユーティリティクラス。

#### アルゴリズムと処理フロー
`NumberNormalizer.normalize(text: str) -> str` は以下の順序でテキストを変換する：

```
入力テキスト
  │
  ├─ 1. 全角数字の半角化 (str.maketrans: ０-９ -> 0-9)
  │
  ├─ 2. 丸数字の変換 (replace: ①-⑳ -> 1-20)
  │
  ├─ 3. ローマ数字の長順変換 (replace: VIII, VII, Ⅷ, Ⅶ, ..., I, Ⅰ -> 8, 7, ..., 1)
  │      ※接頭辞の部分一致競合を防ぐため文字列長降順でソート
  │
  ├─ 4. 漢数字のシンプル変換 (replace: 十->10, 九->9, ..., 一->1, 〇->0, ゼロ->0)
  │
  ├─ 5. 十進位取り補正 (re.sub: r"10([1-9])" -> r"1\1")
  │      ※「十一」->「101」->「11」、「十二」->「102」->「12」等の結合補正
  │
  └─ 6. 全角数字への統一変換 (str.maketrans: 0-9 -> ０-９)
```

#### 依存関係
- **外部依存なし**（標準ライブラリ `re`, `str.maketrans`, `str.translate`, `str.replace` のみ）。

#### 特記事項・注意事項
- 最終出力は全角数字（`０-９`）に変換される。
- `TextPostProcessor` で `to_hankaku=True` が設定されている場合は、後続の `unicodedata.normalize("NFKC", ...)` で半角数字に変換されるため、全角/半角の双方に対応可能。

---

### 1.2 `segment_sanitizer.py` (セグメントサニタイズ & ハルシネーション検出)

#### 概要
Faster-Whisper の認識結果（Segment オブジェクト群）から、無音区間の捏造、異常な発話速度、ループハルシネーション、セグメント内リピートを自動検出し、除外および補正を行うクラス。

#### 主要パラメータ
- `no_speech_threshold: float = 0.6` : 無音判定閾値（この値を超えるセグメントをドロップ）
- `max_chars_per_second: float = 12.0` : 人間の物理的発話速度の許容上限（文字/秒）

#### アルゴリズムと処理フロー
`SegmentSanitizer.sanitize_segments(segments, total_duration=0.0) -> list[SubtitleSegment]`

1. **空文字・空白判定**:
   - `text = getattr(segment, "text", "").strip()` が空ならスキップ。
2. **セグメント内リピート判定・短縮 (Intra-segment Repetition)**:
   - 前半部と後半部が完全一致（`half_len = len(text) // 2`, `text[:half_len] == text[half_len:]`）かつ `len(text) >= 4` を検出。
   - 人間の意図的な繰り返し（「もしもし？もしもし？」）との誤判定を防ぐため、ハルシネーションの兆候（`no_speech_prob > 0.1` または `compression_ratio > 2.0`）がある場合のみ `text = text[:half_len]` に短縮。
3. **単語レベルタイムスタンプによる発声開始位置補正**:
   - `words` 属性が存在する場合、先頭単語の開始時刻（`SegmentSanitizer.get_word_time(words[0], "start")`）を発声開始時刻 `start` に採用（Whisper セグメント開始の余白を短縮）。
4. **発話速度の計算**:
   - `duration = max(end - start, 0.1)`
   - `chars_per_sec = len(text) / duration`
5. **ループハルシネーション除外 (Inter-segment Repetition)**:
   - 直前の有効テキスト `last_valid_text` と完全一致または包含関係（`text == last_valid_text or text in last_valid_text`）であり、かつ `no_speech_prob > 0.1` の場合、セグメントをドロップ。
6. **無音捏造判定**:
   - `no_speech_prob > self.no_speech_threshold`（デフォルト 0.6）の場合、セグメントをドロップ。
7. **異常発話速度判定**:
   - `chars_per_sec > self.max_chars_per_second`（デフォルト 12.0文字/秒）かつ `len(text) > 4` の場合、セグメントをドロップ（4文字以下の短い相槌「はい」等は誤ドロップ防止のため保護）。
8. **有効セグメントの構築**:
   - `SubtitleSegment(start=round(start, 3), end=round(end, 3), text=text)` を生成し、リストに追加。

#### 依存関係
- **外部依存なし**（`logging`, `collections.abc.Iterable` のみ）。

---

### 1.3 `timing_adjuster.py` (字幕タイミング補正)

#### 概要
Whisper が検出した物理的な発声終了時刻に対し、視聴者の可読性を向上させる余韻パディング付与、最小表示時間の確保、および後続セグメントとの重なり防止（ギャップ制御）を行う。

#### 主要パラメータ
- `end_padding: float` (例: 1.0秒) : 発話終了後の余韻表示秒数
- `min_duration: float` (例: 1.5秒) : 字幕の最小表示秒数
- `min_gap: float` (例: 0.05秒) : 連続するセグメント間の最小隙間秒数

#### アルゴリズムと処理フロー
`SubtitleTimingAdjuster.adjust_segments(segments, total_duration=None) -> list[SubtitleSegment]`

各セグメント `seg[i]` に対して以下を順次計算：
1. **余韻延長 & 最小表示時間確保**:
   - `padded_end = seg.end + self.end_padding`
   - `min_required_end = seg.start + self.min_duration`
   - `target_end = max(padded_end, min_required_end)`
2. **次セグメントとの重複防止クリップ**:
   - 後続セグメントが存在する場合（`i + 1 < count`）：
     - `next_start = segments[i + 1].start`
     - `max_allowed_end = next_start - self.min_gap`
     - `if max_allowed_end > seg.start:` -> `target_end = min(target_end, max_allowed_end)`
     - `else:` -> `target_end = min(target_end, next_start)`
3. **動画総再生時間クリップ**:
   - `if total_duration and total_duration > 0:` -> `target_end = min(target_end, total_duration)`
4. **整合性ガード**:
   - `final_end = max(seg.start, target_end)`
5. **補正後セグメント生成**:
   - `SubtitleSegment(start=round(seg.start, 3), end=round(final_end, 3), text=seg.text)`

#### 設計パターン
- `TimingAdjusterProtocol(Protocol)` による抽象化（Strategy パターン）。

#### 依存関係
- **外部依存なし**（`logging`, `typing.Protocol` のみ）。

---

### 1.4 `srt_exporter.py` (字幕エクスポート: SRT / WebVTT / JSON)

#### 概要
`SubtitleSegment` のリストを DaVinci Resolve 互換 SRT、WebVTT、JSON の各形式でファイル出力するクラス。

#### 各フォーマットの仕様と出力構造

| フォーマット | 拡張子 | タイムスタンプ形式 | 仕様要件 |
|---|---|---|---|
| **SRT** | `.srt` | `00:00:00,000` (カンマ区切りミリ秒) | UTF-8, LF改行, 連番インデックス, DaVinci Resolve インポート仕様準拠 |
| **WebVTT** | `.vtt` | `00:00:00.000` (ドット区切りミリ秒) | `WEBVTT` ヘッダー行, 連番インデックス, UTF-8, LF改行 |
| **JSON** | `.json` | 数値 (`start: 1.0, end: 2.5`) | `[{"start": float, "end": float, "text": str}]`, `ensure_ascii=False`, `indent=2` |

#### メソッド一覧
- `format_timestamp(seconds: float) -> str`: 秒数を `HH:MM:SS,mmm` に変換
- `format_vtt_timestamp(seconds: float) -> str`: 秒数を `HH:MM:SS.mmm` に変換
- `save_srt(segments, output_path: Path) -> None`: SRT 出力
- `save_vtt(segments, output_path: Path) -> None`: WebVTT 出力
- `save_json(segments, output_path: Path) -> None`: JSON 出力
- `save_subtitles(segments, output_path: Path, fmt: str | None = None) -> None`: 拡張子または引数による自動ディスパッチ

#### 依存関係と実装方針
- `lumi_companion` ではサードパーティ製 `srt` ライブラリ（`import srt`）を使用している。
- `audio-transcriber` では `srt` パッケージを追加しなくても、標準ライブラリ（文字列フォーマット処理）のみで DaVinci Resolve 互換の SRT を完全・決定論的に生成可能（現行 `transcribe.py` で実装済みの `format_timestamp` ロジックを流用可能）。これにより不要な外部依存を削減できる。

---

### 1.5 `post_processor.py` (テキスト後処理 & カスタム辞書置換)

#### 概要
置換辞書（単語置換）の適用、Unicode (NFKC) 正規化、数字正規化、英小文字化、記号・句読点除去を一括管理するクラス。

#### カスタム辞書機能
- `load_dictionary(file_path: Path) -> dict[str, str]`:
  - 対応形式: `.json`, `.yaml`, `.yml`, および `.toml` (audio-transcriber の要件)
  - 辞書のキー文字列を長さの降順（`sorted(keys, key=len, reverse=True)`）でソートして保持。
  - **長順置換の理由**: 部分一致による誤置換（例: "ABC" -> "123", "AB" -> "99" の場合に "ABC" を先に置換しないと "99C" に誤変換される）を完全に防止するため。

#### テキスト正規化パイプライン (`normalize_text`)
1. **数字正規化** (`normalize_nums=True`): `NumberNormalizer.normalize(result)`
2. **全半角統一** (`to_hankaku=True`): `unicodedata.normalize("NFKC", result)`
3. **記号・句読点処理**:
   - `remove_punct=True`: `re.sub(r"[、。！？!?\s\r\n]", "", result)`
   - `remove_punct=False`: `re.sub(r"[\r\n]+", " ", result).strip()` (改行を半角空白へ)
4. **英小文字化** (`lower=True`): `result.lower()`

#### セグメント適用 (`apply_to_segments`)
- 各セグメントに対し `apply_to_text(seg.text)` を実行し、正規化後のテキストが空でなければ新しい `SubtitleSegment` を生成。

---

### 1.6 データモデル (`SubtitleSegment`)

#### 定義
```python
@dataclass
class SubtitleSegment:
    """タイムスタンプ付き発言字幕データモデル。"""

    start: float
    end: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubtitleSegment":
        return cls(
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            text=str(data.get("text", "")),
        )
```

---

## 2. 依存関係の比較と必要ライブラリの選定

### 2.1 `lumi_companion` と `audio-transcriber` の依存比較

| ライブラリ | lumi_companion での用途 | audio-transcriber での要否 | 理由・方針 |
|---|---|---|---|
| **janome** | 形態素解析による文節分割 (`segment_splitter.py`) | **除外 (不要)** | `ORIGINAL_REQUEST.md` で文節分割の除外が明記されているため |
| **srt** | SRT 字幕文字列の生成 (`srt_exporter.py`) | **不要 (標準ライブラリで代替)** | 標準の文字列フォーマット (`HH:MM:SS,mmm`) で完全に代替可能 |
| **pyyaml** | YAML 形式の置換辞書読み込み | **利用可能 (オプション)** | TOML / JSON は標準ライブラリ（`tomllib`, `json`）で対応。YAML 対応も `pyyaml` が環境にあれば連携可能 |
| **faster-whisper** | 音声認識推論 | **既存利用中** | 既存の依存関係をそのまま維持 |
| **deepfilternet** | ノイズ除去 | **既存利用中** | 音声前処理として維持 |

### 2.2 結論
後処理モジュールの移植にあたり、**新規の外部依存ライブラリの追加は一切不要**。Python 3.11 標準ライブラリ（`dataclasses`, `pathlib`, `re`, `unicodedata`, `json`, `tomllib`, `datetime`, `typing`, `logging`）のみで全要件を型安全に充足可能。

---

## 3. `audio-transcriber` への統合設計方針

### 3.1 ディレクトリ・ファイル構成案

```
src/audio_transcriber/
├── __init__.py
├── cli.py                  # CLI オプション追加（後処理フラグ等）
├── compat.py               # 互換レイヤー
├── config.py               # MAX_SEGMENT_CHARS 削除、後処理パラメータ整備
├── denoise.py              # ノイズ除去
├── media.py                # メディア処理
├── models.py               # SubtitleSegment データモデル
├── pipeline.py             # 後処理統合、PipelineResult (vtt, json 追加)
├── transcribe.py           # Whisper 呼び出し
└── post_process/           # 後処理サブパッケージ (または単一責任のモジュール群)
    ├── __init__.py
    ├── number_normalizer.py # 数字正規化
    ├── sanitizer.py         # ハルシネーションサニタイズ
    ├── timing.py            # タイミング補正
    ├── exporter.py          # SRT / WebVTT / JSON エクスポート
    └── processor.py         # TextPostProcessor
```

### 3.2 パイプライン連携シーケンス

```
WhisperModel.transcribe(audio)
  │ (raw_segments, info)
  ▼
SegmentSanitizer.sanitize_segments(raw_segments, total_duration)
  │ (sanitized SubtitleSegment リスト)
  ▼
TextPostProcessor.apply_to_segments(sanitized_segments)
  │ (正規化・単語置換済 SubtitleSegment リスト)
  ▼
SubtitleTimingAdjuster.adjust_segments(normalized_segments, total_duration)
  │ (余韻・最小表示・重複防止適用済 SubtitleSegment リスト)
  ▼
SubtitleExporter:
  ├─ save_srt(final_segments, srt_path)   -> {stem}.srt
  ├─ save_vtt(final_segments, vtt_path)   -> {stem}.vtt
  └─ save_json(final_segments, json_path) -> {stem}.json
```

### 3.3 廃止・削除対象
- `config.toml`, `config.example.toml`, `src/audio_transcriber/config.py`, `tests/test_config.py` 内の `MAX_SEGMENT_CHARS` / `max_segment_chars` パラメータ。

---

## 4. 品質基準・テスト戦略

1. **モジュール単体テスト (AAA パターン)**:
   - `tests/test_models.py`: `SubtitleSegment` の辞書変換・復元
   - `tests/test_number_normalizer.py`: 漢数字、ローマ数字、丸数字、全角数字の境界値
   - `tests/test_segment_sanitizer.py`: 無音捏造、発話速度異常、短文保護、ループ除外、セグメント内リピート短縮
   - `tests/test_timing_adjuster.py`: 余韻付与、最小表示時間、重複防止ギャップ、総再生時間クリップ
   - `tests/test_srt_exporter.py`: SRT, VTT, JSON の出力フォーマット、タイムスタンプ検証
   - `tests/test_post_processor.py`: TOML/YAML/JSON 辞書読み込み、長順置換、正規化フラグ独立性
2. **パイプライン統合テスト**:
   - `tests/test_pipeline.py`: 後処理ステップの実行と SRT / VTT / JSON 3ファイルの生成確認
3. **静的解析**:
   - `uv run basedpyright` (エラー 0 件)
   - `uv run ruff check .` / `uv run ruff format --check .`
