"""ストリーミングパイプライン用のコールバック定義モジュール。"""

from typing import Protocol, runtime_checkable

from audio_transcriber.models import RecognizedSegment, SoundEvent, VadState


@runtime_checkable
class PipelineCallbacks(Protocol):
    """ストリーミングパイプラインのイベントを受け取るコールバックProtocol。"""

    def on_vad_state_change(self, state: VadState) -> None:
        """VAD状態が変化した際に呼ばれます。"""
        ...

    def on_speech_start(self, timestamp: float) -> None:
        """発話開始が検出された際に呼ばれます。"""
        ...

    def on_speech_end(self, timestamp: float) -> None:
        """発話終了が検出された際に呼ばれます。"""
        ...

    def on_segment_recognized(self, segment: RecognizedSegment) -> None:
        """音声区間の認識が完了した際に呼ばれます。"""
        ...

    def on_partial_recognized(self, segment: RecognizedSegment) -> None:
        """部分的な音声区間の認識が完了した際に呼ばれます（ストリーミング途中経過）。"""
        ...

    def on_sound_event(self, event: SoundEvent) -> None:
        """音響イベントが検出された際に呼ばれます。"""
        ...

    def on_error(self, error: BaseException) -> None:
        """パイプライン処理中にエラーが発生した際に呼ばれます。"""
        ...


class BasePipelineCallbacks(PipelineCallbacks):
    """PipelineCallbacks のデフォルト実装（何もしない）。

    必要に応じてサブクラスでメソッドをオーバーライドして使用します。
    """

    def on_vad_state_change(self, state: VadState) -> None:
        """VAD状態が変化した際に呼ばれます。"""
        pass

    def on_speech_start(self, timestamp: float) -> None:
        """発話開始が検出された際に呼ばれます。"""
        pass

    def on_speech_end(self, timestamp: float) -> None:
        """発話終了が検出された際に呼ばれます。"""
        pass

    def on_segment_recognized(self, segment: RecognizedSegment) -> None:
        """音声区間の認識が完了した際に呼ばれます。"""
        pass

    def on_partial_recognized(self, segment: RecognizedSegment) -> None:
        """部分的な音声区間の認識が完了した際に呼ばれます（ストリーミング途中経過）。"""
        pass

    def on_sound_event(self, event: SoundEvent) -> None:
        """音響イベントが検出された際に呼ばれます。"""
        pass

    def on_error(self, error: BaseException) -> None:
        """パイプライン処理中にエラーが発生した際に呼ばれます。"""
        pass
