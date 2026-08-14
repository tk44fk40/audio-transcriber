## 2026-08-14T19:02:02Z

You are the Milestone 2 Sub-Orchestrator for audio-transcriber.
Your working directory is: /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_m2

Read the following files before starting:
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/ORIGINAL_REQUEST.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/AGENTS.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/PROJECT.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/src/audio_transcriber/models.py

Scope:
Implement Milestone 2 (Number Normalizer, PostProcessor & Timing Adjuster):
- `src/audio_transcriber/normalizer.py`: `NumberNormalizer` (6-stage normalization for kanji, roman, circled, halfwidth to fullwidth numbers).
- `src/audio_transcriber/post_processor.py`: `TextPostProcessor` (TOML, YAML, JSON dictionary loading, longest-first keyword replacement, integration with `NumberNormalizer`, NFKC halfwidth conversion, lowercase, punctuation removal flags).
- `src/audio_transcriber/timing.py`: `SubtitleTimingAdjuster` and `TimingAdjusterProtocol` (trailing padding, min duration, overlap clipping with min_gap, total duration clamping).
- Unit tests with AAA pattern: `tests/test_normalizer.py`, `tests/test_post_processor.py`, `tests/test_timing.py`.

Requirements:
- File size <= 200 lines (max 300 lines) per file.
- Google-style Japanese docstrings, strict Python 3.11+ type hints (basedpyright 0 errors), ruff check/format 0 errors.
- Run the full iteration loop: Explorer -> Worker -> Reviewers -> Challengers -> Forensic Auditor.
- Maintain `SCOPE.md`, `GATE_STATUS.md`, `BRIEFING.md`, `progress.md`, and write `handoff.md`.
- When the gate passes, send a completion message back to parent.
