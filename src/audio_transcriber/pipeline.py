"""End-to-end pipeline for audio/video denoising, transcription, and remuxing."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from audio_transcriber.config import AppConfig
from audio_transcriber.denoise import AudioDenoiser, create_denoiser
from audio_transcriber.media import (
    extract_audio_track,
    get_timecode_offset,
    is_video_file,
    remux_video,
)
from audio_transcriber.models import SubtitleSegment
from audio_transcriber.pipeline_events import (
    TranscriptionPipelineCollector,
    export_pipeline_subtitles,
)
from audio_transcriber.stt import FasterWhisperProvider, TranscriberProvider

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of audio/video processing pipeline."""

    input_file: Path
    denoised_audio: Path | None
    srt_file: Path | None
    transcript_text: str | None
    remuxed_video: Path | None = None
    vtt_file: Path | None = None
    json_file: Path | None = None
    vad_chunks: list[tuple[float, float]] = field(default_factory=list)
    raw_segments: list[dict[str, Any]] = field(default_factory=list)
    sanitized_segments: list[SubtitleSegment] = field(default_factory=list)
    processed_segments: list[SubtitleSegment] = field(default_factory=list)
    final_segments: list[SubtitleSegment] = field(default_factory=list)
    processing_events: list[dict[str, Any]] = field(default_factory=list)


def run_pipeline(
    input_path: str | Path,
    cfg: AppConfig,
    denoise: bool = True,
    transcribe: bool = True,
    denoiser: AudioDenoiser | None = None,
    transcriber: TranscriberProvider | None = None,
    on_progress: Callable[[str, Any], None] | None = None,
    on_segment: Callable[[dict[str, Any]], None] | None = None,
) -> PipelineResult:
    """Run full pipeline: extract mic track, denoise, transcribe, post-process, and remux.

    Args:
        input_path: Path to the input media file (audio or video).
        cfg: Application configuration settings.
        denoise: Whether to apply RNNoise noise reduction.
        transcribe: Whether to run Whisper transcription.
        denoiser: Optional pre-configured AudioDenoiser instance.
        transcriber: Optional pre-configured TranscriberProvider instance.
        on_progress: Optional progress notification callback.
        on_segment: Optional segment recognized notification callback.

    Returns:
        PipelineResult: Result object containing generated file paths and segments.
    """
    in_p = Path(input_path).resolve()
    out_dir = cfg.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = in_p.stem
    is_video = is_video_file(in_p)
    timecode_offset = get_timecode_offset(in_p) if is_video else 0.0

    raw_mic_audio: Path
    if is_video:
        if on_progress:
            on_progress(
                "extract",
                f"マイク音声トラック {cfg.media.mic_track} を動画から抽出中...",
            )
        raw_mic_audio = out_dir / f"{stem}_track{cfg.media.mic_track}_raw.wav"
        extract_audio_track(
            media_path=in_p,
            track_number=cfg.media.mic_track,
            output_wav=raw_mic_audio,
        )
    else:
        raw_mic_audio = in_p

    if timecode_offset > 0.001 and on_progress:
        on_progress(
            "timecode",
            f"動画タイムコードを検出: 開始オフセット +{timecode_offset:.3f}s を字幕・進捗ログに適用します",
        )

    denoised_path: Path | None = None
    srt_path: Path | None = None
    vtt_path: Path | None = None
    json_path: Path | None = None
    remuxed_video_path: Path | None = None
    transcript: str | None = None

    audio_to_transcribe = raw_mic_audio

    if denoise:
        if on_progress:
            on_progress("denoise", "RNNoise によるノイズ除去中...")
        denoised_path = out_dir / f"{stem}_clean.wav"
        active_denoiser = (
            denoiser if denoiser is not None else create_denoiser(cfg.denoise)
        )
        active_denoiser.denoise(raw_mic_audio, denoised_path)
        audio_to_transcribe = denoised_path

    collector: TranscriptionPipelineCollector | None = None
    final_segments: list[SubtitleSegment] = []

    if transcribe:
        if on_progress:
            on_progress(
                "transcribe",
                f"Whisper ({cfg.model.model_size}) による文字起こし推論中...",
            )

        collector = TranscriptionPipelineCollector(
            cfg=cfg,
            timecode_offset=timecode_offset,
            on_progress=on_progress,
            on_segment=on_segment,
        )

        active_transcriber = transcriber
        if active_transcriber is None:
            active_transcriber = FasterWhisperProvider(
                model_size=cfg.model.model_size,
                device=cfg.model.device,
                compute_type=cfg.model.compute_type,
                language=cfg.transcribe.language,
                initial_prompt=cfg.transcribe.initial_prompt,
                vad_parameters={
                    "threshold": cfg.transcribe.vad.vad_threshold,
                    "min_silence_duration_ms": cfg.transcribe.vad.min_silence_duration_ms,
                },
                beam_size=cfg.transcribe.beam_size,
                condition_on_previous_text=cfg.transcribe.condition_on_previous_text,
                no_speech_threshold=cfg.transcribe.no_speech_threshold,
            )

        active_transcriber.transcribe_file(
            file_path=audio_to_transcribe,
            on_segment=collector.handle_segment,
            on_progress=collector.handle_progress,
        )

        final_segments = collector.finalize_timing_and_summary(cfg.subtitle)
        srt_path, vtt_path, json_path, transcript = export_pipeline_subtitles(
            final_segments=final_segments,
            formats=cfg.subtitle.formats,
            out_dir=out_dir,
            stem=stem,
        )

    if is_video and cfg.pipeline.remux and denoised_path and denoised_path.exists():
        output_ext = in_p.suffix
        remuxed_video_path = out_dir / f"{stem}_clean{output_ext}"
        if on_progress:
            on_progress("remux", "クリーン音声で動画を再結合中 (Remux)...")
        remux_video(
            original_video=in_p,
            mic_track_number=cfg.media.mic_track,
            clean_audio=denoised_path,
            output_video=remuxed_video_path,
        )

    if on_progress:
        on_progress("done", "全処理が完了しました。")

    return PipelineResult(
        input_file=in_p,
        denoised_audio=denoised_path,
        srt_file=srt_path,
        transcript_text=transcript,
        remuxed_video=remuxed_video_path,
        vtt_file=vtt_path,
        json_file=json_path,
        vad_chunks=collector.vad_chunks_collected if collector else [],
        raw_segments=collector.offset_segment_dicts if collector else [],
        sanitized_segments=collector.sanitized_segments if collector else [],
        processed_segments=collector.processed_segments if collector else [],
        final_segments=final_segments,
        processing_events=collector.processing_events if collector else [],
    )
