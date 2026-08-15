"""テスト: ストリーミングコールバック"""

from audio_transcriber.callbacks import BasePipelineCallbacks
from audio_transcriber.models import RecognizedSegment, SoundEvent, VadState


def test_base_pipeline_callbacks():
    """BasePipelineCallbacks がデフォルトで例外を投げず、正しく動作することを確認。"""
    callbacks = BasePipelineCallbacks()

    # 呼び出しでエラーにならないことだけを確認
    callbacks.on_vad_state_change(VadState.SPEECH)
    callbacks.on_speech_start(1.0)
    callbacks.on_speech_end(2.0)

    seg = RecognizedSegment(start=1.0, end=2.0, text="test")
    callbacks.on_segment_recognized(seg)
    callbacks.on_partial_recognized(seg)

    event = SoundEvent(event_type="test", timestamp=1.0)
    callbacks.on_sound_event(event)

    callbacks.on_error(ValueError("test error"))
