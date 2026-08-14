"""音声認識・ストリーミング連携用データモデルの単体テスト。"""

from audio_transcriber.models import RecognizedSegment, SoundEvent, VadState


class TestVadState:
    """VadState 列挙型のテスト。"""

    def test_vad_state_values(self) -> None:
        """各ステータス値が正しく定義されていることを確認します。"""
        # Arrange & Act & Assert
        assert VadState.SILENCE.value == "silence"
        assert VadState.SPEECH_START.value == "speech_start"
        assert VadState.SPEECH.value == "speech"
        assert VadState.SPEECH_END.value == "speech_end"


class TestRecognizedSegment:
    """RecognizedSegment データクラスのテスト。"""

    def test_create_and_defaults(self) -> None:
        """インスタンス化とデフォルト値の設定を検証します。"""
        # Arrange & Act
        seg = RecognizedSegment(start=1.0, end=2.5, text="テスト発話")

        # Assert
        assert seg.start == 1.0
        assert seg.end == 2.5
        assert seg.text == "テスト発話"
        assert seg.confidence == 0.0
        assert seg.speaker_id is None
        assert seg.words is None

    def test_to_dict(self) -> None:
        """辞書形式への変換を検証します。"""
        # Arrange
        seg = RecognizedSegment(
            start=0.5,
            end=3.0,
            text="こんにちは",
            confidence=0.95,
            speaker_id="spk_0",
            words=[{"word": "こんにちは", "start": 0.5, "end": 3.0}],
        )

        # Act
        data = seg.to_dict()

        # Assert
        assert data["start"] == 0.5
        assert data["end"] == 3.0
        assert data["text"] == "こんにちは"
        assert data["confidence"] == 0.95
        assert data["speaker_id"] == "spk_0"
        assert data["words"] == [{"word": "こんにちは", "start": 0.5, "end": 3.0}]

    def test_from_dict_with_full_fields(self) -> None:
        """完全な辞書データからの復元を検証します。"""
        # Arrange
        data: dict[str, object] = {
            "start": 1.2,
            "end": 4.5,
            "text": "おはようございます",
            "confidence": 0.88,
            "speaker_id": "spk_1",
            "words": [{"word": "おはよう", "start": 1.2, "end": 3.0}],
        }

        # Act
        seg = RecognizedSegment.from_dict(data)

        # Assert
        assert seg.start == 1.2
        assert seg.end == 4.5
        assert seg.text == "おはようございます"
        assert seg.confidence == 0.88
        assert seg.speaker_id == "spk_1"
        assert seg.words == [{"word": "おはよう", "start": 1.2, "end": 3.0}]

    def test_from_dict_with_missing_fields(self) -> None:
        """欠損フィールドを含む辞書からの復元を検証します。"""
        # Arrange
        data: dict[str, object] = {"text": "一部のみ"}

        # Act
        seg = RecognizedSegment.from_dict(data)

        # Assert
        assert seg.start == 0.0
        assert seg.end == 0.0
        assert seg.text == "一部のみ"
        assert seg.confidence == 0.0
        assert seg.speaker_id is None
        assert seg.words is None


class TestSoundEvent:
    """SoundEvent データクラスのテスト。"""

    def test_create_and_defaults(self) -> None:
        """インスタンス化とデフォルト値の設定を検証します。"""
        # Arrange & Act
        event = SoundEvent(event_type="peak_energy", timestamp=10.5)

        # Assert
        assert event.event_type == "peak_energy"
        assert event.timestamp == 10.5
        assert event.score == 1.0
        assert event.metadata is None

    def test_to_dict(self) -> None:
        """辞書形式への変換を検証します。"""
        # Arrange
        event = SoundEvent(
            event_type="laughter",
            timestamp=12.3,
            score=0.85,
            metadata={"source": "mic"},
        )

        # Act
        data = event.to_dict()

        # Assert
        assert data["event_type"] == "laughter"
        assert data["timestamp"] == 12.3
        assert data["score"] == 0.85
        assert data["metadata"] == {"source": "mic"}

    def test_from_dict_with_full_fields(self) -> None:
        """完全な辞書データからの復元を検証します。"""
        # Arrange
        data: dict[str, object] = {
            "event_type": "cheer",
            "timestamp": 5.0,
            "score": 0.9,
            "metadata": {"volume": 0.8},
        }

        # Act
        event = SoundEvent.from_dict(data)

        # Assert
        assert event.event_type == "cheer"
        assert event.timestamp == 5.0
        assert event.score == 0.9
        assert event.metadata == {"volume": 0.8}

    def test_from_dict_with_missing_fields(self) -> None:
        """欠損フィールドを含む辞書からの復元を検証します。"""
        # Arrange
        data: dict[str, object] = {}

        # Act
        event = SoundEvent.from_dict(data)

        # Assert
        assert event.event_type == "unknown"
        assert event.timestamp == 0.0
        assert event.score == 0.0
        assert event.metadata is None
