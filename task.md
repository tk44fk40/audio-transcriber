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
  - [x] 1.3 `tests/test_models.py`, `tests/test_stt.py` の実装と単体テスト検証
- [x] **CLI 機能強化・リアルタイム進捗表示**
  - [x] 全 CLI オプションの `config.toml` 自動フォールバック（`DEFAULT_VIDEO_PATH`, `ENABLED` 等）
  - [x] RNNoise モデル（`sh.rnnn`, `cb.rnnn`）配置および安全なフォールバック
  - [x] CUDA 12 依存関係解決および `compat.py` による自動パス解決
  - [x] パイプライン・文字起こし中のリアルタイム進捗 ＆ 発話ストリーミング表示（`on_progress`, `on_segment`）
  - [x] `pre-commit` の `fail_fast: true` 設定
  - [x] 全 243 件テスト合格・カバレッジ 98%
