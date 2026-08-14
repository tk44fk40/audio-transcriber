# Handoff Report: Milestone 3 Config Unit Test Design

## 1. Observation
- `tests/test_config.py` (全171行):
  - 行90: `MAX_SEGMENT_CHARS = 25`
  - 行124: `assert cfg.post_process.max_segment_chars == 25`
  - `PostProcessConfig` および `SubtitleConfig` の新規パラメータ群（`custom_dict_path`, `no_speech_threshold`, `max_chars_per_second`, `formats`）のテストが存在しない。
  - セクションエイリアス（`[postprocess]`, `[subtitles]`）や部分設定フォールバックの網羅的テストが不足。
- `src/audio_transcriber/config.py` (全256行):
  - 行75: `max_segment_chars: int = 30`
  - 行192: `max_segment_chars=int(post_data.get("max_segment_chars", 30)),`
- `config.toml` (行116: `MAX_SEGMENT_CHARS = 30`) および `config.example.toml` (行103: `MAX_SEGMENT_CHARS = 30`)。
- `PROJECT.md` / `sub_orch_m3/SCOPE.md`:
  - `PostProcessConfig` (8項目: `custom_dict_path`, `replace_terms`, `normalize_nums`, `to_hankaku`, `lower`, `remove_punct`, `no_speech_threshold`, `max_chars_per_second`)
  - `SubtitleConfig` (4項目: `end_padding`, `min_duration`, `min_gap`, `formats`)
  - `MAX_SEGMENT_CHARS` の完全廃止

## 2. Logic Chain
1. **観測より**: 現行の `tests/test_config.py` は `MAX_SEGMENT_CHARS` の存在を前提としたアサーションを行っており、これを残したまま `config.py` から削除するとテストが失敗する。
2. **観測より**: `PostProcessConfig` と `SubtitleConfig` に新設されるフィールド群と、エイリアス・大文字小文字対応、フォールバックの動作を保証するための単体テストが必要である。
3. **推論と設計**:
   - `test_default_config_instances`: 全設定データクラスのデフォルト値・型を完全検証。
   - `test_load_config_no_file_returns_default`: ファイル未指定時のフォールバックを検証。
   - `test_load_config_full_custom_toml`: 全セクション・全キー（カスタム値）の読み込み・型変換を検証。
   - `test_load_config_partial_fallback`: 部分的なTOML指定時のデフォルト値維持を検証。
   - `test_load_config_case_insensitivity_and_aliases`: 大文字/小文字/エイリアス（`[postprocess]`, `[subtitles]`）のパースを検証。
   - `test_max_segment_chars_absent_and_ignored`: フィールド/属性の非存在（`dataclasses.fields`, `hasattr`）およびTOML指定時の安全な無視を検証。
   - `test_load_config_default_file_in_cwd`: カレントディレクトリ `config.toml` 自動検出を検証。
   - `test_load_config_file_not_found`: `FileNotFoundError` 発生を検証。
   - `test_load_config_invalid_toml`: 不正TOML時の `ValueError` 発生を検証。
   - `test_parse_config_dict_empty`: 空辞書パース時のデフォルト動作を検証。
4. **制約適合性**:
   - 10個のテスト関数をAAAパターンで記述し、合計約195行に収めることで、目標行数（<= 200行）を達成。

## 3. Caveats
- `PostProcessConfig` の辞書パスフィールド名について、`custom_dict_path` と `dictionary_path` の両方の命名可能性を考慮し、パース層で両方を吸収できるようにするか、単一の明確なインターフェースに統一する必要があります（SCOPE.mdの `custom_dict_path` を標準とする）。
- フォーマット指定 `formats` は `list[str]`（例: `["srt", "vtt", "json"]`）を標準としますが、文字列が指定された場合の安全策も考慮されます。

## 4. Conclusion
Milestone 3 の要件を100%満たす `tests/test_config.py` の設計と完全なコード提案を策定した。
これにより、`MAX_SEGMENT_CHARS` の完全廃止確認、新規パラメータ群の型安全なパース検証、大文字小文字/エイリアス対応、異常系ハンドリングが高品質（AAAパターン、Googleスタイル日本語Docstring、厳格な型注釈、行数 <= 200行）に担保される。

## 5. Verification Method
1. `tests/test_config.py` を提案コードで更新後、以下を実行して全テストが通過することを確認する：
   ```bash
   uv run pytest tests/test_config.py
   ```
2. 静的解析および型チェックの検証：
   ```bash
   uv run ruff check tests/test_config.py
   uv run ruff format --check tests/test_config.py
   uv run basedpyright tests/test_config.py
   ```
3. 行数確認：
   ```bash
   wc -l tests/test_config.py
   ```
   （200行以下であることを確認）
