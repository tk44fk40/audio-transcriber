"""テスト: ストリーミング状態管理 (ContextManager, StreamingVadManager)
docs/streaming_statechart.md の状態遷移仕様に基づくテスト。
"""

import numpy as np
import pytest

# 実装クラスが作成されることを前提にインポート
# 実装が存在しないため最初は ImportError で RED になる
try:
    from audio_transcriber.streaming.managers import ContextManager, StreamingVadManager
except ImportError:
    # 意図的なREDのため、ダミークラスを用意せずにそのまま失敗させる
    # または、ここでダミーを定義して中でAssertionErrorにさせることもできるが、
    # AAAパターンのテストコード自体はしっかり書いておく
    pass


class TestContextManager:
    """ContextManager のテスト
    文脈履歴 (initial_prompt) の管理と、タイムアウト・文字数制限時の Trim を検証する。
    """

    @pytest.fixture
    def manager(self):
        # max_length=20, timeout_seconds=5.0
        # ※ 実装側がない場合はここで NameError になるため、これも RED のエビデンスとなる
        return ContextManager(max_length=20, timeout_seconds=5.0)

    def test_initial_state_empty(self, manager):
        """文脈なし (Empty) 状態の確認"""
        assert manager.segments == []
        assert manager.get_prompt() == ""

    def test_add_text_within_limit(self, manager):
        """制限文字数内でのテキスト追加 (ActiveContext)"""
        manager.add_text("こんにちは")
        manager.add_text("世界")

        # 内部的にはリストとして独立したセグメントを保持していること
        assert manager.segments == ["こんにちは", "世界"]
        # Whisperに渡すプロンプトとしては、セグメント同士が癒着しないよう
        # 半角スペースや句読点などのセパレータで結合されていること
        assert manager.get_prompt(separator=" ") == "こんにちは 世界"

    def test_trim_over_limit(self, manager):
        """文字数上限到達時の古いテキスト破棄 (Trim)"""
        # 1回目: 10文字
        manager.add_text("あいうえおかきくけこ")
        # 2回目: 8文字 -> 計18文字 (max_length=20 なのでセーフ)
        manager.add_text("さしすせそたちつ")

        # 3回目: 5文字 -> 計23文字。上限の20文字を超えるため、最も古い発話セグメント
        # "あいうえおかきくけこ" (10文字) がリストから丸ごと破棄(pop)される。
        manager.add_text("てとなにぬ")

        # セグメント単位で管理されていることを確認
        assert manager.segments == ["さしすせそたちつ", "てとなにぬ"]
        assert manager.get_prompt(separator=" ") == "さしすせそたちつ てとなにぬ"

    def test_timeout_clear(self, manager):
        """タイムアウト判定によるクリア (ActiveContext -> Empty)"""
        manager.add_text("テストコンテキスト")
        assert manager.segments == ["テストコンテキスト"]

        # タイムアウト未満(4.9秒)
        manager.check_timeout(silence_duration=4.9)
        assert manager.segments == ["テストコンテキスト"]

        # タイムアウト以上(5.0秒)
        manager.check_timeout(silence_duration=5.0)
        assert manager.segments == []
        assert manager.get_prompt() == ""

    def test_manual_clear(self, manager):
        """手動クリアによる状態遷移 (ActiveContext -> Empty)"""
        manager.add_text("テストコンテキスト")
        manager.clear()
        assert manager.segments == []

    def test_add_empty_text(self, manager):
        """空文字や空白のみのテキストが渡された場合に無視されることの検証"""
        manager.add_text("")
        manager.add_text("   ")
        # 意味のないセグメントはリストに追加されないこと
        assert manager.segments == []
        assert manager.get_prompt() == ""


class TestStreamingVadManager:
    """StreamingVadManager のテスト
    音声チャンクの蓄積、無音による切り出し、短チャンク保留、強制切り出し等の状態遷移を検証する。
    """

    @pytest.fixture
    def manager(self):
        # サンプリングレート 16000Hz
        # 最小無音時間: 1.0秒
        # 最小チャンク長: 2.0秒
        # 最大チャンク長: 5.0秒
        return StreamingVadManager(
            sample_rate=16000,
            min_silence_duration=1.0,
            chunk_min_seconds=2.0,
            chunk_max_seconds=5.0,
        )

    def generate_dummy_audio(self, duration_seconds: float) -> np.ndarray:
        """指定秒数のダミー音声データ(float32)を生成する"""
        samples = int(16000 * duration_seconds)
        return np.zeros(samples, dtype=np.float32)

    def test_idle_to_speech_active(self, manager):
        """無音待機 (Idle) から 発話蓄積中 (SpeechActive) への遷移"""
        # Arrange
        audio = self.generate_dummy_audio(0.5)

        # Act (VAD=0)
        result1 = manager.process_audio(audio, is_speech=False)
        # Assert (Idle -> Idle)
        assert result1 is None

        # Act (VAD=1)
        result2 = manager.process_audio(audio, is_speech=True)
        # Assert (Idle -> SpeechActive、蓄積開始なのでまだ返さない)
        assert result2 is None

    def test_speech_active_to_idle_normal_chunk(self, manager):
        """発話中 -> 無音判定 (min_silence到達) -> 通常チャンク切り出し (Idle)"""
        # Arrange
        # 計2.5秒の発話 (chunk_min_seconds 2.0以上を満たす)
        manager.process_audio(self.generate_dummy_audio(2.5), is_speech=True)

        # Act & Assert
        # 無音 0.5秒 (TraillingSilence: 猶予期間中なのでまだ出ない)
        result1 = manager.process_audio(self.generate_dummy_audio(0.5), is_speech=False)
        assert result1 is None

        # 無音さらに0.5秒 (計1.0秒 = min_silence到達。チャンク長も2.5秒あるので確定)
        result2 = manager.process_audio(self.generate_dummy_audio(0.5), is_speech=False)

        # Assert
        assert result2 is not None
        assert isinstance(result2, np.ndarray)
        # 返されるチャンクは、発話2.5秒＋無音1.0秒 = 3.5秒分になる想定
        assert len(result2) == int(16000 * 3.5)

    def test_trailing_silence_to_speech_active(self, manager):
        """終了猶予中 (TrailingSilence) からの発話再開 (SpeechActive)"""
        # Arrange
        manager.process_audio(self.generate_dummy_audio(1.0), is_speech=True)

        # Act: 無音0.8秒 (min_silence 1.0秒に届かない)
        manager.process_audio(self.generate_dummy_audio(0.8), is_speech=False)

        # Act: 再び発話1.0秒
        result = manager.process_audio(self.generate_dummy_audio(1.0), is_speech=True)

        # Assert: チャンクは分割されず、蓄積が継続している
        assert result is None

    def test_holding_short_chunk(self, manager):
        """短いチャンクの保留状態 (HoldingShortChunk) への遷移"""
        # Arrange: 1.0秒の発話 (chunk_min_seconds 2.0に届かない)
        manager.process_audio(self.generate_dummy_audio(1.0), is_speech=True)

        # Act: 無音1.0秒 (min_silence到達)
        result = manager.process_audio(self.generate_dummy_audio(1.0), is_speech=False)

        # Assert: min_silenceに到達したが、チャンク長が2.0秒未満のため保留される
        assert result is None

    def test_holding_short_chunk_to_speech_active(self, manager):
        """保留状態 (HoldingShortChunk) から次の発話との結合 (SpeechActive)"""
        # Arrange: 1.0秒発話 + 1.0秒無音 -> 保留状態になる
        manager.process_audio(self.generate_dummy_audio(1.0), is_speech=True)
        manager.process_audio(self.generate_dummy_audio(1.0), is_speech=False)

        # Act: 新しい発話1.5秒 (前の保留分と結合される)
        manager.process_audio(self.generate_dummy_audio(1.5), is_speech=True)

        # 無音1.0秒で確定させる
        result = manager.process_audio(self.generate_dummy_audio(1.0), is_speech=False)

        # Assert
        assert result is not None
        # 総計: 1.0(発話) + 1.0(無音) + 1.5(発話) + 1.0(無音) = 4.5秒分
        assert len(result) == int(16000 * 4.5)

    def test_chunk_max_seconds_forced_yield(self, manager):
        """最大チャンク長 (chunk_max_seconds) 到達による強制切り出し"""
        # Arrange: 発話を少しずつ追加
        for _ in range(4):
            # 計4.0秒
            res = manager.process_audio(self.generate_dummy_audio(1.0), is_speech=True)
            assert res is None

        # Act: さらに1.0秒追加 (計5.0秒到達 = chunk_max_seconds)
        result = manager.process_audio(self.generate_dummy_audio(1.0), is_speech=True)

        # Assert: VAD=1だが強制的に切り出される
        assert result is not None
        assert len(result) == int(16000 * 5.0)

    def test_flush_holding_short_chunk(self, manager):
        """保留チャンクのフラッシュ出力"""
        # Arrange: 短いチャンクを保留させる (1.0秒発話 + 1.0秒無音)
        manager.process_audio(self.generate_dummy_audio(1.0), is_speech=True)
        manager.process_audio(self.generate_dummy_audio(1.0), is_speech=False)

        # Act: flushメソッド呼び出し
        result = manager.flush()

        # Assert: 保留されていたチャンクが返る
        assert result is not None
        assert len(result) == int(16000 * 2.0)

    def test_flush_speech_active(self, manager):
        """発話中 (SpeechActive) 状態でのフラッシュ出力"""
        # Arrange: 発話中 (まだ min_silence に達していないし、保留でもない状態)
        manager.process_audio(self.generate_dummy_audio(2.5), is_speech=True)

        # Act: 強制終了 (flush)
        result = manager.flush()

        # Assert: 蓄積されていた発話分がそのまま出力されること
        assert result is not None
        assert len(result) == int(16000 * 2.5)
