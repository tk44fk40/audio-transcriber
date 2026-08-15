# 実装計画: Lumi Companion ストリーミング連携 音声処理ライブラリ拡張 ＆ CLI/マスタリング機能改善

## 1. 概要
- **参照元 要件仕様書**: [`lumi_companion/docs/AUDIO_LIBRARY_REQUIREMENTS.md`](file:///home/tk44/ghq/github.com/tk44fk40/lumi_companion/docs/AUDIO_LIBRARY_REQUIREMENTS.md)
- **詳細設計書**: [`docs/streaming_integration_plan.md`](file:///home/tk44/ghq/github.com/tk44fk40/audio-transcriber/docs/streaming_integration_plan.md)
- 本計画は、Lumi Companion 向けのストリーミング処理基盤の拡張に加えて、以前のセッションで合意した音声品質向上（マスタリング前処理）および CLI 向けの出力改修・バグ修正を全体の計画として統合したものです。

## 2. 実装計画

### Phase 1: モデル常駐型 VAD+Whisper コア ＆ 共通データモデル (完了 - Issue #1)
- [x] `src/audio_transcriber/models.py` に `RecognizedSegment`, `VadState`, `SoundEvent` を定義
- [x] `src/audio_transcriber/stt.py` (`SpeechTranscriber`, `TranscriberProtocol`, `WhisperModelProtocol`) を実装
- [x] 単体テスト作成・検証

### Phase 2: ストリーミング統合パイプライン ＆ 非同期コールバック (実装済み・動作確認待ち)
- [x] `src/audio_transcriber/callbacks.py` (`PipelineCallbacks`, `BasePipelineCallbacks`) を定義
- [x] `src/audio_transcriber/streaming.py` (`AudioStreamPipeline`) を実装
- [x] `tests/test_streaming.py`, `tests/test_callbacks.py` で単体テスト作成・検証（強化済）

### Phase 3: 設定・公開 API 統合 (実装済み・動作確認待ち)
- [x] `src/audio_transcriber/config.py`, `config.toml`, `config.example.toml` にストリーミング用設定モデル追加
- [x] `src/audio_transcriber/__init__.py` で公開クラス・関数をエクスポート

### Phase 4: 音声品質向上のためのマスタリング前処理追加 (進行中 - ブランチ: issue-1/feat-model-resident-stt-core)
- [x] `config.toml`, `config.example.toml`, `src/audio_transcriber/config.py` への `[mastering]` セクションパラメータ追加（※詳細は詳細設計書を参照）
- [x] `cli.py` へのマスタリング用コマンドライン引数追加
- [x] 実装前の FFmpeg パラメータ動作検証（ターミナルでのテスト）
- [x] `rnnoise.py` にノイズ除去 ➔ マスタリング直列フィルタ実装

### Phase 5: CLI・パイプラインのストリーミング対応改修
- [x] `config.toml` へストリーミング・分割用の設定パラメータ追加（※詳細は詳細設計書を参照）
- [x] `cli.py` へのストリーミング用コマンドライン引数追加
- [x] `pipeline.py` (`_internal_on_segment`) での単一セグメント処理・遅延重複防止バッファリングの実装
- [x] `cli.py` をリアルタイムツリー出力またはシンプル出力に改修（一括表示の廃止）
- [x] `sanitizer.py`, `postprocess.py` の単一セグメント対応メソッド整備

### Phase 6: VADタイムスタンプバグ修正
- [x] `stt.py` で VAD出力がサンプル数で返る問題を秒数(float)へ変換するように修正

### Phase 7: マスタリング動画の音声コーデック維持 (Bugfix)
- **作業ブランチ**: 現在のブランチ (`issue-1/feat-model-resident-stt-core`) で実施する
- [ ] `src/audio_transcriber/media.py` の `remux_video` において、出力音声コーデックを `aac` 固定ではなく、元のトラックのコーデック (`codec_name`) を引き継ぐように修正
- [ ] コーデックが取得できない (`unknown`) 場合は `aac` にフォールバックする安全処理を追加
- [ ] 作業完了後はセルフチェック（テスト・静的解析など）を実行し、ユーザーへ結果を報告する
- [ ] **指示があるまでコミットやプッシュ等のGit操作は行わない**

### （将来検討）音響イベント検知
- [ ] マルチトラック分離設計（マイク音 ➔ STT/声検知、ゲーム音 ➔ ゲームSE/環境音検知）
- [ ] 手法 1, 3 によるイベント検知モデルの導入

## 3. ライブラリ利用を想定したパラメータ引き渡し設計
CLIからだけでなく、別のPythonスクリプトからライブラリとして利用される場合でも正しくパラメータが反映されるよう、設定オブジェクトを経由した引き渡し等のアーキテクチャ・実装ルールを遵守します。
※具体的な設計ルールおよび実装例については、**詳細設計書（[`docs/streaming_integration_plan.md`](file:///home/tk44/ghq/github.com/tk44fk40/audio-transcriber/docs/streaming_integration_plan.md)）の「4. ライブラリ利用を想定したパラメータ引き渡し設計」** を参照してください。

## 【ドキュメント更新】
- [ ] `README.md` および関連ドキュメントへ、追加した設定パラメータ・CLI引数の使用方法を追記

## 【品質保証・セルフチェックプロセス】
- [ ] 各機能修正・実装時のセルフチェックリストの実施と結果報告
- [ ] カバレッジナレッジ（`docs/testing_and_coverage.md`）の確認と遵守
- [ ] テストが正しく実装されているか、ケース漏れがないかの網羅性確認（ナレッジで除外指定されている箇所以外は全てカバーする）
- [ ] 静的解析（basedpyright, ruff）の実行
- [ ] カバレッジの計測と報告

## 【Git ワークフロー & 最終確認】
- [ ] **（※重要）自動でのコミット・プッシュは絶対に行わないこと**
- [ ] 実装・自動テスト・カバレッジの確認完了後、ユーザーに報告する
- [ ] ユーザーによる実際の動作確認（手動確認）が完了し、承認を得た後にのみコミットとプッシュを実施する
- [ ] （※Issueの更新およびプルリクエストの作成は省略する）
