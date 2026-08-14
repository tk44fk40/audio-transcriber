## 2026-08-14T18:52:07Z
You are Worker for Milestone 3 (Config Cleanup & Parameter Updates) in audio-transcriber.
Your working directory is: /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/worker_m3_1

Read the following files before starting:
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/ORIGINAL_REQUEST.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/AGENTS.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/PROJECT.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/sub_orch_m3/SCOPE.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/explorer_m3_1/analysis.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/explorer_m3_2/analysis.md
- /home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/explorer_m3_3/analysis.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Scope and Tasks:
1. Update `src/audio_transcriber/config.py`:
   - Completely remove `max_segment_chars` from `PostProcessConfig` and `parse_config_dict`.
   - Update `PostProcessConfig` with fields:
     `custom_dict_path: Path | None = None`
     `replace_terms: bool = True`
     `normalize_nums: bool = True`
     `to_hankaku: bool = False`
     `lower: bool = False`
     `remove_punct: bool = False`
     `no_speech_threshold: float = 0.6`
     `max_chars_per_second: float = 12.0`
   - Add `SubtitleConfig` with fields:
     `end_padding: float = 1.0`
     `min_duration: float = 1.5`
     `min_gap: float = 0.05`
     `formats: list[str] = field(default_factory=lambda: ["srt", "vtt", "json"])`
   - Update `AppConfig` to include `post_process: PostProcessConfig` and `subtitle: SubtitleConfig`.
   - Implement clean TOML parsing helper functions (`_normalize_dict`, `_get_val`) supporting case-insensitivity, aliases (`post_process`/`postprocess`, `subtitle`/`subtitles`), and format list normalization.
   - Keep file size <= 200 lines (target) / max 300 lines. Add Google-style Japanese docstrings and strict Python 3.11+ type annotations.

2. Update `config.toml` and `config.example.toml`:
   - Remove `MAX_SEGMENT_CHARS`.
   - Add commented sections for `[post_process]` and `[subtitle]` with descriptions of all parameters.

3. Update `tests/test_config.py`:
   - Implement comprehensive tests covering defaults, full custom TOML loading, partial fallback, case-insensitivity & aliases, file not found, invalid TOML, empty dict parsing, and negative verification for `max_segment_chars`.
   - Adhere to AAA pattern, Google style Japanese docstrings, strict type hints, and <= 200 lines.

4. Run all verification checks:
   - `uv run pytest --cov=audio_transcriber --cov-report=term-missing`
   - `uv run basedpyright`
   - `uv run ruff check .`
   - `uv run ruff format --check .`
   - `uv run pre-commit run --all-files`

Write your comprehensive implementation report to `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/worker_m3_1/changes.md` and write a soft handoff in `/home/tk44/ghq/github.com/tk44fk40/audio-transcriber/.agents/worker_m3_1/handoff.md`.
Send a message back to the orchestrator when completed with all verification results.
