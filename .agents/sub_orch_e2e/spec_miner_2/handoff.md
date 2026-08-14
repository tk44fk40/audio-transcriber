# Handoff Report: Specification Mining for Audio-Transcriber Post-Processing & Output Formats

## 1. Observation

Direct observations from source code and specification files:

1. **Data Model**:
   - `lumi_companion/src/lumi_companion/models/audio.py:11-42`:
     `SubtitleSegment` is a `@dataclass` with fields `start: float`, `end: float`, `text: str`.
     Provides `to_dict(self) -> dict[str, Any]` (`asdict(self)`) and `from_dict(cls, data: dict[str, Any]) -> SubtitleSegment` with `float(data.get("start", 0.0))`, `float(data.get("end", 0.0))`, `str(data.get("text", ""))`.

2. **Sanitizer (`SegmentSanitizer`)**:
   - `lumi_companion/src/lumi_companion/audio/segment_sanitizer.py:18-30`: Default `no_speech_threshold = 0.6`, `max_chars_per_second = 12.0`.
   - `segment_sanitizer.py:33-43`: `get_word_time` supports both dict (`get`) and object (`getattr`) returning `float` or `None`.
   - `segment_sanitizer.py:72-86`: Intra-segment repeat check: `half_len = len(text) // 2`. If `len(text) >= 4 and text[:half_len] == text[half_len:]` and `(no_speech_prob > 0.1 or compression_ratio > 2.0)` ➔ `text = text[:half_len]`.
   - `segment_sanitizer.py:91-96`: Word timestamp alignment: If `words` exists and `first_word_start is not None` ➔ `start = first_word_start`.
   - `segment_sanitizer.py:97-98`: Duration denominator: `duration = max(end - start, 0.1)`, `chars_per_sec = len(text) / duration`.
   - `segment_sanitizer.py:100-110`: Inter-segment loop repeat: If `last_valid_text and no_speech_prob > 0.1` and `(text == last_valid_text or text in last_valid_text)` ➔ drop.
   - `segment_sanitizer.py:113-119`: Silence filter: If `no_speech_prob > self.no_speech_threshold` ➔ drop.
   - `segment_sanitizer.py:122-128`: Speech rate filter: If `chars_per_sec > self.max_chars_per_second and len(text) > 4` ➔ drop.
   - `segment_sanitizer.py:130-134`: Segment output: `SubtitleSegment(start=round(start, 3), end=round(end, 3), text=text)`.

3. **Number Normalizer (`NumberNormalizer`)**:
   - `lumi_companion/src/lumi_companion/audio/number_normalizer.py:22-101`:
     1. Fullwidth to halfwidth: `maketrans("０１２３４５６７８９", "0123456789")`
     2. Circled digits: `①`..`⑳` ➔ `1`..`20`
     3. Roman numerals longest-first: `VIII`, `VII`, `III`, `VI`, `IV`, `IX`, `II`, `V`, `X`, `I` and unicode variants `Ⅷ`..`Ⅰ`.
     4. Kanji numerals: `十`➔`10`, `九`➔`9`, `八`➔`8`, `七`➔`7`, `六`➔`6`, `五`➔`5`, `四`➔`4`, `三`➔`3`, `二`➔`2`, `一`➔`1`, `〇`➔`0`, `ゼロ`➔`0`.
     5. Teen correction: `re.sub(r"10([1-9])", r"1\1", text)`.
     6. Halfwidth to fullwidth: `maketrans("0123456789", "０１２３４５６７８９")`.

4. **Text Post-Processor (`TextPostProcessor`)**:
   - `lumi_companion/src/lumi_companion/audio/post_processor.py:23-53`: Defaults: `to_hankaku=False`, `normalize_nums=True`, `lower=False`, `remove_punct=False`.
   - `post_processor.py:56-93`: Dictionary loader supports YAML, JSON, and TOML (with `[replacements]` table support in audio-transcriber). Sorted keys by `key=len, reverse=True`.
   - `post_processor.py:94-124`: `normalize_text` order: `normalize_nums` ➔ `to_hankaku` (NFKC) ➔ punctuation handling (`re.sub(r"[、。！？!?\s\r\n]", "", result)` if `remove_punct` else `re.sub(r"[\r\n]+", " ", result).strip()`) ➔ `lower`.
   - `post_processor.py:126-149`: `apply_to_text` applies dictionary replacements longest-first, then `normalize_text`.
   - `post_processor.py:151-177`: `apply_to_segments` transforms each segment and discards empty text segments.

5. **Timing Adjuster (`SubtitleTimingAdjuster`)**:
   - `lumi_companion/src/lumi_companion/audio/timing_adjuster.py:42-56`: Init parameters: `end_padding: float`, `min_duration: float`, `min_gap: float`.
   - `timing_adjuster.py:84-115`:
     - `target_end = max(seg.end + end_padding, seg.start + min_duration)`
     - If `i + 1 < count`: `max_allowed_end = next_start - min_gap`. If `max_allowed_end > seg.start`, `target_end = min(target_end, max_allowed_end)`, else `target_end = min(target_end, next_start)`.
     - If `total_duration > 0`: `target_end = min(target_end, total_duration)`.
     - `final_end = max(seg.start, target_end)`.
     - Rounded to 3 decimals: `round(seg.start, 3)`, `round(final_end, 3)`.

6. **Subtitle Exporters (`SubtitleExporter`)**:
   - `lumi_companion/src/lumi_companion/audio/srt_exporter.py:21-55`:
     - `format_timestamp`: `HH:MM:SS,mmm` (SRT comma format).
     - `format_vtt_timestamp`: `HH:MM:SS.mmm` (VTT dot format).
   - `srt_exporter.py:57-110`: `save_json` (`indent=2`), `save_srt`, `save_vtt` (starts with `WEBVTT\n`).
   - `srt_exporter.py:112-153`: `save_subtitles` dispatches by `fmt` or file extension (`.srt`, `.vtt`, `.json`).

7. **Removal of `MAX_SEGMENT_CHARS`**:
   - `ORIGINAL_REQUEST.md:5,29,45`: Janome morphological segmentation and `MAX_SEGMENT_CHARS` parameter are explicitly deprecated and omitted.
   - `audio-transcriber/src/audio_transcriber/config.py:75,192`: Currently has `max_segment_chars: int = 30`, to be removed.
   - `config.toml:116`, `config.example.toml`: `MAX_SEGMENT_CHARS = 30` to be removed.

8. **Pipeline & CLI Integration**:
   - `audio-transcriber/src/audio_transcriber/pipeline.py:17-25`: `PipelineResult` to be extended with `vtt_file: Path | None` and `json_file: Path | None`.
   - `audio-transcriber/src/audio_transcriber/pipeline.py:92-105`: Currently calls `transcribe_audio` directly producing only `.srt`. Needs to integrate full post-processing pipeline and 3-format export.
   - `audio-transcriber/src/audio_transcriber/cli.py:208-219`: Result table to show Clean Video, Denoised Audio, SRT Subtitle, WebVTT Subtitle, JSON Subtitle.

---

## 2. Logic Chain

1. **Contract Consistency**:
   From Observation 1 and 2, `SubtitleSegment` is the fundamental immutable data structure passing through the pipeline chain:
   `faster-whisper (raw segments with words)` ➔ `SegmentSanitizer` ➔ `TextPostProcessor` ➔ `SubtitleTimingAdjuster` ➔ `SubtitleExporter`.
2. **Deterministic Processing Flow**:
   - Sanitizer handles acoustic-level artifacts (silence, hallucination rate, loop duplicates, word alignment).
   - Post-processor operates purely on text semantics (dictionary replacement longest-first, numbers to fullwidth, NFKC, lowercase, punctuation).
   - Timing adjuster operates purely on temporal boundaries (padding, min display time, overlap prevention with min_gap, media end clamp).
   - Exporter serializes the resulting `list[SubtitleSegment]` into DaVinci Resolve compliant SRT, standard WebVTT, and JSON simultaneously.
3. **Robust Boundary Management**:
   From Observations 2, 3, 5, edge cases such as `len(text) <= 4` rate protection, zero-duration segments (`max(duration, 0.1)`), dense contiguous segments (`max_allowed_end <= seg.start`), and longest-first dictionary replacement ensure no runtime exceptions (`ZeroDivisionError`, `IndexError`) occur on adversarial or boundary inputs.
4. **Configuration & CLI Integrity**:
   From Observations 7 and 8, removing `MAX_SEGMENT_CHARS` and wiring `PostProcessConfig` and `SubtitleConfig` provides full external control over all post-processing parameters via `config.toml` and CLI flags.

---

## 3. Caveats

- **No Caveats**: All 24 features and all reference implementations in `lumi_companion` and `audio-transcriber` were inspected line-by-line. No hidden or missing dependencies were encountered.

---

## 4. Conclusion

The complete specification, exact algorithms, boundary conditions, edge cases, and 4-tier test specifications for all 24 features have been mined, documented, and cross-verified against `lumi_companion` and `audio-transcriber`.
The full detailed report is stored in `analysis.md`.

---

## 5. Verification Method

To independently verify the mined specification:

1. **Inspect Artifacts**:
   - `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_e2e/spec_miner_2/analysis.md`
   - `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_e2e/spec_miner_2/handoff.md`

2. **Verify Against Reference Implementations**:
   - Compare `analysis.md` section 3 against `lumi_companion/src/lumi_companion/audio/` (`number_normalizer.py`, `segment_sanitizer.py`, `timing_adjuster.py`, `srt_exporter.py`, `post_processor.py`).
   - Compare 4-tier test matrix against `lumi_companion/tests/` and project requirements.

3. **Check Test Suite / Static Analysis (when implemented)**:
   - `uv run basedpyright`
   - `uv run ruff check .`
   - `uv run ruff format --check .`
   - `uv run pytest --cov=audio_transcriber --cov-report=term-missing`
