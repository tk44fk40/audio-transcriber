# Handoff Report — explorer_survey_1

## 1. Observation
- 調査対象ファイル：
  - `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/number_normalizer.py` (全103行):
    - `NumberNormalizer.normalize(text: str) -> str`
    - 全角半角変換、丸数字変換（`①`〜`⑳`）、ローマ数字変換（`VIII`〜`I`、`Ⅷ`〜`Ⅰ`）、漢数字変換（`十`〜`一`, `〇`, `ゼロ`）、`10([1-9])` -> `1\1` 正規表現置換、最終的な全角数字変換。外部依存なし。
  - `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/segment_sanitizer.py` (全159行):
    - `SegmentSanitizer.__init__(no_speech_threshold=0.6, max_chars_per_second=12.0)`
    - `sanitize_segments(segments, total_duration=0.0)`
    - セグメント内リピート（`text[:half] == text[half:]` かつ `no_speech_prob > 0.1` または `compression_ratio > 2.0`）の短縮、単語レベルタイムスタンプ（`words`）による発声開始位置補正、直前テキスト（`last_valid_text`）とのループ重複除外、`no_speech_prob > threshold` 除外、発話速度異常（`chars_per_sec > max_chars_per_second` かつ `len(text) > 4`）の除外。
  - `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/timing_adjuster.py` (全126行):
    - `TimingAdjusterProtocol` (Protocol) と `SubtitleTimingAdjuster(end_padding, min_duration, min_gap)`
    - `adjust_segments(segments, total_duration=None)`
    - `target_end = max(seg.end + end_padding, seg.start + min_duration)`、次セグメントとのギャップ制限 `min(target_end, next_start - min_gap)`、動画総再生時間クリップ `min(target_end, total_duration)`。
  - `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/srt_exporter.py` (全153行):
    - `SubtitleExporter`: `format_timestamp` (SRT: `HH:MM:SS,mmm`), `format_vtt_timestamp` (VTT: `HH:MM:SS.mmm`), `save_srt`, `save_vtt`, `save_json`, `save_subtitles`.
  - `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/post_processor.py` (全177行):
    - `TextPostProcessor(dictionary_path, to_hankaku, normalize_nums, lower, remove_punct)`
    - 辞書読み込み `load_dictionary` (キー文字列長降順ソートで置換競合防止)、正規化順序（数字正規化 -> NFKC -> 句読点処理 -> 小文字化）。
  - `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/models/audio.py` (全61行):
    - `SubtitleSegment(start: float, end: float, text: str)` (`to_dict()`, `from_dict()`)
  - 依存環境確認:
    - `uv run python -c "import yaml"` 実行結果: 終了コード 0 (`yaml available`)
    - `uv run python -c "import srt"` 実行結果: 終了コード 1 (`ModuleNotFoundError`)
    - `audio-transcriber/pyproject.toml`: `dependencies` に `deepfilternet`, `faster-whisper`, `rich`, `torch`, `torchaudio`, `typer` が定義済み。

## 2. Logic Chain
1. `number_normalizer.py`, `segment_sanitizer.py`, `timing_adjuster.py` は標準ライブラリのみで完結しており、外部ライブラリ依存がない。
2. `srt_exporter.py` は `lumi_companion` において `srt` ライブラリを使用しているが、`audio-transcriber` では `format_timestamp` による `HH:MM:SS,mmm` 形式の標準出力ロジックを直接実装することで、外部依存パッケージを追加することなく DaVinci Resolve 互換の SRT を生成できる。
3. `post_processor.py` は `yaml` / `json` 辞書を読み込むが、`audio-transcriber` では Python 3.11 の標準ライブラリ `tomllib` による `.toml` 辞書サポートを追加することで、`ORIGINAL_REQUEST.md` で指定された TOML/YAML/JSON の全形式に対応可能である。
4. `lumi_companion` の `segment_splitter.py` (Janome 依存) は、`ORIGINAL_REQUEST.md` の要求に基づき移植対象から完全に除外される。
5. 従って、新規の外部ライブラリを追加することなく、高品質・疎結合・型安全な後処理モジュール群を `audio-transcriber` に移植・統合できる。

## 3. Caveats
- `NumberNormalizer` のデフォルト出力は全角数字（`０-９`）であるため、半角数字を希望する場合は `to_hankaku=True`（NFKC正規化）を併用する必要がある。
- `segment_sanitizer.py` の単語レベル補正は Faster-Whisper 呼び出し時に `word_timestamps=True` が設定されている必要がある。
- `MAX_SEGMENT_CHARS` の廃止に伴い、`config.py`, `config.toml`, `config.example.toml`, `tests/test_config.py` から該当フィールドを漏れなく削除する必要がある。

## 4. Conclusion
- `lumi_companion` の後処理コンポーネント（数字正規化、サニタイズ、タイミング補正、SRT/VTT/JSONエクスポート、辞書置換、データモデル）の移植仕様とアルゴリズムの調査が完了した。
- 全コンポーネントは追加の外部ライブラリなし（Python 3.11 標準ライブラリのみ）で実装可能であり、各モジュールの行数は 100〜180 行程度で AGENTS.md の行長規約（300行以下、目標200行以下）に収まる。
- 詳細な調査結果を `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/explorer_survey_1/survey_report.md` にまとめた。

## 5. Verification Method
1. レポートの確認:
   - `view_file` で `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/explorer_survey_1/survey_report.md` を閲覧し、各要件（1〜6）が網羅されていることを確認。
2. 参照元コードの整合性確認:
   - `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/` 配下の各ファイル（`number_normalizer.py`, `segment_sanitizer.py`, `timing_adjuster.py`, `srt_exporter.py`, `post_processor.py`）の関数・クラスシグネチャとレポート内容が一致していることを確認。
