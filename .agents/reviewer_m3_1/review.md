# Review & Challenge Report — Milestone 3 (Config Cleanup & Parameter Updates)

## Review Summary

**Verdict**: **APPROVE**  
**Integrity Assessment**: PASS (No hardcoded outputs, no facades, genuine implementation)  
**Overall Risk Assessment**: LOW

---

## 1. Quality Review Findings

### Verified Items & Compliance Matrix

| Item | Requirement / Contract | Verification Method | Status | Notes |
|---|---|---|---|---|
| **Removal of MAX_SEGMENT_CHARS** | Complete removal from `config.py`, `config.toml`, `config.example.toml`, `test_config.py` | `grep_search`, inspection, unit test | **PASS** | Fully removed; negative test confirms legacy key is ignored safely |
| **PostProcessConfig** | 8 fields (`custom_dict_path`, `replace_terms`, `normalize_nums`, `to_hankaku`, `lower`, `remove_punct`, `no_speech_threshold`, `max_chars_per_second`) | Code inspection, `test_default_config_instances` | **PASS** | Exact field names, types, and defaults matched |
| **SubtitleConfig** | 4 fields (`end_padding`, `min_duration`, `min_gap`, `formats`) | Code inspection, `test_default_config_instances` | **PASS** | Exact field names, types, and defaults matched (`default_factory` used for list) |
| **AppConfig** | Root dataclass containing `pipeline`, `media`, `model`, `transcribe`, `post_process`, `subtitle` | Code inspection, type checking | **PASS** | Nested config factories and default paths initialized properly |
| **TOML Parser Robustness** | Case-insensitivity, section aliases (`[postprocess]`, `[subtitles]`), comma-separated format parsing, fallback defaults | `test_load_config_case_insensitivity_and_aliases`, `test_load_config_full_custom_toml`, `test_parse_config_dict_formats_fallback` | **PASS** | Recursive key normalization and multi-alias resolution implemented cleanly |
| **File Line Limits** | <= 300 lines per file (target <= 200 lines) | `wc -l` | **PASS** | `config.py`: 297 lines, `test_config.py`: 287 lines |
| **Coding Standards** | PEP 8 / Google-style Japanese docstrings, strict Python 3.11+ type hints | `ruff check`, `ruff format --check`, `basedpyright` | **PASS** | 0 lint errors, 0 format warnings, 0 type errors |
| **Test Quality & Coverage** | AAA pattern, isolated temp paths, error branches tested | `pytest -v` (11 config tests, 35 core tests) | **PASS** | All 11 config unit tests and all 35 core regression tests passed |

---

## 2. Adversarial Review & Challenge Analysis

### Challenge 1: Section Name Variations and Case-Insensitivity
- **Hypothesis/Attack**: TOML files with varying cases (`[Post_Process]`, `[PostProcess]`, `[SUBTITLES]`) or alternative section keys might fail to parse.
- **Investigation**: `_normalize_dict` recursively normalizes all dictionary keys to lowercase. Section resolution checks `norm.get("post_process") or norm.get("postprocess") or norm.get("post_processing")` and `norm.get("subtitle") or norm.get("subtitles")`.
- **Result**: **PASS**. Tested in `test_load_config_case_insensitivity_and_aliases`.

### Challenge 2: Formatting Variations for `formats` Key
- **Hypothesis/Attack**: User might pass a single comma-separated string `formats = "srt, vtt"`, a list `["SRT", "VTT"]`, an invalid type, or omit it.
- **Investigation**: `parse_config_dict` explicitly handles string splitting, list element stripping/lowercasing, and invalid types with safe fallback to `["srt", "vtt", "json"]`.
- **Result**: **PASS**. Tested in `test_parse_config_dict_formats_fallback` and `test_load_config_case_insensitivity_and_aliases`.

### Challenge 3: Legacy `MAX_SEGMENT_CHARS` in Existing TOML Files
- **Hypothesis/Attack**: Existing users' `config.toml` containing `MAX_SEGMENT_CHARS = 30` might cause unexpected keyword argument exceptions during dataclass instantiation.
- **Investigation**: `parse_config_dict` maps inputs into explicit dataclass constructor arguments rather than unpacking dicts (`**dict`), ensuring unknown legacy keys are safely ignored without error.
- **Result**: **PASS**. Tested in `test_max_segment_chars_absent_and_ignored`.

### Challenge 4: Dictionary Path Cascading
- **Hypothesis/Attack**: Specifying `custom_dict_path` inside `[post_process]` vs root level `custom_dictionary_path` might cause inconsistency.
- **Investigation**: Lines 205-210 in `config.py` resolve `custom_dict_path` from both section and root, keeping them synchronized.
- **Result**: **PASS**.

---

## 3. Verified Claims

1. `MAX_SEGMENT_CHARS` is completely decommissioned from active config definitions and runtime.
   - Verified via `grep_search`, `src/audio_transcriber/config.py`, `config.toml`, `config.example.toml`.
2. `PostProcessConfig` and `SubtitleConfig` conform to the Milestone 3 specification.
   - Verified via `src/audio_transcriber/config.py:97-118`.
3. Test suite runs and passes cleanly.
   - `uv run pytest tests/test_config.py -v`: 11 passed in 0.99s.
   - `uv run pytest tests/test_basic.py tests/test_cli.py tests/test_compat.py tests/test_config.py tests/test_denoise.py tests/test_media.py tests/test_pipeline.py tests/test_transcribe.py`: 35 passed in 1.53s.
4. Static analysis and formatting pass cleanly.
   - `uv run basedpyright src/audio_transcriber/config.py tests/test_config.py`: 0 errors.
   - `uv run ruff check src/audio_transcriber/config.py tests/test_config.py`: All checks passed.
   - `uv run ruff format --check src/audio_transcriber/config.py tests/test_config.py`: 2 files already formatted.
5. Line count limits maintained.
   - `src/audio_transcriber/config.py`: 297 lines (<= 300).
   - `tests/test_config.py`: 287 lines (<= 300).

---

## 4. Unverified Items / Gaps

- Parallel milestones M1/M2 modules (`normalizer.py`, `post_processor.py`, `timing.py`) are concurrently developed and tested in separate milestones. Their E2E integration with `AppConfig` will be verified in Milestone 4 (Pipeline & CLI Integration) and E2E review.

---

## 5. Final Recommendation

The implementation provided by `worker_m3_1` satisfies all requirements for Milestone 3 with high code quality, robust parsing logic, complete test coverage, and strict adherence to project standards.

**Final Verdict**: **APPROVE**
