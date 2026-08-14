"""Empirical Adversarial Stress Test Suite for SubtitleExporter and SubtitleSegment.

Executed by Challenger 2 for Milestone 1.
"""

import json
import re
import time
from pathlib import Path

import pytest

from audio_transcriber.exporter import SubtitleExporter
from audio_transcriber.models import SubtitleSegment


def test_extreme_timestamps() -> None:
    """Adversarial testing of extreme timestamps and rollover behavior."""
    test_cases = [
        # (seconds, expected_srt, expected_vtt)
        (0.0, "00:00:00,000", "00:00:00.000"),
        (0.0001, "00:00:00,000", "00:00:00.000"),
        (0.00049, "00:00:00,000", "00:00:00.000"),
        (0.0005, "00:00:00,000", "00:00:00.000"),  # round(0.5) to even = 0
        (0.00051, "00:00:00,001", "00:00:00.001"),
        (0.001, "00:00:00,001", "00:00:00.001"),
        (0.999, "00:00:00,999", "00:00:00.999"),
        (0.9994, "00:00:00,999", "00:00:00.999"),
        (0.9996, "00:00:01,000", "00:00:01.000"),  # second rollover (0.9996s -> 1.000s)
        (59.999, "00:00:59,999", "00:00:59.999"),
        (59.9994, "00:00:59,999", "00:00:59.999"),
        (59.9996, "00:01:00,000", "00:01:00.000"),  # minute rollover
        (59.9999, "00:01:00,000", "00:01:00.000"),
        (3599.999, "00:59:59,999", "00:59:59.999"),
        (3599.9996, "01:00:00,000", "01:00:00.000"),  # hour rollover
        (3599.9999, "01:00:00,000", "01:00:00.000"),
        (86399.999, "23:59:59,999", "23:59:59.999"),
        (86399.9995, "24:00:00,000", "24:00:00.000"),  # 24h rollover
        (86399.9999, "24:00:00,000", "24:00:00.000"),
        (360000.0, "100:00:00,000", "100:00:00.000"),  # 100 hours
        (3600000.123, "1000:00:00,123", "1000:00:00.123"),  # 1000 hours
        (-0.001, "00:00:00,000", "00:00:00.000"),  # negative clamped
        (-1000.0, "00:00:00,000", "00:00:00.000"),
    ]

    for sec, exp_srt, exp_vtt in test_cases:
        actual_srt = SubtitleExporter.format_timestamp(sec)
        actual_vtt = SubtitleExporter.format_vtt_timestamp(sec)
        assert actual_srt == exp_srt, f"SRT failed for {sec}: got {actual_srt!r}, expected {exp_srt!r}"
        assert actual_vtt == exp_vtt, f"VTT failed for {sec}: got {actual_vtt!r}, expected {exp_vtt!r}"

    # Verify regex conformance for all outputs
    srt_pattern = re.compile(r"^\d{2,}:\d{2}:\d{2},\d{3}$")
    vtt_pattern = re.compile(r"^\d{2,}:\d{2}:\d{2}\.\d{3}$")
    for sec, exp_srt, exp_vtt in test_cases:
        assert srt_pattern.match(SubtitleExporter.format_timestamp(sec)), f"SRT regex failed: {sec}"
        assert vtt_pattern.match(SubtitleExporter.format_vtt_timestamp(sec)), f"VTT regex failed: {sec}"


def test_rounding_millisecond_grid() -> None:
    """Test 1000 millisecond steps within a second to verify monotonicity and no gaps."""
    for ms in range(1000):
        sec = 12.0 + ms / 1000.0
        ts_srt = SubtitleExporter.format_timestamp(sec)
        ts_vtt = SubtitleExporter.format_vtt_timestamp(sec)
        assert ts_srt == f"00:00:12,{ms:03d}"
        assert ts_vtt == f"00:00:12.{ms:03d}"

    # Also test around 59 -> 60 rollover
    for ms in range(1000):
        sec = 59.0 + ms / 1000.0
        ts_srt = SubtitleExporter.format_timestamp(sec)
        ts_vtt = SubtitleExporter.format_vtt_timestamp(sec)
        assert ts_srt == f"00:00:59,{ms:03d}"
        assert ts_vtt == f"00:00:59.{ms:03d}"


def test_special_characters_and_encodings(tmp_path: Path) -> None:
    """Test Japanese text, surrogate pairs, emojis, multi-line, HTML tags, quotes, RTL, zero-width."""
    test_texts = [
        "こんにちは世界！これは日本語のテストです。",
        "特殊記号: 「『（【〔［｛《〈”’・…〜～—―",
        "𠮷野家で𩸽（ほっけ）を食べる (CJK Extension B: surrogate pairs)",
        "🎉🚀🔥💡 Single codepoint emojis",
        "👨‍👩‍👧‍👦 👩‍💻 👍🏽 Multi-codepoint & ZWJ sequence emojis",
        "Multi\nLine\nSubtitle\nWith\nLF\nNewlines",
        '<font color="#ff0000"><b>太字赤文字</b></font> & <i>斜体</i> <tag value="1">',
        'Quotes: "double" \'single\' `backtick` \\backslashes\\ /slashes/ {"json": "in_text"}',
        "Tab\tseparated\tand  multiple   spaces",
        "    Leading and trailing spaces    ",
        "مرحبا بالعالم (RTL Arabic text)",
        "שלום עולם (RTL Hebrew text)",
        "Zero\u200bWidth\u200cJoiner\u200dTest",
        "",  # empty text
    ]

    segments = [
        SubtitleSegment(start=float(i * 2), end=float(i * 2 + 1.5), text=t)
        for i, t in enumerate(test_texts)
    ]

    srt_path = tmp_path / "special.srt"
    vtt_path = tmp_path / "special.vtt"
    json_path = tmp_path / "special.json"

    SubtitleExporter.save_srt(segments, srt_path)
    SubtitleExporter.save_vtt(segments, vtt_path)
    SubtitleExporter.save_json(segments, json_path)

    # 1. Verify JSON roundtrip
    with open(json_path, encoding="utf-8") as f:
        loaded_json = json.load(f)
    assert len(loaded_json) == len(test_texts)
    for orig_seg, j_seg in zip(segments, loaded_json):
        assert j_seg["start"] == orig_seg.start
        assert j_seg["end"] == orig_seg.end
        assert j_seg["text"] == orig_seg.text

    # 2. Verify raw bytes for UTF-8 and LF line endings
    raw_srt = srt_path.read_bytes()
    assert b"\r\n" not in raw_srt, "SRT contains CRLF instead of LF"
    assert not raw_srt.startswith(b"\xef\xbb\xbf"), "SRT must not have UTF-8 BOM"

    raw_vtt = vtt_path.read_bytes()
    assert b"\r\n" not in raw_vtt, "VTT contains CRLF instead of LF"

    raw_json = json_path.read_bytes()
    assert b"\r\n" not in raw_json, "JSON contains CRLF instead of LF"

    # 3. Verify text content in SRT
    srt_text = srt_path.read_text(encoding="utf-8")
    assert "𠮷野家で𩸽（ほっけ）を食べる" in srt_text
    assert "👨‍👩‍👧‍👦" in srt_text
    assert '<font color="#ff0000">' in srt_text
    assert "مرحبا بالعالم" in srt_text


def test_empty_and_massive_segments(tmp_path: Path) -> None:
    """Test 0 segments and 10,000+ segments for performance and correctness."""
    # Empty segments
    empty_srt = tmp_path / "empty.srt"
    empty_vtt = tmp_path / "empty.vtt"
    empty_json = tmp_path / "empty.json"

    SubtitleExporter.save_srt([], empty_srt)
    SubtitleExporter.save_vtt([], empty_vtt)
    SubtitleExporter.save_json([], empty_json)

    assert empty_srt.read_text(encoding="utf-8") == ""
    assert empty_vtt.read_text(encoding="utf-8") == "WEBVTT\n"
    assert json.loads(empty_json.read_text(encoding="utf-8")) == []

    # 10,000 segments stress test
    num_segments = 10_000
    massive_segments = [
        SubtitleSegment(
            start=i * 2.5,
            end=i * 2.5 + 2.0,
            text=f"第{i+1}セグメントの発言内容です。インデックス: {i+1}",
        )
        for i in range(num_segments)
    ]

    massive_srt = tmp_path / "massive.srt"
    massive_vtt = tmp_path / "massive.vtt"
    massive_json = tmp_path / "massive.json"

    t0 = time.perf_counter()
    SubtitleExporter.save_srt(massive_segments, massive_srt)
    t1 = time.perf_counter()
    SubtitleExporter.save_vtt(massive_segments, massive_vtt)
    t2 = time.perf_counter()
    SubtitleExporter.save_json(massive_segments, massive_json)
    t3 = time.perf_counter()

    srt_time = t1 - t0
    vtt_time = t2 - t1
    json_time = t3 - t2

    assert srt_time < 2.0, f"SRT export too slow: {srt_time}s"
    assert vtt_time < 2.0, f"VTT export too slow: {vtt_time}s"
    assert json_time < 2.0, f"JSON export too slow: {json_time}s"

    # Verify SRT first, middle, last blocks
    srt_content = massive_srt.read_text(encoding="utf-8")
    assert srt_content.startswith("1\n00:00:00,000 --> 00:00:02,000\n第1セグメント")
    assert "\n\n5000\n" in srt_content
    assert "\n\n10000\n" in srt_content
    assert srt_content.endswith("第10000セグメントの発言内容です。インデックス: 10000\n")

    # Verify VTT first and last blocks
    vtt_content = massive_vtt.read_text(encoding="utf-8")
    assert vtt_content.startswith("WEBVTT\n\n1\n00:00:00.000 --> 00:00:02.000\n第1セグメント")
    assert "\n\n10000\n" in vtt_content

    # Verify JSON length and content
    with open(massive_json, encoding="utf-8") as f:
        loaded = json.load(f)
    assert len(loaded) == 10_000
    assert loaded[9999]["text"] == "第10000セグメントの発言内容です。インデックス: 10000"


def test_file_io_edge_cases(tmp_path: Path) -> None:
    """Test deep directory creation, case-insensitive extensions, invalid formats, overwriting."""
    segs = [SubtitleSegment(start=1.0, end=2.0, text="I/O Test")]

    # 1. Deep directory creation
    deep_path = tmp_path / "deep" / "level1" / "level2" / "level3" / "output.srt"
    assert not deep_path.parent.exists()
    SubtitleExporter.save_subtitles(segs, deep_path)
    assert deep_path.exists()

    # 2. Overwriting existing file
    SubtitleExporter.save_subtitles([SubtitleSegment(start=3.0, end=4.0, text="Overwritten")], deep_path)
    assert "Overwritten" in deep_path.read_text(encoding="utf-8")
    assert "I/O Test" not in deep_path.read_text(encoding="utf-8")

    # 3. Case-insensitive extension handling in save_subtitles
    for ext, expected_first_line in [
        (".SRT", "1\n"),
        (".Srt", "1\n"),
        (".VTT", "WEBVTT"),
        (".Vtt", "WEBVTT"),
        (".JSON", "[\n"),
        (".Json", "[\n"),
    ]:
        p = tmp_path / f"case_test{ext}"
        SubtitleExporter.save_subtitles(segs, p)
        assert p.exists()
        assert p.read_text(encoding="utf-8").startswith(expected_first_line)

    # 4. Explicit fmt overriding extension
    p_override = tmp_path / "override.txt"
    SubtitleExporter.save_subtitles(segs, p_override, fmt="SRT")
    assert "00:00:01,000 --> 00:00:02,000" in p_override.read_text(encoding="utf-8")

    p_override2 = tmp_path / "override2.dat"
    SubtitleExporter.save_subtitles(segs, p_override2, fmt="VTT")
    assert "WEBVTT" in p_override2.read_text(encoding="utf-8")

    p_override3 = tmp_path / "override3.bak"
    SubtitleExporter.save_subtitles(segs, p_override3, fmt="JSON")
    assert json.loads(p_override3.read_text(encoding="utf-8")) == [
        {"start": 1.0, "end": 2.0, "text": "I/O Test"}
    ]

    # 5. Invalid extension error
    with pytest.raises(ValueError, match="未対応の拡張子です"):
        SubtitleExporter.save_subtitles(segs, tmp_path / "invalid.pdf")

    # 6. Invalid fmt error
    with pytest.raises(ValueError, match="未対応のフォーマットです"):
        SubtitleExporter.save_subtitles(segs, tmp_path / "out.srt", fmt="mp4")


def test_subtitle_segment_model_robustness() -> None:
    """Test SubtitleSegment edge cases: malformed dicts, type conversions, negative values."""
    # 1. from_dict with strange types
    data1 = {"start": "10.5", "end": "20.75", "text": 9999}
    seg1 = SubtitleSegment.from_dict(data1)
    assert isinstance(seg1.start, float) and seg1.start == 10.5
    assert isinstance(seg1.end, float) and seg1.end == 20.75
    assert isinstance(seg1.text, str) and seg1.text == "9999"

    # 2. from_dict with missing keys
    data_missing = {}
    seg_missing = SubtitleSegment.from_dict(data_missing)
    assert seg_missing.start == 0.0
    assert seg_missing.end == 0.0
    assert seg_missing.text == ""

    # 3. from_dict with invalid numeric string raises ValueError
    with pytest.raises(ValueError):
        SubtitleSegment.from_dict({"start": "not_a_number"})

    # 4. from_dict with extra keys
    data_extra = {
        "start": 1.0,
        "end": 2.0,
        "text": "test",
        "extra_field": "ignore_me",
        "words": [{"word": "test"}],
    }
    seg_extra = SubtitleSegment.from_dict(data_extra)
    assert seg_extra.start == 1.0
    assert seg_extra.end == 2.0
    assert seg_extra.text == "test"
    assert not hasattr(seg_extra, "extra_field")

    # 5. to_dict produces clean dict
    d = seg_extra.to_dict()
    assert d == {"start": 1.0, "end": 2.0, "text": "test"}

    # 6. dataclass equality and field access
    seg_a = SubtitleSegment(1.0, 2.0, "hello")
    seg_b = SubtitleSegment(1.0, 2.0, "hello")
    assert seg_a == seg_b


def test_davinci_resolve_srt_strict_validation(tmp_path: Path) -> None:
    """Strict validation for DaVinci Resolve import compatibility."""
    segments = [
        SubtitleSegment(0.0, 1.25, "First line"),
        SubtitleSegment(1.5, 3.8, "Second line with comma, and period."),
        SubtitleSegment(4.0, 6.0, "Third line\nSecond subtitle row"),
    ]

    out_srt = tmp_path / "davinci_test.srt"
    SubtitleExporter.save_srt(segments, out_srt)

    # 1. Byte-level checks
    raw_bytes = out_srt.read_bytes()
    # Check no \r
    assert b"\r" not in raw_bytes, "Found CR byte in SRT! DaVinci Resolve requires strict LF."
    # Check UTF-8 validity
    text = raw_bytes.decode("utf-8")

    # 2. Block structure validation
    blocks = text.strip().split("\n\n")
    assert len(blocks) == 3, f"Expected 3 blocks, got {len(blocks)}"

    time_line_pattern = re.compile(
        r"^(\d{2,}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2,}):(\d{2}):(\d{2}),(\d{3})$"
    )

    for i, block in enumerate(blocks, start=1):
        lines = block.split("\n")
        assert lines[0] == str(i), f"Block index mismatch in block {i}: got {lines[0]!r}"
        match = time_line_pattern.match(lines[1])
        assert match is not None, f"Invalid SRT timestamp line in block {i}: {lines[1]!r}"
        h1, m1, s1, ms1, h2, m2, s2, ms2 = (int(x) for x in match.groups())
        assert 0 <= m1 < 60 and 0 <= m2 < 60
        assert 0 <= s1 < 60 and 0 <= s2 < 60
        assert 0 <= ms1 < 1000 and 0 <= ms2 < 1000
        subtitle_text = "\n".join(lines[2:])
        assert len(subtitle_text) > 0, f"Empty text in block {i}"


def test_huge_single_segment_text(tmp_path: Path) -> None:
    """Test massive single subtitle text (100,000 characters)."""
    huge_text = "日本語の長大な字幕テキストです。" * 5000  # ~85,000 chars
    seg = SubtitleSegment(start=0.0, end=100.0, text=huge_text)
    out_srt = tmp_path / "huge.srt"
    out_vtt = tmp_path / "huge.vtt"
    out_json = tmp_path / "huge.json"

    SubtitleExporter.save_srt([seg], out_srt)
    SubtitleExporter.save_vtt([seg], out_vtt)
    SubtitleExporter.save_json([seg], out_json)

    assert out_srt.exists()
    assert huge_text in out_srt.read_text(encoding="utf-8")
    assert out_vtt.exists()
    assert huge_text in out_vtt.read_text(encoding="utf-8")
    assert out_json.exists()
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data[0]["text"] == huge_text


def test_zero_duration_and_unordered_segments(tmp_path: Path) -> None:
    """Test 0 duration segments and verify exporter handles them gracefully."""
    segs = [
        SubtitleSegment(start=10.0, end=10.0, text="瞬時字幕"),
        SubtitleSegment(start=20.0, end=20.0001, text="微小字幕"),
    ]
    out_srt = tmp_path / "zero_dur.srt"
    SubtitleExporter.save_srt(segs, out_srt)
    srt_text = out_srt.read_text(encoding="utf-8")
    assert "00:00:10,000 --> 00:00:10,000" in srt_text
    assert "00:00:20,000 --> 00:00:20,000" in srt_text
