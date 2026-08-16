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
- [x] **Step 1 & 2**: アーキテクチャ設計 (クラス図・フローチャート・状態遷移図) の合意、およびTDDに基づく各単体テストの先行作成とRED（失敗）状態の確認完了。
- **Step 3**: 段階的実装 (GREEN化)
  - [x] 1. **(第1弾) ストリーミング設定の実装**: `config.py` に `StreamContextConfig` を追加し、TOMLからのパース処理を実装。`test_config.py` をGREENにする。
  - [x] 2. **(第2弾) 文脈管理 (ContextManager) の実装**: `streaming/managers.py` に文脈セグメントの破棄・タイムアウトリセットロジックを実装し、関連テストをGREENにする。
  - [x] 3. **(第3弾) VAD制御 (StreamingVadManager) の実装**: 同ファイルにリングバッファと発話チャンク切り出しロジックを実装し、全テストをGREENにする。
  - [x] 4. **設定・CLIからの `vad_filter` 廃止および内部 `vad_filter=False` 固定化**: `VadConfig`・CLIオプションから `vad_filter` を廃止し、WhisperModel呼び出しでは常に `vad_filter=False` 固定とする。
  - [x] 5. **STTインターフェースの新設と逐次推論 (`transcribe_stream`)**: STT Provider に `transcribe_stream(audio_chunk, initial_prompt)` を新設し、ストリーミング用の純粋な波形処理を行う責務に分離。
  - [x] 6. **ストリーミングパイプラインの統合 (`AudioStreamPipeline`)**: `StreamingVadManager`, `ContextManager`, `transcribe_stream` を連携させ、発話区間の切り出し・逐次推論・文脈維持を統合。
  - [x] 7. **ドキュメント反映**: 新設パラメータやストリーミング仕様変更、`vad_filter` の取り扱いについて `README.md` に追記する。
  - [x] 8. **セルフチェック指摘事項の改善**:
    - `cli.py` (603行) を `cli.py`, `cli_ui.py`, `cli_options.py` に分割し全ファイル 300 行以下（目標200行以下）へ。
    - `pipeline.py` (383行) を `pipeline.py`, `pipeline_events.py`, `pipeline_export.py` に分割し全ファイル 300 行以下へ。
    - `media.py` (301行) を 300 行以下へ整理。
    - `stt.py`, `streaming/core.py`, 新規作成モジュールの全公開インターフェースに Google スタイル Docstring を網羅。
    - `tests/test_streaming.py` の `asyncio.sleep(0.01)` を `asyncio.Event` 待機へ置き換え、完全決定論的テストへ改修。
    - `uv run pre-commit run --all-files -v` による静的解析・型チェック・全テスト・カバレッジ100%の検証。
    - セルフチェック9項目の再評価と報告。

### Phase 12: STREAMING_LOG リアルタイムログ出力および無音タイマー式タイミング確定の実装 ＆ エリア・リファクタリング
- **目的**: `STREAMING_LOG` 設定 (`true`/`false`) におけるログ出力フォーマットを刷新し、独自VADチャンク連携、生認識テキストと後処理イベントの分離、「無音タイマー確定方式（最大 `end_padding` 遅延）」によるリアルタイムな余韻調整・重複防止、およびテストコード/ソースコードのモジュール分割（エリア・リファクタリング）を実現する。
- **方針**:
  - `vad_filter=False` に固定のまま、独自実装VADによるチャンクイベント（開始、終了、長さ）を適切に通知・連携する。
  - `sanitizer.py` に `DropReason` / `SanitizeResult` を導入し、除外・短縮理由を判別可能にする。
  - **無音タイマー確定方式（スライディング無音確定）**:
    - VADチャンク検出時に即座に推論・サニタイズを行い、`[VAD]` ➔ `  [Whisper]` ➔ `  [テキスト置換 / 理由別除外]` を出力。
    - 発話終了後、`end_padding`（0.8s〜1.0s）分の無音が経過した時点で満額の余韻を付与して `  [Text]` を確定出力。
    - `end_padding` 以内に次の発話が開始された場合は、重複分を切り詰めて `  [重複防止]` ➔ `  [Text]` を出力。
  - `cli_ui.py` のハンドラを改修し、インデント出力（`STREAMING_LOG = true`）およびシンプル出力（`STREAMING_LOG = false`）を完全実装する。
  - `▶ [postprocess_summary]` 記号を統一。
  - **テストコード・エリアリファクタリング**: 領域 A〜D の責務別テストモジュールに分割・整理し、全42ファイルを 300 行以下（目標200行前後）に収容。
  - **ソースコード・エリアリファクタリング**: `stt.py` (VAD分離), `media.py` (probe/ffmpeg分離), `pipeline_events.py`, `sanitizer.py` を責務分割し、全ファイルを目標200行前後に適正化。
- **タスク詳細**:
  - [x] 12.1 独自実装VADによるチャンクイベント通知の復元・連携 (`vad_filter=False` 前提、`vad_chunks` / `vad_chunk_start`)
  - [x] 12.2 `sanitizer.py` における除外・短縮理由（`no_speech`, `speed`, `loop`, `empty`, `repeat`）の判別機能 (`SanitizeResult`, `DropReason`) 実装
  - [x] 12.3 `timing.py` & `pipeline_events.py` における「無音タイマー確定方式（最大 `end_padding` 遅延）」の実装（即時推論・後処理通知 ➔ 無音経過/次発話時の重複防止・確定通知）
  - [x] 12.4 `cli_ui.py` における `STREAMING_LOG = true` のインデントログ出力フォーマット実装（`[VAD]` / `[Whisper]` / `[後処理]` / `[重複防止]` / `[Text]`、`▶ [postprocess_summary]`）
  - [x] 12.5 `cli_ui.py` における `STREAMING_LOG = false` のシンプル出力実装（余分な進捗抑制、`[Text]` のみ順次出力）
  - [x] 12.6 テストコードのエリア・リファクタリング（領域 A〜D 分割、全42ファイル300行以下・目標200行前後達成）
  - [ ] 12.7 ライブラリソースコードのエリア・リファクタリング（`stt.py`, `media.py`, `pipeline_events.py`, `sanitizer.py` の責務分割・全ファイル200行前後達成）
  - [ ] 12.8 単体・結合テスト全件通過（カバレッジ100%維持）および `uv run pre-commit run --all-files` による一括自動検証

### Phase 13: 耐障害性およびメトリクス通知の実装
※ 要件仕様書に基づく非機能要件の実現タスク。
- [ ] 13.1 **CUDA OOMリカバリの実装**: `stt.py` における Whisper モデルの `model.transcribe` 実行箇所を `try-except RuntimeError` で保護。「out of memory」エラーを捕捉した際、パイプラインをクラッシュさせずに `on_error` コールバックへ通知し、安全にバッファを破棄（または CPU 推論へフォールバック）する安全機構を実装。
- [ ] 13.2 **稼働メトリクス計測と通知**: `pipeline.py` に `MetricsTracker` クラスを新設。VADが `SPEECH_END` を検知した時刻を記録し、後処理を経て `on_segment` コールバックが発火するまでの差分時間（E2Eレイテンシ）を計測。内部バッファの滞留フレーム数とともに `callbacks.on_metrics(latency_ms, buffer_size)` を定期的に呼び出すロジックを構築。

### Phase 14: ライブラリ標準インターフェースとアーキテクチャの準拠
※ 要件仕様書で定義された詳細なインターフェース設計に対する現状の差分を解消するタスク。
- [ ] 14.1 **出力データモデルの標準化**: `models.py` 等の共通定義に要件仕様書通りの `@dataclass RecognizedSegment`（`is_peak_sound` などの将来対応フラグを含む）を厳密に定義し、STTプロバイダーの戻り値およびコールバックの引数の型をこれに統一する。
- [ ] 14.2 **ステータスクリア機能 (`reset`) の実装**: `AudioStreamPipeline` に `reset()` メソッドを新設。内部で `VadManager.reset()`, `ContextManager.clear()` を呼び出し、Lock オブジェクトを用いて非同期推論スレッドと安全に同期しながら、リングバッファや文脈プロンプトを即座に初期化する仕組みを実装。
- [ ] 14.3 **推論エンジンの抽象化と Factory パターン**: 現在 `stt.py` に混在しているロジックを分割。共通の `TranscriberProvider` (Protocol) を定義し、ローカル用の `FasterWhisperProvider` と テスト用の `MockProvider` を実装。`config.stt.engine` の値に基づいて Factory パターンで動的にインスタンスを切り替える DI 構造へリファクタリング。
- [ ] 14.4 **単体テストの Mock 化とカバレッジ強化**: `test_stt.py` などのテストコードにおいて、GPUやデバイスを必要としない `MockProvider` を差し込むアーキテクチャを活用し、`np.zeros` 等のダミー波形入力に対する状態遷移やコールバック発火を検証する高品質な単体テストを拡充する。



### （将来検討）音響イベント検知
- マルチトラック分離設計および事前学習モデルを用いたイベント検知の導入（詳細は設計書参照）


