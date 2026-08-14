# Handoff Report — Explorer 3 (Milestone 1 Test Specification)

## 1. Observation

1. **参照実装・仕様の確認**:
   - `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/models/audio.py`: Lines 11-42 にて `SubtitleSegment(start: float, end: float, text: str)` および `to_dict()`, `from_dict()` の定義を確認。
   - `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/segment_sanitizer.py`: Lines 15-159 にて `SegmentSanitizer`（無音捏造除外 `no_speech_threshold=0.6`、異常発話速度除外 `max_chars_per_second=12.0` / 4文字以下保護、セグメント内リピート半減、セグメント間ループ除外、単語タイムスタンプ開始位置補正、`get_word_time`）の実装を確認。
   - `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/srt_exporter.py`: Lines 17-153 にて `SubtitleExporter`（`format_timestamp` [SRT用], `format_vtt_timestamp` [WebVTT用], `save_srt`, `save_vtt`, `save_json`, `save_subtitles`）の実装を確認。
   - `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/src/audio_transcriber/transcribe.py`: Lines 10-35 にて外部 `srt` ライブラリに依存しない標準ライブラリベースの SRT タイムスタンプ生成ロジックを確認。
2. **既存テストとコーディング規約の確認**:
   - `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/AGENTS.md`: Google スタイル日本語 Docstring、AAA (Arrange-Act-Assert) パターン徹底、1ファイル300行以下、Python 3.11+ 厳格な型注釈、`basedpyright` エラー 0 件。
   - `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/docs/testing_and_coverage.md`: モック活用指針、境界値・例外系テストの網羅。
   - `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/pyproject.toml`: pytest, pytest-cov, ruff, basedpyright 設定。

## 2. Logic Chain

1. [Observation 1] より、`SubtitleSegment` は `start`, `end`, `text` の3フィールドを持ち、辞書相互変換および型変換（数値型への丸めやキャスト）が求められる。したがって `tests/test_models.py` では基本属性、同値性、`to_dict`/`from_dict` 相互変換、型変換・デフォルト値フォールバック、特殊文字/Unicode 保持をテストする。
2. [Observation 1] より、`SegmentSanitizer` は 5 つの主要なフィルタリングロジック（無音判定、発話速度超過・4文字保護境界、セグメント内リピート短縮、無音時セグメント間ループ除外、単語タイムスタンプ補正）と、入力形式の柔軟性（`dict` / `SimpleNamespace` / オブジェクト）を持つ。したがって `tests/test_sanitizer.py` ではこれら各分岐および `get_word_time` 補助関数、進捗ログ出力を単体テスト化する。
3. [Observation 1, 2] より、`SubtitleExporter` は DaVinci Resolve 準拠のミリ秒コンマ区切り SRT、ピリオド区切りの WebVTT、構造化 JSON の3形式をサポートし、拡張子自動判定と `fmt` 引数による明示指定、不正値での `ValueError` 送出を行う。したがって `tests/test_exporter.py` では `tmp_path` フィクスチャを活用したファイル I/O、親ディレクトリ自動生成、特殊文字エスケープ、例外送出をテストする。
4. [Observation 2] より、全てのテストコードは AAA パターンで構成し、モック・フィクスチャを標準化することで可読性と保守性を最大化する。

## 3. Caveats

- Milestone 1 のスコープ外である数字正規化（`NumberNormalizer`）、カスタム辞書置換（`TextPostProcessor`）、タイミング補正（`SubtitleTimingAdjuster`）のテストは Milestone 2 の管轄とし、本分析では言及のみに留めています。
- 外部依存 `srt` ライブラリの有無について：`audio-transcriber` では `pyproject.toml` に `srt` が含まれていないため、`exporter.py` の `save_srt` は `transcribe.py` と同様に標準ライブラリのみでフォーマット生成を行う前提でテスト仕様を策定しています。

## 4. Conclusion

Milestone 1 のテスト仕様および設計ブループリントを策定完了しました。
- `tests/test_models.py` (8テストケース): `SubtitleSegment` の初期化、等価性、シリアライズ/デシリアライズ、型補正、デフォルト値。
- `tests/test_sanitizer.py` (14テストケース): `SegmentSanitizer` の無音除外、発話速度除外、短文保護、重複短縮、ループ除外、単語タイムスタンプ補正、dict/object 入力対応、ログ出力。
- `tests/test_exporter.py` (12テストケース): `SubtitleExporter` のタイムスタンプ変換、SRT/VTT/JSON 保存、自動判定、明示指定、異常系例外送出、親ディレクトリ自動生成、空リスト対応。
- 詳細設計・コードスニペットは `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_m1/explorer_3/analysis.md` に集約。

## 5. Verification Method

1. **仕様ドキュメントの整合性確認**:
   - `analysis.md` と `handoff.md` が本プロジェクトの規約（AGENTS.md, PROJECT.md）に完全に適合しているか確認。
2. **実装フェーズでの検証コマンド**:
   - `uv run pytest tests/test_models.py tests/test_sanitizer.py tests/test_exporter.py --cov=audio_transcriber --cov-report=term-missing`
   - `uv run basedpyright`
   - `uv run ruff check .`
   - `uv run ruff format --check .`
