# audio-transcriber 現行コードベース詳細調査レポート

本レポートは、`lumi_companion` からの後処理機能移植および `MAX_SEGMENT_CHARS` 廃止・SRT/VTT/JSON 3形式出力拡張に向けた、`audio-transcriber` リポジトリの現行コードベース調査結果をまとめたものです。

---

## 1. 設定管理 (`config.py`, `config.toml`, `config.example.toml`)

### 1.1 `MAX_SEGMENT_CHARS` / `max_segment_chars` の存在箇所
調査の結果、`MAX_SEGMENT_CHARS` / `max_segment_chars` は以下のファイル・行に存在しています：

1. **`src/audio_transcriber/config.py`**:
   - 行 75: `PostProcessConfig` クラス内
     ```python
     max_segment_chars: int = 30
     ```
   - 行 192: `parse_config_dict` 関数内
     ```python
     max_segment_chars=int(post_data.get("max_segment_chars", 30)),
     ```
2. **`config.toml`**:
   - 行 116: `[post_process]` セクション内
     ```toml
     # 長大セグメントの文字数による自動分割（0 で機能OFF）
     MAX_SEGMENT_CHARS = 30
     ```
3. **`config.example.toml`**:
   - 行 103: `[post_process]` セクション内
     ```toml
     # 長大セグメントの文字数による自動分割（0 で機能OFF）
     MAX_SEGMENT_CHARS = 30
     ```
4. **`tests/test_config.py`**:
   - 行 90: テスト用 TOML 文字列内 `MAX_SEGMENT_CHARS = 25`
   - 行 124: アサーション `assert cfg.post_process.max_segment_chars == 25`

### 1.2 現行の後処理関連設定クラスの構造
`src/audio_transcriber/config.py` における現在の設定クラス構成は以下の通りです：

```python
@dataclass
class PostProcessConfig:
    """Text post-processing configuration."""

    replace_terms: bool = True
    to_hankaku: bool = False
    normalize_nums: bool = True
    lower: bool = False
    remove_punct: bool = False
    max_segment_chars: int = 30  # ← 廃止対象


@dataclass
class SubtitleConfig:
    """Subtitle timing adjustment configuration."""

    end_padding: float = 1.0
    min_duration: float = 1.5
    min_gap: float = 0.05


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

### 1.3 必要な変更点
- `PostProcessConfig` および `parse_config_dict` から `max_segment_chars` パラメータを完全削除する。
- `config.toml` および `config.example.toml` から `MAX_SEGMENT_CHARS` の定義・コメントを削除する。
- `test_config.py` 内のテストケースから `MAX_SEGMENT_CHARS` のテストを削除・更新する。
- 必要に応じてサニタイズ用のパラメータ（`max_chars_per_second: float = 12.0` など）を設定項目に追加検討する。

---

## 2. パイプラインオーケストレーション (`pipeline.py`)

### 2.1 現行の `PipelineResult` と `run_pipeline`
現在 `src/audio_transcriber/pipeline.py` (全122行) は以下のように実装されています：

```python
@dataclass
class PipelineResult:
    """Result of audio/video processing pipeline."""

    input_file: Path
    denoised_audio: Path | None
    srt_file: Path | None
    transcript_text: str | None
    remuxed_video: Path | None = None
```

現行の `run_pipeline` 処理フロー：
1. 入力パスが動画か音声かを判定 (`is_video_file`)。
2. 動画の場合、`extract_audio_track` で指定マイク音声を WAV 抽出。
3. `denoise=True` の場合、`denoise_audio` (DeepFilterNet) でクリーン音声を生成 (`{stem}_clean.wav`)。
4. `transcribe=True` の場合、`transcribe_audio` (faster-whisper) を呼び出し、直接 `{stem}.srt` を出力。
5. `remux=True` かつ動画の場合、`remux_video` (ffmpeg) でクリーン音声を映像トラックと再結合 (`{stem}_clean.{ext}`)。
6. `PipelineResult` を返却。

### 2.2 後処理ステージおよび新出力形式 (VTT, JSON) の統合方針
要件 R1 / R2 に基づき、パイプラインを以下のように拡張・統合します：

1. **`PipelineResult` のフィールド拡張**:
   ```python
   @dataclass
   class PipelineResult:
       input_file: Path
       denoised_audio: Path | None
       srt_file: Path | None
       vtt_file: Path | None = None  # 追加
       json_file: Path | None = None  # 追加
       transcript_text: str | None = None
       remuxed_video: Path | None = None
   ```
2. **文字起こし・後処理パイプラインの結合**:
   - `transcribe_audio` は Faster-Whisper による推論と生のセグメント（単語タイムスタンプ `words` を含む）取得を担当。
   - 取得した生セグメントに対して以下の後処理を順次適用：
     1. **`SegmentSanitizer`**: 無音捏造除外 (`no_speech_prob`)、異常発話速度除外 (`chars_per_sec > 12.0`)、セグメント内リピート短縮、ループ重複除外、単語タイムスタンプによる発声開始位置補正。
     2. **`TextPostProcessor`**: カスタム辞書置換（最長一致順）、数字正規化 (`NumberNormalizer`)、全角半角正規化 (`NFKC`)、英小文字化、句読点除去。
     3. **`SubtitleTimingAdjuster`**: 余韻パディング (`end_padding`)、最小表示時間 (`min_duration`)、セグメント間隙間確保 (`min_gap`)、総再生時間でのクリッピング。
     4. **`SubtitleExporter`**: 同一の調整済み `SubtitleSegment` リストから SRT (`{stem}.srt`)、WebVTT (`{stem}.vtt`)、JSON (`{stem}.json`) の3形式ファイルを一括生成。
3. **パラメータの受け渡し**:
   - `run_pipeline` に `post_process_config: PostProcessConfig | None`, `subtitle_config: SubtitleConfig | None`, `custom_dictionary_path: Path | None` などの引数を追加、または設定オブジェクトを受け取れるように拡張する。

---

## 3. CLI インターフェース (`cli.py`)

### 3.1 現行の CLI 実装
`src/audio_transcriber/cli.py` (全226行) は `typer` および `rich` を使用して構築されています。

現在の主なオプション：
- `--config` / `-C`: 設定ファイルパス
- `--output-dir` / `-o`: 出力先ディレクトリ
- `--mic-track` / `-t`: マイク音声トラック番号
- `--model-size` / `-m`: Whisper モデルサイズ
- `--device` / `-d`: 推論デバイス
- `--compute-type` / `-c`: 量子化タイプ
- `--language` / `-l`: 言語コード
- `--prompt` / `-p`: 初期プロンプト
- `--denoise-only`: ノイズ除去のみ実行
- `--transcribe-only`: 文字起こしのみ実行
- `--remux / --no-remux`: 動画再結合の有無
- `--min-silence-ms`: VAD 最小無音時間

### 3.2 後処理オプションの追加と配線
1. **追加すべき CLI オプション**:
   - `--custom-dict` / `-D`: カスタム置換辞書ファイルパス (`Path | None`)
   - `--end-padding`: 字幕余韻秒数 (`float | None`)
   - `--min-duration`: 字幕最小表示秒数 (`float | None`)
   - `--min-gap`: 字幕セグメント最小間隔秒数 (`float | None`)
   - `--normalize-nums / --no-normalize-nums`: 数字正規化フラグ (`bool | None`)
   - `--to-hankaku / --no-to-hankaku`: 半角化フラグ (`bool | None`)
2. **実行結果表示テーブルの更新**:
   - `Table` に `VTT Subtitle` (`result.vtt_file`) および `JSON Subtitle` (`result.json_file`) の表示行を追加。

---

## 4. 字幕生成ロジックと target との比較 (`subtitles.py` / `transcribe.py`)

### 4.1 現行実装 (`transcribe.py`)
現在は独立した `subtitles.py` やエクスポートモジュールは存在せず、`transcribe.py` 内で簡易関数として実装されています：

- `format_timestamp(seconds: float) -> str`: 秒数を `HH:MM:SS,mmm` (SRT 形式) にフォーマット。
- `segments_to_srt(segments: Iterable[Any]) -> str`: Faster-Whisper のセグメントをループして単純な SRT 文字列を組み立て。

### 4.2 移植元 (`lumi_companion`) のアーキテクチャ
`lumi_companion` では以下のモジュールに責務が分離されています：
1. **`models/audio.py`**:
   - `SubtitleSegment(start: float, end: float, text: str)`: `to_dict()`, `from_dict()` を持つデータモデル。
2. **`number_normalizer.py`**:
   - `NumberNormalizer.normalize(text: str) -> str`: 全角数字の半角化 ➔ 丸数字 (①〜⑳) ➔ ローマ数字 (I〜X, Ⅰ〜Ⅹ) ➔ 漢数字 (〇〜十) ➔ 全角数字化。
3. **`segment_sanitizer.py`**:
   - `SegmentSanitizer`: ハルシネーション検出、セグメント内リピート短縮、異常発話速度検出、単語レベルタイムスタンプによる文頭位置補正。
4. **`post_processor.py`**:
   - `TextPostProcessor`: 置換辞書（.yaml/.json）読み込み、最長キー順置換、`NumberNormalizer` 連携、NFKC 正規化、句読点除去。
5. **`timing_adjuster.py`**:
   - `SubtitleTimingAdjuster` (および `TimingAdjusterProtocol`): 余韻付与、最小表示時間確保、次セグメントとの重複防止クリップ。
6. **`srt_exporter.py`**:
   - `SubtitleExporter`: DaVinci Resolve 仕様に準拠した SRT、WebVTT、JSON の出力。
7. ※ `segment_splitter.py` (Janome による文節分割): 要件 R1 に従い **移植対象から除外・廃止**。

### 4.3 `audio-transcriber` への移植設計
`audio-transcriber` は外部ライブラリ `srt` を持たず、純粋な標準ライブラリ（`json`, `tomllib`, `re`, `datetime`）で SRT / VTT / JSON を生成可能な設計にします。これにより無駄な外部依存を増やさず、高速かつ DaVinci Resolve の厳格な仕様（ミリ秒 `,` 区切り、UTF-8、LF 改行）を確実に満たします。

また、辞書フォーマットとして既存の `data/custom_dictionary.toml` (`[replacements]` 形式) をサポートするため、TOML, YAML, JSON の3形式を透過的に読み込めるローダーを `TextPostProcessor` に実装します。

---

## 5. 既存テストスイートおよび依存関係

### 5.1 テストスイートの現況
- テストファイル数: 8 ファイル (`tests/test_*.py`)
- テスト件数: 31 件
- テスト結果: 全件 PASS (1.53秒)
- カバレッジ: **100%** (364 statements / 0 missing)
- 静的解析 (`basedpyright`): **0 errors, 0 warnings**
- リント (`ruff check`): **All checks passed**

### 5.2 依存関係 (`pyproject.toml`)
- 現在のメイン依存:
  - `deepfilternet>=0.5.6`
  - `faster-whisper>=1.2.1`
  - `rich>=15.0.0`
  - `torch>=2.13.0`
  - `torchaudio>=2.11.0`
  - `typer>=0.27.1`
- 開発依存:
  - `basedpyright>=1.39.10`, `pre-commit>=4.6.2`, `pytest>=9.1.1`, `pytest-cov>=7.1.0`, `ruff>=0.16.3`
- 仮想環境 (`uv pip list`):
  - `pyyaml 6.0.3` が既にインストール済み。TOML は標準ライブラリ `tomllib` (Python 3.11+)、JSON は `json` で利用可能。
  - YAML 辞書を正式サポートする場合、`pyproject.toml` に `pyyaml>=6.0` を明記するか、オプショナルインポート／フォールバックを実装可能。

---

## 6. ファイル行数・モジュール構造・AGENTS.md 規約適合性

### 6.1 現行ファイルの行数一覧
| ファイルパス | 行数 | 300行上限規約判定 |
|---|---|---|
| `src/audio_transcriber/__init__.py` | 26 行 | 適合 (目標200行以下クリア) |
| `src/audio_transcriber/cli.py` | 226 行 | 適合 (300行以下、微増に注意) |
| `src/audio_transcriber/compat.py` | 37 行 | 適合 (目標200行以下クリア) |
| `src/audio_transcriber/config.py` | 255 行 | 適合 (300行以下) |
| `src/audio_transcriber/denoise.py` | 47 行 | 適合 (目標200行以下クリア) |
| `src/audio_transcriber/media.py` | 217 行 | 適合 (300行以下) |
| `src/audio_transcriber/pipeline.py` | 122 行 | 適合 (目標200行以下クリア) |
| `src/audio_transcriber/transcribe.py` | 94 行 | 適合 (目標200行以下クリア) |

### 6.2 新規追加モジュールの構成案（単一責任原則と行数抑制）
新機能の追加にあたり、各モジュールを 200 行以下のコンパクトな設計とします：

1. `src/audio_transcriber/models.py` (~40行):
   - `SubtitleSegment` データクラス (`start`, `end`, `text`, `to_dict()`, `from_dict()`)
2. `src/audio_transcriber/number_normalizer.py` (~100行):
   - `NumberNormalizer` クラス
3. `src/audio_transcriber/segment_sanitizer.py` (~150行):
   - `SegmentSanitizer` クラス
4. `src/audio_transcriber/post_processor.py` (~160行):
   - `TextPostProcessor` クラス (TOML / YAML / JSON 辞書読み込み対応)
5. `src/audio_transcriber/timing_adjuster.py` (~120行):
   - `TimingAdjusterProtocol`, `SubtitleTimingAdjuster` クラス
6. `src/audio_transcriber/subtitles.py` (~140行):
   - `SubtitleExporter` クラス (SRT, WebVTT, JSON 書き出し)

---

## 7. 調査まとめと推奨実装ロードマップ

1. **Phase 1: データモデルおよび個別後処理コンポーネントの構築**
   - `models.py`, `number_normalizer.py`, `segment_sanitizer.py`, `post_processor.py`, `timing_adjuster.py`, `subtitles.py` を実装。
   - 各コンポーネント用の単体テスト (`tests/test_*.py`) を作成し、AAA パターンで 100% カバレッジを確保。
2. **Phase 2: 設定および不要パラメータの廃止**
   - `config.py`, `config.toml`, `config.example.toml` から `max_segment_chars` / `MAX_SEGMENT_CHARS` を削除。
   - `test_config.py` を更新。
3. **Phase 3: パイプラインおよび CLI への統合**
   - `transcribe.py` で単語タイムスタンプ (`word_timestamps=True`) を有効化し、`SubtitleSegment` の抽出を整備。
   - `pipeline.py` に後処理パイプラインと SRT / VTT / JSON の一括書き出しを統合し、`PipelineResult` を拡張。
   - `cli.py` に後処理オプションを追加し、出力テーブルに 3 形式のパスを表示。
   - `test_pipeline.py`, `test_cli.py`, `test_transcribe.py` を更新。
4. **Phase 4: 品質検証**
   - `uv run basedpyright`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest --cov=audio_transcriber --cov-report=term-missing` を実行し、エラー 0 件と高カバレッジを検証。
