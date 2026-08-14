# Scope: Milestone 2 (Number Normalizer, PostProcessor & Timing Adjuster)

## Architecture & Responsibilities
- `src/audio_transcriber/normalizer.py`:
  - `NumberNormalizer`: 6-stage normalization (kanji numerals, Roman numerals, circled numbers, fullwidth to halfwidth numbers, etc.)
- `src/audio_transcriber/post_processor.py`:
  - `TextPostProcessor`: Load replacement dictionary (TOML/YAML/JSON), longest-first keyword replacement, integration with `NumberNormalizer`, NFKC halfwidth conversion, lowercase, punctuation removal flags.
- `src/audio_transcriber/timing.py`:
  - `TimingAdjusterProtocol` and `SubtitleTimingAdjuster`: Trailing padding, min duration, overlap clipping with min_gap, total duration clamping.
- Unit Tests (AAA pattern):
  - `tests/test_normalizer.py`
  - `tests/test_post_processor.py`
  - `tests/test_timing.py`

## Interface Contracts
- See `PROJECT.md` and `src/audio_transcriber/models.py` for segment and config types (`TranscriptionSegment`, `TranscriptionConfig`, etc.).
- Normalizer: `NumberNormalizer.normalize(text: str) -> str`
- PostProcessor: `TextPostProcessor.process(text: str) -> str`, `process_segments(segments: list[TranscriptionSegment]) -> list[TranscriptionSegment]`
- TimingAdjuster: `SubtitleTimingAdjuster.adjust(segments: list[TranscriptionSegment], total_duration: float | None = None) -> list[TranscriptionSegment]`

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M2 | Milestone 2 Implementation | normalizer, post_processor, timing, unit tests | M1 | IN_PROGRESS |
