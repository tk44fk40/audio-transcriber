# E2E Testing Architecture & Test Suite Investigation Report

## Executive Summary
This report analyzes the existing test suite, testing conventions, mocking strategies, and coverage configuration in `audio-transcriber`, and provides a detailed architectural plan for organizing the End-to-End (E2E) test suite (covering Tiers 1–4 across all 24 features in `PROJECT.md`).

---

## 1. Existing Test Suite and Structure Analysis

### 1.1 File Layout and Line Count Audit
The existing test suite is located in `tests/` and consists of 8 test files without a shared `conftest.py`:

| Test File | Lines | Scope & Responsibilities |
|---|---|---|
| `tests/test_basic.py` | 35 | Verifies basic timestamp formatting (`HH:MM:SS,mmm`) and segment-to-SRT string conversion. |
| `tests/test_cli.py` | 101 | CLI argument validation, `--help`, `--denoise-only` vs `--transcribe-only` conflict, error handling, config parsing, and `run_pipeline` invocation. |
| `tests/test_compat.py` | 23 | Torchaudio compatibility layer fallback on `ImportError` and dummy `AudioMetaData` injection into `sys.modules`. |
| `tests/test_config.py` | 171 | Default configuration dataclasses, TOML parsing (UPPER_CASE keys), CWD auto-loading, error handling on invalid TOML or missing files. |
| `tests/test_denoise.py` | 68 | DeepFilterNet noise reduction: initialization, audio load/enhance/save, and df_state reuse. |
| `tests/test_media.py` | 227 | Video extension check, ffprobe stream parsing, ffmpeg audio extraction, multitrack remuxing, error handling, and real ffmpeg synthetic video workflow. |
| `tests/test_pipeline.py` | 92 | Full pipeline execution for audio-only and multitrack video files, verifying artifact path outputs. |
| `tests/test_transcribe.py` | 99 | faster-whisper model invocation mocking, segment dictionary generation, SRT file generation with/without output path. |

**Observation on Line Counts**: All existing files are strictly within the 300-line ceiling (max is `test_media.py` at 227 lines; average ~102 lines).

### 1.2 Test Execution and Performance Baseline
Executing `uv run pytest --cov=audio_transcriber --cov-report=term-missing`:
- **Result**: 31 passed in 2.04 seconds.
- **Coverage**: 100% statement coverage (364/364 statements covered across all 8 source files in `src/audio_transcriber/`).
- **Static Analysis**: `uv run basedpyright` passes with 0 errors, 0 warnings, 0 notes.
- **Linter & Formatter**: `uv run ruff check .` and `uv run ruff format --check src tests` pass with 0 violations.

---

## 2. Testing Conventions, Fixtures, and Mocking Practices

### 2.1 Pytest & Coverage Configuration (`pyproject.toml`)
- **Pytest settings**:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  pythonpath = ["src"]
  ```
- **Coverage exclusion rules**:
  ```toml
  [tool.coverage.report]
  exclude_lines = [
      "pragma: no cover",
      'if __name__ == "__main__":',
      "if TYPE_CHECKING:",
      "raise NotImplementedError",
      '^\\s*\\.\\.\\.\\s*$',
  ]
  ```
- **Docstrings & AAA Pattern**:
  - Every test function contains a Google-style docstring in Japanese describing the purpose.
  - AAA (Arrange-Act-Assert) pattern is consistently applied.

### 2.2 Mocking Patterns and Best Practices
1. **AI/ML Heavy Models (`WhisperModel`, `DeepFilterNet`)**:
   - Never load real weights or run real GPU/CPU inference during unit/E2E test runs.
   - `unittest.mock.patch("audio_transcriber.transcribe.WhisperModel")` and mock generator for `transcribe()` returning `(iter(segments), info)`.
   - `unittest.mock.patch("audio_transcriber.denoise.init_df")`, `enhance`, `load_audio`, `save_audio`.
2. **External CLI Tools (`ffmpeg`, `ffprobe`)**:
   - Mocked via `patch("subprocess.run")` returning `MagicMock(stdout=..., returncode=0)` or raising `subprocess.CalledProcessError`.
   - Real CLI integration: Fast synthetic generator using ffmpeg `lavfi` filters (`testsrc=duration=1`, `sine=duration=1`) in temporary directories (`tmp_path`). This executes in <100ms without committing binary audio/video fixtures to git.
3. **Environment & Filesystem**:
   - Uses pytest `tmp_path: Path` fixture for all filesystem outputs.
   - Uses `monkeypatch: pytest.MonkeyPatch` for CWD switching and environment variable manipulation.

---

## 3. E2E Test Suite Architecture & Structure Design

### 3.1 Principles for E2E Suite Design
1. **Opaque-Box Requirement-Driven Testing**:
   - Tests focus on external contracts, data flow between modules, pipeline execution, CLI commands, and output file integrity (SRT, VTT, JSON, audio/video).
2. **No Interference with Unit Tests**:
   - Co-located in `tests/` prefixed with `test_e2e_*.py`.
   - Pytest marker `@pytest.mark.e2e` registered in `pyproject.toml` so developers can run unit-only (`-m "not e2e"`), E2E-only (`-m e2e`), or full suite.
3. **Strict Compliance with 300-Line Limit (Target <= 200 lines)**:
   - Split E2E tests into focused modules according to functional domain and integration boundaries.
4. **Shared Fixtures via `tests/conftest.py`**:
   - Provide centralized fixtures for sample subtitle segments, mock Whisper transcription outputs with word timestamps, sample dictionary files (TOML, YAML, JSON), and synthetic audio creators.

### 3.2 Proposed E2E Test Suite Partitioning

| File Name | Target Features | Target Lines | Scope & Coverage |
|---|---|---|---|
| `tests/conftest.py` | Fixtures | ~120 lines | Shared fixtures: `sample_segments`, `mock_whisper_transcription`, `sample_dict_toml`, `sample_dict_yaml`, `sample_dict_json`, `synthetic_audio_file`. |
| `tests/test_e2e_models_sanitizer.py` | F1–F6 | ~180 lines | Data model serialization (`to_dict`/`from_dict`), hallucination filtering, speech rate thresholding, repetition reduction, loop drop, word timestamp alignment. |
| `tests/test_e2e_postprocess.py` | F10–F13 | ~190 lines | Number normalization (kanji, roman, circled, fullwidth), multi-format dictionary loading (TOML, YAML, JSON), longest-first substitution, NFKC/lowercase/punctuation flags. |
| `tests/test_e2e_timing.py` | F14–F17 | ~170 lines | Trailing end padding, minimum duration guarantee, overlap/min_gap clipping, total media duration boundary clamping, edge cases (empty list, dense segments). |
| `tests/test_e2e_exporters.py` | F7–F9 | ~180 lines | DaVinci Resolve SRT compliance (`HH:MM:SS,mmm`, UTF-8, LF, 1-based indexing), WebVTT header/period format, JSON schema structure, multi-format exporter dispatcher (`save_subtitles`). |
| `tests/test_e2e_config.py` | F18–F19 | ~150 lines | PostProcessConfig and SubtitleConfig parsing from TOML, CLI option overrides, verification of complete removal of MAX_SEGMENT_CHARS. |
| `tests/test_e2e_pipeline_cli.py` | F20–F23 | ~200 lines | `run_pipeline` end-to-end generating 3 subtitle formats simultaneously (`.srt`, `.vtt`, `.json`), `PipelineResult` field verification, CLI command execution and Rich table output. |
| `tests/test_e2e_scenarios.py` | F24 (Tier 4) | ~220 lines | Real-world conversational workloads, gaming stream with custom terminology + numbers, noisy audio with hallucination patterns, DaVinci Resolve import compliance check, corrupted input resilience. |

### 3.3 Pyproject.toml Recommended Additions
To cleanly integrate E2E tests, register the custom marker in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
markers = [
    "e2e: End-to-end and cross-component integration tests",
]
```

---

## 4. Key Recommendations for Implementation
1. **Create `tests/conftest.py` early**: Centralizing shared fixtures prevents duplicate definitions in unit and E2E test files.
2. **Follow AAA pattern consistently**: Keep test methods structured and avoid branching inside test assertions.
3. **Use fast in-memory / synthetic fixtures**: Ensure all E2E tests execute within a few seconds to maintain rapid development cycles.
4. **Enforce strict line limits**: Keep all test files <= 220 lines so they remain maintainable and adhere to project standards.
