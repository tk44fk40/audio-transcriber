# Scope: E2E Testing Track

## Architecture
- **Opaque-Box Requirement-Driven Testing**:
  - Validates full end-to-end flow from input audio/transcription data models to sanitized, normalized, timing-adjusted subtitles exported to SRT (DaVinci compliant), WebVTT, and JSON.
  - Tests CLI invocations, pipeline runs, configuration loading/validation, and standalone post-processor module interaction.
- **Coverage Tiers**:
  - **Tier 1 (Feature Coverage)**: >=5 tests per feature area (Data Model, Sanitizer, Exporter, Normalizer, PostProcessor, TimingAdjuster, Config, Pipeline, CLI).
  - **Tier 2 (Boundary & Corner Cases)**: >=5 tests per feature area (Empty inputs, 0.0 timestamps, negative offsets, extreme speech rate, overlapping intervals, special unicode/NFKC, malformed dicts, edge durations).
  - **Tier 3 (Cross-Feature Combinations)**: Pairwise interactions (e.g., Sanitizer + NumberNormalizer + TimingAdjuster + SRT/VTT/JSON exporters).
  - **Tier 4 (Real-World Workloads)**: Multi-speaker conversational data, noisy media with silence/hallucination, tech presentation with custom glossary & numbers, DaVinci Resolve import compliance scenarios.

## Feature Inventory Mapping
All 24 features from PROJECT.md are mapped to test suites in `tests/`:
- F1-F6: Sanitizer & SubtitleSegment model (`tests/test_e2e_sanitizer.py` / `tests/test_e2e_models.py`)
- F7-F9: SRT/VTT/JSON Exporters (`tests/test_e2e_exporters.py`)
- F10-F13: Normalizer & PostProcessor (`tests/test_e2e_postprocess.py`)
- F14-F17: Timing Adjuster (`tests/test_e2e_timing.py`)
- F18-F19: Config parameters & removal of MAX_SEGMENT_CHARS (`tests/test_e2e_config.py`)
- F20-F23: Pipeline & CLI end-to-end (`tests/test_e2e_pipeline_cli.py`)
- F24: Full Integration Acceptance & Adversarial Hardening (`tests/test_e2e_integration.py`)

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E1 | E2E Architecture & Test Infra | `TEST_INFRA.md`, test fixtures | none | IN_PROGRESS |
| E2 | Tiers 1-4 Test Suite Implementation | `tests/test_e2e_*.py` | E1 | PLANNED |
| E3 | Verification, Audit & TEST_READY | Reviewers, Challengers, Auditor, `TEST_READY.md` | E2 | PLANNED |
