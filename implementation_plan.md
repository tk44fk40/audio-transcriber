# 実装計画: Lumi Companion ストリーミング連携 音声処理ライブラリ拡張 ＆ CLI改修

## 1. 概要
- **詳細設計書**: [docs/detailed_design.md](./docs/detailed_design.md)
- 本計画書は、詳細設計書に基づき実際のコーディング作業（TODO）を管理・追跡するためのタスク概要です。設計の背景や理由、リスク検証などの詳細は上記詳細設計書を参照して実装してください。

## 2. 実装計画（完了済みフェーズ概要）
以下のフェーズは全て実装および動作確認が完了しています。
- **Phase 1**: モデル常駐型 VAD+Whisper コア ＆ 共通データモデルの実装
- **Phase 2**: ストリーミング統合パイプライン ＆ 非同期コールバックの実装
- **Phase 3**: 設定・公開 API 統合
- **Phase 4**: 音声品質向上のためのマスタリング前処理追加（設定追加・RNNoise連携）
- **Phase 5**: CLI・パイプラインのストリーミング対応改修（リアルタイムツリー出力等）
- **Phase 6**: VADタイムスタンプバグ修正（サンプル数から秒数への変換）
- **Phase 7**: マスタリング動画の音声コーデック維持 (Bugfix)
- **Phase 8**: カバレッジ（テスト漏れ）の完全網羅（100%達成）
- **Phase 9**: ストリーミング出力 (cli.py) の完全リアルタイム化
- **Phase 10**: リアルタイム処理アーキテクチャの完全修正（VADタイムスタンプ・後処理のストリーミング化）

## 3. 実装計画（進行中フェーズ）

### Phase 11: 真のストリーミング入力（True Streaming）アーキテクチャへの完全移行
※ 設計詳細、リスク対策（文脈のチャンク切り詰め、長短チャンク保護、ファイル・ストリーミング処理の分離等）については `docs/detailed_design.md` の該当セクションを参照して実装すること。

#### 【実装ステップ（TODO）】
- [ ] 1. **ストリーミング設定の追加**: `config.py` の `AppConfig` に `StreamContextConfig` クラスを新設。`config.toml` の `[stream]` セクションから `context_max_length`, `context_timeout_seconds`, `chunk_min_seconds`, `chunk_max_seconds` 等をパースする処理を追加。
- [ ] 2. **CLIからのDI実装**: `cli.py` の `typer.Option` に `--chunk-min-sec`, `--context-timeout` などを追加し、パース結果を `AppConfig` インスタンスへ格納。パイプライン構築時にこの設定オブジェクトをコンストラクタ注入（DI）する構造を整備。
- [ ] 3. **STTインターフェースの分離**: `interfaces.py` 等の STT Provider 定義に `def transcribe_stream(self, audio_chunk: np.ndarray)` を新設。既存の `transcribe()` にはマスタリング等のファイル専用処理を残し、ストリーミング時は純粋な波形処理のみを行うよう責務を分離。
- [ ] 4. **ストリーミングVADマネージャーの実装**: `stt.py` に `StreamingVadManager` クラスを新設。`feed_chunk` で渡された波形を内部のリングバッファに追記しつつ Silero VAD で推論を実行。`chunk_max_seconds` への到達、または `SPEECH_END` の検知をトリガーとして確定チャンク（`np.ndarray`）を切り出して `yield` するロジックを実装。
- [ ] 5. **文脈管理と逐次推論**: Whisper の推論ループにおいて、過去セグメントのテキスト長を合算管理する `ContextManager` を導入。合算文字数が `context_max_length` を超えるか、無音時間が `context_timeout_seconds` を超えたタイミングで `initial_prompt` を空にクリアするロジックを実装し、テストケースを追加する。
- [ ] 6. **ドキュメント反映**: 新設したパラメータやCLIの挙動（特に文脈リセットの仕様）について `README.md` に具体的な利用例を追記する。

### Phase 12: 耐障害性およびメトリクス通知の実装
※ 要件仕様書に基づく非機能要件の実現タスク。
- [ ] 1. **CUDA OOMリカバリの実装**: `stt.py` における Whisper モデルの `model.transcribe` 実行箇所を `try-except RuntimeError` で保護。「out of memory」エラーを捕捉した際、パイプラインをクラッシュさせずに `on_error` コールバックへ通知し、安全にバッファを破棄（または CPU 推論へフォールバック）する安全機構を実装。
- [ ] 2. **稼働メトリクス計測と通知**: `pipeline.py` に `MetricsTracker` クラスを新設。VADが `SPEECH_END` を検知した時刻を記録し、後処理を経て `on_segment` コールバックが発火するまでの差分時間（E2Eレイテンシ）を計測。内部バッファの滞留フレーム数とともに `callbacks.on_metrics(latency_ms, buffer_size)` を定期的に呼び出すロジックを構築。

### Phase 13: ライブラリ標準インターフェースとアーキテクチャの準拠
※ 要件仕様書で定義された詳細なインターフェース設計に対する現状の差分を解消するタスク。
- [ ] 1. **出力データモデルの標準化**: `models.py` 等の共通定義に要件仕様書通りの `@dataclass RecognizedSegment`（`is_peak_sound` などの将来対応フラグを含む）を厳密に定義し、STTプロバイダーの戻り値およびコールバックの引数の型をこれに統一する。
- [ ] 2. **ステータスクリア機能 (`reset`) の実装**: `AudioStreamPipeline` に `reset()` メソッドを新設。内部で `VadManager.reset()`, `ContextManager.clear()` を呼び出し、Lock オブジェクトを用いて非同期推論スレッドと安全に同期しながら、リングバッファや文脈プロンプトを即座に初期化する仕組みを実装。
- [ ] 3. **推論エンジンの抽象化と Factory パターン**: 現在 `stt.py` に混在しているロジックを分割。共通の `TranscriberProvider` (Protocol) を定義し、ローカル用の `FasterWhisperProvider` と テスト用の `MockProvider` を実装。`config.stt.engine` の値に基づいて Factory パターンで動的にインスタンスを切り替える DI 構造へリファクタリング。
- [ ] 4. **単体テストの Mock 化とカバレッジ強化**: `test_stt.py` などのテストコードにおいて、GPUやデバイスを必要としない `MockProvider` を差し込むアーキテクチャを活用し、`np.zeros` 等のダミー波形入力に対する状態遷移やコールバック発火を検証する高品質な単体テストを拡充する。

### （将来検討）音響イベント検知
- マルチトラック分離設計および事前学習モデルを用いたイベント検知の導入（詳細は設計書参照）

