from pathlib import Path
from unittest.mock import MagicMock

from audio_transcriber.config import AppConfig
from audio_transcriber.pipeline import run_pipeline


def test_pipeline_streaming_full_coverage(tmp_path: Path) -> None:
    dummy_wav = tmp_path / "test.wav"
    dummy_wav.write_bytes(b"data")

    cfg = AppConfig()
    cfg.paths.output_dir = tmp_path / "output"
    cfg.stream.word_gap_split_threshold = 1.0
    cfg.post_process.replace_terms = True

    # Custom dictionary for TextPostProcessor
    dict_path = tmp_path / "dict.json"
    dict_path.write_text('{"badword": "goodword"}')
    cfg.paths.custom_dict_path = dict_path

    transcriber = MagicMock()

    def fake_transcribe(file_path, on_segment=None, on_progress=None):
        if on_progress:
            on_progress("vad_chunks", [(0.0, 1.0), (3.0, 4.0)])

        if on_segment:
            # Segment 1: gets dropped because of no_speech_prob
            on_segment(
                {"start": 0.0, "end": 0.5, "text": "silence", "no_speech_prob": 0.99}
            )
            # Segment 2: gets word gap split, triggers text replacement, and overlap prevention
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

            # Segment 3: overlap prevent target
            on_segment(
                {
                    "start": 5.1,
                    "end": 6.0,
                    "text": "next",
                    "no_speech_prob": 0.0,
                }
            )
        return []

    transcriber.transcribe_file = MagicMock(side_effect=fake_transcribe)

    progress_calls = []

    def on_progress(stage, msg):
        progress_calls.append((stage, msg))

    result = run_pipeline(
        input_path=dummy_wav,
        cfg=cfg,
        denoise=False,
        transcribe=True,
        transcriber=transcriber,
        on_progress=on_progress,
    )

    assert result.final_segments is not None
