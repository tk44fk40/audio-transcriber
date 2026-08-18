# タスクリスト (Task List)

## 進行中フェーズ



### Phase 14: 統合パイプラインアーキテクチャの実装 (コーディングフェーズ)

Phase 13 で策定した詳細設計（`detailed_design.md`）に基づき、新しいキューベース・リアルタイム進行アーキテクチャを実装します。

#### 14.1 オーケストレーターとプロデューサー層の構築
- [x] 14.1.1 `pipeline_supervisor.py` の作成
  - `PipelineSupervisor` クラスの実装（全体例外捕捉、CLI向けFacade）
  - CUDA OOM 等のランタイムエラーからの安全なリカバリ処理の実装
  - ステータスクリア機能 (`reset()` メソッド) によるライフサイクル管理の実装
- [x] 14.1.2 `audio_producers.py` の作成と課題修正
  - [x] `AudioChunkQueue` (非同期セーフキュー) の実装
    - `asyncio.Queue(maxsize=maxsize)` による Backpressure（バックプレッシャー）制御
    - キューが満杯時は投入元（Producers）を非ブロッキングでブロック（`await queue.put`）し、メモリ過剰消費（OOM）を防止
  - [x] `StreamAudioProducer` の実装
    - 外部から `feed_chunk(chunk, is_speech)` された音声バイト列をそのまま（パススルーで）キューへ供給
    - 終了時に `stop()` を呼ぶことで、終了センチネル `None` を安全にキューへ投入
  - [x] `FileAudioProducer` の実装
    - ノイズ除去（RNNoise等）が有効な場合、`AudioDenoiser` を用いて一時クリーンファイル（`*_clean_temp.wav`）を非同期スレッド（`asyncio.to_thread`）で生成
    - `asyncio.create_subprocess_exec` で非同期 FFmpeg プロセス（`pcm_s16le`, モノラル, 指定レート）を起動し、音声データを逐次デコード
    - デコード出力を `chunk_size_ms`（デフォルト100ms ＝ 16kHz時3200バイト）単位に厳密にスライスしながら、ループでキューへ順次投入
    - キャンセル・エラー・終了時に FFmpeg 子プロセスを確実に terminate/wait し、一時クリーンファイルを自動削除するクリーンアップ（`_cleanup()`）を実装
  - [x] `tests/test_audio_producers.py` の作成とテスト検証
    - [x] `test_audio_chunk_queue_basic`: 基本的なデータ投入、取得、qsize 挙動の検証
    - [x] `test_audio_chunk_queue_backpressure`: キュー満杯時に put が適切にブロックされ、get されたら再開される Backpressure 制御の検証
    - [x] `test_stream_audio_producer`: ストリーミングデータのパススルーと終了通知の検証
    - [x] `test_file_audio_producer_without_denoise`: デノイズ無効時の FFmpeg 非同期プロセス経由のデコードと100ms境界での正確なチャンク分割（不完全チャンクの余り処理、終了センチネル None 投入を含む）の検証
    - [x] `test_file_audio_producer_with_denoise`: デノイズ有効時に RNNoise 前処理（一時ファイル生成）を経てから、その一時ファイルを FFmpeg に渡して非同期にキューへ流す全体の連動テストの検証
  - [x] **指摘問題点に対する対処（タスク14.1.2 の堅牢化課題）**
    - [x] **課題A: キュー容量制限の動的化**
      - `AudioChunkQueue` の `maxsize=100` ハードコーディングを廃止。1チャンクの時間長とサンプリングレートから算出されるバイト数、および総蓄積目標秒数に基づき動的に `maxsize` を受け取るように改修する
    - [x] **課題B: 動画リマックス（音声トラック差し戻し）を見据えた一時ファイル（ノイズ除去済み音声）のライフサイクル再設計**
      - **背景**: ファイル入力（動画）時、文字起こし完了後に「ノイズが除去された綺麗な音声トラック」を元の動画に書き戻すリマックス（合成）処理が必要になる。そのため、ノイズ除去済み一時ファイル（`*_clean_*.wav`）を途中で勝手に削除してはならない。
      - **対策**:
        1. `FileAudioProducer` が勝手に一時ファイルを消去せず、ファイルパスを `producer.denoised_audio_path` プロパティ等で外部（オーケストレーター）に公開できるように設計変更する。
        2. 一時ファイルの最終クリーンアップ（削除）所有権をプロデューサー単体から、上位の `PipelineSupervisor` または統合パイプラインへ引き上げ、文字起こし ➔ リマックス（合成）のすべての行程が完全に終了した段階で、オーケストレーターが一括して消去するようにライフサイクルをリファクタリングする。
        3. 最初のノイズ除去時に生成したファイルを最後まで使い回すことで、ディスク書き出し（I/O）を最小限（全行程で1回のみ）に抑え効率を最大化する。
    - [x] **課題C: プロセス終了時のタイムアウトおよび強制停止（SIGKILL）の導入**
      - `_cleanup()` 内で `self._ffmpeg_process.terminate()` 後に一定時間（例: 0.5秒） `wait()` をタイムアウト監視。タイムアウトした場合は `kill()` (SIGKILL) を呼び出し、プロセス詰まりによる非同期イベントループの永続フリーズを防止する
    - [x] **課題D: FFmpeg のエラーログ伝播と異常終了検知**
      - `stderr=DEVNULL` を廃止し、`asyncio.subprocess.PIPE` 等で stderr をバッファリング。FFmpeg が異常終了（exit code != 0）した際、サイレントに文字起こしを空にするのではなく、エラー詳細を含む `RuntimeError` を送出しコールバックへ適切にエラー通知する
    - [x] **課題E: サンプリングレート仕様 of プロトコル整合性**
      - 16000Hz (Whisper想定) 以外のモデル（24kHzや48kHz等）が将来混在した際にも矛盾が生じないよう、Producer が要求サンプリングレートを引数で受け取る、または設定から動的に解決するインターフェース設計へ見直す
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
