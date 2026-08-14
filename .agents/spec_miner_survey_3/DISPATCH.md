## 2026-08-15T03:46:04Z

Extract and compile complete, unambiguous specifications and requirements for the post-processing porting:
1. Exact data model definition for `SubtitleSegment` (fields: start, end, text, words, confidence, etc., and methods like `to_dict()`).
2. Exact requirements for text sanitization (hallucination filters, silence probability, repetition reduction).
3. Exact requirements for number normalization and dictionary replacement (TOML/YAML/JSON dictionary support, case-insensitive config).
4. Exact timing adjustment rules (trailing padding, min duration, overlap prevention).
5. Exact export format specifications (SRT: 00:00:00,000, UTF-8, LF; WebVTT: WEBVTT header, 00:00:00.000, LF; JSON: structured format).
6. Exact CLI and Config parameter changes (removal of MAX_SEGMENT_CHARS, new options for post-processing).
7. Pipeline integration and `PipelineResult` signature (`vtt_file: Path | None`, `json_file: Path | None`).
8. Quality and verification criteria (basedpyright 0 errors, ruff check/format, AAA pytest, max 300 lines / file).

Write your detailed specification document to `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/spec_miner_survey_3/survey_report.md` and write a handoff report to `handoff.md`.
