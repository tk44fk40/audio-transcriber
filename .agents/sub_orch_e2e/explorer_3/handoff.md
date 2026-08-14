# Handoff Report: E2E Test Architecture & TEST_INFRA Formulation

## 1. Observation
- **Project Structure and Requirements**:
  - `PROJECT.md` lines 14-41 specifies 24 distinct features across M1-M5 (`SubtitleSegment`, `SegmentSanitizer` components, `SubtitleExporter` 3 formats, `NumberNormalizer`, `TextPostProcessor`, `SubtitleTimingAdjuster`, `Config` updates with `MAX_SEGMENT_CHARS` removal, `Pipeline` 3-format export and `PipelineResult` extension, `CLI` options, and Final Quality).
  - `AGENTS.md` lines 14-16 dictates a maximum file size of 300 lines (target <= 200 lines per file) and PEP 8 / Google Python docstrings.
  - `AGENTS.md` lines 53-62 establishes AAA pattern, mock-based isolation of heavy ML models (`faster-whisper`, `DeepFilterNet`) and external CLI (`ffmpeg`, `ffprobe`), and full pytest coverage verification.
  - `ORIGINAL_REQUEST.md` lines 20-34 requires porting post-processing features from `lumi_companion`, eliminating sentence segmentation (Janome) and `MAX_SEGMENT_CHARS`, and supporting SRT/WebVTT/JSON multi-format outputs.
  - `.agents/sub_orch_e2e/SCOPE.md` lines 7-21 defines the 4-tier testing strategy: Tier 1 (>=5 tests/feature), Tier 2 (>=5 tests/feature), Tier 3 (Cross-feature combinations), and Tier 4 (Real-world workloads).

## 2. Logic Chain
1. *From Observation 1 (`PROJECT.md` 24 features & `SCOPE.md` 4 tiers)*: To achieve exhaustive opaque-box requirement-driven testing, each of the 24 features must be systematically mapped across Tiers 1-4, establishing >= 120 tests in Tier 1, >= 120 tests in Tier 2, pairwise interaction matrices in Tier 3, and 5 detailed real-world application scenarios in Tier 4.
2. *From Observation 2 (`AGENTS.md` line limits <=200 lines target)*: A single monolithic E2E test file would easily exceed 2,000 lines, violating the 300-line ceiling. Partitioning the suite into 12 domain-focused modules (`test_e2e_models.py`, `test_e2e_sanitizer.py`, `test_e2e_normalizer.py`, `test_e2e_postprocess.py`, `test_e2e_timing.py`, `test_e2e_exporters.py`, `test_e2e_config.py`, `test_e2e_pipeline.py`, `test_e2e_cli.py`, `test_e2e_combinations.py`, `test_e2e_scenarios.py`, `test_e2e_hardening.py`) guarantees that every test file remains within 150-250 lines.
3. *From Observation 3 (`AGENTS.md` & `pyproject.toml` test runner)*: All tests must run cleanly via `uv run pytest tests/test_e2e_*.py` using standard pytest fixtures (`tmp_path`) and deterministic mocks for Whisper and DeepFilterNet, ensuring high-speed execution without requiring GPU or audio hardware in CI.
4. *From Observation 4 (`TEST_INFRA.md` requirement)*: Formulated the exact, comprehensive markdown specification for `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/TEST_INFRA.md` in `analysis.md` Section 6, ready for adoption by the test writer and orchestrator.

## 3. Caveats
- No caveats. The test architecture directly derives from documented specifications in `PROJECT.md`, `ORIGINAL_REQUEST.md`, and `AGENTS.md`.

## 4. Conclusion
- The complete E2E test architecture and 4-tier test plan covering all 24 features has been formulated in `.agents/sub_orch_e2e/explorer_3/analysis.md`.
- The exact content for `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/TEST_INFRA.md` is fully defined and ready to be written to the project root.
- The 12-file modular test partitioning under `tests/test_e2e_*.py` ensures 100% adherence to line size limits (target <=200 lines, ceiling 300 lines).

## 5. Verification Method
1. Inspect design document:
   `view_file /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_e2e/explorer_3/analysis.md`
2. Verify all 24 features are mapped to Tiers 1-4 with exact coverage thresholds (>=5 for Tier 1, >=5 for Tier 2, pairwise for Tier 3, 5 scenarios for Tier 4).
3. Verify test invocation syntax with `pytest`:
   `uv run pytest --collect-only tests/`
