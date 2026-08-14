# タスクリスト (Task List)

## 進行中 / 未完了
- [ ] **Phase 2: ストリーミング統合パイプライン ＆ 非同期コールバック**
  - [ ] 2.1 `src/audio_transcriber/callbacks.py` (`PipelineCallbacks`) の定義
  - [ ] 2.2 `src/audio_transcriber/streaming.py` (`AudioStreamPipeline`) の実装
  - [ ] 2.3 `tests/test_streaming.py`, `tests/test_callbacks.py` の実装と検証
- [ ] **Phase 3: 設定・公開 API 統合 ＆ 品質保証**
  - [ ] 3.1 `src/audio_transcriber/config.py` および `__init__.py` の更新
  - [ ] 3.2 全体テスト（pytest / basedpyright / ruff）による品質保証

## 完了済み
- [x] **Phase 1: モデル常駐型 VAD+Whisper コア ＆ 共通データモデル (Issue #1)**
  - [x] 1.1 `src/audio_transcriber/models.py` への `RecognizedSegment`, `VadState`, `SoundEvent` 追加
  - [x] 1.2 `src/audio_transcriber/stt.py` (`SpeechTranscriber`, `TranscriberProtocol`, `WhisperModelProtocol`) の実装
  - [x] 1.3 `tests/test_models.py`, `tests/test_stt.py` の実装と単体テスト検証（全235件パス、98%カバレッジ）
- [x] 設定ファイル・後処理モジュール整理（CLI・設定機能互換維持）
