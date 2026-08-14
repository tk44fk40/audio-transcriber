## 2026-08-15T03:46:04+09:00

Investigate the reference implementation in `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/`.
Thoroughly examine and document:
1. `number_normalizer.py`: How kanji numbers, Roman numerals, and Arabic numerals are normalized. Any external dependencies or algorithms.
2. `segment_sanitizer.py`: How hallucination detection, silence/no-speech probability filtering, compression ratio checks, speech rate anomalies, and repeated phrase reduction are implemented.
3. `timing_adjuster.py`: How trailing padding, minimum display duration, and overlap prevention / gap control are calculated and applied.
4. `srt_exporter.py`: How SubtitleSegment is exported to DaVinci Resolve compatible SRT (00:00:00,000, UTF-8, LF), WebVTT, and JSON.
5. `post_processor.py`: How the overall post-processing pipeline executes, how dictionary replacement (custom dictionary) works, and how SubtitleSegment data model is defined and converted.
6. Identify what dependencies (e.g. libraries) are used in lumi_companion vs what is needed in audio-transcriber (Note: Janome / morphological clause segmentation is explicitly excluded per ORIGINAL_REQUEST.md).

Write your detailed findings to `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/explorer_survey_1/survey_report.md` and write a handoff report to `handoff.md`.
