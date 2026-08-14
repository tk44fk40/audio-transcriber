# Dispatch Assignment

## 2026-08-15T03:49:18+09:00

You are the Milestone 1 Sub-Orchestrator for audio-transcriber.
Your working directory is: /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_m1

Read the following files before starting:
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/ORIGINAL_REQUEST.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/AGENTS.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/PROJECT.md

Scope:
Implement Milestone 1 (Core Data Model, Sanitizer & Exporter):
- `src/audio_transcriber/models.py`: `SubtitleSegment` dataclass (`start`, `end`, `text`, `to_dict()`, `from_dict()`).
- `src/audio_transcriber/sanitizer.py`: `SegmentSanitizer` (hallucination detection, silence probability, speech rate anomaly, repetition reduction, loop repeat drop, word timestamp start adjustment).
- `src/audio_transcriber/exporter.py`: `SubtitleExporter` (DaVinci Resolve compatible SRT with `00:00:00,000` / UTF-8 / LF, WebVTT with `00:00:00.000` / LF, JSON, and `save_subtitles`).
- Unit tests with AAA pattern: `tests/test_models.py`, `tests/test_sanitizer.py`, `tests/test_exporter.py`.

Requirements:
- File size <= 200 lines (max 300 lines) per file.
- Google-style Japanese docstrings, strict Python 3.11+ type hints (basedpyright 0 errors), ruff check/format 0 errors.
- Run the full iteration loop: Explorer -> Worker -> Reviewers -> Challengers -> Forensic Auditor.
- Maintain `SCOPE.md`, `GATE_STATUS.md`, `BRIEFING.md`, `progress.md`, and write `handoff.md`.
- When the gate passes, send a completion message back to parent.
