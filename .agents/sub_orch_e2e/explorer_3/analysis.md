# E2E Test Plan & Architecture Design for audio-transcriber

## Executive Summary
This document provides the complete architectural design and test specification for the End-to-End (E2E) testing framework of `audio-transcriber`. It maps all 24 features defined in `PROJECT.md` across a 4-Tier test hierarchy (Feature Coverage, Boundary & Corner Cases, Cross-Feature Combinations, and Real-World Workloads) and establishes the exact content specification for `TEST_INFRA.md`.

---

## 1. Test Philosophy & Core Principles

1. **Opaque-Box Requirement-Driven Testing**:
   - Tests validate functional behavior, data contracts, and output formats based strictly on requirements (`ORIGINAL_REQUEST.md`, `PROJECT.md`) without coupling to internal private implementation details.
   - Tests assert observable inputs and outputs across public interfaces, CLI commands, generated files (SRT, VTT, JSON, WAV, MP4), and data model conversions.

2. **Deterministic & High-Speed Execution (AAA Pattern)**:
   - Heavy machine learning models (`faster-whisper`, `DeepFilterNet`) and external CLI utilities (`ffmpeg`, `ffprobe`) are mocked deterministically at provider/boundary layers.
   - All tests follow the Arrange-Act-Assert (AAA) pattern with zero side-effects on the workspace (using `tmp_path`).

3. **DaVinci Resolve Compliance & Subtitle Precision**:
   - SRT timestamps must strictly conform to `HH:MM:SS,mmm` (comma separator) with UTF-8 encoding and LF line endings.
   - WebVTT timestamps must strictly conform to `WEBVTT` header with `HH:MM:SS.mmm` (dot separator).
   - JSON outputs must contain valid JSON arrays of segment dictionaries with `start`, `end`, `text`.

4. **Line Budget & KISS Compliance**:
   - Each test file under `tests/` is scoped to a single cohesive domain and strictly maintained below 200 lines (hard ceiling: 300 lines per `AGENTS.md`).

---

## 2. 4-Tier Testing Hierarchy & Coverage Thresholds

| Tier | Focus | Requirement / Threshold | Description |
|---|---|---|---|
| **Tier 1** | Feature Coverage | $\ge 5$ test cases per feature ($\ge 120$ tests total) | Happy-path and nominal functional verification of each feature in isolation. |
| **Tier 2** | Boundary & Corner Cases | $\ge 5$ test cases per feature ($\ge 120$ tests total) | Edge cases, extreme values, empty inputs, 0.0 timestamps, malformed files, invalid types, clip boundaries. |
| **Tier 3** | Cross-Feature Interactions | Pairwise & multi-way combinations ($\ge 8$ core interaction matrices) | Verifies interplay between Sanitizer, Normalizer, PostProcessor, TimingAdjuster, Config, Pipeline, and Exporters. |
| **Tier 4** | Real-World Workloads | $\ge 5$ realistic multi-stage scenarios | End-to-end simulation of real-world use cases (Gaming, Keynote, Interview, Podcast, DaVinci Resolve CLI workflow). |

---

## 3. Feature Inventory & 4-Tier Mapping (Features 1 to 24)

| # | Feature | Milestone | Tier 1: Feature Coverage ($\ge 5$) | Tier 2: Boundary & Corner ($\ge 5$) | Tier 3: Combinations | Tier 4: Scenarios |
|---|---|---|---|---|---|---|
| 1 | `SubtitleSegment` Data Model | M1 | Instantiation, `to_dict()`, `from_dict()`, float conversion, text stripping | Empty dict, missing keys, negative timestamps, `start > end`, extreme floats | Data interchange between Sanitizer, Normalizer, Exporters | Scenarios 1-5 |
| 2 | `SegmentSanitizer` (Silence/Hallucination) | M1 | Standard threshold filtering, low speech prob drop, valid speech pass, log emission, threshold config | `no_speech_prob=0.0`, `1.0`, `threshold=0.0`, `threshold=1.0`, empty segment list | Sanitizer + TimingAdjuster + Exporter | Scenario 4 (High noise) |
| 3 | `SegmentSanitizer` (Speech Rate Filter) | M1 | >12.0 chars/sec drop, <=12.0 pass, short text (<=4 chars) protection, duration calculation, custom rate | Duration 0.0s, 0.001s, 4-char boundary ("はい" vs "あいうえお"), 100 chars in 0.5s | Sanitizer + NumberNormalizer | Scenario 1 (Gaming shouts) |
| 4 | `SegmentSanitizer` (Repetition Reduction) | M1 | 2-half exact repetition halving, comp_ratio threshold, speech_prob threshold, non-repetitive preservation, odd length handling | 4-char boundary ("ああああ"), 100-char repeat, non-even split, comp_ratio=2.0 boundary, 0 speech prob | Sanitizer + TextPostProcessor dict | Scenario 4 (Podcast loops) |
| 5 | `SegmentSanitizer` (Loop Repeat Drop) | M1 | Exact match drop, sub-phrase inclusion drop, consecutive speech pass, silence condition, state reset | Identical text across 5 segments, empty previous text, 1-char match, casing differences | Sanitizer loop drop + TimingAdjuster gap | Scenario 4 (Whisper loops) |
| 6 | `SegmentSanitizer` (Word Timestamp Alignment) | M1 | First word start aligned, dict word struct, Word object struct, missing words fallback, empty words list | Word start > segment end, negative word start, word start < segment start, None words | Word alignment + end_padding + min_gap | Scenario 3 (Interview pauses) |
| 7 | DaVinci Resolve SRT Exporter | M1 | `HH:MM:SS,mmm` format, sequential numbering, UTF-8 LF, multi-line text, auto-directory creation | 0.0s (`00:00:00,000`), >24h (`25:00:00,000`), empty segments, sub-millisecond rounding, non-ASCII | TimingAdjuster + SRT output | Scenarios 1, 2, 5 |
| 8 | WebVTT Exporter | M1 | `WEBVTT` header, `HH:MM:SS.mmm` format, sequential numbering, UTF-8 LF, auto-directory creation | 0.0s (`00:00:00.000`), 3600.5s (`01:00:00.500`), empty segments, special chars, LF consistency | TimingAdjuster + VTT output | Scenarios 2, 5 |
| 9 | JSON Subtitle Exporter | M1 | Structured JSON array, `indent=2`, UTF-8 LF, `to_dict()` fidelity, auto-directory creation | Empty segments `[]`, unicode Japanese characters, float precision round, malformed input | Sanitizer + JSON output | Scenarios 2, 5 |
| 10 | `NumberNormalizer` | M2 | Kanji numbers (一-十), Roman numerals (I-X), circled (①-⑳), halfwidth to fullwidth (0-9 -> ０-９), decimal fix | Complex kanji ("十一" -> "１１", "二十五" -> "２５"), roman prefixes ("VIII" vs "V"), mixed text, no numbers, empty string | Normalizer + PostProcessor NFKC | Scenario 2 (Keynote) |
| 11 | `TextPostProcessor` Dict Loader | M2 | TOML dict loading, YAML dict loading, JSON dict loading, key length descending sort, default dict path | Missing file (`FileNotFoundError`), invalid syntax (`ValueError`), non-dict root (`ValueError`), empty dict, unicode keys | Dict Loader + Term Replacement | Scenarios 1, 2 |
| 12 | `TextPostProcessor` Term Replacement | M2 | Longest-first replacement, multiple terms, word boundary agnostic, Japanese terms, `replace_terms=False` | Substring collision ("ABC" vs "AB"), overlapping replacements, empty term value, case sensitivity | Dict replacement + NumberNormalizer | Scenario 1 (Game terms) |
| 13 | `TextPostProcessor` Normalization Flags | M2 | `to_hankaku` (NFKC), `lower` (lowercase), `remove_punct` (punctuation strip), whitespace normalize, multi-flag combo | All symbols (`、。！？`), mixed alphabet/kana, already normalized string, empty string, only symbols | Dict + NFKC + Lower + Punct + Exporter | Scenario 5 (CLI options) |
| 14 | `SubtitleTimingAdjuster` (Trailing Padding) | M2 | `end_padding` extension, multiple segments, positive float, custom padding, timestamp rounding | `end_padding=0.0`, large padding (10.0s), fractional padding (0.123s), single segment, 0-duration segment | Word alignment + Trailing Padding | Scenario 3 (Conversations) |
| 15 | `SubtitleTimingAdjuster` (Min Duration) | M2 | `min_duration` enforcement on short segment, longer segment untouched, `target_end` max calculation | Segment duration 0.05s -> 1.5s, `min_duration=0.0`, `min_duration < end_padding`, equal duration | Min duration + Overlap Clipping | Scenario 1 (Short shouts) |
| 16 | `SubtitleTimingAdjuster` (Overlap Clipping) | M2 | Next segment start collision clip, `min_gap` spacing, multiple sequential collisions, gap adjustment | Gap < 0.05s, negative gap, identical start times, `max_allowed_end < seg.start` fallback | Min duration + Overlap Clipping + Exporters | Scenario 3 (Rapid turns) |
| 17 | `SubtitleTimingAdjuster` (Total Duration) | M2 | `total_duration` clamp on last segment, intermediate segment clamp, `total_duration=None` no-op | `total_duration < seg.start`, `total_duration == seg.end`, `total_duration=0.0`, negative total duration | Trailing padding + Total Duration Clamping | Scenario 5 (Video bounds) |
| 18 | Config: `MAX_SEGMENT_CHARS` Removal | M3 | Absence from `PostProcessConfig`, omission from `config.toml`, omission from `config.example.toml`, unparsed ignored key, loader validity | TOML with legacy `MAX_SEGMENT_CHARS` ignored cleanly, default config load, case-insensitive config norm | Config load + Pipeline execution | Scenario 5 (Config load) |
| 19 | Config: Post-Processing Parameters | M3 | `PostProcessConfig` parsing, `SubtitleConfig` parsing, case-insensitivity, default fallback, custom TOML load | Out-of-range floats, boolean type coercion, missing sub-sections, partial overrides, invalid TOML syntax | Config + CLI overrides + Pipeline | Scenario 5 (Full config) |
| 20 | Pipeline: 3-Format Simultaneous Export | M4 | Simultaneous creation of `.srt`, `.vtt`, `.json`, matching timestamps across all 3, output dir creation | Write-protected dir error, empty transcription result, only audio input, video input, existing file overwrite | Pipeline + 3 Exporters + Timing | Scenarios 1, 2, 5 |
| 21 | Pipeline: `PipelineResult` Extension | M4 | Fields `vtt_file`, `json_file`, `srt_file`, `denoised_audio`, `transcript_text`, `remuxed_video` validity | None values when transcribe=False, Path object resolution, dataclass immutability/asdict | Pipeline execution return validation | Scenarios 1-5 |
| 22 | Pipeline: Post-Processing Integration | M4 | Sanitizer -> PostProcessor -> TimingAdjuster -> Exporters sequence, parameter propagation, clean flow | Denoise=False + Transcribe=True, Transcribe=False, custom dict integration, failed step handling | Full pipeline integration chain | Scenarios 1-5 |
| 23 | CLI: Post-Processing Flags & Summary Table | M4 | `--config`, `--output-dir`, `--prompt`, summary table with SRT/VTT/JSON, exit code 0 on success | Invalid args exit 1, conflicting `--denoise-only --transcribe-only` exit 1, missing input file exit 2 | CLI runner -> Config -> Pipeline | Scenario 5 (CLI batch) |
| 24 | Final Quality & E2E Acceptance | M5 | 100% test pass rate, 0 basedpyright errors, 0 ruff errors, stress test resilience, AAA pattern compliance | Adversarial fuzz inputs, extreme concurrency/memory safety, non-ASCII file paths, corrupted media handling | Full project test suite execution | Full Test Suite |

---

## 4. Real-World Application Scenarios (Tier 4 Detailed Specifications)

### Scenario 1: Live Gaming Commentary with Slang Dictionary & Keyboard Noise
- **Profile**: Multi-track gameplay video (MP4) containing high-tempo commentary with rapid game terms ("レイス", "ウルト", "アーマー", "1v3クラッチ"), background mechanical keyboard clatter, short shout reactions ("よし！", "ナイス！"), and silence gaps.
- **Workflow**:
  1. Audio track 2 extracted from MP4 container.
  2. DeepFilterNet denoising removes keyboard clicks -> `{stem}_clean.wav`.
  3. Faster-Whisper transcribes with word timestamps.
  4. `SegmentSanitizer` protects short shouts (<=4 chars), filters any silence hallucinations.
  5. `TextPostProcessor` applies `custom_dictionary.toml` to standardize game slang.
  6. `SubtitleTimingAdjuster` applies 1.0s end padding, ensures 1.5s min duration, and prevents overlap on rapid shouting.
  7. `SubtitleExporter` writes DaVinci Resolve compliant `.srt`, `.vtt`, and `.json`.
  8. Remux replaces audio track 2 with clean audio in `{stem}_clean.mp4`.
- **Validation**: Assert all 3 subtitle files exist, clean MP4 exists with valid track, and dictionary terms are replaced longest-first.

### Scenario 2: Technical Keynote Lecture with Roman/Kanji Numerals & YAML Glossary
- **Profile**: 60-minute technical lecture audio containing mixed numeral formats ("第VIII章", "2026年4月", "一万二千円", "①番目") and domain-specific acronyms.
- **Workflow**:
  1. Input audio processed with `transcribe_only=True`.
  2. `NumberNormalizer` normalizes Roman numerals, circled digits, and Kanji into standard numeric format.
  3. `TextPostProcessor` loads YAML glossary (`glossary.yaml`) and replaces technical terms.
  4. `SubtitleTimingAdjuster` applies timing padding and duration constraints.
  5. 3 subtitle formats generated simultaneously.
- **Validation**: Assert Roman numerals "VIII" -> "8" without collision ("V" -> "5"), Kanji "十一" -> "１１", and WebVTT contains correct `WEBVTT` header.

### Scenario 3: Multi-Speaker Conversational Turn-Taking with Subtitle Anti-Flicker
- **Profile**: Dialogue audio with fast back-and-forth speech turns, micro-pauses (0.05s - 0.3s), and speaker interruptions.
- **Workflow**:
  1. Raw speech transcribed into contiguous segments.
  2. `SegmentSanitizer` aligns `start` to `words[0].start` to eliminate pre-speech dead space.
  3. `SubtitleTimingAdjuster` calculates `end + end_padding` but detects subsequent speaker start within 0.05s.
  4. Overlap clipping truncates end timestamp to `next_start - min_gap` (0.05s) to guarantee zero overlapping subtitles and eliminate subtitle flicker in NLEs.
- **Validation**: Assert for all consecutive segments `seg[i].end <= seg[i+1].start - 0.05` and `seg[i].start < seg[i].end`.

### Scenario 4: High-Noise Podcasting with Severe Hallucination & Silence Loops
- **Profile**: Studio recording with long pauses where Whisper generates repetitive phantom loops ("ご視聴ありがとうございました", repeated phrases) and silence noise.
- **Workflow**:
  1. Audio processed through pipeline.
  2. `SegmentSanitizer` drops segments where `no_speech_prob > 0.6`.
  3. `SegmentSanitizer` detects intra-segment repetition ("あいうえおあいうえお") under high compression ratio and truncates to "あいうえお".
  4. `SegmentSanitizer` detects inter-segment loop repeats in low-speech zones and drops duplicate hallucinated segments.
- **Validation**: Assert hallucinated segments are completely eliminated and clean transcript contains only legitimate speech.

### Scenario 5: End-to-End DaVinci Resolve CLI Workflow with Custom Config & CLI Overrides
- **Profile**: Video editor executes `audio-transcriber video.mp4 -C custom_config.toml -o ./davinci_subs --prompt "DaVinci"`.
- **Workflow**:
  1. CLI parses arguments, loads TOML config, verifies absence of `MAX_SEGMENT_CHARS`.
  2. CLI merges command-line overrides with configuration defaults.
  3. Pipeline executes extraction, denoising, transcription, post-processing, and 3-format export.
  4. Rich CLI table renders all generated outputs with green checkmarks.
- **Validation**: Exit code is 0, SRT file passes DaVinci Resolve format checks (comma milliseconds, LF line endings, UTF-8 without BOM), VTT and JSON match SRT segment counts.

---

## 5. Test Architecture & Modular Partitioning (<= 200 Lines Target)

To adhere strictly to `AGENTS.md` (target <= 200 lines, maximum 300 lines per file), the E2E test suite is partitioned into 12 dedicated modules under `tests/`:

```
tests/
├── test_e2e_models.py         (~150 lines) -> Feature 1 (SubtitleSegment dataclass & dict conversions)
├── test_e2e_sanitizer.py      (~190 lines) -> Features 2, 3, 4, 5, 6 (Silence, Speech Rate, Repetitions, Loops, Word Timestamps)
├── test_e2e_normalizer.py     (~160 lines) -> Feature 10 (NumberNormalizer 6-stage normalization, Kanji, Roman, Circled)
├── test_e2e_postprocess.py    (~190 lines) -> Features 11, 12, 13 (TextPostProcessor dict loading, longest-first, NFKC/lower/punct)
├── test_e2e_timing.py         (~190 lines) -> Features 14, 15, 16, 17 (SubtitleTimingAdjuster padding, min duration, gap, total duration)
├── test_e2e_exporters.py      (~190 lines) -> Features 7, 8, 9 (SubtitleExporter SRT DaVinci, WebVTT, JSON, auto-dispatch)
├── test_e2e_config.py         (~160 lines) -> Features 18, 19 (Config parsing, MAX_SEGMENT_CHARS removal, PostProcess & Subtitle config)
├── test_e2e_pipeline.py       (~190 lines) -> Features 20, 21, 22 (run_pipeline 3-format export, PipelineResult, post-processing integration)
├── test_e2e_cli.py            (~180 lines) -> Feature 23 (Typer CLI options, Rich summary table, exit codes)
├── test_e2e_combinations.py   (~190 lines) -> Tier 3 Cross-feature pairwise interaction test matrices
├── test_e2e_scenarios.py      (~200 lines) -> Tier 4 Real-world realistic scenarios 1-5
└── test_e2e_hardening.py      (~180 lines) -> Feature 24 (Adversarial stress testing, edge-case hardening, resilience)
```

### Test Invocation & Pass/Fail Semantics:
- **Individual suite execution**: `uv run pytest tests/test_e2e_sanitizer.py`
- **Full E2E suite execution**: `uv run pytest tests/test_e2e_*.py`
- **Full project test suite & coverage**: `uv run pytest --cov=audio_transcriber --cov-report=term-missing`
- **Pass Semantics**: All test assertions must evaluate to `True`, 0 test failures, 0 errors, 0 warnings.
- **Fail Semantics**: Any non-zero exit code, unhandled exception, assertion failure, or timeout triggers immediate failure.

---

## 6. Complete Specification for `TEST_INFRA.md`

Below is the formulated exact markdown content for `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/TEST_INFRA.md`:

```markdown
# TEST_INFRA: End-to-End Testing Infrastructure Specification

## 1. Test Philosophy
- **Opaque-Box & Requirement-Driven**: All E2E tests are designed against requirements specified in `PROJECT.md` and `ORIGINAL_REQUEST.md` without reliance on private implementation details.
- **Deterministic & High-Speed**: Machine learning inference (`faster-whisper`, `DeepFilterNet`) and external CLI utilities (`ffmpeg`) are mocked at boundary protocols, guaranteeing sub-second test runs and reproducible results.
- **DaVinci Resolve Import Compatibility**: Strict adherence to SRT `HH:MM:SS,mmm` comma milliseconds, UTF-8 encoding, and LF line breaks.
- **KISS & Size Compliance**: Every test module is strictly budgeted to <=200 lines target (maximum 300 lines) following the Arrange-Act-Assert (AAA) pattern.

## 2. Feature Inventory & Tier Mapping (24 Features)
All 24 features from PROJECT.md are mapped across the 4-Tier testing structure:
- **F1**: `SubtitleSegment` Data Model -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F2**: `SegmentSanitizer` Silence/Hallucination Filter -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F3**: `SegmentSanitizer` Speech Rate Filter -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F4**: `SegmentSanitizer` Repetition Reduction -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F5**: `SegmentSanitizer` Loop Repeat Drop -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F6**: `SegmentSanitizer` Word Timestamp Alignment -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F7**: DaVinci Resolve SRT Exporter -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F8**: WebVTT Subtitle Exporter -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F9**: JSON Subtitle Exporter -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F10**: `NumberNormalizer` (6-stage normalization) -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F11**: `TextPostProcessor` Dictionary Loader (TOML/YAML/JSON) -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F12**: `TextPostProcessor` Term Replacement (Longest-First) -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F13**: `TextPostProcessor` Text Normalization Flags -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F14**: `SubtitleTimingAdjuster` Trailing Padding -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F15**: `SubtitleTimingAdjuster` Minimum Duration -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F16**: `SubtitleTimingAdjuster` Overlap Clipping -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F17**: `SubtitleTimingAdjuster` Total Duration Clamping -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F18**: Config: `MAX_SEGMENT_CHARS` Parameter Removal -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F19**: Config: Post-Processing & Subtitle Parameters -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F20**: Pipeline: 3-Format Simultaneous Export (.srt, .vtt, .json) -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F21**: Pipeline: `PipelineResult` Extension -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F22**: Pipeline: Post-Processing Integration -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F23**: CLI: Post-Processing Flags & Summary Table -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4
- **F24**: Final Quality & E2E Acceptance -> Tier 1 (5 tests), Tier 2 (5 tests), Tier 3, Tier 4

## 3. Test Architecture & Modular Partitioning
The E2E test suite resides under `tests/` and is divided into 12 modular files ensuring < 200 lines per file:
1. `tests/test_e2e_models.py`: Data model serialization & validation.
2. `tests/test_e2e_sanitizer.py`: Silence filtering, speech rate thresholding, repetition reduction, loop drops, word alignment.
3. `tests/test_e2e_normalizer.py`: 6-stage number normalization (Kanji, Roman, Circled, fullwidth).
4. `tests/test_e2e_postprocess.py`: TOML/YAML/JSON dictionary loading, longest-first replacement, NFKC, lowercase, punctuation removal.
5. `tests/test_e2e_timing.py`: Trailing padding, minimum duration expansion, overlap clipping with min gap, total duration clamp.
6. `tests/test_e2e_exporters.py`: SRT (DaVinci format), WebVTT, JSON exports, UTF-8 LF verification, format auto-dispatch.
7. `tests/test_e2e_config.py`: Removal of MAX_SEGMENT_CHARS, PostProcessConfig, SubtitleConfig, TOML parsing.
8. `tests/test_e2e_pipeline.py`: Simultaneous 3-format generation, PipelineResult fields, pipeline post-processing flow.
9. `tests/test_e2e_cli.py`: CLI flags, rich summary table output, error handling and exit codes.
10. `tests/test_e2e_combinations.py`: Tier 3 cross-feature interactions and pairwise matrices.
11. `tests/test_e2e_scenarios.py`: Tier 4 real-world workloads (Gaming, Keynote, Interview, Podcast, DaVinci CLI).
12. `tests/test_e2e_hardening.py`: Tier 5 / F24 adversarial edge cases, stress testing, corrupted inputs.

### Test Runner Invocation:
- Full E2E Test Suite: `uv run pytest tests/test_e2e_*.py`
- With Coverage: `uv run pytest --cov=audio_transcriber --cov-report=term-missing`
- Static Analysis: `uv run basedpyright && uv run ruff check . && uv run ruff format --check .`

## 4. Real-World Application Scenarios (Tier 4)
- **Scenario 1**: Live Gaming Commentary with Slang Dictionary & Keyboard Noise (MP4 multi-track, Denoise, Slang replacement, 3-format export, Remux).
- **Scenario 2**: Technical Keynote Lecture with Roman/Kanji Numerals & YAML Glossary (Transcribe-only, NumberNormalizer, YAML dict, VTT/SRT).
- **Scenario 3**: Multi-Speaker Conversational Turn-Taking with Subtitle Anti-Flicker (Word timestamp alignment, min gap clipping, overlap prevention).
- **Scenario 4**: High-Noise Podcasting with Severe Hallucination & Silence Loops (Silence thresholding, loop repeat drops, intra-segment halving).
- **Scenario 5**: End-to-End DaVinci Resolve CLI Workflow with Custom Config & CLI Overrides (TOML config load, CLI overrides, rich output table, DaVinci format verification).

## 5. Coverage Thresholds
- **Tier 1 (Feature Coverage)**: $\ge 5$ test cases per feature area ($\ge 120$ test cases).
- **Tier 2 (Boundary & Corner Cases)**: $\ge 5$ test cases per feature area ($\ge 120$ test cases).
- **Tier 3 (Cross-Feature Combinations)**: $\ge 8$ comprehensive pairwise/multi-way interaction test matrices.
- **Tier 4 (Real-World Workloads)**: 5 end-to-end multi-stage application workflows.
```
