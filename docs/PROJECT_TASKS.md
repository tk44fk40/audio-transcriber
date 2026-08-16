# タスクリスト (Task List)

## 進行中フェーズ

### Phase 13: コードベースリファクタリング

#### 13.1 モジュール責務分割（最優先）

**`pipeline_events_collector.py`（291行）の分割**
現状: イベント収集・通知 ＋ 後処理オーケストレーション(sanitize/postprocess/timing) ＋ UIフォーマット が混在
- [ ] 13.1.1 後処理オーケストレーション（sanitize → postprocess → timing適用）を `segment_processor.py` として分離
- [ ] 13.1.2 UIフォーマット処理（タイムスタンプ文字列生成・矢印記号等）を `cli_ui.py` 側に移動し、コレクターはデータ（数値）のみ通知するように変更

**`stt.py`（267行）の分割**
現状: Whisper推論 ＋ VADチャンク検出 が混在
- [ ] 13.1.3 `transcribe_file` 内の VAD チャンク検出ロジックを `stt_vad.py` に移動し、`on_progress` 有無によるコードパス分岐バグを修正

**`config.py`（258行）の分割**
現状: TOMLファイルロード ＋ 辞書→Dataclass変換パース処理 が混在
- [ ] 13.1.4 `parse_config_dict` を `config_parser.py` に分離し、`config.py` を 100 行以下に削減

**`config_models.py`（258行）の分割**
現状: 13以上の設定Dataclassが1ファイルに集中
- [ ] 13.1.5 機能エリア別ファイルに分割（例: `config_models_stt.py`, `config_models_stream.py`）し 200 行以下に削減

**`streaming/core.py`（275行）の分割**
現状: パイプラインライフサイクル管理 ＋ 後処理(sanitize/postprocess) が混在
- [ ] 13.1.6 後処理部分（sanitize → postprocess）を `segment_processor.py`（13.1.1で作成）に委譲

#### 13.2 重複コードの共通化（優先度: 高）
- [ ] 13.2.1 `normalize_audio_array(audio) -> np.ndarray` 関数を `audio_utils.py` に追加する
  - 対象: `streaming/core.py` の `int16→float32` 変換と `stt.py` のステレオ→モノラル変換を統合

#### 13.3 `stt.py` の実装改善（優先度: 高）
- [ ] 13.3.1 `FasterWhisperProvider.__init__` でのモデルロードを廃止し、初回推論時に遅延ロードする形に変更（§7.4 準拠）

#### 13.4 セグメントデータ型の統一（優先度: 高）
- [ ] 13.4.1 `stt.py` の `transcribe_file` / `transcribe_stream` 戻り値を `list[dict[str, Any]]` から `list[RecognizedSegment]` に変更
- [ ] 13.4.2 `pipeline_events_collector.py` の `handle_segment` を `dict` → 型付きモデルで受け取るように変更
- [ ] 13.4.3 `timing.py` の `# type: ignore[type-arg]` を全廃
- [ ] 13.4.4 `sanitizer_core.py` の `segment: object` 型を型付きモデルに変更し `isinstance(segment, dict)` 分岐を排除

#### 13.5 再エクスポートのみのモジュールを削除（優先度: 中）
- [ ] 13.5.1 `media.py` / `sanitizer.py` / `pipeline_events.py` を削除し、呼び出し元を新モジュール名（`media_ffmpeg.py`, `media_probe.py`, `sanitizer_core.py` 等）に直接書き換える

#### 13.6 外部依存ツールの存在チェック追加（優先度: 中）
- [ ] 13.6.1 `cli.py` または `pipeline.py` 初期化時に `ffmpeg` および `ffprobe` の存在チェック（`shutil.which`）を追加し、未インストール時はわかりやすいエラーで終了させる

#### 13.7 `exporter.py` の時間フォーマット共通化（優先度: 中）
- [ ] 13.7.1 `exporter.py` 内の `format_timestamp` (SRT用) と `format_vtt_timestamp` (WebVTT用) で重複している時間計算ロジックを共通ヘルパーメソッドに統合

#### 13.8 Docstring・型注釈の品質向上（優先度: 低）
- [ ] 13.8.1 `exporter.py` の `Raises` セクション追記
- [ ] 13.8.2 `basedpyright` の型チェック警告をゼロにする

#### 13.9 テストモジュールの再構成（各モジュール分割に追従）

13.8 までの全リファクタリング作業の完了後、対応するテストモジュールも分割後の粒度に合わせて再構成する。
原則: **1テストモジュール = 1ソースモジュール**

**`pipeline_events_collector.py` 分割に追従（13.1.1 / 13.1.2）**
- [ ] 13.9.1 新規 `test_segment_processor.py` を作成し、`segment_processor.py` の後処理オーケストレーション（sanitize → postprocess → timing）を単体テスト
- [ ] 13.9.2 `test_pipeline_events.py` をイベント収集・通知のみのテストに絞り込み、後処理テストを削除

**`stt.py` 分割に追従（13.1.3）**
- [ ] 13.9.3 `test_stt_vad.py` に移動した VAD チャンク検出ロジックのテストを追加
- [ ] 13.9.4 `test_stt.py` から VAD 関連テストを削除し、Whisper推論・モデルライフサイクルに限定

**`config.py` 分割に追従（13.1.4）**
- [ ] 13.9.5 新規 `test_config_parser.py` を作成し、`config_parser.py` の辞書→Dataclass変換ロジックをテスト
- [ ] 13.9.6 `test_config_parse.py` を TOML ファイルロード処理のみに絞り込み

**`config_models.py` 分割に追従（13.1.5）**
- [ ] 13.9.7 `test_config_models.py` をエリア別ファイルに合わせて分割（例: `test_config_models_stt.py`, `test_config_models_stream.py`）

**再エクスポートモジュール削除に追従（13.5.1）**
- [ ] 13.9.8 `test_media_extract.py` / `test_media_remux.py` のインポートを `media_ffmpeg.py` / `media_probe.py` に直接更新

## 未着手のフェーズ

### Phase 14: 耐障害性およびメトリクス通知の実装
- [ ] 14.1 CUDA OOM 発生時の例外捕捉と安全な CPU フォールバック等のリカバリ処理実装
- [ ] 14.2 処理レイテンシやバッファ残量等の稼働状況を監視し `on_metrics` コールバックで定期通知する仕組みの構築

### Phase 15: ライブラリ標準インターフェースとアーキテクチャの準拠
- [ ] 15.1 出力データモデルの標準化 (`RecognizedSegment` 等への完全準拠)
- [ ] 15.2 ステータスクリア機能 (`reset()` メソッド) の実装
- [ ] 15.3 推論エンジンの抽象化と Factory パターンによる DI 切り替えリファクタリング

### Phase 16: GPU/デバイス不要テスト基盤の整備（DI注入による全体テスト堅牢化）
- [ ] 16.1 `MockProvider` の全テストモジュール展開（GPU 依存スキップ制御整備）
- [ ] 16.2 ダミー波形入力によるパイプライン状態遷移・コールバック発火の単体テスト拡充（全モジュール横断）
- [ ] 16.3 CPU 環境での完全実行検証（CI 導入への道を開く）

## 将来対応
- [ ] 音響イベント検知（叫び声・大音量ピーク・笑い声等の分類検知および即時通知）

## 全フェーズ共通ルール
- [ ] **品質保証・セルフチェックプロセス** (テストケース網羅・静的解析・カバレッジ100%)
- [ ] **Git ワークフロー** (自動コミット・プッシュ禁止。動作確認後に実施)
