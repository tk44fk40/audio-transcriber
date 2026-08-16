"""パイプラインのエクスポート・ポストプロセス統合・単語ギャップ分割・辞書置換の単体テスト。"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from audio_transcriber.config import AppConfig
from audio_transcriber.pipeline import run_pipeline
from audio_transcriber.stt import TranscriberProvider


class MockPipelineCoverageTranscriber(TranscriberProvider):
    """詳細なパイプラインカバレッジ検証用モックプロバイダー。"""

    def transcribe_file(
        self,
        file_path: Path | str,
        on_segment: Any = None,
        on_progress: Any = None,
    ) -> list[dict[str, Any]]:
        if on_progress:
            on_progress("vad_chunks", [(0.0, 1.0)])

        segment = {
            "start": 0.0,
            "end": 5.0,
            "text": "Hello BAD_WORD. This is test.",
            "words": [
                {"start": 0.0, "end": 1.0, "word": "Hello "},
                {"start": 3.0, "end": 4.0, "word": "BAD_WORD. "},
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

    def transcribe_stream(
        self,
        audio: Any,
        initial_prompt: str | None = None,
        on_segment: Any = None,
    ) -> list[dict[str, Any]]:
        return []


@patch("audio_transcriber.pipeline.is_video_file", return_value=True)
@patch("audio_transcriber.pipeline.get_timecode_offset", return_value=1.5)
@patch("audio_transcriber.pipeline.extract_audio_track")
@patch("audio_transcriber.pipeline.create_denoiser")
@patch("audio_transcriber.pipeline.FasterWhisperProvider")
@patch("audio_transcriber.pipeline.remux_video")
@patch("audio_transcriber.exporter.SubtitleExporter.save_srt")
@patch("audio_transcriber.exporter.SubtitleExporter.save_vtt")
@patch("audio_transcriber.exporter.SubtitleExporter.save_json")
def test_pipeline_coverage_full_and_postprocessing(
    mock_save_json: MagicMock,
    mock_save_vtt: MagicMock,
    mock_save_srt: MagicMock,
    mock_remux: MagicMock,
    mock_fw_provider: MagicMock,
    mock_create_denoiser: MagicMock,
    mock_extract: MagicMock,
    mock_timecode: MagicMock,
    mock_is_video: MagicMock,
    tmp_path: Path,
) -> None:
    """全ステージ通過とテキスト置換・重複防止・VADチャンク収集を検証。"""
    mock_fw_instance = MagicMock()
    mock_fw_provider.return_value = mock_fw_instance
    mock_fw_instance.transcribe_file = MockPipelineCoverageTranscriber().transcribe_file

    cfg = AppConfig()
    cfg.paths.output_dir = tmp_path
    cfg.pipeline.remux = True
    cfg.subtitle.formats = ["srt", "vtt", "json"]
    cfg.subtitle.end_padding = 0.5
    cfg.subtitle.min_duration = 1.0
    cfg.subtitle.min_gap = 0.1
    cfg.post_process.no_speech_threshold = 0.9
    cfg.post_process.replace_terms = True
    cfg.paths.custom_dict_path = tmp_path / "dict.toml"
    (tmp_path / "dict.toml").write_text('BAD_WORD = "GOOD_WORD"')

    in_video = tmp_path / "test_video.mp4"
    in_video.write_text("dummy")

    mock_denoiser = MagicMock()
    mock_denoiser.denoise.side_effect = lambda raw, out: out.write_text("dummy")
    mock_create_denoiser.return_value = mock_denoiser

    progress_messages: list[tuple[str, str]] = []
    res = run_pipeline(
        input_path=in_video,
        cfg=cfg,
        denoise=True,
        transcribe=True,
        transcriber=None,
        on_progress=lambda stage, msg: progress_messages.append((stage, msg)),
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
    assert "postprocess_drop_no_speech" in stages
    assert "postprocess_replaced" in stages
    assert "postprocess_overlap_prevented" in stages

    assert len(res.vad_chunks) == 1
    assert res.vad_chunks[0] == (1.5, 2.5)


def test_pipeline_word_gap_split_and_replacement_details(tmp_path: Path) -> None:
    """単語ギャップ分割とテキスト置換の具体値を厳密に検証。"""
    dummy_wav = tmp_path / "test.wav"
    dummy_wav.write_bytes(b"data")

    cfg = AppConfig()
    cfg.paths.output_dir = tmp_path / "output"
    cfg.stream.word_gap_split_threshold = 1.0
    cfg.post_process.replace_terms = True

    dict_path = tmp_path / "dict.json"
    dict_path.write_text('{"badword": "goodword"}')
    cfg.paths.custom_dict_path = dict_path

    transcriber = MagicMock()

    def fake_transcribe(
        file_path: Any, on_segment: Any = None, on_progress: Any = None
    ) -> list[dict[str, Any]]:
        if on_progress:
            on_progress("vad_chunks", [(0.0, 1.0), (3.0, 4.0)])
        if on_segment:
            on_segment(
                {"start": 0.0, "end": 0.5, "text": "silence", "no_speech_prob": 0.99}
            )
            on_segment(
                {
                    "start": 0.5,
                    "end": 5.0,
                    "text": "hello badword bye",
                    "no_speech_prob": 0.0,
                    "words": [
                        {"start": 0.5, "end": 1.0, "word": "hello "},
                        {"start": 3.0, "end": 3.5, "word": "badword "},
                        {"start": 3.6, "end": 5.0, "word": "bye"},
                    ],
                }
            )
        return []

    transcriber.transcribe_file = MagicMock(side_effect=fake_transcribe)

    result = run_pipeline(
        input_path=dummy_wav,
        cfg=cfg,
        denoise=False,
        transcribe=True,
        transcriber=transcriber,
    )

    assert result.final_segments is not None
    assert len(result.final_segments) >= 2
    # 単語ギャップで分割され、badwordがgoodwordに置換されていることを厳密アサート
    texts = [s.text for s in result.final_segments]
    assert "hello" in texts[0]
    assert "goodword" in texts[1]
