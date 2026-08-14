# Original User Request

## Initial Request — 2026-08-14T18:45:05Z

`lumi_companion` リポジトリ（`~/ghq/github.com/tk44fk40/lumi_companion`）の実装を参考に、`audio-transcriber` プロジェクトへ音声認識後の後処理機能（サニタイズ、数字正規化、タイミング調整、SRT/VTT/JSON 3形式出力等）を移植・統合する。文節分割（Janome形態素解析）および `MAX_SEGMENT_CHARS` パラメータは不要のため除外・廃止する。

Working directory: /home/tk44/ghq/github.com/tk44fk40/audio-transcriber
Integrity mode: development

## Reference Material
- 移植元リファレンス実装: `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/`
  - `number_normalizer.py`: 漢数字・ローマ数字・数字の正規化
  - `segment_sanitizer.py`: ハルシネーション・無音捏造・異常発話速度のサニタイズ
  - `timing_adjuster.py`: 余韻パディング、最小表示時間、重複防止ギャップ制御
  - `srt_exporter.py`: DaVinci Resolve互換SRT、WebVTT、JSONエクスポート
  - `post_processor.py`: 置換辞書適用およびテキスト正規化パイプライン

## Requirements

### R1. 後処理コンポーネント群の移植とモジュール設計
- 音声認識結果データモデル（`SubtitleSegment`）を定義し、型安全なデータ構造（`to_dict()`等）を確立すること。
- テキストサニタイズ（無音確率・圧縮率判定によるハルシネーション除外、繰り返し語の短縮）を実装すること。
- 数字正規化（全角/半角、漢数字等の標準化）およびカスタム辞書（TOML/YAML/JSON）による単語置換処理を実装すること。
- 字幕タイミング補正（発話終了後の余韻パディング付与、最小表示時間の確保、次セグメントとの重なり防止）を実装すること。
- 字幕エクスポート機能（DaVinci Resolveインポート仕様に準拠したミリ秒表記 `00:00:00,000`・UTF-8・LF改行のSRT、WebVTT、JSONの3形式出力）を実装すること。
- ※文節分割モジュール（Janome等の形態素解析による分割）は含めないこと。

### R2. 設定・パイプラインおよびCLIへの統合
- `config.toml`, `config.example.toml`, `src/audio_transcriber/config.py` から `MAX_SEGMENT_CHARS` / `max_segment_chars` パラメータを削除・廃止すること。
- パイプライン（`audio_transcriber.pipeline`）に後処理ステップを組み込み、文字起こし後に一連の後処理が適用されて SRT・VTT・JSON の3ファイルが出力されるようにすること。
- `PipelineResult` に `vtt_file: Path | None`, `json_file: Path | None` を追加すること。
- 設定ファイルおよびCLI（`cli.py`）に後処理の各種パラメータ（余韻秒数、最小表示秒数、カスタム辞書パス、各後処理フラグ等）を反映すること。
- 疎結合性・単体実行性を維持し、各後処理モジュールが単体でも呼び出し・テスト可能であること。

### R3. プロジェクト規約・品質基準・テストの遵守
- 1ファイル最大300行以下（目標200行以下）を厳守し、単一責任原則に従って適切にモジュール分割すること。
- 全モジュール/クラス/公開関数に Google スタイルの日本語 Docstring を記述すること。
- Python 3.11+ 厳格な型注釈を付与すること。

## Acceptance Criteria

### 機能検証
- [ ] 移植された各後処理（サニタイズ、数字正規化、タイミング調整、SRT/VTT/JSON出力）が正常に動作すること。
- [ ] `run_pipeline` 実行時に後処理が適用され、適切なフォーマットで SRT / VTT / JSON ファイルが同時出力されること。
- [ ] `MAX_SEGMENT_CHARS` パラメータが設定およびコードから完全に削除されていること。

### 静的解析・品質検証
- [ ] `uv run basedpyright` を実行し、型チェックエラーが 0 件であること。
- [ ] `uv run ruff check .` および `uv run ruff format --check .` を実行し、リント・フォーマット違反がないこと。

### 自動テスト・カバレッジ検証
- [ ] `tests/` 配下に各モジュールの単体テスト（AAAパターン）が整備されていること。
- [ ] `uv run pytest --cov=audio_transcriber --cov-report=term-missing` を実行し、全テストがパスすること。
