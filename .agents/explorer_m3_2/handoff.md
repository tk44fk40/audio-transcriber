# Handoff Report — Explorer M3-2

## 1. Observation

- **参照リポジトリ (`lumi_companion`) のパラメータ構造**:
  - `src/lumi_companion/config.py`:
    - `custom_dictionary_path: Path = Path("data/custom_dictionary.yaml")` (行100)
    - `whisper_post_process_to_hankaku: bool = False` (行103)
    - `whisper_post_process_normalize_nums: bool = True` (行104)
    - `whisper_post_process_lower: bool = False` (行105)
    - `whisper_post_process_remove_punct: bool = False` (行106)
    - `subtitle_end_padding: float = 0.8` (行109)
    - `subtitle_min_duration: float = 1.2` (行110)
    - `subtitle_min_gap: float = 0.05` (行111)
  - `src/lumi_companion/audio/segment_sanitizer.py`:
    - `no_speech_threshold: float = 0.6` (行20)
    - `max_chars_per_second: float = 12.0` (行21)
  - `src/lumi_companion/audio/srt_exporter.py`:
    - SRT, WebVTT, JSON の 3 形式をサポート。

- **現在の `audio-transcriber` の状態**:
  - `src/audio_transcriber/config.py`:
    - 行 75: `max_segment_chars: int = 30` が `PostProcessConfig` 内に残存。
    - 行 192: `max_segment_chars=int(post_data.get("max_segment_chars", 30))` が `parse_config_dict` に残存。
    - `PostProcessConfig` に `custom_dict_path`, `no_speech_threshold`, `max_chars_per_second` が未定義。
    - `SubtitleConfig` に `formats: list[str] = field(default_factory=lambda: ["srt", "vtt", "json"])` が未定義。
  - `config.toml` & `config.example.toml`:
    - 行 116 (config.toml) / 行 103 (config.example.toml): `MAX_SEGMENT_CHARS = 30` が残存。
    - `POST_PROCESS_NO_SPEECH_THRESHOLD`, `POST_PROCESS_MAX_CHARS_PER_SECOND`, `SUBTITLE_FORMATS` が未記載。
  - `tests/test_config.py`:
    - 行 90, 124: `MAX_SEGMENT_CHARS` のテストが残存。

## 2. Logic Chain

1. **[Observation 1 に基づく]** `lumi_companion` では、サニタイズ処理（`no_speech_threshold`, `max_chars_per_second`）、テキスト正規化・辞書置換、タイミング補正（`end_padding`, `min_duration`, `min_gap`）、および 3 形式（SRT/VTT/JSON）出力が独立して定義されている。
2. **[Observation 2 に基づく]** `audio-transcriber` の `PostProcessConfig` に `custom_dict_path`, `no_speech_threshold`, `max_chars_per_second` を追加し、`SubtitleConfig` に `formats` を追加することで、パイプラインおよび後処理コンポーネントとのインターフェース完全一致が達成される。
3. **[Observation 2 に基づく]** `MAX_SEGMENT_CHARS` は文節分割モジュールの廃止に伴い不要であるため、`PostProcessConfig`、`parse_config_dict`、`config.toml`、`config.example.toml`、`tests/test_config.py` から完全削除する必要がある。
4. **[設計方針に基づく]** `_normalize_dict` と `_get_val` による二重吸収レイヤーを設けることで、ユーザーが TOML 上で `[post_process]` / `[postprocess]`、`POST_PROCESS_REPLACE_TERMS` / `replace_terms` などの表記揺れを用いても堅牢にパースできる。

## 3. Caveats

- `config.py` における `formats` の文字列パース（例: `"srt, vtt"`）はカンマ区切りを許容するようハンドリングするが、不正なフォーマット文字列（例: `"mp4"`）が渡された場合のバリデーションは、後段のエクスポーター（`SubtitleExporter`）またはパース時に警告/フォールバックする想定。
- `custom_dict_path` は `[post_process]` 内部で指定されたものが最優先され、未指定の場合はルートレベルの `CUSTOM_DICTIONARY_PATH` にフォールバックする双方向互換性を維持する。

## 4. Conclusion

- `src/audio_transcriber/config.py` の設計を確定（`PostProcessConfig` 8フィールド、`SubtitleConfig` 4フィールド、`AppConfig` 10フィールド、コード行数 ~225行）。
- `MAX_SEGMENT_CHARS` の完全削除と `_get_val` による大文字小文字・エイリアス対応パース仕様を策定。
- `analysis.md` に完全なソースコードおよび TOML 設定例を記録完了。

## 5. Verification Method

実装後の検証手順:
1. `uv run pytest tests/test_config.py`
2. `uv run basedpyright src/audio_transcriber/config.py tests/test_config.py`
3. `uv run ruff check src/audio_transcriber/config.py tests/test_config.py`
4. `uv run ruff format --check src/audio_transcriber/config.py tests/test_config.py`
5. `wc -l src/audio_transcriber/config.py` を実行し、300行以下（目標200行前後）であることを確認。
