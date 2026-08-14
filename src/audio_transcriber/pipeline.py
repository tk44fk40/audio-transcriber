"""End-to-end pipeline for audio/video denoising, transcription, and remuxing."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from audio_transcriber.config import AppConfig, load_config
from audio_transcriber.denoise import AudioDenoiser, create_denoiser
from audio_transcriber.exporter import SubtitleExporter
from audio_transcriber.media import extract_audio_track, is_video_file, remux_video
from audio_transcriber.postprocess import TextPostProcessor
from audio_transcriber.sanitizer import SegmentSanitizer
from audio_transcriber.timing import SubtitleTimingAdjuster
from audio_transcriber.transcribe import transcribe_audio

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


def run_pipeline(
    input_path: str | Path,
    output_dir: str | Path = "./output",
    model_size: str = "small",
    device: str = "cuda",
    compute_type: str = "float16",
    language: str = "ja",
    initial_prompt: str | None = None,
    denoise: bool = True,
    transcribe: bool = True,
    mic_track: int = 2,
    remux: bool = True,
    vad_filter: bool = True,
    min_silence_duration_ms: int = 500,
    config_path: str | Path | None = None,
    denoiser: AudioDenoiser | None = None,
) -> PipelineResult:
    """Run full pipeline: extract mic track, denoise, transcribe, post-process, and remux.

    Args:
        input_path: Path to input audio or video file.
        output_dir: Directory where output files will be saved.
        model_size: Whisper model size ('tiny', 'base', 'small', 'medium', 'large-v3').
        device: 'cuda' or 'cpu'.
        compute_type: 'float16', 'int8_float16', 'int8', 'float32'.
        language: Language code for transcription.
        initial_prompt: Optional transcription prompt.
        denoise: Whether to perform noise removal and audio enhancement.
        transcribe: Whether to perform faster-whisper transcription.
        mic_track: 1-indexed audio track number to process when input is video (default: 2).
        remux: Whether to produce a remuxed video with replaced mic track (default: True).
        vad_filter: Whether to enable Silero-VAD filtering.
        min_silence_duration_ms: Minimum silence duration in ms for VAD splitting (default: 500).
        config_path: Optional path to config.toml for post-processing settings.
        denoiser: Optional AudioDenoiser instance for dependency injection.

    Returns:
        PipelineResult containing paths to generated files.
    """
    in_p = Path(input_path).resolve()
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = in_p.stem
    is_video = is_video_file(in_p)

    raw_mic_audio: Path
    if is_video:
        raw_mic_audio = out_dir / f"{stem}_track{mic_track}_raw.wav"
        extract_audio_track(
            media_path=in_p,
            track_number=mic_track,
            output_wav=raw_mic_audio,
        )
    else:
        raw_mic_audio = in_p

    denoised_path: Path | None = None
    srt_path: Path | None = None
    vtt_path: Path | None = None
    json_path: Path | None = None
    remuxed_video_path: Path | None = None
    transcript: str | None = None

    audio_to_transcribe = raw_mic_audio

    cfg: AppConfig = load_config(config_path)

    if denoise:
        denoised_path = out_dir / f"{stem}_clean.wav"
        active_denoiser = (
            denoiser if denoiser is not None else create_denoiser(cfg.denoise)
        )
        active_denoiser.denoise(raw_mic_audio, denoised_path)
        audio_to_transcribe = denoised_path

    if transcribe:
        # 設定の読み込み（後処理パラメータ取得）
        pp_cfg = cfg.post_process
        sub_cfg = cfg.subtitle

        # 文字起こし
        srt_raw, segment_dicts = transcribe_audio(
            audio_path=audio_to_transcribe,
            output_srt_path=None,  # 後処理後に出力するため一旦 None
            model_size=model_size,
            device=device,
            compute_type=compute_type,
            language=language,
            initial_prompt=initial_prompt,
            vad_filter=vad_filter,
            min_silence_duration_ms=min_silence_duration_ms,
        )
        transcript = srt_raw

        # セグメントのサニタイズ
        sanitizer = SegmentSanitizer(
            no_speech_threshold=pp_cfg.no_speech_threshold,
            max_chars_per_second=pp_cfg.max_chars_per_second,
        )
        raw_segments = _dicts_to_segment_objects(segment_dicts)
        sanitized = sanitizer.sanitize_segments(raw_segments)

        # テキスト後処理（辞書置換・正規化）
        dict_path = cfg.paths.custom_dict_path
        processor = TextPostProcessor(
            dictionary_path=dict_path if pp_cfg.replace_terms else None,
            to_hankaku=pp_cfg.to_hankaku,
            normalize_nums=pp_cfg.normalize_nums,
            lower=pp_cfg.lower,
            remove_punct=pp_cfg.remove_punct,
        )
        processed = processor.apply_to_segments(sanitized)

        # タイミング補正
        adjuster = SubtitleTimingAdjuster(
            end_padding=sub_cfg.end_padding,
            min_duration=sub_cfg.min_duration,
            min_gap=sub_cfg.min_gap,
        )
        final_segments = adjuster.adjust_segments(processed)

        # 字幕ファイル出力 (SRT / VTT / JSON)
        formats = sub_cfg.formats
        if "srt" in formats:
            srt_path = out_dir / f"{stem}.srt"
            SubtitleExporter.save_srt(final_segments, srt_path)
            logger.info("SRT を出力しました: %s", srt_path)
        if "vtt" in formats:
            vtt_path = out_dir / f"{stem}.vtt"
            SubtitleExporter.save_vtt(final_segments, vtt_path)
            logger.info("VTT を出力しました: %s", vtt_path)
        if "json" in formats:
            json_path = out_dir / f"{stem}.json"
            SubtitleExporter.save_json(final_segments, json_path)
            logger.info("JSON を出力しました: %s", json_path)

    if is_video and remux and denoised_path and denoised_path.exists():
        output_ext = in_p.suffix
        remuxed_video_path = out_dir / f"{stem}_clean{output_ext}"
        remux_video(
            original_video=in_p,
            mic_track_number=mic_track,
            clean_audio=denoised_path,
            output_video=remuxed_video_path,
        )

    return PipelineResult(
        input_file=in_p,
        denoised_audio=denoised_path,
        srt_file=srt_path,
        transcript_text=transcript,
        remuxed_video=remuxed_video_path,
        vtt_file=vtt_path,
        json_file=json_path,
    )


def _dicts_to_segment_objects(segment_dicts: list[dict[str, Any]]) -> list[Any]:
    """segment_dicts を sanitizer が受け付けるオブジェクトに変換します。

    Args:
        segment_dicts (list[dict[str, Any]]): transcribe_audio が返すセグメント辞書リスト。

    Returns:
        list[Any]: 属性アクセス可能なセグメントオブジェクトリスト。
    """
    return segment_dicts  # sanitizer は dict にも対応しているためそのまま渡す
