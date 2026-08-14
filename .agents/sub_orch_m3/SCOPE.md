# Scope: Milestone 3 (Config Cleanup & Parameter Updates)

## Architecture & Integration
- Module: `src/audio_transcriber/config.py`
- Configuration files: `config.toml`, `config.example.toml`
- Test files: `tests/test_config.py`

## Objectives
1. Remove `MAX_SEGMENT_CHARS` and `max_segment_chars` everywhere:
   - `src/audio_transcriber/config.py` (defaults, fields, loader parsing)
   - `config.toml`, `config.example.toml`
   - `tests/test_config.py`
2. Add `PostProcessConfig` to `config.py`:
   - `custom_dict_path: Path | None = None`
   - `replace_terms: bool = True`
   - `normalize_nums: bool = True`
   - `to_hankaku: bool = False`
   - `lower: bool = False`
   - `remove_punct: bool = False`
   - `no_speech_threshold: float = 0.6`
   - `max_chars_per_second: float = 12.0`
3. Add `SubtitleConfig` to `config.py`:
   - `end_padding: float = 1.0`
   - `min_duration: float = 1.5`
   - `min_gap: float = 0.05`
   - `formats: list[str] = ["srt", "vtt", "json"]` (or default format list)
4. Update `AppConfig`:
   - Include `post_process: PostProcessConfig = field(default_factory=PostProcessConfig)`
   - Include `subtitle: SubtitleConfig = field(default_factory=SubtitleConfig)`
   - Ensure `load_config` handles sections `[post_process]` / `[postprocess]` and `[subtitle]` with case-insensitive / flexible keys.
5. Update `config.toml` and `config.example.toml`:
   - Add sample/default sections for `[post_process]` and `[subtitle]` with comments.
6. Update `tests/test_config.py`:
   - Test default values of `PostProcessConfig`, `SubtitleConfig`, `AppConfig`.
   - Test loading custom config from TOML (all sections including post_process and subtitle).
   - Test case-insensitivity and fallback behavior.
   - Assert `max_segment_chars` is not an attribute or key.

## Interface Contracts
- `PostProcessConfig` (dataclass)
- `SubtitleConfig` (dataclass)
- `AppConfig` (dataclass containing `denoise`, `transcribe`, `post_process`, `subtitle`)
- `load_config(config_path: Path | None = None) -> AppConfig`
