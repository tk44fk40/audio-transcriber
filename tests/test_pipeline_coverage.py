from unittest.mock import MagicMock, patch

from audio_transcriber.config import AppConfig
from audio_transcriber.pipeline import run_pipeline
from audio_transcriber.stt import TranscriberProvider


class MockTranscriber(TranscriberProvider):
    def transcribe_file(self, file_path, on_segment=None, on_progress=None):
        if on_progress:
            on_progress("vad_chunks", [(0.0, 1.0)])

        segment = {
            "start": 0.0,
            "end": 5.0,
            "text": "Hello BAD_WORD. This is test.",
            "words": [
                {"start": 0.0, "end": 1.0, "word": "Hello "},
                {"start": 3.0, "end": 4.0, "word": "BAD_WORD. "},  # Gap >= 1.0
                {"start": 4.0, "end": 5.0, "word": "This is test."},
            ],
        }

        dropped_segment = {
            "start": 6.0,
            "end": 6.5,
            "text": "silence loop",
            "no_speech_prob": 0.99,
            "words": [],
        }

        overlap_segment_1 = {
            "start": 7.0,
            "end": 10.0,
            "text": "overlap start",
            "words": [],
        }
        overlap_segment_2 = {
            "start": 10.1,
            "end": 12.0,
            "text": "overlap end",
            "words": [],
        }

        segments = [segment, dropped_segment, overlap_segment_1, overlap_segment_2]

        for s in segments:
            if on_segment:
                on_segment(s)

        return segments


@patch("audio_transcriber.pipeline.is_video_file")
@patch("audio_transcriber.pipeline.get_timecode_offset")
@patch("audio_transcriber.pipeline.extract_audio_track")
@patch("audio_transcriber.pipeline.create_denoiser")
@patch("audio_transcriber.pipeline.FasterWhisperProvider")
@patch("audio_transcriber.pipeline.remux_video")
@patch("audio_transcriber.exporter.SubtitleExporter.save_srt")
@patch("audio_transcriber.exporter.SubtitleExporter.save_vtt")
@patch("audio_transcriber.exporter.SubtitleExporter.save_json")
def test_pipeline_coverage_full(
    mock_save_json,
    mock_save_vtt,
    mock_save_srt,
    mock_remux,
    mock_fw_provider,
    mock_create_denoiser,
    mock_extract,
    mock_timecode,
    mock_is_video,
    tmp_path,
):
    mock_is_video.return_value = True
    mock_timecode.return_value = 1.5

    mock_fw_instance = MagicMock()
    mock_fw_provider.return_value = mock_fw_instance
    mock_fw_instance.transcribe_file = MockTranscriber().transcribe_file

    cfg = AppConfig()
    cfg.paths.output_dir = tmp_path
    cfg.pipeline.remux = True
    cfg.subtitle.formats = ["srt", "vtt", "json"]
    cfg.subtitle.end_padding = 0.5
    cfg.subtitle.min_duration = 1.0
    cfg.subtitle.min_gap = 0.1
    cfg.post_process.no_speech_threshold = 0.9  # to drop the loop segment
    cfg.post_process.replace_terms = True
    cfg.paths.custom_dict_path = tmp_path / "dict.toml"

    (tmp_path / "dict.toml").write_text('BAD_WORD = "GOOD_WORD"')

    in_video = tmp_path / "test_video.mp4"
    in_video.write_text("dummy")

    # We create a dummy denoised file so remux_video can see it exists
    def side_effect_denoise(raw, out):
        out.write_text("dummy")

    mock_denoiser = MagicMock()
    mock_denoiser.denoise.side_effect = side_effect_denoise
    mock_create_denoiser.return_value = mock_denoiser

    progress_messages = []

    def on_prog(stage, msg):
        progress_messages.append((stage, msg))

    res = run_pipeline(
        input_path=in_video,
        cfg=cfg,
        denoise=True,
        transcribe=True,
        transcriber=None,  # forces creating FasterWhisperProvider
        on_progress=on_prog,
        on_segment=lambda s: None,
    )

    assert res is not None
    assert mock_remux.called
    assert mock_save_srt.called
    assert mock_save_vtt.called
    assert mock_save_json.called

    stages = [p[0] for p in progress_messages]
    assert "extract" in stages
    assert "timecode" in stages
    assert "remux" in stages
    assert "postprocess_dropped" in stages
    assert "postprocess_replaced" in stages
    assert "postprocess_overlap_prevented" in stages

    # Check vad chunks collected
    assert len(res.vad_chunks) == 1
    assert res.vad_chunks[0] == (1.5, 2.5)


def test_pipeline_coverage_abort(tmp_path):
    mock_extract = MagicMock(side_effect=Exception("extract error"))
    with patch("audio_transcriber.pipeline.extract_audio_track", mock_extract):
        with patch("audio_transcriber.pipeline.is_video_file", return_value=True):
            in_video = tmp_path / "test_video.mp4"
            in_video.write_text("dummy")
            try:
                run_pipeline(in_video, AppConfig(), denoise=False, transcribe=False)
            except Exception:
                pass
