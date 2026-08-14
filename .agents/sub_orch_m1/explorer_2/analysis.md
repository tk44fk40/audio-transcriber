# Milestone 1: リポジトリ構造・開発環境・モジュール統合詳細調査報告書 (Analysis)

## 概要 (Executive Summary)

本調査報告書は、`audio-transcriber` プロジェクトにおける Milestone 1（`models.py`, `sanitizer.py`, `exporter.py`）の実装および統合に向け、既存のコードベース構造、開発・静的解析環境、テスト構成、ロギング・エラーハンドリング規約、および各モジュールのインターフェース整合性を徹底調査・分析した結果をまとめたものである。

---

## 1. 既存リポジトリ構造と環境仕様分析

### 1.1 `src/audio_transcriber/` モジュール構成

現在の `src/audio_transcriber/` 配下は以下のモジュール群で構成されている：

| モジュール名 | 行数 | 責務・主要機能 | 主な公開クラス / 関数 |
|---|---|---|---|
| `__init__.py` | 27行 | パッケージ公開シンボルの再エクスポート | `PipelineResult`, `run_pipeline`, `denoise_audio`, `transcribe_audio` 等 |
| `config.py` | 256行 | TOML 設定の読み込み・大文字小文字正規化・データクラス定義 | `AppConfig`, `MediaConfig`, `ModelConfig`, `VadConfig`, `TranscribeConfig`, `PostProcessConfig`, `SubtitleConfig`, `load_config`, `parse_config_dict` |
| `transcribe.py` | 95行 | Faster-Whisper による音声認識・簡易 SRT 出力 | `transcribe_audio`, `format_timestamp`, `segments_to_srt` |
| `denoise.py` | 48行 | DeepFilterNet によるキーボード音・環境ノイズ除去 | `denoise_audio` |
| `media.py` | 218行 | ffmpeg / ffprobe による動画・音声トラック検査・抽出・リマックス | `AudioTrackInfo`, `get_audio_tracks`, `extract_audio_track`, `remux_video`, `is_video_file` |
| `pipeline.py` | 123行 | 音声抽出・ノイズ除去・文字起こし・動画リマックスの統合パイプライン | `PipelineResult`, `run_pipeline` |
| `compat.py` | 38行 | DeepFilterNet と最新 torchaudio 間の互換性シム | `apply_torchaudio_compat` |
| `cli.py` | 227行 | Typer + Rich による CLI エントリポイント | `app`, `main` |
| `py.typed` | 0行 | PEP 561 型情報マーカーファイル | - |

### 1.2 ロギングおよびエラーハンドリング規約

1. **ロギング**:
   - 各モジュール先頭で `logger = logging.getLogger(__name__)` を宣言。
   - `logger.info`: 通常処理の進行状況（例: 辞書読み込み、設定ファイル読み込み、セグメント検出進捗）。
   - `logger.debug`: 詳細な内部判定結果（例: 無音捏造ドロップ、異常速度ドロップ）。
   - `logger.error`: 外部ツール（ffmpeg/ffprobe）の実行エラー詳細ログ。
2. **エラーハンドリング**:
   - パラメータ不正・未対応拡張子・未対応フォーマット: `ValueError` を送出。
   - 外部プロセス（ffmpeg / ffprobe 等）失敗: `subprocess.CalledProcessError` をキャッチし、ログ記録後に `RuntimeError` へラップ（`from e` で原因チェーン維持）。
   - シリアライズ・デシリアライズ: 欠損キーや不正型に対して安全なフォールバック / 型変換を実施。

### 1.3 依存関係とツール設定 (`pyproject.toml`)

- **Python バージョン**: `>=3.11`
- **ランタイム依存パッケージ**:
  - `deepfilternet>=0.5.6`
  - `faster-whisper>=1.2.1`
  - `rich>=15.0.0`
  - `torch>=2.13.0`
  - `torchaudio>=2.11.0`
  - `typer>=0.27.1`
  - **重要**: `srt` パッケージは依存関係に含まれておらず、追加すべきではない（Pure Python で実装）。
- **開発・静的解析ツール**:
  - `basedpyright>=1.39.10`: `typeCheckingMode = "standard"`, 対象: `src`, `tests`。エラー 0 件必須。
  - `ruff>=0.16.3`: `target-version = "py311"`, `line-length = 100`, ルール: `["E", "F", "W", "I", "UP", "B", "RUF"]`。
  - `pytest>=9.1.1`, `pytest-cov>=7.1.0`: `testpaths = ["tests"]`, `pythonpath = ["src"]`。
- **現在のカバレッジ状況**:
  - 全モジュール 100% カバレッジ達成（31 テストパス、364/364 ステートメント）。

---

## 2. 既存テストスイート構造 (`tests/`)

| テストファイル | 行数 | テスト対象 | 主要な検証手法 |
|---|---|---|---|
| `test_basic.py` | 35行 | `format_timestamp`, `segments_to_srt` | タイムスタンプフォーマットおよび SRT 文字列生成の単体検証 |
| `test_cli.py` | 101行 | `cli.py` (Typer CLI) | `CliRunner`, `tmp_path`, `unittest.mock.patch` |
| `test_compat.py` | 23行 | `compat.py` | `sys.modules` パッチによるインポート例外・シム注入検証 |
| `test_config.py` | 171行 | `config.py` | TOML パース、大文字小文字正規化、デフォルトフォールバック |
| `test_denoise.py` | 68行 | `denoise.py` | `init_df`, `load_audio`, `enhance`, `save_audio` のモック検証 |
| `test_media.py` | 227行 | `media.py` | ffprobe 出力モック、例外ハンドリング、実 ffmpeg による統合テスト |
| `test_pipeline.py` | 92行 | `pipeline.py` | パイプライン全体のモックによる連携フロー検証 |
| `test_transcribe.py` | 99行 | `transcribe.py` | `WhisperModel.transcribe` モックによるファイル出力および辞書変換検証 |

### テスト規約の特徴
- **AAA パターンの徹底**: すべてのテストで Arrange / Act / Assert が明確に構造化されている。
- **モックの決定論的利用**: 重い推論モデルや外部コマンドは `unittest.mock` を用いてミリ秒単位で高速実行。
- **独立性**: テスト間に状態の共有がなく、`tmp_path` による一時ディレクトリ分離が徹底されている。

---

## 3. Milestone 1 対象モジュールの設計と適合仕様

### 3.1 `src/audio_transcriber/models.py`
- **データモデル**:
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
      def from_dict(cls, data: dict[str, Any]) -> SubtitleSegment:
          return cls(
              start=float(data.get("start", 0.0)),
              end=float(data.get("end", 0.0)),
              text=str(data.get("text", "")),
          )
  ```
- **行数見込み**: 約 40 行（制限 300 行以下を大幅にクリア）。

### 3.2 `src/audio_transcriber/sanitizer.py`
- **クラス設計**:
  ```python
  class SegmentSanitizer:
      """Whisper 認識結果のハルシネーション検出およびフィルタリングを行うクラス。"""
      def __init__(
          self,
          no_speech_threshold: float = 0.6,
          max_chars_per_second: float = 12.0,
      ) -> None: ...

      @staticmethod
      def get_word_time(word_obj: object, attr_name: str) -> float | None: ...

      def sanitize_segments(
          self,
          segments: Iterable[object],
          total_duration: float = 0.0,
      ) -> list[SubtitleSegment]: ...
  ```
- **処理ロジック**:
  1. 空白テキストのスキップ (`text.strip() == ""`)
  2. セグメント内リピート検出・短縮（前半と後半の一致かつ `no_speech_prob > 0.1` または `compression_ratio > 2.0`）
  3. 単語レベルタイムスタンプ（`words`）による文頭開始時刻（`start`）の補正
  4. セグメント間ループ重複の除外（直前有効テキストと一致/包含かつ `no_speech_prob > 0.1`）
  5. 無音捏造の除外（`no_speech_prob > no_speech_threshold`）
  6. 異常発話速度の除外（`chars_per_sec > max_chars_per_second` かつ `len(text) > 4`）
  7. `SubtitleSegment(start=round(start, 3), end=round(end, 3), text=text)` の構築
- **行数見込み**: 約 160 行。

### 3.3 `src/audio_transcriber/exporter.py`
- **クラス設計**:
  ```python
  class SubtitleExporter:
      """字幕 JSON, SRT および WebVTT ファイルのエクスポートクラス。"""

      @staticmethod
      def format_timestamp(seconds: float) -> str: ...  # HH:MM:SS,mmm

      @staticmethod
      def format_vtt_timestamp(seconds: float) -> str: ...  # HH:MM:SS.mmm

      @classmethod
      def save_json(cls, segments: Sequence[SubtitleSegment], output_path: Path) -> None: ...

      @classmethod
      def save_srt(cls, segments: Sequence[SubtitleSegment], output_path: Path) -> None: ...

      @classmethod
      def save_vtt(cls, segments: Sequence[SubtitleSegment], output_path: Path) -> None: ...

      @classmethod
      def save_subtitles(
          cls,
          segments: Sequence[SubtitleSegment],
          output_path: Path,
          fmt: str | None = None,
      ) -> None: ...
  ```
- **DaVinci Resolve / WebVTT / JSON 互換性の重要仕様**:
  - SRT: `HH:MM:SS,mmm`（カンマ区切り）、UTF-8、LF改行、1-indexed 連番ブロック、空行区切り。
  - WebVTT: 先頭 `WEBVTT\n\n`、`HH:MM:SS.mmm`（ドット区切り）、UTF-8、LF改行、連番ブロック。
  - JSON: `[{"start": ..., "end": ..., "text": ...}]`、`indent=2`、`ensure_ascii=False`、UTF-8、LF改行。
  - ディレクトリ自動生成: `output_path.parent.mkdir(parents=True, exist_ok=True)`。
  - フォーマット判定: 大文字小文字を吸収し、未対応形式には明確な `ValueError` を送出。
  - Pure Python 実装: `import srt` などの外部依存を完全排除。
- **行数見込み**: 約 150 行。

---

## 4. 統合性・競合リスク評価 (Integration & Conflict Risk Assessment)

| 潜在的リスク / 懸念点 | 影響度 | 評価結果・対策方針 |
|---|---|---|
| **外部ライブラリ依存 (`srt`)** | 高 | `lumi_companion` では `import srt` を使用していたが、`audio-transcriber` では Pure Python で実装する。これにより新規依存の追加が不要となり、環境互換性が完全に維持される。 |
| **`format_timestamp` の重複** | 低 | `transcribe.py` に既存の `format_timestamp` が存在する。Milestone 1 では `transcribe.py` は変更せず、`exporter.py` 側に `SubtitleExporter.format_timestamp` を定義する。Milestone 4 のパイプライン統合時に一元化可能。 |
| **既存コードへの破壊的影響** | なし | Milestone 1 の作業範囲は新規ファイル 3 点（`models.py`, `sanitizer.py`, `exporter.py`）および対応テスト 3 点の追加のみ。既存モジュール（`pipeline.py`, `transcribe.py`, `config.py`, `cli.py`）には一切手を加えないため、既存の 31 テストへの影響はゼロ。 |
| **ファイル行数制限の遵守** | なし | `models.py` (~40行), `sanitizer.py` (~160行), `exporter.py` (~150行) となり、プロジェクト目標である 200 行以下 / 上限 300 行以下を完全に満たす。 |
| **静的型チェック (`basedpyright`)** | 中 | `Iterable[object]` や `dict[str, Any]`、`Sequence[SubtitleSegment]` の厳格な型注釈を付与し、`typeCheckingMode = "standard"` で 0 エラーを達成する設計とする。 |

---

## 5. 結論と次のステップへの提言

1. **モジュール追加の安全性の確認**: Milestone 1 の 3 モジュール（`models.py`, `sanitizer.py`, `exporter.py`）は、既存コードに何ら副作用を与えずにクリーンに追加可能である。
2. **Pure Python 実装の採用**: `srt` パッケージ依存を排除し、標準ライブラリのみで DaVinci Resolve 互換 SRT、WebVTT、JSON 出力器を構築する。
3. **単体テストの網羅**: `tests/test_models.py`, `tests/test_sanitizer.py`, `tests/test_exporter.py` により、境界値・エッジケース・辞書/オブジェクト互換性を 100% カバレッジで検証可能である。
