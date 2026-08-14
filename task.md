# タスクリスト (Task List)

## 進行中 / 未完了
- [ ] **Phase 1: モデル常駐型 VAD+Whisper コア ＆ 共通データモデル**
  - [ ] 1.1 `src/audio_transcriber/models.py` への `RecognizedSegment`, `VadState`, `SoundEvent` 追加
  - [ ] 1.2 `src/audio_transcriber/stt.py` (`SpeechTranscriber`) の実装
  - [ ] 1.3 `tests/test_stt.py` の実装と単体テスト検証
- [ ] **Phase 2: ストリーミング統合パイプライン ＆ 非同期コールバック**
  - [ ] 2.1 `src/audio_transcriber/callbacks.py` (`PipelineCallbacks`) の定義
  - [ ] 2.2 `src/audio_transcriber/streaming.py` (`AudioStreamPipeline`) の実装
  - [ ] 2.3 `tests/test_streaming.py`, `tests/test_callbacks.py` の実装と検証
- [ ] **Phase 3: 設定・公開 API 統合 ＆ 品質保証**
  - [ ] 3.1 `src/audio_transcriber/config.py` および `__init__.py` の更新
  - [ ] 3.2 全体テスト（pytest / basedpyright / ruff）による品質保証

## 完了済み
- [x] 1. `config.toml` および `config.example.toml` の更新（`[path]`, `[denoise]`, `[post_process]` 整理）
- [x] 2. `src/audio_transcriber/config.py` の更新（`PathConfig` 定義、`PostProcessConfig` 整理、`parse_config_dict` 改修）
- [x] 3. `src/audio_transcriber/pipeline.py` & `src/audio_transcriber/cli.py` の参照先調整
- [x] 4. `tests/test_config.py` および `tests/test_cli.py` 他のテストケース更新
- [x] 5. 静的解析（ruff, basedpyright）およびテスト（pytest: 224 passed / 99% coverage）の実行・検証
- [x] 6. ストリーミング連携計画書の作成（`docs/streaming_integration_plan.md`）
