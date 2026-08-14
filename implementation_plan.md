# 実装計画: Lumi Companion ストリーミング連携 音声処理ライブラリ拡張

## 1. 概要
- **参照元 要件仕様書**: [`lumi_companion/docs/AUDIO_LIBRARY_REQUIREMENTS.md`](file:///home/tk44/ghq/github.com/tk44fk40/lumi_companion/docs/AUDIO_LIBRARY_REQUIREMENTS.md)
- **詳細設計書**: [`docs/streaming_integration_plan.md`](docs/streaming_integration_plan.md)

上記の要求仕様に準拠し、`audio-transcriber` をリアルタイムストリーミング対応の音声処理ライブラリとして拡張する。

## 2. 実装計画

### Phase 1: モデル常駐型 VAD+Whisper コア ＆ 共通データモデル
- [ ] `src/audio_transcriber/models.py` に `RecognizedSegment`, `VadState`, `SoundEvent` を定義
- [ ] `src/audio_transcriber/stt.py` (`SpeechTranscriber`) を実装（Faster-Whisper+Silero-VAD 常駐、波形/ファイル推論、VRAM解放）
- [ ] `tests/test_stt.py` で単体テスト作成・検証

### Phase 2: ストリーミング統合パイプライン ＆ 非同期コールバック
- [ ] `src/audio_transcriber/callbacks.py` (`PipelineCallbacks`, `BasePipelineCallbacks`) を定義
- [ ] `src/audio_transcriber/streaming.py` (`AudioStreamPipeline`) を実装（リングバッファ、非同期キュー、発話区間切り出し、後処理連携、コールバック通知）
- [ ] `tests/test_streaming.py` および `tests/test_callbacks.py` で単体テスト作成・検証

### Phase 3: 設定・公開 API 統合 ＆ 品質保証
- [ ] `src/audio_transcriber/config.py` にストリーミング用設定モデル（`AudioPipelineConfig` 等）を追加
- [ ] `src/audio_transcriber/__init__.py` で公開クラス・関数をエクスポート
- [ ] 既存バッチ/CLIテスト（224件）との互換性・リグレッション検証
- [ ] 静的解析（basedpyright, ruff）およびテストカバレッジ 85% 以上の維持

### （将来検討）音響イベント検知
- [ ] マルチトラック分離設計（マイク音 ➔ STT/声検知、ゲーム音 ➔ ゲームSE/環境音検知）
- [ ] 手法 1: 短時間 RMS / dBFS 閾値判定によるピーク・叫び声検知の実装
- [ ] 手法 3: ONNX 版 YAMNet による笑い声・ゲームSE 分類モデルの検討
