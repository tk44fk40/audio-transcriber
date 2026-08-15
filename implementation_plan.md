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
- [x] `src/audio_transcriber/media.py` の `remux_video` において、出力音声コーデックを `aac` 固定ではなく、元のトラックのコーデック (`codec_name`) を引き継ぐように修正
- [x] コーデックが取得できない (`unknown`) 場合は非圧縮の `pcm_s16le` にフォールバックする安全処理を追加
- [x] 作業完了後はセルフチェック（テスト・静的解析など）を実行し、ユーザーへ結果を報告する
- [x] **指示があるまでコミットやプッシュ等のGit操作は行わない**

### Phase 8: カバレッジ（テスト漏れ）の完全網羅 (新規追加)
- [x] `pyproject.toml` の `exclude_lines` の修正（Protocol等の `...` 記述が正しく除外されるように正規表現を修正）
- [x] `src/audio_transcriber/cli.py` のテスト実装（ストリーミングモード、進捗コールバック処理等の網羅）
- [x] `src/audio_transcriber/pipeline.py` のテスト実装（単一セグメント処理、重複防止バッファリング等の網羅）
- [x] `src/audio_transcriber/stt.py` のテスト実装（VADタイムスタンプ事前取得と例外処理等の網羅）
- [x] `src/audio_transcriber/streaming.py` のテスト実装（非同期ストリーミングパイプラインの例外・キャンセル処理等の網羅）
- [x] `src/audio_transcriber/postprocess.py`, `media.py`, `denoise/engines/rnnoise.py` 等の残り未カバー行（例外系ハンドリング等）のテスト実装
- [x] 再度 `uv run pre-commit run --all-files -v` にてセルフチェックを実行し、除外項目以外が100%カバーされたことを確認・報告する

### Phase 9: ストリーミング出力 (cli.py) の完全リアルタイム化 (Bugfix)
- **現状の問題**: `streaming_integration_plan.md` で合意した「処理完了後の一括ツリー表示の廃止」と「STREAMING_LOG (ツリーモード/シンプルモード) に応じたリアルタイム出力」が正しく実装されていない。
- **修正内容**:
  1. `config.py` と `config.toml` のストリーミング設定 (`StreamConfig`) に `streaming_log: bool = False` を追加。
  2. `cli.py` に `--streaming-log / --no-streaming-log` のコマンドライン引数を追加。
  3. `cli.py` の `run_pipeline` 終了後に一括表示しているツリーログ処理（345行目付近〜末尾）を完全削除。
  4. `handle_progress` および `handle_segment` を修正し、`streaming_log == True` の場合はリアルタイムに `[VAD]`, `[Whisper生]`, `[無音捏造等除外]` などのイベントをツリー形式で出力するように変更。`False` の場合は、生字幕1行のみをシンプルに出力。
  5. これらの改修に伴い、すでに書かれているテスト（`test_cli.py`等）も最新のリアルタイム出力仕様に合わせて修正・カバレッジ100%を維持する。

### Phase 10: リアルタイム処理アーキテクチャの完全修正（VADタイムスタンプ・後処理のストリーミング化）
- **現状の問題**:
  - `faster-whisper` から事前に取得したVADチャンクのタイムスタンプが数千時間等の異常な値で出力されている。
  - 後処理（無音捏造フィルタ・辞書置換等のサニタイズ）が、依然として `pipeline.py` の最後で一括処理されるバッチ処理アーキテクチャのまま残っているため、Whisper出力・VAD・後処理のログがすべて別のブロックで出力されてしまい、ユーザーの求める「VADチャンクごとにネストされたリアルタイムのツリー表示」になっていない。
- **修正内容**:
  1. `pipeline.py` の `_internal_on_segment` コールバック内に、`TextPostProcessor` と `SegmentSanitizer` の処理を移動させ、**セグメント1件ごとにリアルタイムで後処理・サニタイズ**を行うストリーミング型にアーキテクチャを完全修正する。
  2. `pipeline.py` は、現在のセグメントが属する `[VAD]` チャンクを特定し、新しいVADチャンクに入ったタイミングで `handle_progress("vad_chunk_start", ...)` を発行するようにし、VADチャンクのヘッダがリアルタイムに適切なタイミングで表示されるようにする。
  3. `[無音捏造等除外]` などのサニタイズ除外イベントも、セグメント処理と同時に `handle_progress` 経由で発行し、`[Whisper生]` の直下にツリー状に出力されるようにする。
  4. VADタイムスタンプ異常の原因（`faster-whisper` のログパースミスやサンプルレートの誤算等）を特定し、正しい秒数（タイムコードオフセット加算済み）で出力されるように修正する。
  5. テストを修正し、100%カバレッジを維持する。

- **修正後の出力イメージ**:
  ```text
  ▶  Whisper (large-v3-turbo) による文字起こし推論中...

  [VAD] 00:08:49,000 --> 00:09:07,000 (18.00s)
    [Whisper生] 00:08:49,707 --> 00:08:52,137 (2.43s) "お前もっとおいで。回収。"
    [Whisper生] 00:08:53,857 --> 00:08:57,227 (3.37s) "回収。そこにあるでしょ。"
    [Whisper生] 00:08:59,007 --> 00:09:01,007 (2.00s) "そうそう、そりゃそりゃ。"
    [Whisper生] 00:09:01,227 --> 00:09:02,107 (0.88s) "そりゃ、もっとおいでそりゃ。"
    [無音捏造等除外] [除外] 00:09:01,227 (0.9s) 'そりゃ、もっとおいでそりゃ。' (無音捏造/高速ループ)
    [Whisper生] 00:09:03,157 --> 00:09:04,617 (1.46s) "よしよしよしよし。"

  [VAD] 00:09:27,000 --> 00:09:44,000 (17.00s)
    [Whisper生] 00:09:27,087 --> 00:09:29,187 (2.10s) "おいで。おやつあげるからおいで。"
    [Whisper生] 00:09:31,067 --> 00:09:43,317 (12.25s) "おやつあげるから。頑張ろうな。"
    [テキスト置換] [置換] '頑張ろうな' -> 'がんばろうな'
    [Whisper生] 00:09:43,037 --> 00:09:43,317 (0.28s) "張ろうな。"
    [無音捏造等除外] [除外] 00:09:43,037 (0.3s) '張ろうな。' (無音捏造/高速ループ)
  ```

### （将来検討）音響イベント検知
- [ ] マルチトラック分離設計（マイク音 ➔ STT/声検知、ゲーム音 ➔ ゲームSE/環境音検知）
- [ ] 手法 1, 3 によるイベント検知モデルの導入

## 3. ライブラリ利用を想定したパラメータ引き渡し設計
CLIからだけでなく、別のPythonスクリプトからライブラリとして利用される場合でも正しくパラメータが反映されるよう、設定オブジェクトを経由した引き渡し等のアーキテクチャ・実装ルールを遵守します。
※具体的な設計ルールおよび実装例については、**詳細設計書（[`docs/streaming_integration_plan.md`](file:///home/tk44/ghq/github.com/tk44fk40/audio-transcriber/docs/streaming_integration_plan.md)）の「4. ライブラリ利用を想定したパラメータ引き渡し設計」** を参照してください。

## 【ドキュメント更新】
- [x] `README.md` および関連ドキュメントへ、追加した設定パラメータ・CLI引数の使用方法を追記

## 【品質保証・セルフチェックプロセス】
- [x] 各機能修正・実装時のセルフチェックリストの実施と結果報告
- [x] カバレッジナレッジ（`docs/testing_and_coverage.md`）の確認と遵守
- [x] テストが正しく実装されているか、ケース漏れがないかの網羅性確認（ナレッジで除外指定されている箇所以外は全てカバーする）
- [x] 静的解析（basedpyright, ruff）の実行
- [x] カバレッジの計測と報告

## 【Git ワークフロー & 最終確認】
- [x] **（※重要）自動でのコミット・プッシュは絶対に行わないこと**
- [x] 実装・自動テスト・カバレッジの確認完了後、ユーザーに報告する
- [x] ユーザーによる実際の動作確認（手動確認）が完了し、承認を得た後にのみコミットとプッシュを実施する
- [x] （※Issueの更新およびプルリクエストの作成は省略する）
