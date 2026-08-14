# Scope: Milestone 1 — Core Model, Sanitizer & Exporter

## Architecture & Responsibilities
- `src/audio_transcriber/models.py`:
  - `SubtitleSegment(start: float, end: float, text: str)` dataclass
  - `to_dict() -> dict[str, Any]`
  - `from_dict(data: dict[str, Any]) -> SubtitleSegment`
- `src/audio_transcriber/sanitizer.py`:
  - `SegmentSanitizer(no_speech_threshold: float = 0.6, max_chars_per_second: float = 12.0)`
  - `sanitize_segments(segments: Iterable[Any]) -> list[SubtitleSegment]`
  - Handles:
    1. no_speech_prob filtering (> threshold -> drop)
    2. compression_ratio / silence repetitive reduction (if repeat text at start/end and high compression ratio -> simplify)
    3. excessive speech rate filtering (> 12.0 chars/sec, len > 4 chars -> drop)
    4. loop repeat drop (identical text consecutively in silence)
    5. word timestamp alignment (adjust start time to first word timestamp if present)
- `src/audio_transcriber/exporter.py`:
  - `SubtitleExporter`:
    - `save_srt(segments: Sequence[SubtitleSegment], output_path: Path) -> None` (DaVinci Resolve compliant: `HH:MM:SS,mmm`, UTF-8, LF)
    - `save_vtt(segments: Sequence[SubtitleSegment], output_path: Path) -> None` (WebVTT compliant: `WEBVTT\n\n`, `HH:MM:SS.mmm`, UTF-8, LF)
    - `save_json(segments: Sequence[SubtitleSegment], output_path: Path) -> None` (JSON compliant: `indent=2`, UTF-8, LF)
    - `save_subtitles(segments: Sequence[SubtitleSegment], output_path: Path, fmt: str | None = None) -> None` (format inferred or specified)
- Unit Tests:
  - `tests/test_models.py`
  - `tests/test_sanitizer.py`
  - `tests/test_exporter.py`

## Reference Implementation
- Reference: `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/`
  - `segment_sanitizer.py`
  - `srt_exporter.py`

## Interface Contracts
- `models.py`: `SubtitleSegment(start: float, end: float, text: str)`
- `sanitizer.py`: `SegmentSanitizer(no_speech_threshold: float = 0.6, max_chars_per_second: float = 12.0)`
- `exporter.py`: `SubtitleExporter` methods `save_srt`, `save_vtt`, `save_json`, `save_subtitles`
