# タスクリスト (Task List)

## 完了済みフェーズ
- [x] **Phase 1**: モデル常駐型 VAD+Whisper コア ＆ 共通データモデルの実装
- [x] **Phase 2**: ストリーミング統合パイプライン ＆ 非同期コールバックの実装
- [x] **Phase 3**: 設定・公開 API 統合
- [x] **Phase 4**: 音声品質向上のためのマスタリング前処理追加
- [x] **Phase 5**: CLI・パイプラインのストリーミング対応改修
- [x] **Phase 6**: VADタイムスタンプバグ修正
- [x] **Phase 7**: マスタリング動画の音声コーデック維持
- [x] **Phase 8**: カバレッジ（テスト漏れ）の完全網羅（100%達成）
- [x] **Phase 9**: ストリーミング出力 (cli.py) の完全リアルタイム化
- [x] **Phase 10**: リアルタイム処理アーキテクチャの完全修正（VADタイムスタンプ・後処理のストリーミング化）

- [x] **Phase 11**: 真のストリーミング入力（True Streaming）アーキテクチャへの完全移行
  - [x] 11.1 (第1弾) Config周りの実装: `config.py` と TOML のパース処理追加し `test_config.py` を GREEN にする
  - [x] 11.2 (第2弾) ContextManager の実装: `managers.py` に文脈管理ロジックを実装し該当テストを GREEN にする
  - [x] 11.3 (第3弾) StreamingVadManager の実装: チャンク管理ロジックを実装し全テストを GREEN にする
  - [x] 11.4 設定・CLIからの `vad_filter` 廃止および内部 `vad_filter=False` 固定化
  - [x] 11.5 `TranscriberProvider` (STTインターフェース) / `FasterWhisperProvider` に `transcribe_stream` を新設・逐次推論ロジック実装
  - [x] 11.6 パイプラインにおける「ファイル入力」と「ストリーミング入力」の責務分離 (`AudioStreamPipeline` 統合)
  - [x] 11.7 新規パラメータおよびストリーミング仕様変更について `README.md` に反映
  - [x] 11.8 テストコード品質改善・自律リファクタリングループ (境界値バリデーション・決定論的非同期テスト・統合ファイル整理・カバレッジ100%達成)
  - [x] 11.9 セルフチェック指摘事項の改善（ファイル行数300行以下削減、Docstring網羅、非同期sleep完全排除、自動検証）
    - [x] モジュール行数削減（cli.py, pipeline.py, media.py の分割・300行以下厳格化）
    - [x] Docstring 補強（stt.py, streaming/core.py, 新規モジュール等の全公開APIにGoogleスタイルDocstring付与）
    - [x] 非同期テストの sleep 完全排除（test_streaming.py を asyncio.Event 待機へ改修）
    - [x] 一括自動検証（pre-commit run --all-files で100%パス・カバレッジ100%）
    - [x] セルフチェック9項目の再評価と報告書作成

## 進行中フェーズ

### Phase 14: STREAMING_LOG リアルタイムログ出力および無音タイマー式タイミング確定・独自VADチャンク連携の修正
- [x] 14.1 独自実装VADによるチャンクイベント通知の復元・連携 (`vad_filter=False` 前提、`vad_chunks` / `vad_chunk_start`)
- [x] 14.2 `sanitizer.py` における除外・短縮理由（`no_speech`, `speed`, `loop`, `empty`, `repeat`）の判別機能 (`SanitizeResult`, `DropReason`) 実装
- [x] 14.3 `timing.py` & `pipeline_events.py` における「無音タイマー確定方式（最大 `end_padding` 遅延）」の実装（即時推論・後処理通知 ➔ 無音経過/次発話時の重複防止・確定通知）
- [x] 14.4 `cli_ui.py` における `STREAMING_LOG = true` のインデントログ出力フォーマット実装（`[VAD]` / `[Whisper]` / `[後処理]` / `[重複防止]` / `[Text]`、`▶ [postprocess_summary]`）
- [x] 14.5 `cli_ui.py` における `STREAMING_LOG = false` のシンプル出力実装（余分な進捗抑制、`[Text]` のみ順次出力）
- [x] 14.6 単体テスト・結合テストの追加・更新（TDDサイクル、境界値・エッジケース網羅）
- [x] 14.7 全ファイル300行以下・Docstring網羅・`uv run pre-commit run --all-files` で全検証（カバレッジ100%達成）


## 将来対応
- [ ] 音響イベント検知（叫び声・大音量ピーク・笑い声等の分類検知および即時通知）

## 全フェーズ共通ルール
- [ ] **品質保証・セルフチェックプロセス** (テストケース網羅・静的解析・カバレッジ100%)
- [ ] **Git ワークフロー** (自動コミット・プッシュ禁止。動作確認後に実施)

