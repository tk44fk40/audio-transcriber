"""Transcription module using faster-whisper and SRT generation."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel


def format_timestamp(seconds: float) -> str:
    """Format seconds into SRT timestamp format (HH:MM:SS,mmm)."""
    assert seconds >= 0, "non-negative timestamp expected"
    milliseconds = round(seconds * 1000.0)

    hours = milliseconds // 3_600_000
    milliseconds -= hours * 3_600_000

    minutes = milliseconds // 60_000
    milliseconds -= minutes * 60_000

    secs = milliseconds // 1_000
    milliseconds -= secs * 1_000

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def segments_to_srt(segments: Iterable[Any]) -> str:
    """Convert faster-whisper segments to standard SRT format string."""
    srt_entries = []
    for i, segment in enumerate(segments, start=1):
        start_str = format_timestamp(segment.start)
        end_str = format_timestamp(segment.end)
        text = segment.text.strip()
        srt_entries.append(f"{i}\n{start_str} --> {end_str}\n{text}\n")
    return "\n".join(srt_entries)


def transcribe_audio(
    audio_path: str | Path,
    output_srt_path: str | Path | None = None,
    model_size: str = "small",
    device: str = "cuda",
    compute_type: str = "float16",
    language: str = "ja",
    initial_prompt: str | None = None,
    vad_filter: bool = True,
    min_silence_duration_ms: int = 500,
) -> tuple[str, list[dict[str, Any]]]:
    """Transcribe audio file using faster-whisper and optionally save as SRT.

    Args:
        audio_path: Path to the input audio file.
        output_srt_path: Optional path where the SRT file will be saved.
        model_size: Whisper model size ('tiny', 'base', 'small', 'medium', 'large-v3').
        device: Device to run inference on ('cuda' or 'cpu').
        compute_type: Quantization type ('float16', 'int8_float16', 'int8', 'float32').
        language: Language code ('ja' for Japanese).
        initial_prompt: Optional initial prompt to guide transcription context.
        vad_filter: Whether to enable Silero-VAD filtering.
        min_silence_duration_ms: Minimum silence duration in ms for VAD splitting (default: 500).

    Returns:
        Tuple of (SRT formatted text string, list of segment dictionaries).
    """
    audio_p = Path(audio_path)
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    segments_gen, _info = model.transcribe(
        str(audio_p),
        language=language,
        initial_prompt=initial_prompt,
        vad_filter=vad_filter,
        vad_parameters=dict(min_silence_duration_ms=min_silence_duration_ms),
    )

    segment_list = list(segments_gen)
    srt_content = segments_to_srt(segment_list)

    if output_srt_path:
        out_p = Path(output_srt_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(srt_content, encoding="utf-8")

    segment_dicts = [
        {
            "id": s.id,
            "start": s.start,
            "end": s.end,
            "text": s.text.strip(),
        }
        for s in segment_list
    ]

    return srt_content, segment_dicts
