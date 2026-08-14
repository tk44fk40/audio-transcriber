## 2026-08-14T19:02:24Z

You are Explorer 2 for Milestone 2 of audio-transcriber.
Your working directory is: /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_m2_explorer_2

Read the following files before starting:
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/ORIGINAL_REQUEST.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/AGENTS.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/PROJECT.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/src/audio_transcriber/models.py

Your focus:
Investigate and design the technical specifications and implementation strategy for `TextPostProcessor` in `src/audio_transcriber/post_processor.py`:
1. Dictionary loading:
   - Support TOML, YAML, JSON formats for custom word replacement dictionaries.
   - Robust loading from file path or dictionary mapping.
   - Error handling for invalid syntax or missing files.
2. Replacement algorithm:
   - Longest-first (Aho-Corasick or sorted regex/trie approach) keyword replacement to avoid substring clash (e.g., "東京都" vs "東京").
   - Case sensitivity options / word boundaries where applicable.
3. Pipeline transformations:
   - Integration with `NumberNormalizer` (optional/configurable flag).
   - NFKC half-width conversion flag.
   - Lowercase flag.
   - Punctuation removal flag (preserving necessary sentence structures).
   - Method for string processing: `process(text: str) -> str`.
   - Method for segment list processing: `process_segments(segments: list[TranscriptionSegment]) -> list[TranscriptionSegment]`.
4. Code layout & architectural constraints: <=200 lines (max 300 lines), Google-style docstrings, basedpyright 0 errors, ruff 0 errors.

Write your detailed findings to:
`/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_m2_explorer_2/analysis.md`
and write a summary handoff to:
`/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_m2_explorer_2/handoff.md`

Send a completion message back to parent when done.
