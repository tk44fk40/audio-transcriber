# Handoff Report — Codebase Survey (Post-Processing & Output Formats)

## 1. Observation

### 1.1 `MAX_SEGMENT_CHARS` / `max_segment_chars` 存在箇所
- `src/audio_transcriber/config.py`:
  - 75行目: `max_segment_chars: int = 30` (`PostProcessConfig` 内)
  - 192行目: `max_segment_chars=int(post_data.get("max_segment_chars", 30)),` (`parse_config_dict` 内)
- `config.toml`:
  - 116行目: `MAX_SEGMENT_CHARS = 30`
- `config.example.toml`:
  - 103行目: `MAX_SEGMENT_CHARS = 30`
- `tests/test_config.py`:
  - 90行目: `MAX_SEGMENT_CHARS = 25`
  - 124行目: `assert cfg.post_process.max_segment_chars == 25`

### 1.2 パイプライン構造 (`pipeline.py`)
- `PipelineResult` (行 17-24) は現在以下の5フィールドのみ定義:
  ```python
  @dataclass
  class PipelineResult:
      input_file: Path
      denoised_audio: Path | None
      srt_file: Path | None
      transcript_text: str | None
      remuxed_video: Path | None = None
  ```
- `run_pipeline` (行 27-123) は `transcribe_audio` を直接呼び出し、後処理（サニタイズ・数字正規化・タイミング補正）を介さずに `{stem}.srt` を出力している。

### 1.3 CLI 構造 (`cli.py`)
- CLI コマンド `main` (行 25-224) には、現状後処理オプション（`--custom-dict`, `--end-padding`, `--min-duration`, `--min-gap`, `--normalize-nums`, `--to-hankaku` 等）が渡されておらず、結果テーブルも SRT のみ表示している。

### 1.4 字幕生成ロジック (`transcribe.py`)
- 独立した `subtitles.py` や `SubtitleSegment` モデルは存在せず、`transcribe.py` (行 10-35) の `format_timestamp` と `segments_to_srt` で直接 SRT 文字列を組み立てている。

### 1.5 依存関係とテスト状況
- `uv run pytest --cov=audio_transcriber --cov-report=term-missing` 実行結果: 31 passed in 2.02s, 100% coverage (364 statements).
- `uv run basedpyright` 実行結果: 0 errors, 0 warnings, 0 notes.
- `uv run ruff check .` 実行結果: All checks passed.
- `uv pip list` により `pyyaml` (6.0.3) は仮想環境内に存在することを確認。標準ライブラリ `tomllib` および `json` により、外部ライブラリ `srt` に依存せず 3 形式（SRT/VTT/JSON）の出力が可能。

### 1.6 ファイル行数
- `src/audio_transcriber/`:
  - `__init__.py`: 26 行
  - `cli.py`: 226 行
  - `compat.py`: 37 行
  - `config.py`: 255 行
  - `denoise.py`: 47 行
  - `media.py`: 217 行
  - `pipeline.py`: 122 行
  - `transcribe.py`: 94 行
- 全ファイルが 300 行以下（AGENTS.md 規約適合）。

---

## 2. Logic Chain

1. **観測 1.1 より**: `MAX_SEGMENT_CHARS` は `config.py`, `config.toml`, `config.example.toml`, `test_config.py` の計4箇所にのみ定義・参照されており、他モジュール（`pipeline.py` や `transcribe.py`）では現在参照されていない。したがって、これら4箇所から削除することで安全に完全廃止できる。
2. **観測 1.2 & 1.4 より**: 現状の `run_pipeline` は `transcribe_audio` から直接 SRT を生成している。`lumi_companion` から移植する各コンポーネント（`SubtitleSegment`, `SegmentSanitizer`, `NumberNormalizer`, `TextPostProcessor`, `SubtitleTimingAdjuster`, `SubtitleExporter`）を独立モジュールとして配置し、`pipeline.py` で一連の後処理ステージとして呼び出すことで、単体実行性と疎結合性を保ちながら SRT/VTT/JSON の3形式同時出力が可能となる。
3. **観測 1.5 より**: 現在のリポジトリは 100% のテストカバレッジと型チェック 0 エラーを達成しているため、各新規モジュールの単体テスト（AAA パターン）を `tests/` に追加し、パイプラインテストを更新することで、高い品質基準を維持できる。
4. **観測 1.6 より**: 現行コードベースは最大 255 行であり、新規モジュールも 40〜160 行程度で分割可能なため、AGENTS.md の 1 ファイル最大 300 行（目標 200 行）ルールを確実に遵守できる。

---

## 3. Caveats

- **辞書フォーマット**: `data/custom_dictionary.toml` には `[replacements]` テーブルが含まれているため、辞書ローダーは root 直下の辞書だけでなく `[replacements]` テーブル形式も透過的に解釈する必要がある。
- **形態素解析・文節分割の除外**: `lumi_companion` に含まれる `segment_splitter.py` (Janome) は要件 R1 / ORIGINAL_REQUEST.md により意図的に除外対象とされている。

---

## 4. Conclusion

- `audio-transcriber` への後処理移植および 3 形式（SRT/VTT/JSON）出力対応、`MAX_SEGMENT_CHARS` 廃止の準備調査が完了した。
- 詳細な調査結果および推奨アーキテクチャ・実装ロードマップを `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/explorer_survey_2/survey_report.md` に記載した。

---

## 5. Verification Method

- 詳細レポートの確認:
  - `view_file` で `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/explorer_survey_2/survey_report.md` を閲覧
- 現行のテスト・静的解析の再現確認:
  ```bash
  uv run pytest --cov=audio_transcriber --cov-report=term-missing
  uv run basedpyright
  uv run ruff check .
  ```
