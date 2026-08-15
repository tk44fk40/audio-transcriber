"""End-to-end pipeline for audio/video denoising, transcription, and remuxing."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from audio_transcriber.config import AppConfig
from audio_transcriber.denoise import AudioDenoiser, create_denoiser
from audio_transcriber.exporter import SubtitleExporter
from audio_transcriber.media import (
    extract_audio_track,
    get_timecode_offset,
    is_video_file,
    remux_video,
)
from audio_transcriber.postprocess import TextPostProcessor
from audio_transcriber.sanitizer import SegmentSanitizer
from audio_transcriber.stt import FasterWhisperProvider, TranscriberProvider
from audio_transcriber.timing import SubtitleTimingAdjuster

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
    cfg: AppConfig,
    denoise: bool = True,
    transcribe: bool = True,
    denoiser: AudioDenoiser | None = None,
    transcriber: TranscriberProvider | None = None,
    on_progress: Callable[[str, str], None] | None = None,
    on_segment: Callable[[dict[str, Any]], None] | None = None,
) -> PipelineResult:
    """Run full pipeline: extract mic track, denoise, transcribe, post-process, and remux."""
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

    if transcribe:
        if on_progress:
            on_progress(
                "transcribe",
                f"Whisper ({cfg.model.model_size}) による文字起こし推論中...",
            )
        pp_cfg = cfg.post_process
        sub_cfg = cfg.subtitle

        def _internal_on_segment(seg_dict: dict[str, Any]) -> None:
            if on_segment is not None:
                mapped = dict(seg_dict)
                mapped["start"] = float(seg_dict.get("start", 0.0)) + timecode_offset
                mapped["end"] = float(seg_dict.get("end", 0.0)) + timecode_offset
                if seg_dict.get("words"):
                    new_words = []
                    for w in seg_dict["words"]:
                        if isinstance(w, dict):
                            new_w = dict(w)
                            new_w["start"] = (
                                float(w.get("start", 0.0)) + timecode_offset
                            )
                            new_w["end"] = float(w.get("end", 0.0)) + timecode_offset
                            new_words.append(new_w)
                    mapped["words"] = new_words
                on_segment(mapped)

        active_transcriber = transcriber
        if active_transcriber is None:
            active_transcriber = FasterWhisperProvider(
                model_size=cfg.model.model_size,
                device=cfg.model.device,
                compute_type=cfg.model.compute_type,
                language=cfg.transcribe.language,
                initial_prompt=cfg.transcribe.initial_prompt,
                vad_filter=cfg.transcribe.vad.vad_filter,
                vad_parameters={
                    "threshold": cfg.transcribe.vad.vad_threshold,
                    "min_silence_duration_ms": cfg.transcribe.vad.min_silence_duration_ms,
                },
                beam_size=cfg.transcribe.beam_size,
                condition_on_previous_text=cfg.transcribe.condition_on_previous_text,
                no_speech_threshold=cfg.transcribe.no_speech_threshold,
            )

        segment_dicts = active_transcriber.transcribe_file(
            file_path=audio_to_transcribe,
            on_segment=_internal_on_segment,
            on_progress=on_progress,
        )

        # タイムコードオフセットを適用したセグメントリストに変換
        offset_segment_dicts = []
        for d in segment_dicts:
            new_d = dict(d)
            new_d["start"] = float(d["start"]) + timecode_offset
            new_d["end"] = float(d["end"]) + timecode_offset
            if d.get("words"):
                new_words = []
                for w in d["words"]:
                    if isinstance(w, dict):
                        new_w = dict(w)
                        new_w["start"] = float(w.get("start", 0.0)) + timecode_offset
                        new_w["end"] = float(w.get("end", 0.0)) + timecode_offset
                        new_words.append(new_w)
                new_d["words"] = new_words
            offset_segment_dicts.append(new_d)

        raw_count = len(offset_segment_dicts)
        if on_progress:
            on_progress(
                "postprocess_start",
                f"字幕サニタイズ ＆ テキスト後処理を開始 (生セグメント: {raw_count}件)...",
            )

        sanitizer = SegmentSanitizer(
            no_speech_threshold=pp_cfg.no_speech_threshold,
            max_chars_per_second=pp_cfg.max_chars_per_second,
        )
        sanitized = sanitizer.sanitize_segments(offset_segment_dicts)
        dropped_count = raw_count - len(sanitized)

        if on_progress:
            sanitized_ids = {
                (
                    round(
                        float(
                            getattr(
                                s,
                                "start",
                                s.get("start", 0.0) if isinstance(s, dict) else 0.0,
                            )
                        ),
                        3,
                    ),
                    round(
                        float(
                            getattr(
                                s,
                                "end",
                                s.get("end", 0.0) if isinstance(s, dict) else 0.0,
                            )
                        ),
                        3,
                    ),
                )
                for s in sanitized
            }
            for raw_seg in offset_segment_dicts:
                key = (
                    round(float(raw_seg["start"]), 3),
                    round(float(raw_seg["end"]), 3),
                )
                if key not in sanitized_ids:
                    s_str = SubtitleExporter.format_timestamp(float(raw_seg["start"]))
                    dur = float(raw_seg["end"]) - float(raw_seg["start"])
                    on_progress(
                        "postprocess_dropped",
                        f"[除外] {s_str} ({dur:.1f}s) '{raw_seg['text']}' (無音捏造/高速ループ)",
                    )

        dict_path = cfg.paths.custom_dict_path
        processor = TextPostProcessor(
            dictionary_path=dict_path if pp_cfg.replace_terms else None,
            to_hankaku=pp_cfg.to_hankaku,
            normalize_nums=pp_cfg.normalize_nums,
            lower=pp_cfg.lower,
            remove_punct=pp_cfg.remove_punct,
        )
        processed = processor.apply_to_segments(sanitized)
        replaced_count = 0

        if on_progress:
            for before_seg, after_seg in zip(sanitized, processed, strict=False):
                b_text = (
                    before_seg.get("text", "")
                    if isinstance(before_seg, dict)
                    else getattr(before_seg, "text", "")
                )
                a_text = getattr(after_seg, "text", "")
                if b_text != a_text:
                    replaced_count += 1
                    s_str = SubtitleExporter.format_timestamp(
                        float(getattr(after_seg, "start", 0.0))
                    )
                    on_progress(
                        "postprocess_replaced",
                        f"[置換・正規化] {s_str}: '{b_text}' ➔ '{a_text}'",
                    )

        adjuster = SubtitleTimingAdjuster(
            end_padding=sub_cfg.end_padding,
            min_duration=sub_cfg.min_duration,
            min_gap=sub_cfg.min_gap,
        )
        final_segments = adjuster.adjust_segments(processed)
        overlap_prevented_count = 0

        if on_progress:
            for i, (p_seg, f_seg) in enumerate(
                zip(processed, final_segments, strict=False)
            ):
                if i + 1 < len(processed):
                    next_start = getattr(processed[i + 1], "start", 0.0)
                    p_end = getattr(p_seg, "end", 0.0)
                    p_start = getattr(p_seg, "start", 0.0)
                    raw_target_end = max(
                        p_end + sub_cfg.end_padding, p_start + sub_cfg.min_duration
                    )
                    f_end = getattr(f_seg, "end", 0.0)
                    if raw_target_end > f_end and (
                        raw_target_end > next_start - sub_cfg.min_gap
                    ):
                        overlap_prevented_count += 1
                        txt = getattr(f_seg, "text", "")
                        on_progress(
                            "postprocess_overlap_prevented",
                            f"[重複防止] '{txt}': 終了時刻 {SubtitleExporter.format_timestamp(raw_target_end)} ➔ {SubtitleExporter.format_timestamp(f_end)} (次発話 {SubtitleExporter.format_timestamp(next_start)} との重複を回避)",
                        )
            on_progress(
                "postprocess_summary",
                f"サマリー: {raw_count}件中 {dropped_count}件除外、{replaced_count}件置換、{overlap_prevented_count}件重複防止 (確定字幕: {len(final_segments)}件)",
            )

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

        transcript = "\n\n".join(
            f"{i}\n{SubtitleExporter.format_timestamp(getattr(s, 'start', 0.0))} --> "
            f"{SubtitleExporter.format_timestamp(getattr(s, 'end', 0.0))}\n{getattr(s, 'text', '')}"
            for i, s in enumerate(final_segments, start=1)
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
    )
