# Comprehensive Specification & Test Mining Report: Audio-Transcriber Post-Processing & Output Formats

## 1. Executive Summary

This specification document establishes the definitive contract, algorithmic requirements, input/output behaviors, boundary conditions, edge cases, and 4-tier test specifications for the post-processing and multi-format subtitle export extension of `audio-transcriber`.

All requirements are mined directly from:
1. Reference implementation in `lumi_companion` (`src/lumi_companion/audio/`, `models/audio.py`, and test suites).
2. Project specification in `PROJECT.md` and user requirements in `ORIGINAL_REQUEST.md`.
3. Existing `audio-transcriber` codebase (`config.py`, `pipeline.py`, `transcribe.py`, `cli.py`, `media.py`, `denoise.py`).

Janome morphological segmentation and the `MAX_SEGMENT_CHARS` parameter are explicitly deprecated and omitted per architectural decision.

---

## 2. Features Discovered (24 Features)

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Data Model | `SubtitleSegment` Data Model | Type-safe dataclass for timestamped subtitle segment with serialization methods. | `start: float`, `end: float`, `text: str` | `SubtitleSegment` instance | In `from_dict`: falls back to `0.0` for missing/invalid start/end, `""` for text. | `models/audio.py`, `PROJECT.md` |
| 2 | Sanitizer | Hallucination / Silence Filter | Filters out hallucinated segments generated over silence where `no_speech_prob > no_speech_threshold`. | `segments: Iterable[Any]`, `no_speech_threshold: float = 0.6` | `list[SubtitleSegment]` | Skips dropped segments, logs at DEBUG. | `segment_sanitizer.py:113` |
| 3 | Sanitizer | Excessive Speech Rate Filter | Drops segments exceeding physical human speech limits (`chars_per_sec > max_chars_per_second` and `len(text) > 4`). | `max_chars_per_second: float = 12.0` | `list[SubtitleSegment]` | Skips dropped segments, logs at DEBUG. Short text (`len <= 4`) is protected. | `segment_sanitizer.py:122` |
| 4 | Sanitizer | Intra-Segment Repetition Reduction | Detects exact 2-half repeats (`text[:half] == text[half:]`, `len >= 4`) under high silence/compression (`no_speech_prob > 0.1 or comp_ratio > 2.0`) and truncates to first half. | Segment with `text`, `no_speech_prob`, `compression_ratio` | Truncated `text` in `SubtitleSegment` | Keeps original text if acoustic confidence is high. | `segment_sanitizer.py:72` |
| 5 | Sanitizer | Inter-Segment Loop Repeat Drop | Drops subsequent segments that are identical to or substrings of `last_valid_text` when `no_speech_prob > 0.1`. | Consecutive segments in silence | Filtered segment stream | Keeps repeated text if `no_speech_prob <= 0.1` (intentional natural repetition). | `segment_sanitizer.py:101` |
| 6 | Sanitizer | Word Timestamp Alignment | Aligns segment `start` timestamp to `words[0].start` when word-level timestamps are provided by Whisper. | Segment with `words` list | `SubtitleSegment` with adjusted `start` | Falls back to segment `start` if `words` is empty or missing `start` attribute. | `segment_sanitizer.py:92` |
| 7 | Exporter | DaVinci Resolve SRT Exporter | Exports subtitles to `.srt` format using `HH:MM:SS,mmm` timestamp, 1-based indexing, UTF-8, LF. | `Sequence[SubtitleSegment]`, `output_path: Path` | `.srt` file on disk | Creates parent directories automatically. | `srt_exporter.py:70`, `PROJECT.md` |
| 8 | Exporter | WebVTT Subtitle Exporter | Exports subtitles to `.vtt` format starting with `WEBVTT\n`, `HH:MM:SS.mmm` timestamp, UTF-8, LF. | `Sequence[SubtitleSegment]`, `output_path: Path` | `.vtt` file on disk | Creates parent directories automatically. | `srt_exporter.py:94`, `PROJECT.md` |
| 9 | Exporter | JSON Subtitle Exporter & Dispatcher | Exports subtitles to JSON (`indent=2`, UTF-8, LF) and provides format auto-detection by extension. | `Sequence[SubtitleSegment]`, `output_path: Path`, `fmt: str | None` | `.json` / `.srt` / `.vtt` file | Raises `ValueError` for unknown extensions/formats. | `srt_exporter.py:57,112` |
| 10 | Normalizer | 6-Stage Number Normalizer | Normalizes kanji numerals, Roman numerals, circled numbers, and fullwidth/halfwidth digits to uniform fullwidth Japanese numerals. | `text: str` | `str` (normalized text) | Returns input string unmodified if no numbers present. | `number_normalizer.py:9` |
| 11 | PostProcessor | Multi-Format Dictionary Loader | Loads custom term replacement dictionaries from TOML (including `[replacements]` table), YAML, and JSON. | `file_path: Path` | `dict[str, str]` | Raises `FileNotFoundError` if missing, `ValueError` if content is not a dict. | `post_processor.py:56`, `custom_dictionary.toml` |
| 12 | PostProcessor | Longest-First Term Replacement | Replaces dictionary keywords in text ordered by descending string length (`len(key)`) to prevent substring collisions. | `text: str`, loaded dictionary | Replaced `str` | Replaces in-place without altering unmatched terms. | `post_processor.py:51,139` |
| 13 | PostProcessor | Text Normalization Pipeline | Applies configurable Unicode NFKC, number normalization, lowercasing, and punctuation stripping. | `text: str`, flags (`normalize_nums`, `to_hankaku`, `lower`, `remove_punct`) | Normalized `str` | Handles empty string, multiline collapse to single space when `remove_punct=False`. | `post_processor.py:94` |
| 14 | Timing | Trailing Padding Adjustment | Extends segment end timestamp by `end_padding` (default +1.0s) for natural reading cadence. | `segments: list[SubtitleSegment]`, `end_padding: float` | `list[SubtitleSegment]` with extended `end` | Handled gracefully for single or multiple segments. | `timing_adjuster.py:86` |
| 15 | Timing | Minimum Display Duration | Enforces `end >= start + min_duration` (default 1.5s) so short utterances remain readable. | `segments: list[SubtitleSegment]`, `min_duration: float` | `list[SubtitleSegment]` with minimum duration | Applied before next-segment clipping. | `timing_adjuster.py:87` |
| 16 | Timing | Next-Segment Overlap Clipping | Clips segment `end` to `next_start - min_gap` (default 0.05s) to prevent subtitle overlaps. | `segments: list[SubtitleSegment]`, `min_gap: float` | `list[SubtitleSegment]` with non-overlapping bounds | Ensures `end >= start` even when `next_start - start < min_gap`. | `timing_adjuster.py:91` |
| 17 | Timing | Total Duration Clamping | Clamps segment `end` to `total_duration` when media playback duration is supplied. | `total_duration: float | None` | `list[SubtitleSegment]` within media boundary | Ignored if `total_duration` is None or `<= 0`. | `timing_adjuster.py:103` |
| 18 | Config | `MAX_SEGMENT_CHARS` Removal | Complete deprecation and removal of `max_segment_chars` / `MAX_SEGMENT_CHARS` from all configs and models. | TOML config or dict | `AppConfig` without `max_segment_chars` | Clean removal without breaking legacy optional keys. | `ORIGINAL_REQUEST.md`, `config.py` |
| 19 | Config | Post-Processing Configuration | Dataclasses (`PostProcessConfig`, `SubtitleConfig`) and TOML loading for all post-processing settings. | TOML config / dictionary | Typed `AppConfig` instance | Case-insensitive TOML keys, sensible defaults for omitted keys. | `config.py`, `PROJECT.md` |
| 20 | Pipeline | 3-Format Simultaneous Export | Generates `.srt`, `.vtt`, and `.json` files in the output directory during pipeline execution. | `run_pipeline(..., transcribe=True)` | Writes 3 subtitle files to disk | Creates output directory if missing. | `pipeline.py`, `PROJECT.md` |
| 21 | Pipeline | `PipelineResult` Extension | Extends `PipelineResult` dataclass with `vtt_file: Path | None` and `json_file: Path | None`. | Pipeline execution return | `PipelineResult` instance | Fields are None if `transcribe=False`. | `pipeline.py`, `PROJECT.md` |
| 22 | Pipeline | Post-Processing Pipeline Integration | Integrates `SegmentSanitizer` ➔ `TextPostProcessor` ➔ `SubtitleTimingAdjuster` ➔ `SubtitleExporter` in `run_pipeline`. | Media input path, config parameters | Processed media and 3 subtitle files | Robust end-to-end execution with full error propagation. | `pipeline.py`, `PROJECT.md` |
| 23 | CLI | Post-Processing CLI Options & Output Table | Exposes CLI flags for post-processing and updates the Rich summary table to list SRT, VTT, and JSON. | CLI arguments / options | Terminal output & exit code | Exits with code 1 on invalid arguments or pipeline crash. | `cli.py`, `PROJECT.md` |
| 24 | Acceptance | Static Typing & E2E Acceptance | Full compliance with `basedpyright` (0 errors), `ruff` (0 errors), and 100% pytest pass rate across 4 tiers. | Entire codebase & test suite | Validation report & green test run | Zero tolerance for type errors or test regressions. | `PROJECT.md`, `AGENTS.md` |

---

## 3. Detailed Component Specifications & Algorithms

### 3.1 Data Model: `SubtitleSegment` (`models.py`)
```python
@dataclass
class SubtitleSegment:
    start: float
    end: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubtitleSegment:
        return cls(
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            text=str(data.get("text", "")),
        )
```

### 3.2 `SegmentSanitizer` (`sanitizer.py`)
- **Constructor**: `SegmentSanitizer(no_speech_threshold: float = 0.6, max_chars_per_second: float = 12.0)`
- **`get_word_time(word_obj: object, attr_name: str) -> float | None`**:
  - Checks if `isinstance(word_obj, dict)` ➔ `word_obj.get(attr_name)`
  - Else `getattr(word_obj, attr_name, None)`
  - Returns `float(val)` if `isinstance(val, int | float)`, else `None`.
- **Filtering Rules in `sanitize_segments(segments, total_duration=0.0)`**:
  1. `text = getattr(segment, "text", "").strip()`. If `not text`: skip segment.
  2. Extract `no_speech_prob = getattr(segment, "no_speech_prob", 0.0)` and `compression_ratio = getattr(segment, "compression_ratio", 0.0)`.
  3. **Intra-segment 2-half Repeat**:
     - `half_len = len(text) // 2`
     - If `len(text) >= 4 and text[:half_len] == text[half_len:]`:
       - If `no_speech_prob > 0.1 or compression_ratio > 2.0`:
         - `text = text[:half_len]`
  4. **Word Timestamp Alignment**:
     - `start = getattr(segment, "start", 0.0)`, `end = getattr(segment, "end", 0.0)`
     - If `words := getattr(segment, "words", None)`:
       - `first_start = get_word_time(words[0], "start")`
       - If `first_start is not None`: `start = first_start`
  5. `duration = max(end - start, 0.1)`
  6. `chars_per_sec = len(text) / duration`
  7. **Inter-segment Loop Repeat**:
     - If `last_valid_text and no_speech_prob > 0.1`:
       - If `text == last_valid_text or text in last_valid_text`:
         - Drop segment (continue).
  8. **No Speech Hallucination**:
     - If `no_speech_prob > self.no_speech_threshold`:
       - Drop segment (continue).
  9. **Excessive Speech Rate**:
     - If `chars_per_sec > self.max_chars_per_second and len(text) > 4`:
       - Drop segment (continue).
  10. Construct `SubtitleSegment(start=round(start, 3), end=round(end, 3), text=text)`.
  11. `last_valid_text = text` and record progress log.

### 3.3 `NumberNormalizer` (`normalizer.py`)
- **Algorithm**:
  1. `text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))`
  2. Circled digits `①`..`⑳` ➔ `1`..`20` (ordered 1 to 20 replace)
  3. Roman numerals longest-first:
     `[("VIII", "8"), ("VII", "7"), ("III", "3"), ("VI", "6"), ("IV", "4"), ("IX", "9"), ("II", "2"), ("V", "5"), ("X", "10"), ("I", "1"), ("Ⅷ", "8"), ("Ⅶ", "7"), ("Ⅲ", "3"), ("Ⅵ", "6"), ("Ⅳ", "4"), ("Ⅸ", "9"), ("Ⅱ", "2"), ("Ⅴ", "5"), ("Ⅹ", "10"), ("Ⅰ", "1")]`
  4. Kanji numerals:
     `[("十", "10"), ("九", "9"), ("八", "8"), ("七", "7"), ("六", "6"), ("五", "5"), ("四", "4"), ("三", "3"), ("二", "2"), ("一", "1"), ("〇", "0"), ("ゼロ", "0")]`
  5. Regex teen correction:
     `text = re.sub(r"10([1-9])", r"1\1", text)`
  6. Convert to Zenkaku:
     `text = text.translate(str.maketrans("0123456789", "０１２３４５６７８９"))`

### 3.4 `TextPostProcessor` (`post_processor.py`)
- **Dictionary Loading**:
  - Checks `.toml` ➔ `tomllib.loads(content)`. If dict has key `"replacements"` and `isinstance(data["replacements"], dict)`, extracts `data["replacements"]`.
  - Checks `.yaml` / `.yml` ➔ `yaml.safe_load(content)`
  - Checks `.json` ➔ `json.loads(content)`
  - Fallback ➔ `yaml.safe_load(content)`
  - Ensures all keys/values are strings: `dict[str, str]`
- **`normalize_text(text: str) -> str`**:
  1. If `self.normalize_nums`: `result = NumberNormalizer.normalize(result)`
  2. If `self.to_hankaku`: `result = unicodedata.normalize("NFKC", result)`
  3. If `self.remove_punct`: `result = re.sub(r"[、。！？!?\s\r\n]", "", result)`
     Else: `result = re.sub(r"[\r\n]+", " ", result).strip()`
  4. If `self.lower`: `result = result.lower()`
- **`apply_to_text(text: str) -> str`**:
  1. If `dictionary`: replace keys in descending length order (`_sorted_keys`).
  2. Apply `normalize_text(result)`.
- **`apply_to_segments(segments: list[SubtitleSegment]) -> list[SubtitleSegment]`**:
  - Applies `apply_to_text` to each segment. Drops empty resulting segments.

### 3.5 `SubtitleTimingAdjuster` (`timing.py`)
- **Algorithm in `adjust_segments(segments, total_duration=None)`**:
  - If `not segments`: return `[]`
  - For index `i`, `seg` in enumerate(segments):
    1. `padded_end = seg.end + self.end_padding`
    2. `min_required_end = seg.start + self.min_duration`
    3. `target_end = max(padded_end, min_required_end)`
    4. Next segment gap prevention:
       If `i + 1 < len(segments)`:
         `next_start = segments[i + 1].start`
         `max_allowed_end = next_start - self.min_gap`
         If `max_allowed_end > seg.start`:
           `target_end = min(target_end, max_allowed_end)`
         Else:
           `target_end = min(target_end, next_start)`
    5. Total duration clamping:
       If `total_duration is not None and total_duration > 0`:
         `target_end = min(target_end, total_duration)`
    6. Safety lower bound:
       `final_end = max(seg.start, target_end)`
    7. Append `SubtitleSegment(start=round(seg.start, 3), end=round(final_end, 3), text=seg.text)`

### 3.6 `SubtitleExporter` (`exporter.py`)
- **Timestamp Formatting**:
  - SRT: `format_timestamp(seconds)` ➔ `HH:MM:SS,mmm` (e.g. `01:01:01,500`)
  - VTT: `format_vtt_timestamp(seconds)` ➔ `HH:MM:SS.mmm` (e.g. `01:01:01.500`)
- **Output Methods**:
  - `save_srt(segments, output_path: Path)`: 1-indexed, UTF-8, LF, `srt.compose` format.
  - `save_vtt(segments, output_path: Path)`: Starts with `WEBVTT\n`, 1-indexed, `00:00:00.000 --> 00:00:00.000`, UTF-8, LF.
  - `save_json(segments, output_path: Path)`: `json.dump([s.to_dict() for s in segments], f, ensure_ascii=False, indent=2)`.
  - `save_subtitles(segments, output_path: Path, fmt: str | None = None)`: Auto-detects extension or uses `fmt.lower()`. Raises `ValueError` on invalid format.

---

## 4. Edge Cases & Boundary Conditions Matrix

| # | Feature | Input Condition | Expected / Observed Behavior |
|---|---------|-----------------|------------------------------|
| E01 | `SubtitleSegment` | `data = {}` (empty dict to `from_dict`) | Yields `SubtitleSegment(start=0.0, end=0.0, text="")`. |
| E02 | `SubtitleSegment` | `data = {"start": "12.34", "end": 50, "text": 12345}` | Automatically converts strings/ints to float and string: `start=12.34`, `end=50.0`, `text="12345"`. |
| E03 | `SegmentSanitizer` | `no_speech_prob == no_speech_threshold` (e.g. 0.6 == 0.6) | Segment is KEPT (condition is strictly `>`). |
| E04 | `SegmentSanitizer` | `chars_per_sec == 12.0` (exact max threshold) | Segment is KEPT (condition is strictly `>`). |
| E05 | `SegmentSanitizer` | `len(text) == 4` and `chars_per_sec = 40.0` (0.1s duration) | Segment is KEPT because short text (`len <= 4`) is protected. |
| E06 | `SegmentSanitizer` | `len(text) == 5` and `chars_per_sec = 12.1` | Segment is DROPPED because `len > 4` and exceeds 12.0 c/s. |
| E07 | `SegmentSanitizer` | Intra-segment repeat with odd length (e.g. `"あいうあい"`, len=5) | `len//2 = 2` ➔ `"あい"` != `"うあい"` ➔ Not reduced. |
| E08 | `SegmentSanitizer` | Intra-segment repeat with `len < 4` (e.g. `"ああ"`, len=2) | Not reduced because `len >= 4` requirement fails. |
| E09 | `SegmentSanitizer` | Intra-segment repeat with confident speech (`no_speech_prob=0.05`, `comp_ratio=1.2`) | Not reduced (preserves intentional natural repeats like `"はいはい"` or `"そうそう"`). |
| E10 | `SegmentSanitizer` | Segment text is empty `""` or whitespace `"   \n\t"` | Immediately skipped, does not create empty `SubtitleSegment`. |
| E11 | `SegmentSanitizer` | `words` list with dicts vs SimpleNamespace vs missing `start` | Safely extracts `start` if present and numeric; falls back to segment `start` if missing/invalid. |
| E12 | `SegmentSanitizer` | `end == start` (0.0s duration) | `max(end - start, 0.1)` enforces 0.1s denominator, preventing `ZeroDivisionError`. |
| E13 | `NumberNormalizer` | `"第I章"` (Roman numeral I) vs `"第i章"` | `"第I章"` ➔ `"第１章"`; lowercase `"第i章"` is untouched by normalizer unless `lower` flag in post-processor. |
| E14 | `NumberNormalizer` | Roman `"VIII"` | Longest-first matches `"VIII"` ➔ `"8"` ➔ `"８"` (not clobbered by `"V"` or `"I"`). |
| E15 | `NumberNormalizer` | Kanji `"十一"` | `"十1"` ➔ regex `101` ➔ `"11"` ➔ `"１１"`. |
| E16 | `NumberNormalizer` | Kanji `"二十"` | `"210"` ➔ `"２１０"`. |
| E17 | `NumberNormalizer` | Circled number `"㉑"` (21, outside 1-20 map) | Left unchanged by `maru_map` (supports ① through ⑳). |
| E18 | `TextPostProcessor` | Dictionary with overlapping keys `{"AI": "人工知能", "AIツール": "AI支援ツール"}` | Sorted descending by length ➔ `"AIツール"` replaced before `"AI"`. |
| E19 | `TextPostProcessor` | TOML dictionary with `[replacements]` table vs flat TOML | Both formats loaded seamlessly into `dict[str, str]`. |
| E20 | `TextPostProcessor` | Non-existent dictionary file path | Raises `FileNotFoundError`. |
| E21 | `TextPostProcessor` | Invalid dictionary file (e.g. JSON array `[1, 2, 3]`) | Raises `ValueError`. |
| E22 | `TextPostProcessor` | Multiline text when `remove_punct=False` | `\r\n` replaced by single space and `.strip()`. |
| E23 | `TextPostProcessor` | Text when `remove_punct=True` | Strips `、。！？!?\s\r\n` completely. |
| E24 | `SubtitleTimingAdjuster` | Single segment | `padded_end = end + end_padding`, `min_duration` checked, clamped to `total_duration`. |
| E25 | `SubtitleTimingAdjuster` | Two contiguous segments with gap < `min_gap` (e.g. `0.01s`) | `max_allowed_end <= seg.start` ➔ clips to `next_start` to prevent backwards jump. |
| E26 | `SubtitleTimingAdjuster` | Empty segment list `[]` | Returns `[]` without error. |
| E27 | `SubtitleTimingAdjuster` | `total_duration` is smaller than segment start | `final_end = max(seg.start, total_duration)` ensures `end >= start`. |
| E28 | `SubtitleExporter` | Timestamp over 24 hours (`seconds = 90000.0`) | Formats correctly to `25:00:00,000` (SRT) and `25:00:00.000` (VTT). |
| E29 | `SubtitleExporter` | `save_subtitles` with uppercase format `fmt="SRT"` / `.VTT` | Case-insensitively routes to appropriate save method. |
| E30 | `SubtitleExporter` | `save_subtitles` with unsupported extension `.docx` | Raises `ValueError("未対応の拡張子です...")`. |
| E31 | `Config` | Deprecated `MAX_SEGMENT_CHARS` in old TOML | Ignored during parse without crashing; not present on `AppConfig` or `PostProcessConfig`. |
| E32 | `Pipeline` | Video input with `remux=True`, `denoise=True`, `transcribe=True` | Generates `{stem}_clean.wav`, `{stem}_clean.{ext}`, `{stem}.srt`, `{stem}.vtt`, `{stem}.json`. |
| E33 | `CLI` | Mutual exclusion: `--denoise-only` AND `--transcribe-only` | Exits with error message and exit code 1. |

---

## 5. Four-Tier Test Specification Matrix

### Tier 1: Feature Coverage (Unit & Component Test Specifications)
*Objective: Verify every individual feature in isolation with standard valid inputs.*

1. **`test_models_subtitle_segment_init_and_asdict`**:
   - Verify `SubtitleSegment(1.5, 3.0, "テスト")` attributes.
   - Verify `to_dict()` produces `{"start": 1.5, "end": 3.0, "text": "テスト"}`.
   - Verify `from_dict()` reconstructs identical object.
2. **`test_sanitizer_drops_no_speech_above_threshold`**:
   - Input segments with `no_speech_prob = 0.7` (threshold 0.6). Verify dropped.
3. **`test_sanitizer_drops_excessive_speech_rate`**:
   - 0.2s duration, 10 characters (50 chars/sec). Verify dropped.
4. **`test_sanitizer_reduces_intra_segment_2half_repeat`**:
   - Input `"あいうえおあいうえお"` with `no_speech_prob=0.2`. Verify becomes `"あいうえお"`.
5. **`test_sanitizer_drops_inter_segment_loop_repeat`**:
   - Consecutive segments `"ご視聴ありがとうございました。"` with `no_speech_prob=0.15`. Verify second is dropped.
6. **`test_sanitizer_aligns_word_timestamp`**:
   - Segment with `start=1.0`, `words=[{"start": 1.45, "end": 1.8}]`. Verify segment start becomes `1.45`.
7. **`test_exporter_save_srt_format`**:
   - Verify index, `HH:MM:SS,mmm --> HH:MM:SS,mmm`, UTF-8, LF, and content.
8. **`test_exporter_save_vtt_format`**:
   - Verify `WEBVTT\n\n` header, `HH:MM:SS.mmm --> HH:MM:SS.mmm`, UTF-8, LF.
9. **`test_exporter_save_json_format`**:
   - Verify `json.dump` with `indent=2`, UTF-8, list of dicts.
10. **`test_normalizer_6_stages`**:
    - Verify kanji, roman, circled, fullwidth conversions in one combined phrase: `"第I章 十個のりんご ①番 １２３"`.
11. **`test_post_processor_load_dictionary_toml_yaml_json`**:
    - Test loading dictionary from `.toml` (both `[replacements]` and flat), `.yaml`, `.json`.
12. **`test_post_processor_longest_first_replacement`**:
    - Dictionary `{"ABC": "123", "AB": "99"}` on `"ABC and AB"`. Verify `"123 and 99"`.
13. **`test_post_processor_normalization_flags`**:
    - Test combinations of `to_hankaku`, `normalize_nums`, `lower`, `remove_punct`.
14. **`test_timing_adjuster_trailing_padding`**:
    - `start=1.0, end=3.0, end_padding=1.0` ➔ `end=4.0`.
15. **`test_timing_adjuster_min_duration`**:
    - `start=1.0, end=1.2, min_duration=1.5` ➔ `end=2.5`.
16. **`test_timing_adjuster_overlap_clipping_with_min_gap`**:
    - `seg1=(1.0, 3.0)`, `seg2=(3.5, 5.0)`, `padding=1.0`, `min_gap=0.05` ➔ `seg1.end = 3.45`.
17. **`test_timing_adjuster_total_duration_clamping`**:
    - `seg=(8.0, 9.5)`, `padding=1.0`, `total_duration=10.0` ➔ `seg.end = 10.0`.
18. **`test_config_max_segment_chars_removed`**:
    - Verify `AppConfig`, `PostProcessConfig` have no `max_segment_chars` attribute.
19. **`test_config_post_process_and_subtitle_sections`**:
    - Verify TOML loading of `[post_process]` and `[subtitle]` with mixed-case and uppercase keys.
20. **`test_pipeline_generates_3_formats`**:
    - Mocked `run_pipeline(..., transcribe=True)` verifies creation of `.srt`, `.vtt`, `.json`.
21. **`test_pipeline_result_dataclass_fields`**:
    - Verify `PipelineResult` contains `vtt_file` and `json_file`.
22. **`test_pipeline_post_processing_integration`**:
    - Verify pipeline invokes sanitizer ➔ post_processor ➔ timing_adjuster ➔ exporter.
23. **`test_cli_post_process_flags_and_table`**:
    - Verify Typer CLI accepts `--custom-dict`, `--end-padding`, `--min-duration`, `--min-gap`, etc., and prints 3 formats in table.
24. **`test_quality_static_analysis_pass`**:
    - Run `basedpyright`, `ruff check`, `ruff format --check`.

---

### Tier 2: Boundary & Corner Case Test Specifications
*Objective: Stress limits, boundary values, empty inputs, malformed types, and edge conditions.*

1. **`test_models_from_dict_boundary_cases`**:
   - Missing fields, non-numeric strings, negative timestamps, Unicode emoji text.
2. **`test_sanitizer_exact_threshold_boundaries`**:
   - `no_speech_prob == 0.6000000000000000` (kept).
   - `no_speech_prob == 0.6000000000000001` (dropped).
   - `chars_per_sec == 12.0` (kept).
   - `chars_per_sec == 12.00001` with `len(text) == 5` (dropped).
   - `len(text) == 4` with `chars_per_sec == 100.0` (protected, kept).
3. **`test_sanitizer_intra_repeat_corner_cases`**:
   - Odd string length (`"あいうえお"`, len=5) -> no split.
   - Very short string (`"ああ"`, len=2) -> no reduction.
   - Repetition with high confidence (`no_speech_prob=0.01`, `comp_ratio=1.0`) -> kept intact.
4. **`test_sanitizer_inter_repeat_substring_matching`**:
   - Previous: `"こんにちは世界"`, Current: `"世界"` with `no_speech_prob=0.15` (dropped).
   - Previous: `"こんにちは世界"`, Current: `"世界"` with `no_speech_prob=0.05` (kept).
5. **`test_sanitizer_zero_duration_segment`**:
   - `start == 1.0, end == 1.0` -> `duration = max(0.0, 0.1) = 0.1` -> handles division safely.
6. **`test_number_normalizer_boundary_expressions`**:
   - Roman numerals: `"VIII"`, `"VII"`, `"III"`, `"IV"`, `"IX"`, `"X"`, `"I"`, Unicode `"Ⅷ"`, `"Ⅳ"`.
   - Kanji combinations: `"十一"`, `"十九"`, `"二十"`, `"〇"`, `"ゼロ"`, mixed `"第I章 １０連休"`.
   - Text with no numbers -> unchanged.
   - Text with only numbers -> fully normalized.
7. **`test_post_processor_dictionary_loader_errors`**:
   - Non-existent file -> `FileNotFoundError`.
   - Non-dict content (list or string) -> `ValueError`.
   - TOML with `[replacements]` vs flat TOML.
8. **`test_post_processor_whitespace_and_newlines`**:
   - `remove_punct=False`: `"\r\n\r\n"` collapsed to single space, `.strip()` applied.
   - `remove_punct=True`: `、。！？!?\s\r\n` completely removed.
9. **`test_timing_adjuster_inverted_and_dense_segments`**:
   - Segment gap `< min_gap` (e.g. `0.01s`). Ensure `start <= end <= next_start`.
   - `total_duration` clamp when `total_duration < start + min_duration`.
   - Empty segment list `[]`.
10. **`test_exporter_boundary_timestamps`**:
    - `seconds = 0.0` ➔ `00:00:00,000` (SRT) and `00:00:00.000` (VTT).
    - `seconds = 86399.999` ➔ `23:59:59,999`.
    - `seconds = 360000.0` (100 hours) ➔ `100:00:00,000`.
11. **`test_exporter_save_subtitles_dispatch`**:
    - Uppercase extensions (`.SRT`, `.VTT`, `.JSON`).
    - Explicit `fmt="srt"`, `fmt="VTT"`, `fmt="JSON"`.
    - Invalid format / extension ➔ `ValueError`.

---

### Tier 3: Cross-Feature Interaction Test Specifications
*Objective: Verify interactions across multiple components and subsystem boundaries.*

1. **`test_sanitizer_to_postprocessor_to_timing_flow`**:
   - Raw Whisper output with hallucinations, word timestamps, Roman numbers, and tight gaps.
   - Verify:
     1. Sanitizer drops hallucinations and aligns `start` to word timestamp.
     2. Post-processor normalizes Roman numerals and custom dictionary keywords.
     3. Timing adjuster adds end padding and clips overlapping segments.
     4. Exporter writes valid SRT, VTT, and JSON with identical adjusted data.
2. **`test_dictionary_replacement_expansion_with_timing_adjustment`**:
   - Custom dictionary replaces short keyword with long phrase (e.g. `"S"` ➔ `"萌えスイッチ"`).
   - Verify post-processor expands text without affecting timestamps, and timing adjuster maintains proper spacing.
3. **`test_word_timestamp_alignment_with_min_gap_timing`**:
   - Word timestamp moves `seg1.start` forward, creating gap that allows `seg0` padding to extend further without clipping.
4. **`test_pipeline_denoise_transcribe_export_all_formats`**:
   - End-to-end mocked pipeline execution checking that audio denoising feeds into transcription, which feeds into 3-format exporter and video remuxing.
5. **`test_cli_config_precedence_and_overrides`**:
   - Config file sets `SUBTITLE_END_PADDING = 0.5`, CLI provides `--end-padding 1.2`. Verify 1.2 takes precedence in pipeline call.

---

### Tier 4: Real-World Workload Scenario Test Specifications
*Objective: Validate end-to-end behavior against complex, representative real-world use cases.*

1. **Scenario 1: Game Stream Commentary with Rapid Callouts & Sound Effects**
   - Workload: 60-second transcript containing:
     - Rapid repetitions: `"はいはいはいはい"` (dropped if hallucinated over noise, kept if natural speech).
     - Game jargon from `custom_dictionary.toml`: `"大田使用量"` ➔ `"クォータ使用量"`, `"Sスイッチ"` ➔ `"萌えスイッチ"`, `"カル"` ➔ `"狩る。"`.
     - Fast commentary with short utterances (`"ナイス"`, `"よし"`).
   - Assertions:
     - Accurate terminology replacement.
     - Short utterances preserved with `min_duration >= 1.5s`.
     - Valid SRT, VTT, JSON outputs matching DaVinci Resolve import standards.
2. **Scenario 2: Technical Presentation / Academic Lecture**
   - Workload: 120-second transcript containing:
     - Roman numerals: `"第I章"`, `"第IV節"`, `"VII"`.
     - Kanji numbers: `"十二"`, `"三十"`, `"百"`.
     - Mixed English acronyms: `"DeepFilterNet"`, `"Whisper"`, `"OBS"`.
     - Long sentences spanning natural pauses.
   - Assertions:
     - Complete number normalization to Zenkaku Japanese numerals.
     - Accurate subtitle gap clipping (0.05s) between slide transitions.
3. **Scenario 3: Multi-Track Video Ingestion & Remuxing**
   - Workload: MP4 video with Track 1 (Game Audio) and Track 2 (Microphone Audio).
   - Flow:
     1. Audio extraction of Track 2 to WAV.
     2. DeepFilterNet denoising to `{stem}_clean.wav`.
     3. Post-processed transcription to `{stem}.srt`, `{stem}.vtt`, `{stem}.json`.
     4. Video remuxing replacing Track 2 with `{stem}_clean.wav` to `{stem}_clean.mp4`.
   - Assertions:
     - `PipelineResult` contains valid paths for all 5 assets.
     - Video remuxing completes without audio-video desync.
4. **Scenario 4: High-Noise / Silent Ambient Recording (Hallucination Stress Test)**
   - Workload: Audio containing 80% silence with air conditioner background noise.
   - Whisper produces repetitive hallucination loops (`"ご視聴ありがとうございました"` repeatedly, `no_speech_prob > 0.6` or loop repeats).
   - Assertions:
     - Sanitizer drops all hallucinated segments.
     - Clean subtitle files contain only genuine speech segments.
     - If all segments dropped, empty subtitle files (`WEBVTT\n\n`, empty SRT, `[]` JSON) are safely produced without pipeline crashes.
5. **Scenario 5: 1-Hour Long-Form Content Drift & Precision Test**
   - Workload: 500+ segments spanning 3600+ seconds.
   - Assertions:
     - Timestamps format correctly above 1 hour (`01:00:00,000`).
     - Subtitle timing adjuster enforces `total_duration` clamp at 3600.0s.
     - Millisecond precision (`round(ts, 3)`) is maintained throughout without floating-point accumulation drift.

---

## 6. Summary of Architectural Constants & Configurations

| Parameter | Default Value | Location | Description |
|-----------|---------------|----------|-------------|
| `no_speech_threshold` | `0.6` (Config: `0.85`) | `sanitizer.py`, `config.py` | Silence probability threshold for dropping hallucinated segments. |
| `max_chars_per_second` | `12.0` | `sanitizer.py` | Maximum physiological Japanese speech rate. Protected for len <= 4. |
| `end_padding` | `1.0` | `timing.py`, `config.py` | Trailing display padding in seconds added to subtitle end. |
| `min_duration` | `1.5` | `timing.py`, `config.py` | Minimum subtitle display duration in seconds. |
| `min_gap` | `0.05` | `timing.py`, `config.py` | Minimum gap in seconds between consecutive subtitles. |
| `replace_terms` | `True` | `post_processor.py`, `config.py` | Whether to perform dictionary term replacements. |
| `normalize_nums` | `True` | `post_processor.py`, `config.py` | Whether to normalize numbers to Zenkaku digits. |
| `to_hankaku` | `False` | `post_processor.py`, `config.py` | Whether to apply NFKC halfwidth conversion. |
| `lower` | `False` | `post_processor.py`, `config.py` | Whether to lowercase English alphabetic characters. |
| `remove_punct` | `False` | `post_processor.py`, `config.py` | Whether to strip punctuation (`、。！？!?\s\r\n`). |
