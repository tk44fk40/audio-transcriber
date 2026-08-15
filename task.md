# タスクリスト (Task List)

## 進行中 / 未完了
- [ ] **Phase 4: 音声品質向上のためのマスタリング前処理追加** (完了待ち - ブランチ: issue-1/feat-model-resident-stt-core)
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
- [ ] **Phase 7: マスタリング動画の音声コーデック維持 (Bugfix)**
  - [ ] 作業ブランチ (`issue-1/feat-model-resident-stt-core`) にて作業
  - [ ] 7.1 `media.py` の `remux_video` にて出力音声コーデックを元のトラックから引き継ぐように修正
  - [ ] 7.2 セルフチェック（テスト・静的解析）を実施し結果報告
  - [ ] 7.3 指示があるまでコミット・プッシュは保留する

## 完了・待機中
- [ ] **Phase 2 & 3: ストリーミング統合パイプライン・コールバック・API (動作確認待ち)**
  - [x] `callbacks.py` の定義
  - [x] `streaming.py` の実装
  - [x] テストの追加・検証・厳格化
  - [x] `config.py` および TOML ファイルへの `[stream]` パラメータ追加
- [x] **Phase 1: モデル常駐型 VAD+Whisper コア ＆ 共通データモデル**

## アーキテクチャ設計・実装指針
- [ ] **7. ライブラリ利用を想定したパラメータ引き渡し設計の遵守**
  - [ ] 7.1 設定オブジェクト (`AppConfig`, `MasteringConfig` 等) を経由したパラメータの引き渡し
  - [ ] 7.2 関数・クラスへのコンストラクタ注入 (DI) の徹底
  - [ ] 7.3 `rnnoise.py` や `pipeline.py` におけるグローバルステート（CLIコンテキスト等）の排除

## ドキュメント更新
- [ ] **7. README 等のドキュメント更新**
  - [ ] 7.1 追加された設定パラメータ（TOML）とCLI引数の使用方法を `README.md` に追記
  - [ ] 7.2 必要に応じて `docs/` 配下の関連ドキュメントを更新

## 全フェーズ共通
- [ ] **品質保証・セルフチェックプロセス**
  - [ ] 各機能修正・実装時のセルフチェックリストの実施と結果報告
  - [ ] カバレッジナレッジの確認と遵守、テストケース漏れの確認
  - [ ] 静的解析（basedpyright, ruff）の実行、カバレッジ計測と報告
- [ ] **Git ワークフロー & 最終確認**
  - [ ] **自動でのコミット・プッシュは行わない**
  - [ ] 実装・テスト完了後、ユーザーへ報告し動作確認を依頼
  - [ ] 動作確認と承認後、コミットとプッシュを実施（Issue/PR作成は省略）
