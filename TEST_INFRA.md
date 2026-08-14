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
