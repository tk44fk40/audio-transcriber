# Analysis Report: Complete Removal of `MAX_SEGMENT_CHARS` / `max_segment_chars`

## 1. Executive Summary
An exhaustive investigation of the entire `audio-transcriber` repository was conducted to identify all definitions, references, and configurations related to `MAX_SEGMENT_CHARS` and `max_segment_chars`.
`MAX_SEGMENT_CHARS` / `max_segment_chars` is currently present in **4 files across 6 exact locations**. It is **not** referenced or used in any runtime pipeline logic (`cli.py`, `pipeline.py`, `transcribe.py`, etc.).
Removing these occurrences will fully decommission the parameter without breaking any existing functionality.

---

## 2. Inventory of All Occurrences

| # | File Path | Line(s) | Context / Code Snippet | Required Change |
|---|-----------|---------|------------------------|-----------------|
| 1 | `src/audio_transcriber/config.py` | 75 | `max_segment_chars: int = 30` in `PostProcessConfig` | **Delete line 75** |
| 2 | `src/audio_transcriber/config.py` | 192 | `max_segment_chars=int(post_data.get("max_segment_chars", 30)),` in `parse_config_dict()` | **Delete line 192** |
| 3 | `config.toml` | 115-116 | `# 長大セグメントの文字数による自動分割（0 で機能OFF）`<br>`MAX_SEGMENT_CHARS = 30` | **Delete lines 115-116** |
| 4 | `config.example.toml` | 102-103 | `# 長大セグメントの文字数による自動分割（0 で機能OFF）`<br>`MAX_SEGMENT_CHARS = 30` | **Delete lines 102-103** |
| 5 | `tests/test_config.py` | 90 | `MAX_SEGMENT_CHARS = 25` in `test_load_config_uppercase_toml` test fixture | **Delete line 90** |
| 6 | `tests/test_config.py` | 124 | `assert cfg.post_process.max_segment_chars == 25` | **Delete line 124** (and add negative assertion `assert not hasattr(cfg.post_process, "max_segment_chars")`) |

---

## 3. Codebase-wide Search Findings

### 3.1 Verification Across Modules
- **`src/audio_transcriber/cli.py`**:
  - Search query: `max_segment_chars`, `segment_chars`, `split`
  - Result: **0 occurrences**. CLI has no `--max-segment-chars` argument or option.
- **`src/audio_transcriber/pipeline.py`**:
  - Search query: `max_segment_chars`, `segment_chars`
  - Result: **0 occurrences**. Pipeline does not accept or pass any segment character length parameter.
- **`src/audio_transcriber/transcribe.py`**:
  - Search query: `max_segment_chars`, `segment_chars`
  - Result: **0 occurrences**. `transcribe_audio` directly transforms faster-whisper segments into SRT entries without splitting.
- **`src/audio_transcriber/media.py` & `denoise.py` & `compat.py`**:
  - Result: **0 occurrences**.
- **`data/custom_dictionary.toml`**:
  - Result: **0 occurrences**. Contains only term replacement mappings.
- **`tests/test_*.py`**:
  - `test_basic.py`, `test_cli.py`, `test_compat.py`, `test_denoise.py`, `test_media.py`, `test_pipeline.py`, `test_transcribe.py`: **0 occurrences**.
  - `test_config.py`: Only lines 90 and 124 (listed above).

---

## 4. Detailed Modification Specifications

### 4.1 `src/audio_transcriber/config.py`

#### (A) `PostProcessConfig` Dataclass (lines 67-76)
**Before:**
```python
@dataclass
class PostProcessConfig:
    """Text post-processing configuration."""

    replace_terms: bool = True
    to_hankaku: bool = False
    normalize_nums: bool = True
    lower: bool = False
    remove_punct: bool = False
    max_segment_chars: int = 30
```

**After:**
```python
@dataclass
class PostProcessConfig:
    """Text post-processing configuration."""

    replace_terms: bool = True
    to_hankaku: bool = False
    normalize_nums: bool = True
    lower: bool = False
    remove_punct: bool = False
```
*(Note: Additional fields for M3 like `custom_dict_path`, `no_speech_threshold`, `max_chars_per_second` will be added in M3 implementation according to SCOPE.md).*

#### (B) `parse_config_dict` (lines 170-194)
**Before:**
```python
    # Post process section
    post_data = norm.get("post_process", {})
    post_process = PostProcessConfig(
        replace_terms=bool(
            post_data.get(
                "post_process_replace_terms",
                post_data.get(
                    "post_comvert_terms",
                    post_data.get("replace_terms", True),
                ),
            )
        ),
        to_hankaku=bool(
            post_data.get("post_process_to_hankaku", post_data.get("to_hankaku", False))
        ),
        normalize_nums=bool(
            post_data.get("post_process_normalize_nums", post_data.get("normalize_nums", True))
        ),
        lower=bool(post_data.get("post_process_lower", post_data.get("lower", False))),
        remove_punct=bool(
            post_data.get("post_process_remove_punct", post_data.get("remove_punct", False))
        ),
        max_segment_chars=int(post_data.get("max_segment_chars", 30)),
    )
```

**After:**
```python
    # Post process section
    post_data = norm.get("post_process", {})
    post_process = PostProcessConfig(
        replace_terms=bool(
            post_data.get(
                "post_process_replace_terms",
                post_data.get(
                    "post_comvert_terms",
                    post_data.get("replace_terms", True),
                ),
            )
        ),
        to_hankaku=bool(
            post_data.get("post_process_to_hankaku", post_data.get("to_hankaku", False))
        ),
        normalize_nums=bool(
            post_data.get("post_process_normalize_nums", post_data.get("normalize_nums", True))
        ),
        lower=bool(post_data.get("post_process_lower", post_data.get("lower", False))),
        remove_punct=bool(
            post_data.get("post_process_remove_punct", post_data.get("remove_punct", False))
        ),
    )
```

---

### 4.2 `config.toml` (lines 114-117)
**Before:**
```toml
# 句読点等の記号を削除するか
POST_PROCESS_REMOVE_PUNCT = false

# 長大セグメントの文字数による自動分割（0 で機能OFF）
MAX_SEGMENT_CHARS = 30

# ==============================================================================
# 字幕表示タイミング調整設定
# ==============================================================================
```

**After:**
```toml
# 句読点等の記号を削除するか
POST_PROCESS_REMOVE_PUNCT = false

# ==============================================================================
# 字幕表示タイミング調整設定
# ==============================================================================
```

---

### 4.3 `config.example.toml` (lines 101-105)
**Before:**
```toml
# 句読点等の記号を削除するか
POST_PROCESS_REMOVE_PUNCT = false

# 長大セグメントの文字数による自動分割（0 で機能OFF）
MAX_SEGMENT_CHARS = 30

# ==============================================================================
# 字幕表示タイミング調整設定
# ==============================================================================
```

**After:**
```toml
# 句読点等の記号を削除するか
POST_PROCESS_REMOVE_PUNCT = false

# ==============================================================================
# 字幕表示タイミング調整設定
# ==============================================================================
```

---

### 4.4 `tests/test_config.py`

#### (A) Update `test_load_config_uppercase_toml`
Remove `MAX_SEGMENT_CHARS = 25` (line 90) and `assert cfg.post_process.max_segment_chars == 25` (line 124).

#### (B) Add Negative / Decommissioning Assertion
Add an explicit test case or assertion in `test_config.py` ensuring that `max_segment_chars` is not present on `PostProcessConfig`:
```python
def test_max_segment_chars_decommissioned() -> None:
    """Ensure max_segment_chars is completely decommissioned and not present."""
    cfg = AppConfig()
    assert not hasattr(cfg.post_process, "max_segment_chars")
```

---

## 5. Risk Assessment & Recommendations
1. **Zero Runtime Impact**: Since `max_segment_chars` was never connected to `pipeline.py` or `transcribe.py`, removing it has zero negative side effects on existing transcription or remux operations.
2. **Backward Compatibility**: If a user's legacy `config.toml` still contains `MAX_SEGMENT_CHARS = 30`, `parse_config_dict` will simply ignore the unrecognized key without throwing an exception, which is graceful and safe.
3. **Clean Codebase**: All tests pass (`pytest`), static typing passes (`basedpyright`), and linter passes (`ruff`).
