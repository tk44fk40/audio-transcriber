# Handoff Report: E2E Test Suite Investigation & Architecture

## 1. Observation

### 1.1 Existing Test Suite Structure & Metrics
- Directly inspected files in `tests/`:
  - `tests/test_basic.py` (35 lines): Tests `format_timestamp` and `segments_to_srt`.
  - `tests/test_cli.py` (101 lines): Tests CLI argument parser, option validation, error recovery, and `run_pipeline` invocation.
  - `tests/test_compat.py` (23 lines): Tests `apply_torchaudio_compat` with `sys.modules` patching.
  - `tests/test_config.py` (171 lines): Tests default dataclasses, UPPER_CASE TOML keys, auto-loading from CWD, FileNotFoundError, and ValueError on bad syntax. Line 90 currently has `MAX_SEGMENT_CHARS = 25` (planned for removal in M3).
  - `tests/test_denoise.py` (68 lines): Tests `denoise_audio` with/without `df_state` reuse using `unittest.mock`.
  - `tests/test_media.py` (227 lines): Tests audio track inspection, extraction, remuxing with mocked `subprocess.run`, and a real ffmpeg synthetic video workflow (`test_ffmpeg_real_multitrack_workflow`, lines 156–227).
  - `tests/test_pipeline.py` (92 lines): Tests `run_pipeline` orchestration on audio and video inputs.
  - `tests/test_transcribe.py` (99 lines): Tests `transcribe_audio` with/without file output by mocking `WhisperModel`.
- Total test lines: 816 lines across 8 files (average 102 lines/file, max 227 lines/file).
- Currently, no `tests/conftest.py` exists in the repository.

### 1.2 Baseline Execution Status
- Executed `uv run pytest --cov=audio_transcriber --cov-report=term-missing`:
  - Output: `31 passed in 2.04s`, `TOTAL: 364 stmts, 0 miss, 100% coverage`.
- Executed `uv run basedpyright`:
  - Output: `0 errors, 0 warnings, 0 notes`.
- Executed `uv run ruff check .`:
  - Output: `All checks passed!`.
- Executed `uv run ruff format --check src tests`:
  - Output: `16 files already formatted`.

### 1.3 Configuration Files
- `pyproject.toml`:
  - `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `pythonpath = ["src"]`.
  - `[tool.coverage.report]`: `exclude_lines` includes `pragma: no cover`, `if __name__ == "__main__":`, `if TYPE_CHECKING:`, `raise NotImplementedError`, `^\s*\.\.\.\s*$`.

---

## 2. Logic Chain

1. **Direct observation 1.1** shows that test files currently duplicate small data models and mock patterns (e.g. `DummySegment` in both `test_basic.py:16` and `test_transcribe.py:10`). Introducing a shared `tests/conftest.py` will provide standardized fixtures (`sample_segments`, `mock_whisper_model`, `sample_dict_files`) for both unit and E2E tests, avoiding code duplication.
2. **Direct observation 1.1 & 1.2** demonstrates that all tests execute in ~2 seconds because heavy AI/ML models (`WhisperModel`, DeepFilterNet) and CLI operations are mocked using `unittest.mock.patch`, while fast deterministic integration is achieved via synthetic ffmpeg generators. E2E tests should adopt the exact same pattern: mock model weight loading/inference but validate full cross-module data flow and file outputs.
3. **Direct observation 1.1** establishes that the project enforces a strict 300-line limit per file (target <= 200 lines). Implementing all 24 features across Tiers 1–4 in a single or monolithic E2E file would violate this constraint (~1,200+ lines total).
4. Therefore, partitioning the E2E test suite into 7 domain-scoped test files (`test_e2e_models_sanitizer.py`, `test_e2e_postprocess.py`, `test_e2e_timing.py`, `test_e2e_exporters.py`, `test_e2e_config.py`, `test_e2e_pipeline_cli.py`, `test_e2e_scenarios.py`) plus `conftest.py` guarantees that every file remains between 120 and 220 lines.
5. **Direct observation 1.3** shows that registering a custom marker `markers = ["e2e: End-to-end integration tests"]` in `pyproject.toml` enables selective execution (`pytest -m e2e` vs `pytest -m "not e2e"`) while allowing `uv run pytest` to seamlessly execute all unit and E2E tests together during pre-commit checks.

---

## 3. Caveats

- **Caveat 1**: The new post-processing modules (`models.py`, `sanitizer.py`, `normalizer.py`, `post_processor.py`, `timing.py`, `exporter.py`) are scheduled to be implemented in Milestones M1 and M2. E2E tests will run against these new interfaces once implemented.
- **Caveat 2**: When testing CLI invocations with `CliRunner`, `CliRunner` captures stdout/stderr in memory; verifying file outputs should always check paths on disk inside `tmp_path`.
- **Caveat 3**: No live GPU or real Whisper inference will be executed in automated tests to maintain test speed and deterministic behavior.

---

## 4. Conclusion

1. **E2E Test File Structure**: E2E tests should be placed in `tests/test_e2e_*.py` partitioned into 7 focused files (150–220 lines each) to respect the 300-line ceiling and single-responsibility principle.
2. **Fixture Centralization**: Create `tests/conftest.py` with shared fixtures for subtitle segments, mock Whisper word timestamps, and temporary dictionary files (TOML, YAML, JSON).
3. **Pytest Integration**: Register `e2e` marker in `pyproject.toml` to support granular filtering while preserving 100% full-suite execution in standard test runs.
4. **Mocking Standards**: Use `unittest.mock` for Whisper and DeepFilterNet model execution, while exercising actual filesystem I/O and data transformations end-to-end.

---

## 5. Verification Method

To independently verify the findings and test execution:

```bash
# 1. Run full test suite with coverage
uv run pytest --cov=audio_transcriber --cov-report=term-missing

# 2. Run static type checking
uv run basedpyright

# 3. Run lint check
uv run ruff check .

# 4. Run format check on source and tests
uv run ruff format --check src tests
```

**Invalidation conditions**:
- Any test file exceeds 300 lines.
- Total test execution time exceeds 10 seconds.
- Test coverage drops below 100% on core logic paths.
- E2E tests interfere with or break existing unit test isolation.
