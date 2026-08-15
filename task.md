# タスクリスト (Task List)

## 進行中 / 未完了
- [x] **Phase 4: 音声品質向上のためのマスタリング前処理追加** (完了待ち - ブランチ: issue-1/feat-model-resident-stt-core)
  - [x] 4.1 実装前の FFmpeg パラメータ動作検証（ターミナルでのテスト）
  - [x] 4.2 `config.toml`, `config.example.toml`, `config.py` への `[mastering]` 設定追加（詳細は[`docs/streaming_integration_plan.md`](file:///home/tk44/ghq/github.com/tk44fk40/audio-transcriber/docs/streaming_integration_plan.md)参照）
  - [x] 4.3 `cli.py` へのマスタリング用コマンドライン引数追加
  - [x] 4.4 `rnnoise.py` の FFmpeg フィルタチェーンへのマスタリング処理組み込み
- [x] **Phase 5: CLI・パイプラインのストリーミング対応改修**
  - [x] 5.1 `config.toml`, `config.example.toml`, `config.py` へのストリーミング用設定追加（詳細は[`docs/streaming_integration_plan.md`](file:///home/tk44/ghq/github.com/tk44fk40/audio-transcriber/docs/streaming_integration_plan.md)参照）
  - [x] 5.2 `cli.py` へのストリーミング用コマンドライン引数追加
  - [x] 5.3 `pipeline.py` における `_internal_on_segment` コールバックのストリーミング対応（単一セグメント処理・遅延バッファリング）
  - [x] 5.4 `sanitizer.py`, `postprocess.py` の単一セグメント対応メソッド追加
  - [x] 5.5 `cli.py` の出力をストリーミング形式（リアルタイムツリーまたはシンプル出力）に改修（一括表示の廃止）
- [x] **Phase 6: VADタイムスタンプバグ修正**
  - [x] 6.1 `stt.py` で VAD タイムスタンプをサンプル数から秒数(float)へ変換する処理の修正
- [x] **Phase 7: マスタリング動画の音声コーデック維持 (Bugfix)**
  - [x] 作業ブランチ (`issue-1/feat-model-resident-stt-core`) にて作業
  - [x] 7.1 `media.py` の `remux_video` にて出力音声コーデックを元のトラックから引き継ぐ（不明時は `pcm_s16le` にフォールバック）ように修正
  - [x] 作業完了後はセルフチェック（テスト・静的解析など）を実行し、ユーザーへ結果を報告する
- [x] **指示があるまでコミットやプッシュ等のGit操作は行わない**

### Phase 8: カバレッジ（テスト漏れ）の完全網羅
- [x] `pyproject.toml` の `exclude_lines` の修正（Protocol等の `...` が正しく除外されるように正規表現修正）
- [x] `cli.py` のテスト実装（ストリーミングモード等）
- [x] `pipeline.py` のテスト実装（単一セグメント処理・バッファリング等）
- [x] `stt.py` のテスト実装（VADタイムスタンプ事前取得等）
- [x] `streaming.py` のテスト実装（非同期ストリーミングの例外等）
- [x] `postprocess.py`, `media.py`, `rnnoise.py` 等の残り未カバー行テスト実装
- [x] `uv run pre-commit run --all-files -v` にてセルフチェックを実行し、除外項目以外100%カバーを確認・報告

### Phase 9: ストリーミング出力 (cli.py) の完全リアルタイム化 (Bugfix)
- [x] `config.py` と `config.toml` に `streaming_log: bool = False` を追加
- [x] `cli.py` に `--streaming-log` のコマンドライン引数を追加
- [x] 処理完了後の一括ツリー表示（345行目以降）を完全削除
- [x] `handle_progress` と `handle_segment` を修正し、設定値に応じてリアルタイムツリーまたはシンプル出力に切り替えるように実装
- [x] 今回の変更に合わせて `test_cli.py` を修正し、カバレッジ100%を維持する

### Phase 10: リアルタイム処理アーキテクチャの完全修正（VADタイムスタンプ・後処理のストリーミング化）
- [x] `stt.py` の VAD タイムスタンプ抽出ロジック（`faster-whisper` のログパース）を修正し、正しい秒数を取得する
- [x] `pipeline.py` にて、後処理（`TextPostProcessor`, `SegmentSanitizer`）の実行をファイル末尾での一括処理から `_internal_on_segment` 内部での1セグメントごとの処理に移行する
- [x] `_internal_on_segment` にて、セグメントの時間から現在のVADチャンクを特定し、新しいVADチャンクに入ったタイミングで `vad_chunk_start` イベントを発行する
- [x] 後処理の除外・置換結果も、`_internal_on_segment` 内で即座に `handle_progress` でイベント発行する
- [x] アーキテクチャ変更に合わせてテスト群（`test_pipeline.py` 等）を修正し、カバレッジ100%を維持する

### （将来検討）音響イベント検知

## 完了・待機中
- [x] **Phase 2 & 3: ストリーミング統合パイプライン・コールバック・API (動作確認待ち)**
  - [x] `callbacks.py` の定義
  - [x] `streaming.py` の実装
  - [x] テストの追加・検証・厳格化
  - [x] `config.py` および TOML ファイルへの `[stream]` パラメータ追加
- [x] **Phase 1: モデル常駐型 VAD+Whisper コア ＆ 共通データモデル**

## アーキテクチャ設計・実装指針
- [x] **7. ライブラリ利用を想定したパラメータ引き渡し設計の遵守**
  - [x] 7.1 設定オブジェクト (`AppConfig`, `MasteringConfig` 等) を経由したパラメータの引き渡し
  - [x] 7.2 関数・クラスへのコンストラクタ注入 (DI) の徹底
  - [x] 7.3 `rnnoise.py` や `pipeline.py` におけるグローバルステート（CLIコンテキスト等）の排除

## ドキュメント更新
- [x] **7. README 等のドキュメント更新**
  - [x] 7.1 追加された設定パラメータ（TOML）とCLI引数の使用方法を `README.md` に追記
  - [x] 7.2 必要に応じて `docs/` 配下の関連ドキュメントを更新

## 全フェーズ共通
- [x] **品質保証・セルフチェックプロセス**
  - [x] 各機能修正・実装時のセルフチェックリストの実施と結果報告
  - [x] カバレッジナレッジの確認と遵守、テストケース漏れの確認
  - [x] 静的解析（basedpyright, ruff）の実行、カバレッジ計測と報告
- [x] **Git ワークフロー & 最終確認**
  - [x] **自動でのコミット・プッシュは行わない**
  - [x] 実装・テスト完了後、ユーザーへ報告し動作確認を依頼
  - [x] 動作確認と承認後、コミットとプッシュを実施（Issue/PR作成は省略）
