# Handoff Report: Milestone 1 Reference Investigation & Architectural Analysis

## 1. Observation
1. **リファレンス実装ファイルの確認**:
   - `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/models/audio.py`:
     - `SubtitleSegment(start: float, end: float, text: str)` dataclass (Lines 11-42)。
     - `to_dict() -> dict[str, Any]` および `from_dict(cls, data: dict[str, Any]) -> SubtitleSegment` が実装されている。
   - `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/segment_sanitizer.py`:
     - `SegmentSanitizer` クラス (Lines 15-158)。
     - `no_speech_threshold=0.6`, `max_chars_per_second=12.0`。
     - セグメント内リピート短縮: `len(text) >= 4 and text[:half_len] == text[half_len:]` かつ `(no_speech_prob > 0.1 or compression_ratio > 2.0)` (Lines 75-85)。
     - 単語開始位置補正: `words[0]` から `start` 属性を取得し `start` を補正 (Lines 92-96)。
     - セグメント間ループ重複除外: `last_valid_text and no_speech_prob > 0.1` かつ `(text == last_valid_text or text in last_valid_text)` (Lines 101-110)。
     - 無音捏造除外: `no_speech_prob > self.no_speech_threshold` (Lines 113-119)。
     - 異常発話速度除外: `chars_per_sec > self.max_chars_per_second and len(text) > 4` (Lines 122-128)。
     - 有効セグメントのタイムスタンプ丸め: `round(start, 3)`, `round(end, 3)` (Lines 130-135)。
   - `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/srt_exporter.py`:
     - `SubtitleExporter` クラス (Lines 17-153)。
     - `format_timestamp`: `HH:MM:SS,mmm` (SRT用、ミリ秒はカンマ区切り)。
     - `format_vtt_timestamp`: `HH:MM:SS.mmm` (WebVTT用、ミリ秒はドット区切り)。
     - `save_srt`: `srt.Subtitle` および `srt.compose` を使用 (Lines 70-92)。
     - `save_vtt`: `WEBVTT\n` ヘッダーと `HH:MM:SS.mmm` (Lines 94-110)。
     - `save_json`: `json.dump` (UTF-8, `ensure_ascii=False`, `indent=2`) (Lines 57-68)。
     - `save_subtitles`: 拡張子 (`.srt`, `.vtt`, `.json`) 自動判別または明示 `fmt` 指定 (Lines 112-153)。
2. **`audio-transcriber` 環境と既存コードの確認**:
   - `pyproject.toml`: `dependencies` に `srt` は含まれていない（`deepfilternet`, `faster-whisper`, `rich`, `torch`, `torchaudio`, `typer` のみ）。
   - `src/audio_transcriber/transcribe.py`: 自前の `format_timestamp` (Line 10) および `segments_to_srt` (Line 27) を持ち、標準ライブラリのみで SRT 変換可能。
   - `PROJECT.md` & `SCOPE.md`: M1 では `models.py`, `sanitizer.py`, `exporter.py` およびテストを実装対象とする。

## 2. Logic Chain
1. [Observation 1, 2] `lumi_companion` の `srt_exporter.py` はサードパーティ製 `srt` ライブラリを使用しているが、`audio-transcriber` の `pyproject.toml` には `srt` 依存が存在しない。
2. [Observation 2] `transcribe.py` での実装実績および SRT フォーマットの平易性（連番、`HH:MM:SS,mmm --> HH:MM:SS,mmm`、テキスト、空行）から、標準ライブラリのみで `save_srt` を完全実装可能である。
3. [Observation 1] `SegmentSanitizer` は、入力セグメントがオブジェクト（faster-whisper の `Segment`）または辞書型（`dict`）のいずれであっても安全にプロパティ（`text`, `start`, `end`, `no_speech_prob`, `compression_ratio`, `words`）を抽出できるよう `get_word_time` と同様の柔軟なアクセスを行う必要がある。
4. [Observation 1, 2] プロジェクト規約（ファイルサイズ 300 行以下、Google Docstring、Python 3.11+ 型注釈、AAA テスト）に則り、`models.py`, `sanitizer.py`, `exporter.py` を独立したモジュールとして設計・実装することで、Milestone 1 の要件を完全に充足できる。

## 3. Caveats
- `lumi_companion` では `AudioProcessResult` が定義されているが、`audio-transcriber` では `pipeline.py` に `PipelineResult` が既に存在するため、`models.py` では `SubtitleSegment` のみを対象とする。
- `total_duration` パラメータは進捗ログ表示用であり、タイミング補正（クランプ）は Milestone 2 の `timing.py` (`SubtitleTimingAdjuster`) で行う。

## 4. Conclusion
- `lumi_companion` からの移植仕様とアルゴリズムは完全に把握・分析完了。
- 外部依存 `srt` を追加せず、Pure Python で `SubtitleExporter` を実装する方針が最適。
- M1 実装対象コンポーネント（`models.py`, `sanitizer.py`, `exporter.py`）および単体テスト群の設計が確定。

## 5. Verification Method
- 実装後に以下のテストコマンドを実行し、全テストパスおよび型チェック・リント適合を確認する：
  1. `uv run pytest tests/test_models.py tests/test_sanitizer.py tests/test_exporter.py`
  2. `uv run basedpyright` (エラー 0 件)
  3. `uv run ruff check .` および `uv run ruff format --check .`
