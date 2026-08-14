## 2026-08-14T18:50:01Z

You are Spec Miner 2 for the E2E Testing Track of audio-transcriber.
Your working directory is: /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_e2e/spec_miner_2

Read the following files before starting:
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/ORIGINAL_REQUEST.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/AGENTS.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/PROJECT.md

Reference implementation to investigate:
- /home/tk44/ghq/github.com/tk44fk40/lumi_companion/src/lumi_companion/audio/
  - `number_normalizer.py`
  - `segment_sanitizer.py`
  - `timing_adjuster.py`
  - `srt_exporter.py`
  - `post_processor.py`
  - and any tests in `/home/tk44/ghq/github.com/tk44fk40/lumi_companion/tests/`

Task:
1. Systematically mine the exact requirements, input/output behaviors, boundary conditions, regexes, and edge cases from the reference implementation and PROJECT.md for all 24 features across:
   - Data models (`SubtitleSegment`)
   - Sanitizer (hallucination, silence prob, max speech rate, 2-half repetition, loop repeats, word timestamp alignment)
   - Number normalizer (kanji numerals, roman numerals, circled numbers, fullwidth/halfwidth)
   - Text post-processor (dictionary replacement longest-first, TOML/YAML/JSON dict loading, NFKC, lowercase, punctuation stripping)
   - Timing adjuster (trailing padding, min duration, overlap clipping with min_gap, total duration clipping)
   - Subtitle exporters (DaVinci Resolve SRT with `HH:MM:SS,mmm`, WebVTT with `HH:MM:SS.mmm`, JSON with `indent=2`, UTF-8, LF)
   - Pipeline and CLI multi-format export and options
2. Enumerate detailed test specifications for Tier 1 (Feature coverage), Tier 2 (Boundary & Corner), Tier 3 (Cross-feature interactions), and Tier 4 (Real-world workload scenarios).
3. Write your analysis to `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_e2e/spec_miner_2/analysis.md` and handoff report to `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_e2e/spec_miner_2/handoff.md`.
4. Send a completion message back.
