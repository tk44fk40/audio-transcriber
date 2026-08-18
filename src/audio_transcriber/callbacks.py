"""ストリーミングパイプライン用のコールバック定義。

音声活動検出（VAD）の開始・終了イベント、状態遷移、文字認識確定、
およびパイプライン異常終了等のエラーイベントを外部システムへリアルタイムに
通知するためのコールバックインターフェース（Protocol）と、
そのデフォルト実装を提供します。
"""

from typing import Protocol, runtime_checkable

from audio_transcriber.models import RecognizedSegment, SoundEvent, VadState


@runtime_checkable
class PipelineCallbacks(Protocol):
    """リアルタイムイベント受信用のコールバック。

    本プロトコルは、文字起こし全体のライフサイクルイベントをリスンする
    インターフェースとして機能します。
    すべてのコールバックメソッドはブロッキングを避け、
    迅速に呼び出し元に復帰する設計を推奨します。
    """

    def on_vad_state_change(self, state: VadState) -> None:
        """VADの状態変化時に呼び出されます。

        Args:
            state (VadState): 移行後の新しいVAD状態
                （例: VadState.SILENCE, VadState.SPEECH,
                VadState.SPEECH_START, VadState.SPEECH_END）。

        Returns:
            None
        """
        ...

    def on_speech_start(self, timestamp: float) -> None:
        """発話区間の開始検出時に呼び出されます。

        Args:
            timestamp (float): 発話開始と判定された絶対/相対タイムコード（秒）。
                入力ソース（動画・配信・キャプチャ）の開始地点からの経過秒数です。

        Returns:
            None
        """
        ...

    def on_speech_end(self, timestamp: float) -> None:
        """発話区間の終了検出時に呼び出されます。

        Args:
            timestamp (float): 発話終了と判定された絶対/相対タイムコード（秒）。
                入力ソース（動画・配信・キャプチャ）の開始地点からの経過秒数です。

        Returns:
            None
        """
        ...

    def on_segment_recognized(self, segment: RecognizedSegment) -> None:
        """音声認識の確定時に呼び出されます。

        Args:
            segment (RecognizedSegment): 完全に確定された認識結果。
                - segment.start (float): 発話全体の開始を基準とした、
                  このセグメントの開始オフセット（秒単位）。
                - segment.end (float): 発話全体の開始を基準とした、
                  このセグメントの終了オフセット（秒単位）。
                - segment.text (str): ハルシネーションフィルタや専門用語置換・
                  小文字化を適用し終えた最終文字起こしテキスト。
                - segment.confidence (float): 該当セグメントの信頼スコア
                  （0.0 〜 1.0、デフォルトは 0.99）。
                - segment.words (list | None): 単語単位（Word-level）の
                  アライメント詳細情報が存在する場合に、
                  格納されるオブジェクトのリスト。

        Returns:
            None
        """
        ...

    def on_partial_recognized(self, segment: RecognizedSegment) -> None:
        """部分的な音声認識の完了時に呼び出されます。

        Args:
            segment (RecognizedSegment): 処理途中の認識結果。
                - segment.start (float): 現在認識を試みている途中の部分区間の
                  開始時刻（秒）。
                - segment.end (float): 現在認識を試みている途中の部分区間の
                  終了時刻（秒）。
                - segment.text (str): 途中経過の認識文字列。

        Returns:
            None
        """
        ...

    def on_sound_event(self, event: SoundEvent) -> None:
        """音響イベント検出時に呼び出されます。

        Args:
            event (SoundEvent): 検出された音響イベント定義。
                （イベント名や発生時刻、持続時間、信頼度を内包）。

        Returns:
            None
        """
        ...

    def on_error(self, error: BaseException) -> None:
        """致命的なエラー発生時に呼び出されます。

        Args:
            error (BaseException): 発生した例外オブジェクト。
                例外の原因究明や、上位層への伝播・通知に使用します。

        Returns:
            None
        """
        ...


class BasePipelineCallbacks(PipelineCallbacks):
    """標準のデフォルト実装クラス。

    各種アプリケーションやテストにおいて、
    特定のイベントのみをハンドルしたい場合は、本クラスを継承し、
    必要なイベントメソッドのみをオーバーライドして
    実装を作成できます。
    """

    def on_vad_state_change(self, state: VadState) -> None:
        """VAD状態変化時のデフォルト処理。

        Args:
            state (VadState): 移行後の新しいVAD状態。
        """
        pass

    def on_speech_start(self, timestamp: float) -> None:
        """発話開始検出時のデフォルト処理。

        Args:
            timestamp (float): 発話開始のタイムコード（秒）。
        """
        pass

    def on_speech_end(self, timestamp: float) -> None:
        """発話終了検出時のデフォルト処理。

        Args:
            timestamp (float): 発話終了のタイムコード（秒）。
        """
        pass

    def on_segment_recognized(self, segment: RecognizedSegment) -> None:
        """音声認識確定時のデフォルト処理。

        Args:
            segment (RecognizedSegment): 確定した認識結果。
        """
        pass

    def on_partial_recognized(self, segment: RecognizedSegment) -> None:
        """部分的音声認識完了時のデフォルト処理。

        Args:
            segment (RecognizedSegment): 途中の認識結果。
        """
        pass

    def on_sound_event(self, event: SoundEvent) -> None:
        """音響イベント検出時のデフォルト処理。

        Args:
            event (SoundEvent): 検出された音響イベントオブジェクト。
        """
        pass

    def on_error(self, error: BaseException) -> None:
        """エラー発生時のデフォルト処理。

        Args:
            error (BaseException): 発生した例外。
        """
        pass
