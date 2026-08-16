# タスクリスト (Task List)

## 進行中フェーズ



### Phase 14: 統合パイプラインアーキテクチャの実装 (コーディングフェーズ)

Phase 13 で策定した詳細設計（`detailed_design.md`）に基づき、新しいキューベース・リアルタイム進行アーキテクチャを実装します。

#### 14.1 オーケストレーターとプロデューサー層の構築
- [ ] 14.1.1 `pipeline_supervisor.py` の作成
  - `PipelineSupervisor` クラスの実装（全体例外捕捉、CLI向けFacade）
  - CUDA OOM 等のランタイムエラーからの安全なリカバリ処理の実装
  - ステータスクリア機能 (`reset()` メソッド) によるライフサイクル管理の実装
- [ ] 14.1.2 `audio_producers.py` の作成
  - `AudioChunkQueue` (非同期セーフキュー) の実装
  - `FileAudioProducer` の実装（RNNoise前処理 → 一時ファイル読み込み）
  - `StreamAudioProducer` の実装
- [ ] 14.1.3 `file_remuxer.py` の作成
  - `FileRemuxer` クラスの実装（動画ファイル入力時の音声書き戻し処理）

#### 14.2 コア・パイプラインと波形スライス抽出の実装
- [ ] 14.2.1 `vad_manager.py` の改修・新規作成
  - `VadManagerProtocol` の定義 (DI注入用インターフェース)
  - `StreamingVadManager` の実装（内部に `AudioRingBuffer` を保持）
  - VAD終端検知時の波形スライス抽出とバッファ破棄メカニズムの構築
- [ ] 14.2.2 `unified_pipeline.py` の作成
  - `UnifiedTranscriptionPipeline` の実装
  - キューからの取り出し、タイムコード管理、および「VAD波形抽出 ➔ 推論 ➔ 後処理 ➔ 文脈追加」の同期直列ループの制御
  - 処理レイテンシやバッファ残量等の稼働状況を監視し `on_metrics` コールバックで定期通知する仕組みの構築

#### 14.3 推論エンジンのDI化と、後処理・文脈モジュールの実装
- [ ] 14.3.1 `stt.py` の改修 (DI・プロバイダーパターン化)
  - `TranscriberProvider` (Protocol) の定義
  - 既存の推論ロジックを `FasterWhisperProvider` として整理し、VADチャンク単位の逐次推論メソッドへ特化
  - 推論エンジンの抽象化と Factory パターンによる DI 切り替え機能の実装
- [ ] 14.3.2 `postprocessor.py` の作成 (旧ファイルの統合・マイグレーション)
  - `PostProcessorProtocol` の定義 (DI注入用インターフェース)
  - `TextPostProcessor` クラスの実装（無音・無効破棄、重複除去、辞書置換、正規化、タイミング・余韻補正）
  - 既存の `sanitizer_core.py` と `postprocess.py` のロジックを本ファイルに統合し、旧ファイルを削除
- [ ] 14.3.3 `context_manager.py` の作成
  - `ContextManagerProtocol` の定義 (DI注入用インターフェース)
  - `ContextManager` クラスの実装（履歴テキストのFIFO管理、トークン・文字数溢れ制御、次チャンク用プロンプト生成）
  - 履歴クリアのための `reset()` メソッドの実装

#### 14.4 エントリーポイントの統合とクリーンアップ
- [ ] 14.4.1 `cli.py` の改修と出力モデル標準化
  - 出力データモデルを `RecognizedSegment` へ完全準拠させる
  - 呼び出しロジックを新設した `PipelineSupervisor` の Facade へ切り替え
- [ ] 14.4.2 テストコードの再整備 (MockProviderの導入)
  - `MockProvider` を作成・展開し、GPUレスで非同期キューやDIパイプラインの全体状態遷移テストを可能にする
  - 新規作成・分割した各コンポーネント（特にバッファスライス抽出や溢れ制御）に対応する単体テストの追加・更新
- [ ] 14.4.3 旧アーキテクチャファイルの削除
  - E2Eで動作確認後、不要となった旧パイプラインコード（`pipeline.py`, `streaming/core.py` 等）の削除・整理

## 未着手のフェーズ



### Phase 15: GPU/デバイス不要テスト基盤の整備
- [ ] 15.1 ダミー波形入力によるパイプライン状態遷移・コールバック発火の単体テスト拡充（全モジュール横断）
- [ ] 15.2 CPU 環境での完全実行検証（CI 導入への道を開く）

## 将来対応
- [ ] 音響イベント検知（叫び声・大音量ピーク・笑い声等の分類検知および即時通知）

## 全フェーズ共通ルール
- [ ] **品質保証・セルフチェックプロセス** (テストケース網羅・静的解析・カバレッジ100%)
- [ ] **Git ワークフロー** (自動コミット・プッシュ禁止。動作確認後に実施)
