# Handoff Report — Specification Mining for Post-Processing Porting

## 1. Observation

- **Reference Implementation**: Inspected files in `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/` and `tests/`:
  - `src/lumi_companion/models/audio.py`: `SubtitleSegment` definition with `start: float`, `end: float`, `text: str`, `to_dict()`, `from_dict()`.
  - `src/lumi_companion/audio/segment_sanitizer.py`: `SegmentSanitizer` implementing silence drop (`no_speech_prob > no_speech_threshold`), excessive speech rate drop (`chars_per_sec > max_chars_per_second` for `len > 4`), intra-segment repeat reduction (`text[:half_len] == text[half_len:]`), inter-segment loop drop, and word-level timestamp start correction.
  - `src/lumi_companion/audio/number_normalizer.py`: `NumberNormalizer.normalize(text)` performing 6-stage transformation (full-width to half-width, circled numbers, length-descending Roman numerals, Kanji numbers, regex 10-series fix, half-width to full-width).
  - `src/lumi_companion/audio/post_processor.py`: `TextPostProcessor` loading dictionary (`.yaml`, `.yml`, `.json`), applying length-descending term replacement, `NumberNormalizer`, NFKC normalization (`to_hankaku`), punctuation handling, and lowercase.
  - `src/lumi_companion/audio/timing_adjuster.py`: `SubtitleTimingAdjuster` applying `end_padding`, `min_duration`, `min_gap` overlap clipping with `next_start`, and `total_duration` clipping.
  - `src/lumi_companion/audio/srt_exporter.py`: `SubtitleExporter` exporting SRT (`00:00:00,000`, DaVinci Resolve compliant), WebVTT (`WEBVTT\n`, `00:00:00.000`), and structured JSON.
- **Audio-Transcriber Codebase**: Inspected `audio-transcriber` files:
  - `src/audio_transcriber/config.py`: `PostProcessConfig` currently has `max_segment_chars: int = 30` (line 75) which must be removed; `SubtitleConfig` has `end_padding: float = 1.0`, `min_duration: float = 1.5`, `min_gap: float = 0.05`.
  - `src/audio_transcriber/pipeline.py`: `PipelineResult` currently has `srt_file: Path | None` (line 22) and needs `vtt_file: Path | None`, `json_file: Path | None`.
  - `src/audio_transcriber/cli.py`: CLI commands currently do not expose post-processing flags and dictionary options.
  - Baseline execution: `uv run pytest` ran 31 tests and passed with 0 failures; `uv run basedpyright` reported 0 errors; `uv run ruff check .` and `uv run ruff format --check .` passed.
  - Environment check: Python 3.11 with standard library `tomllib`, `json`, `unicodedata`, and installed packages `pyyaml` (6.0.3), `faster-whisper` (1.2.1).

## 2. Logic Chain

1. **Requirement R1 (Post-processing components)**:
   - `SubtitleSegment` provides the unified data contract across sanitization, text post-processing, timing adjustment, and export.
   - Morphological splitting (`janome`, `SegmentSplitter`) and `MAX_SEGMENT_CHARS` are explicitly excluded per user request.
   - `SegmentSanitizer` handles hallucination filtering deterministically based on `no_speech_prob`, compression ratio, speech rate, and word timestamps.
   - `NumberNormalizer` and `TextPostProcessor` must support TOML (via stdlib `tomllib`), YAML (via `pyyaml`), and JSON (via `json`), sorting dictionary keys by length in descending order to avoid substring collisions.
   - `SubtitleTimingAdjuster` ensures DaVinci Resolve readable subtitles by enforcing padding, minimum duration, and gap clipping.
   - `SubtitleExporter` outputs UTF-8 LF files in SRT (`00:00:00,000`), WebVTT (`00:00:00.000`), and JSON formats.
2. **Requirement R2 (Integration & Config/CLI changes)**:
   - `PipelineResult` must be expanded with `vtt_file: Path | None` and `json_file: Path | None`.
   - `MAX_SEGMENT_CHARS` must be excised from configuration files (`config.toml`, `config.example.toml`) and `PostProcessConfig`.
   - `run_pipeline` must apply the post-processing chain and generate all 3 subtitle formats simultaneously.
   - `cli.py` must expose post-processing options and present all outputs in the summary table.
3. **Requirement R3 (Quality & Architecture standards)**:
   - Keeping each file under 300 lines (target < 200 lines) requires separate single-responsibility modules: `models.py`, `sanitizer.py`, `normalizer.py`, `post_processor.py`, `timing.py`, `exporter.py`.
   - All modules must have Google-style docstrings and full type annotations passing `basedpyright`.

## 3. Caveats

- `pyyaml` is already present in the active environment (6.0.3), but if `pyproject.toml` is strictly validated in fresh environments, `pyyaml` should be declared under `dependencies` if not already installed as a transitive dependency.
- Janome morphology-based splitting is intentionally excluded as requested; Faster-Whisper's natural segment boundaries combined with `SubtitleTimingAdjuster` are used instead.

## 4. Conclusion

The exact specifications for all 8 required areas have been extracted, validated against the authoritative reference implementations in `lumi_companion` and `audio-transcriber`, and documented in `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/spec_miner_survey_3/survey_report.md`.

## 5. Verification Method

To verify the specification report and environment readiness:
1. Inspect the survey report:
   ```bash
   cat /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/spec_miner_survey_3/survey_report.md
   ```
2. Verify baseline environment and tools:
   ```bash
   uv run pytest
   uv run basedpyright
   uv run ruff check .
   uv run ruff format --check .
   ```
