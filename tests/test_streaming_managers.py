"""テスト: ストリーミング状態管理 (ContextManager, StreamingVadManager)

docs/detailed_design.md の状態遷移仕様に基づくテスト。
"""

from typing import Any

import numpy as np
import pytest

from audio_transcriber.streaming.managers import ContextManager, StreamingVadManager


class TestContextManager:
    """ContextManager のテスト。

    文脈履歴 (initial_prompt) の管理と、タイムアウト・文字数制限時の Trim を検証する。
    """

    @pytest.fixture
    def manager(self) -> ContextManager:
        return ContextManager(max_length=20, timeout_seconds=5.0)

    def test_initial_state_empty(self, manager: ContextManager) -> None:
        """文脈なし (Empty) 状態の確認。"""
        assert manager.segments == []
        assert manager.get_prompt() == ""

    def test_add_text_within_limit(self, manager: ContextManager) -> None:
        """制限文字数内でのテキスト追加 (ActiveContext)。"""
        manager.add_text("こんにちは")
        manager.add_text("世界")

        assert manager.segments == ["こんにちは", "世界"]
        assert manager.get_prompt(separator=" ") == "こんにちは 世界"

    def test_trim_over_limit(self, manager: ContextManager) -> None:
        """文字数上限到達時の古いテキスト破棄 (Trim)。"""
        # 1回目: 10文字
        manager.add_text("あいうえおかきくけこ")
        # 2回目: 8文字 -> 計18文字 (max_length=20 なのでセーフ)
        manager.add_text("さしすせそたちつ")

        # 3回目: 5文字 -> 計23文字。上限の20文字を超えるため古いセグメントが破棄
        manager.add_text("てとなにぬ")

        assert manager.segments == ["さしすせそたちつ", "てとなにぬ"]
        assert manager.get_prompt(separator=" ") == "さしすせそたちつ てとなにぬ"

    def test_add_single_long_text(self, manager: ContextManager) -> None:
        """max_lengthを超える単一長大テキストが末尾max_length文字に切り詰められることを検証。"""
        long_text = "0123456789abcdefghijklmnopqrstuvwxyz"  # 36文字
        manager.add_text(long_text)
        assert len(manager.get_prompt()) <= 20
        assert manager.segments == ["ghijklmnopqrstuvwxyz"[-20:]]

    def test_trim_with_separator_spacing(self, manager: ContextManager) -> None:
        """スペース区切りを含めてmax_lengthを超過した場合の破棄動作を検証。"""
        # 各9文字 (計18文字 + スペース1文字 = 19文字 <= 20)
        manager.add_text("123456789")
        manager.add_text("abcdefghi")
        assert len(manager.segments) == 2

        # 3文字追加 -> 9+1+9+1+3 = 23文字 > 20 -> 先頭が破棄
        manager.add_text("xyz")
        assert manager.segments == ["abcdefghi", "xyz"]

    def test_timeout_clear(self, manager: ContextManager) -> None:
        """タイムアウト判定によるクリア (ActiveContext -> Empty)。"""
        manager.add_text("テストコンテキスト")
        assert manager.segments == ["テストコンテキスト"]

        # タイムアウト未満(4.9秒)
        manager.check_timeout(silence_duration=4.9)
        assert manager.segments == ["テストコンテキスト"]

        # タイムアウト以上(5.0秒)
        manager.check_timeout(silence_duration=5.0)
        assert manager.segments == []
        assert manager.get_prompt() == ""

    def test_manual_clear(self, manager: ContextManager) -> None:
        """手動クリアによる状態遷移 (ActiveContext -> Empty)。"""
        manager.add_text("テストコンテキスト")
        manager.clear()
        assert manager.segments == []

    def test_add_empty_text(self, manager: ContextManager) -> None:
        """空文字や空白のみのテキストが渡された場合に無視されることの検証。"""
        manager.add_text("")
        manager.add_text("   ")
        assert manager.segments == []
        assert manager.get_prompt() == ""


class TestStreamingVadManager:
    """StreamingVadManager のテスト。

    音声チャンクの蓄積、無音による切り出し、短チャンク保留、強制切り出し等の状態遷移を検証する。
    """

    @pytest.fixture
    def manager(self) -> StreamingVadManager:
        return StreamingVadManager(
            sample_rate=16000,
            min_silence_duration=1.0,
            chunk_min_seconds=2.0,
            chunk_max_seconds=5.0,
        )

    def generate_dummy_audio(self, duration_seconds: float) -> np.ndarray[Any, Any]:
        """指定秒数のダミー音声データ(float32)を生成する。"""
        samples = int(16000 * duration_seconds)
        return np.zeros(samples, dtype=np.float32)

    def test_idle_to_speech_active(self, manager: StreamingVadManager) -> None:
        """無音待機 (Idle) から 発話蓄積中 (SpeechActive) への遷移。"""
        audio = self.generate_dummy_audio(0.5)

        result1 = manager.process_audio(audio, is_speech=False)
        assert result1 is None

        result2 = manager.process_audio(audio, is_speech=True)
        assert result2 is None

    def test_speech_active_to_idle_normal_chunk(
        self, manager: StreamingVadManager
    ) -> None:
        """発話中 -> 無音判定 (min_silence到達) -> 通常チャンク切り出し (Idle)。"""
        # 計2.5秒の発話 (chunk_min_seconds 2.0以上を満たす)
        manager.process_audio(self.generate_dummy_audio(2.5), is_speech=True)

        result1 = manager.process_audio(self.generate_dummy_audio(0.5), is_speech=False)
        assert result1 is None

        result2 = manager.process_audio(self.generate_dummy_audio(0.5), is_speech=False)
        assert result2 is not None
        assert isinstance(result2, np.ndarray)
        assert len(result2) == int(16000 * 3.5)

    def test_trailing_silence_to_speech_active(
        self, manager: StreamingVadManager
    ) -> None:
        """終了猶予中 (TrailingSilence) からの発話再開 (SpeechActive)。"""
        manager.process_audio(self.generate_dummy_audio(1.0), is_speech=True)
        manager.process_audio(self.generate_dummy_audio(0.8), is_speech=False)
        result = manager.process_audio(self.generate_dummy_audio(1.0), is_speech=True)
        assert result is None

    def test_holding_short_chunk(self, manager: StreamingVadManager) -> None:
        """短いチャンクの保留状態 (HoldingShortChunk) への遷移。"""
        manager.process_audio(self.generate_dummy_audio(1.0), is_speech=True)
        result = manager.process_audio(self.generate_dummy_audio(1.0), is_speech=False)
        assert result is None

    def test_holding_short_chunk_to_speech_active(
        self, manager: StreamingVadManager
    ) -> None:
        """保留状態 (HoldingShortChunk) から次の発話との結合 (SpeechActive)。"""
        manager.process_audio(self.generate_dummy_audio(1.0), is_speech=True)
        manager.process_audio(self.generate_dummy_audio(1.0), is_speech=False)
        manager.process_audio(self.generate_dummy_audio(1.5), is_speech=True)
        result = manager.process_audio(self.generate_dummy_audio(1.0), is_speech=False)

        assert result is not None
        assert len(result) == int(16000 * 4.5)

    def test_holding_short_chunk_prolonged_silence_fallback(
        self, manager: StreamingVadManager
    ) -> None:
        """保留中に無音が長時間（3倍以上）継続した場合のフォールバック切り出しを検証。"""
        # 1.0秒発話 + 1.0秒無音 -> 保留状態
        manager.process_audio(self.generate_dummy_audio(1.0), is_speech=True)
        manager.process_audio(self.generate_dummy_audio(1.0), is_speech=False)

        # さらに無音を2.0秒継続（合計無音3.0秒 = min_silence 1.0秒の3倍到達）
        result = manager.process_audio(self.generate_dummy_audio(2.0), is_speech=False)
        assert result is not None
        assert len(result) == int(16000 * 4.0)

    def test_chunk_max_seconds_forced_yield(self, manager: StreamingVadManager) -> None:
        """最大チャンク長 (chunk_max_seconds) 到達による強制切り出し。"""
        for _ in range(4):
            res = manager.process_audio(self.generate_dummy_audio(1.0), is_speech=True)
            assert res is None

        result = manager.process_audio(self.generate_dummy_audio(1.0), is_speech=True)
        assert result is not None
        assert len(result) == int(16000 * 5.0)

    def test_flush_holding_short_chunk(self, manager: StreamingVadManager) -> None:
        """保留チャンクのフラッシュ出力。"""
        manager.process_audio(self.generate_dummy_audio(1.0), is_speech=True)
        manager.process_audio(self.generate_dummy_audio(1.0), is_speech=False)

        result = manager.flush()
        assert result is not None
        assert len(result) == int(16000 * 2.0)

    def test_flush_speech_active(self, manager: StreamingVadManager) -> None:
        """発話中 (SpeechActive) 状態でのフラッシュ出力。"""
        manager.process_audio(self.generate_dummy_audio(2.5), is_speech=True)
        result = manager.flush()
        assert result is not None
        assert len(result) == int(16000 * 2.5)

    def test_flush_empty_buffer(self, manager: StreamingVadManager) -> None:
        """空バッファ状態でのフラッシュ出力が None であることの検証。"""
        result = manager.flush()
        assert result is None
