"""Empirical Stress Test & Adversarial Harness for SegmentSanitizer (Pytest format)."""

import math
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, NamedTuple

import pytest

from audio_transcriber.models import SubtitleSegment
from audio_transcriber.sanitizer import SegmentSanitizer


def test_empty_segment_list() -> None:
    """Empty segment list returns empty list."""
    sanitizer = SegmentSanitizer()
    res = sanitizer.sanitize_segments([])
    assert res == []


@pytest.mark.parametrize(
    "seg_dict, expected_field",
    [
        ({"text": "hello", "no_speech_prob": None, "start": 0.0, "end": 2.0}, "no_speech_prob"),
        ({"text": "hello", "compression_ratio": None, "start": 0.0, "end": 2.0}, "compression_ratio"),
        ({"text": "hello", "start": None, "end": 2.0}, "start"),
        ({"text": "hello", "start": 0.0, "end": None}, "end"),
    ],
)
def test_none_values_in_dict_fields_behavior(seg_dict: dict[str, Any], expected_field: str) -> None:
    """Verify that None values in numeric dict fields raise TypeError when float(None) is called."""
    sanitizer = SegmentSanitizer()
    with pytest.raises(TypeError):
        sanitizer.sanitize_segments([seg_dict])


def test_none_text_in_dict() -> None:
    """If dict has text=None, str(None) becomes 'None'."""
    sanitizer = SegmentSanitizer()
    res = sanitizer.sanitize_segments([{"text": None, "start": 0.0, "end": 2.0}])
    # Observation: str(None).strip() becomes "None"
    assert len(res) == 1
    assert res[0].text == "None"


@pytest.mark.parametrize(
    "seg_obj",
    [
        SimpleNamespace(text="hello", no_speech_prob=None, start=0.0, end=2.0),
        SimpleNamespace(text="hello", compression_ratio=None, start=0.0, end=2.0),
        SimpleNamespace(text="hello", start=None, end=2.0),
        SimpleNamespace(text="hello", start=0.0, end=None),
    ],
)
def test_none_values_in_object_fields(seg_obj: Any) -> None:
    """Verify that None values in numeric object fields raise TypeError when float(None) is called."""
    sanitizer = SegmentSanitizer()
    with pytest.raises(TypeError):
        sanitizer.sanitize_segments([seg_obj])


def test_none_text_in_object() -> None:
    """If object has text=None, str(None) becomes 'None'."""
    sanitizer = SegmentSanitizer()
    res = sanitizer.sanitize_segments([SimpleNamespace(text=None, start=0.0, end=2.0)])
    assert len(res) == 1
    assert res[0].text == "None"


def test_nan_and_inf_float_values() -> None:
    """Verify behavior with NaN and Inf float values."""
    sanitizer = SegmentSanitizer()

    # Start/End as NaN: short text (<= 4 chars) bypasses speech rate check
    res = sanitizer.sanitize_segments([{"text": "短文", "start": float("nan"), "end": 1.0}])
    assert len(res) == 1
    assert math.isnan(res[0].start)

    # Inf start with short text
    res_inf = sanitizer.sanitize_segments([{"text": "短文", "start": float("inf"), "end": 1.0}])
    assert len(res_inf) == 1
    assert math.isinf(res_inf[0].start)

    # total_duration as NaN
    res_td = sanitizer.sanitize_segments([{"text": "短文", "start": 0.0, "end": 1.0}], total_duration=float("nan"))
    assert len(res_td) == 1


def test_inverted_and_negative_timestamps() -> None:
    """Verify behavior with inverted (start > end) and negative timestamps."""
    sanitizer = SegmentSanitizer()

    # start > end for short text (<= 4 chars)
    res = sanitizer.sanitize_segments([{"text": "短文", "start": 10.0, "end": 2.0}])
    assert len(res) == 1
    assert res[0].start == 10.0
    assert res[0].end == 2.0

    # start > end for longer text (> 4 chars)
    # duration = max(2.0 - 10.0, 0.1) = 0.1 -> chars_per_sec = 5 / 0.1 = 50 > 12 -> dropped!
    res = sanitizer.sanitize_segments([{"text": "長めの発話", "start": 10.0, "end": 2.0}])
    assert len(res) == 0

    # negative timestamps
    res = sanitizer.sanitize_segments([{"text": "負の開始", "start": -5.0, "end": -1.0}])
    assert len(res) == 1
    assert res[0].start == -5.0
    assert res[0].end == -1.0


def test_extreme_float_values() -> None:
    """Verify behavior with huge float values."""
    sanitizer = SegmentSanitizer()
    res = sanitizer.sanitize_segments([{"text": "宇宙規模", "start": 1e300, "end": 1e300 + 1.0}])
    assert len(res) == 1
    assert res[0].start == 1e300


@pytest.mark.parametrize(
    "ws",
    [
        "   ",
        "\t\n\r",
        "   \u3000\t  ",
    ],
)
def test_whitespace_filtering(ws: str) -> None:
    """Whitespace-only segments are filtered out."""
    sanitizer = SegmentSanitizer()
    res = sanitizer.sanitize_segments([{"text": ws, "start": 0.0, "end": 1.0}])
    assert len(res) == 0


def test_unicode_and_emojis() -> None:
    """Complex unicode, emojis, combining characters."""
    sanitizer = SegmentSanitizer()

    # ZWJ sequence family emoji
    res = sanitizer.sanitize_segments([{"text": "👨‍👩‍👧‍👦", "start": 0.0, "end": 2.0}])
    assert len(res) == 1
    assert res[0].text == "👨‍👩‍👧‍👦"

    # Repeated ZWJ sequence family emoji (len 14, half 7, 7 chars / 2.0s = 3.5 chars/s <= 12.0)
    res = sanitizer.sanitize_segments([{"text": "👨‍👩‍👧‍👦👨‍👩‍👧‍👦", "start": 0.0, "end": 2.0, "no_speech_prob": 0.2}])
    assert len(res) == 1
    assert res[0].text == "👨‍👩‍👧‍👦"

    # Combining characters
    res = sanitizer.sanitize_segments([{"text": "e\u0301e\u0301", "start": 0.0, "end": 2.0}])
    assert len(res) == 1

    # Surrogate pairs / rare kanji
    res = sanitizer.sanitize_segments([{"text": "𠮷野家𠮷野家", "start": 0.0, "end": 2.0, "compression_ratio": 2.5}])
    assert len(res) == 1
    assert res[0].text == "𠮷野家"

    # Control chars & ANSI
    res = sanitizer.sanitize_segments([{"text": "Hello\x00\x1b[31mRed\x1b[0m", "start": 0.0, "end": 2.0}])
    assert len(res) == 1


def test_massive_string_dropped_by_rate() -> None:
    """100k character text gets dropped by rate limit."""
    sanitizer = SegmentSanitizer()
    huge_text = "あ" * 100_000
    res = sanitizer.sanitize_segments([{"text": huge_text, "start": 0.0, "end": 10.0}])
    assert len(res) == 0


@pytest.mark.parametrize(
    "text, nsp, cr, expected",
    [
        ("ああああ", 0.2, 1.0, "ああ"),
        ("あいうあいう", 0.2, 1.0, "あいう"),
        ("はいはいはい", 0.2, 1.0, "はいはいはい"),
        ("はいはいはいはい", 0.2, 1.0, "はいはい"),
        ("はいはい", 0.05, 1.0, "はいはい"),
        ("はいはい", 0.15, 1.0, "はい"),
        ("はいはい", 0.05, 2.5, "はい"),
    ],
)
def test_repetition_halving_cases(text: str, nsp: float, cr: float, expected: str) -> None:
    """Verify intra-segment repetition halving behavior."""
    sanitizer = SegmentSanitizer()
    res = sanitizer.sanitize_segments([{"text": text, "start": 0.0, "end": 2.0, "no_speech_prob": nsp, "compression_ratio": cr}])
    assert len(res) == 1
    assert res[0].text == expected


def test_word_timestamp_containers() -> None:
    """Test words as list, tuple, generator, set, dict, non-iterable."""
    sanitizer = SegmentSanitizer()

    # list
    res = sanitizer.sanitize_segments([{"text": "単語", "start": 0.0, "end": 2.0, "words": [{"start": 0.5, "end": 1.0}]}])
    assert res[0].start == 0.5

    # tuple
    res = sanitizer.sanitize_segments([{"text": "単語", "start": 0.0, "end": 2.0, "words": ({"start": 0.6, "end": 1.0},)}])
    assert res[0].start == 0.6

    # generator
    def w_gen():
        yield {"start": 0.7, "end": 1.0}
    res = sanitizer.sanitize_segments([{"text": "単語", "start": 0.0, "end": 2.0, "words": w_gen()}])
    assert res[0].start == 0.7

    # empty generator
    res = sanitizer.sanitize_segments([{"text": "単語", "start": 0.0, "end": 2.0, "words": (x for x in [])}])
    assert res[0].start == 0.0

    # non-iterable int or bool (if words=123, iter(123) raises TypeError)
    with pytest.raises(TypeError):
        sanitizer.sanitize_segments([{"text": "単語", "start": 0.0, "end": 2.0, "words": 123}])


def test_word_malformed_objects() -> None:
    """Test words containing malformed items."""
    sanitizer = SegmentSanitizer()

    # first word None
    res = sanitizer.sanitize_segments([{"text": "単語", "start": 0.0, "end": 2.0, "words": [None]}])
    assert res[0].start == 0.0

    # first word empty dict
    res = sanitizer.sanitize_segments([{"text": "単語", "start": 0.0, "end": 2.0, "words": [{}]}])
    assert res[0].start == 0.0

    # first word non-numeric start
    res = sanitizer.sanitize_segments([{"text": "単語", "start": 0.0, "end": 2.0, "words": [{"start": "invalid"}]}])
    assert res[0].start == 0.0


def test_custom_data_structures() -> None:
    """Test SegmentSanitizer with dataclass, NamedTuple, custom classes, and generator of segments."""
    sanitizer = SegmentSanitizer()

    @dataclass
    class CustomSegment:
        text: str
        start: float
        end: float
        no_speech_prob: float = 0.0
        compression_ratio: float = 0.0
        words: Any = None

    class CustomNamedTuple(NamedTuple):
        text: str
        start: float
        end: float
        no_speech_prob: float = 0.0
        compression_ratio: float = 0.0
        words: Any = None

    class CustomClassWithProperties:
        def __init__(self, text: str, start: float, end: float) -> None:
            self._text = text
            self._start = start
            self._end = end

        @property
        def text(self) -> str:
            return self._text

        @property
        def start(self) -> float:
            return self._start

        @property
        def end(self) -> float:
            return self._end

    segs = [
        CustomSegment(text="データクラス", start=0.0, end=1.0),
        CustomNamedTuple(text="タプル", start=1.0, end=2.0),
        CustomClassWithProperties(text="プロパティクラス", start=2.0, end=3.0),
    ]
    res = sanitizer.sanitize_segments(segs)
    assert len(res) == 3
    assert [r.text for r in res] == ["データクラス", "タプル", "プロパティクラス"]


def test_inter_segment_loop_filtering() -> None:
    """Test inter-segment loop substring filtering and preservation."""
    sanitizer = SegmentSanitizer()
    segs = [
        {"text": "これはとても長い文章の一部です", "start": 0.0, "end": 2.0, "no_speech_prob": 0.05},
        {"text": "文章", "start": 2.1, "end": 3.0, "no_speech_prob": 0.15},
        {"text": "これは", "start": 3.1, "end": 4.0, "no_speech_prob": 0.05},
        {"text": "別の文章", "start": 4.1, "end": 5.0, "no_speech_prob": 0.15},
    ]
    res = sanitizer.sanitize_segments(segs)
    assert [r.text for r in res] == ["これはとても長い文章の一部です", "これは", "別の文章"]


def test_speech_rate_boundary() -> None:
    """Test speech rate boundary conditions (4 chars vs 5 chars)."""
    sanitizer = SegmentSanitizer(max_chars_per_second=12.0)
    segs = [
        {"text": "1234", "start": 0.0, "end": 0.01, "no_speech_prob": 0.0},
        {"text": "12345", "start": 1.0, "end": 1.4, "no_speech_prob": 0.0},
        {"text": "12345", "start": 2.0, "end": 2.5, "no_speech_prob": 0.0},
    ]
    res = sanitizer.sanitize_segments(segs)
    assert len(res) == 2
    assert res[0].text == "1234"
    assert res[1].text == "12345"
    assert res[1].start == 2.0


def test_instance_state_isolation_between_calls() -> None:
    """Verify that multiple consecutive calls on the same sanitizer instance do not leak last_valid_text."""
    sanitizer = SegmentSanitizer()

    # Call 1 ends with "チャンネル登録お願いします"
    res1 = sanitizer.sanitize_segments([
        {"text": "チャンネル登録お願いします", "start": 0.0, "end": 2.0, "no_speech_prob": 0.05}
    ])
    assert len(res1) == 1

    # Call 2 begins with "チャンネル登録" and nsp = 0.3.
    # If state leaked from Call 1, this would be dropped as a loop.
    # Because state is reset per call, this is the first segment in Call 2 and should NOT be dropped.
    res2 = sanitizer.sanitize_segments([
        {"text": "チャンネル登録", "start": 0.0, "end": 2.0, "no_speech_prob": 0.3}
    ])
    assert len(res2) == 1
    assert res2[0].text == "チャンネル登録"


def test_concurrent_execution_thread_safety() -> None:
    """Verify thread-safe execution across multiple threads on a shared instance."""
    sanitizer = SegmentSanitizer()

    def process_batch(batch_id: int) -> list[SubtitleSegment]:
        segs = [
            {"text": f"バッチ発話_{batch_id}", "start": 0.0, "end": 1.0, "no_speech_prob": 0.05},
            {"text": f"バッチ発話_{batch_id}_後編", "start": 1.0, "end": 2.0, "no_speech_prob": 0.05},
        ]
        return sanitizer.sanitize_segments(segs)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_batch, i) for i in range(50)]
        results = [f.result() for f in futures]

    assert len(results) == 50
    for r in results:
        assert len(r) == 2


def test_high_volume_stress_100k() -> None:
    """Stress test with 100,000 segments."""
    sanitizer = SegmentSanitizer()
    N = 100_000

    def gen_stress_segments() -> Generator[dict[str, Any], None, None]:
        for i in range(N):
            # len("発話_00") = 5. duration = 1.0 -> 5.0 chars/sec <= 12.0.
            # every 10th item has nsp=0.8 (> 0.6) -> dropped.
            yield {
                "text": f"発話_{i % 50:02d}",
                "start": float(i * 2),
                "end": float(i * 2) + 1.0,
                "no_speech_prob": 0.05 if i % 10 != 0 else 0.8,
                "compression_ratio": 1.0,
                "words": [{"start": float(i * 2) + 0.1, "end": float(i * 2) + 0.9, "word": f"単語_{i}"}],
            }

    t0 = time.perf_counter()
    res = sanitizer.sanitize_segments(gen_stress_segments(), total_duration=float(N * 2))
    t1 = time.perf_counter()
    elapsed = t1 - t0
    # Must process 100,000 items in < 5 seconds
    assert elapsed < 5.0
    assert len(res) == 90_000


def test_consecutive_repeats_stress_10k() -> None:
    """Stress test with 10,000 identical repeats under silence."""
    sanitizer = SegmentSanitizer()
    N = 10_000

    def gen_repeat_segments() -> Generator[dict[str, Any], None, None]:
        for i in range(N):
            # len("同じテキスト") = 6. duration = 1.0 -> 6.0 chars/sec <= 12.0.
            yield {
                "text": "同じテキスト",
                "start": float(i * 2),
                "end": float(i * 2) + 1.0,
                "no_speech_prob": 0.3,
            }

    t0 = time.perf_counter()
    res = sanitizer.sanitize_segments(gen_repeat_segments())
    t1 = time.perf_counter()
    assert (t1 - t0) < 1.0
    assert len(res) == 1
