## 2026-08-15T03:52:14Z

You are the Worker for Milestone 1 of audio-transcriber.
Your working directory is: /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_m1/worker_1

Please read the following documents first:
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/ORIGINAL_REQUEST.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/AGENTS.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/PROJECT.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_m1/SCOPE.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_m1/explorer_1/analysis.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_m1/explorer_2/analysis.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_m1/explorer_3/analysis.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

File Write Ownership (You exclusively own these files):
- `src/audio_transcriber/models.py`
- `src/audio_transcriber/sanitizer.py`
- `src/audio_transcriber/exporter.py`
- `tests/test_models.py`
- `tests/test_sanitizer.py`
- `tests/test_exporter.py`

Tasks:
1. Implement `src/audio_transcriber/models.py`:
   - `@dataclass class SubtitleSegment`: fields `start: float`, `end: float`, `text: str`.
   - Method `to_dict() -> dict[str, Any]` (or asdict).
   - Class method `from_dict(cls, data: dict[str, Any]) -> SubtitleSegment` with type coercion (`float`, `str`) and safe defaults (`start=0.0`, `end=0.0`, `text=""`).
2. Implement `src/audio_transcriber/sanitizer.py`:
   - `class SegmentSanitizer`: `__init__(self, no_speech_threshold: float = 0.6, max_chars_per_second: float = 12.0) -> None`.
   - `get_word_time(word_obj: object, attr_name: str) -> float | None` (supports dict and object).
   - `sanitize_segments(self, segments: Iterable[object], total_duration: float = 0.0) -> list[SubtitleSegment]`:
     - Skips empty / whitespace-only text (`text.strip() == ""`).
     - Intra-segment repetition reduction: if `len(text) >= 4` and first half == second half, and (`no_speech_prob > 0.1` or `compression_ratio > 2.0`) -> shorten to `text[:half_len]`.
     - Word timestamp start alignment: if `words` available and first word has `start`, set `start = words[0].start`.
     - Inter-segment consecutive loop drop: if `last_valid_text` is set and `no_speech_prob > 0.1` and (`text == last_valid_text` or `text in last_valid_text`) -> drop.
     - Silence drop: if `no_speech_prob > no_speech_threshold` -> drop.
     - Speech rate anomaly drop: `duration = max(end - start, 0.1)`, `chars_per_sec = len(text) / duration`; if `chars_per_sec > max_chars_per_second` and `len(text) > 4` (protecting <= 4 chars) -> drop.
     - Construct `SubtitleSegment(start=round(start, 3), end=round(end, 3), text=text)`.
     - Log progress percentage if `total_duration > 0.0`.
3. Implement `src/audio_transcriber/exporter.py`:
   - Pure Python standard library implementation (no `import srt`).
   - `class SubtitleExporter`:
     - `@staticmethod format_timestamp(seconds: float) -> str` -> `HH:MM:SS,mmm` (comma separator).
     - `@staticmethod format_vtt_timestamp(seconds: float) -> str` -> `HH:MM:SS.mmm` (dot separator).
     - `@classmethod save_srt(cls, segments: Sequence[SubtitleSegment], output_path: Path) -> None` (DaVinci Resolve compatible: UTF-8, LF line endings, 1-indexed block numbers, `HH:MM:SS,mmm --> HH:MM:SS,mmm`, creates parent directories).
     - `@classmethod save_vtt(cls, segments: Sequence[SubtitleSegment], output_path: Path) -> None` (`WEBVTT\n\n` header, 1-indexed block numbers, `HH:MM:SS.mmm --> HH:MM:SS.mmm`, UTF-8, LF line endings, creates parent directories).
     - `@classmethod save_json(cls, segments: Sequence[SubtitleSegment], output_path: Path) -> None` (`indent=2`, `ensure_ascii=False`, UTF-8, LF line endings, creates parent directories).
     - `@classmethod save_subtitles(cls, segments: Sequence[SubtitleSegment], output_path: Path, fmt: str | None = None) -> None` (auto-detect format from extension `.srt`, `.vtt`, `.json` case-insensitively, or use explicit `fmt` case-insensitively; raises `ValueError` for unsupported format or extension).
4. Implement comprehensive unit tests (AAA pattern, Google-style Japanese docstrings):
   - `tests/test_models.py`
   - `tests/test_sanitizer.py`
   - `tests/test_exporter.py`
5. Verification:
   - Run `uv run pytest tests/test_models.py tests/test_sanitizer.py tests/test_exporter.py --cov=audio_transcriber --cov-report=term-missing` (must pass with 100% coverage on new modules).
   - Run `uv run pytest` (all project tests must pass).
   - Run `uv run basedpyright` (must have 0 errors).
   - Run `uv run ruff check .` and `uv run ruff format --check .` (must have 0 errors).
   - Ensure each file is <= 200 lines (max 300 lines).
