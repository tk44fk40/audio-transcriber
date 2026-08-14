# Project: audio-transcriber Post-Processing & Output Formats Extension

## Architecture
- **Data Flow**:
  1. Input Audio/Video ➔ Media Extraction / Denoising (DeepFilterNet) ➔ `{stem}_clean.wav`
  2. Transcription (Faster-Whisper with `word_timestamps=True`) ➔ Raw Segments with word timestamps
  3. `SegmentSanitizer` ➔ Filtered `list[SubtitleSegment]` (hallucination, silence prob, excessive speech rate, loops removed, word start timestamps aligned)
  4. `TextPostProcessor` ➔ Normalized `list[SubtitleSegment]` (custom dictionary terms replaced longest-first, `NumberNormalizer` applied, NFKC/lower/punctuation flags handled)
  5. `SubtitleTimingAdjuster` ➔ Timing-adjusted `list[SubtitleSegment]` (trailing padding, min duration, min gap clipping, total duration clipping)
  6. `SubtitleExporter` ➔ 3 output files generated simultaneously: `{stem}.srt` (DaVinci Resolve compliant), `{stem}.vtt` (WebVTT), `{stem}.json` (JSON)
  7. Video Remux (if video input and remux enabled) ➔ `{stem}_clean.{ext}`
  8. `PipelineResult` returned containing paths to all outputs (`srt_file`, `vtt_file`, `json_file`, `denoised_audio`, `remuxed_video`, `transcript_text`).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | `SubtitleSegment` Data Model | Dataclass representing subtitle segments with `start`, `end`, `text`, `to_dict()`, `from_dict()` | M1 | survey |
| 2 | `SegmentSanitizer` (Hallucination / Silence Filter) | Drops segments with `no_speech_prob > threshold` | M1 | survey |
| 3 | `SegmentSanitizer` (Speech Rate Filter) | Drops segments exceeding max chars/sec (>12.0 c/s, >4 chars protected) | M1 | survey |
| 4 | `SegmentSanitizer` (Repetition Reduction) | Reduces 2-half repetitive text within segment under high comp/silence ratio | M1 | survey |
| 5 | `SegmentSanitizer` (Loop Repeat Drop) | Drops identical or sub-phrase repeat segments in silence | M1 | survey |
| 6 | `SegmentSanitizer` (Word Timestamp Alignment) | Adjusts segment `start` timestamp to first word's start timestamp if available | M1 | survey |
| 7 | DaVinci Resolve SRT Exporter | Exports subtitles to `.srt` with `HH:MM:SS,mmm`, UTF-8, LF | M1 | survey |
| 8 | WebVTT Exporter | Exports subtitles to `.vtt` with `WEBVTT` header and `HH:MM:SS.mmm`, UTF-8, LF | M1 | survey |
| 9 | JSON Subtitle Exporter | Exports subtitles to structured `.json` (`indent=2`, UTF-8, LF) | M1 | survey |
| 10 | `NumberNormalizer` | 6-stage normalization for kanji, roman, circled, halfwidth to fullwidth numbers | M2 | survey |
| 11 | `TextPostProcessor` Dictionary Loader | Loads custom dictionaries from TOML, YAML, JSON formats | M2 | survey |
| 12 | `TextPostProcessor` Term Replacement | Longest-first keyword replacement using dictionary | M2 | survey |
| 13 | `TextPostProcessor` Text Normalization | NFKC halfwidth conversion, lowercase, punctuation removal flags | M2 | survey |
| 14 | `SubtitleTimingAdjuster` (Trailing Padding) | Extends segment end timestamp by `end_padding` seconds | M2 | survey |
| 15 | `SubtitleTimingAdjuster` (Min Duration) | Ensures minimum display duration of `min_duration` seconds | M2 | survey |
| 16 | `SubtitleTimingAdjuster` (Overlap Clipping) | Clips end timestamp before next segment start with `min_gap` | M2 | survey |
| 17 | `SubtitleTimingAdjuster` (Total Duration Clamping) | Clips end timestamp at media total duration | M2 | survey |
| 18 | Config: `MAX_SEGMENT_CHARS` Removal | Completely removes `MAX_SEGMENT_CHARS` / `max_segment_chars` from config & code | M3 | survey |
| 19 | Config: Post-Processing Parameters | Adds `PostProcessConfig` and `SubtitleConfig` options in `config.py` & TOMLs | M3 | survey |
| 20 | Pipeline: 3-Format Simultaneous Export | Generates `.srt`, `.vtt`, and `.json` files in `run_pipeline` | M4 | survey |
| 21 | Pipeline: `PipelineResult` Extension | Adds `vtt_file: Path | None` and `json_file: Path | None` to `PipelineResult` | M4 | survey |
| 22 | Pipeline: Post-Processing Integration | Connects sanitizer, post-processor, timing adjuster, and exporter in `pipeline.py` | M4 | survey |
| 23 | CLI: Post-Processing Flags & Summary Table | Exposes CLI flags for post-processing and updates rich result table with 3 formats | M4 | survey |
| 24 | Final Quality & E2E Acceptance | 100% E2E test pass, adversarial test hardening, 0 basedpyright & ruff errors | M5 | survey |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Core Model, Sanitizer & Exporter | `models.py`, `sanitizer.py`, `exporter.py`, unit tests | none | DONE |
| 2 | Normalizer, PostProcessor & Timing | `normalizer.py`, `post_processor.py`, `timing.py`, unit tests | M1 | IN_PROGRESS |
| 3 | Config Cleanup & Parameter Updates | `config.py`, `config.toml`, `config.example.toml`, `test_config.py` | none | IN_PROGRESS |
| 4 | Pipeline & CLI Integration | `pipeline.py`, `transcribe.py`, `cli.py`, updated pipeline/CLI tests | M1, M2, M3 | PLANNED |
| 5 | Final Acceptance & Adversarial Hardening | Full E2E test suite execution, Tier 5 adversarial testing, static analysis | M4 | PLANNED |

## Interface Contracts
### `models.py`
- `SubtitleSegment(start: float, end: float, text: str)`
  - `to_dict() -> dict[str, Any]`
  - `from_dict(data: dict[str, Any]) -> SubtitleSegment`

### `sanitizer.py`
- `SegmentSanitizer(no_speech_threshold: float = 0.6, max_chars_per_second: float = 12.0)`
  - `sanitize_segments(segments: Iterable[Any]) -> list[SubtitleSegment]`

### `normalizer.py`
- `NumberNormalizer`
  - `normalize(text: str) -> str` (class or static method)

### `post_processor.py`
- `TextPostProcessor(dictionary_path: Path | None = None, replace_terms: bool = True, normalize_nums: bool = True, to_hankaku: bool = False, lower: bool = False, remove_punct: bool = False)`
  - `apply_to_text(text: str) -> str`
  - `apply_to_segments(segments: list[SubtitleSegment]) -> list[SubtitleSegment]`

### `timing.py`
- `SubtitleTimingAdjuster(end_padding: float = 1.0, min_duration: float = 1.5, min_gap: float = 0.05)`
  - `adjust_segments(segments: list[SubtitleSegment], total_duration: float | None = None) -> list[SubtitleSegment]`

### `exporter.py`
- `SubtitleExporter`
  - `save_srt(segments: Sequence[SubtitleSegment], output_path: Path) -> None`
  - `save_vtt(segments: Sequence[SubtitleSegment], output_path: Path) -> None`
  - `save_json(segments: Sequence[SubtitleSegment], output_path: Path) -> None`
  - `save_subtitles(segments: Sequence[SubtitleSegment], output_path: Path, fmt: str | None = None) -> None`

### `pipeline.py`
- `PipelineResult`: fields `input_file: Path`, `denoised_audio: Path | None`, `srt_file: Path | None`, `vtt_file: Path | None`, `json_file: Path | None`, `transcript_text: str | None`, `remuxed_video: Path | None = None`
- `run_pipeline(...) -> PipelineResult`

## Code Layout
- `src/audio_transcriber/models.py` — `SubtitleSegment` data model
- `src/audio_transcriber/sanitizer.py` — `SegmentSanitizer`
- `src/audio_transcriber/normalizer.py` — `NumberNormalizer`
- `src/audio_transcriber/post_processor.py` — `TextPostProcessor`
- `src/audio_transcriber/timing.py` — `SubtitleTimingAdjuster`
- `src/audio_transcriber/exporter.py` — `SubtitleExporter`
- `src/audio_transcriber/config.py` — Configuration classes & loader
- `src/audio_transcriber/transcribe.py` — Faster-Whisper wrapper
- `src/audio_transcriber/pipeline.py` — Audio transcription pipeline
- `src/audio_transcriber/cli.py` — Typer CLI entrypoint
- `tests/test_models.py` — Unit tests for SubtitleSegment
- `tests/test_sanitizer.py` — Unit tests for SegmentSanitizer
- `tests/test_normalizer.py` — Unit tests for NumberNormalizer
- `tests/test_post_processor.py` — Unit tests for TextPostProcessor
- `tests/test_timing.py` — Unit tests for SubtitleTimingAdjuster
- `tests/test_exporter.py` — Unit tests for SubtitleExporter
- `tests/test_config.py` — Tests for config parsing & removal of MAX_SEGMENT_CHARS
- `tests/test_pipeline.py` — Tests for pipeline execution and 3-format export
- `tests/test_cli.py` — Tests for CLI flags and summary table
