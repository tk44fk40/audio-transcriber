# 実装計画: Lumi Companion ストリーミング連携 音声処理ライブラリ拡張 ＆ CLI改修

## 1. 概要
- **詳細設計書**: [detailed_design.md](./detailed_design.md)
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
- **Phase 11**: 真のストリーミング入力アーキテクチャへの完全移行（`AudioStreamPipeline` 統合）
- **Phase 12**: STREAMING_LOG リアルタイムログ出力・無音タイマー確定方式実装
- **Phase 13**: ファイル・ストリーミング統合パイプラインの詳細設計策定

## 3. 実装計画（進行中フェーズ）

具体的なタスク詳細は [PROJECT_TASKS.md](./PROJECT_TASKS.md) を参照。

### Phase 14: 統合パイプラインアーキテクチャの実装
Phase 13で策定した詳細設計に基づき、キューベースのリアルタイム進行パイプラインを実装する。

**【新旧共存・漸進的移行（漸進的リファクタリング）戦略】**
大規模な再設計を伴うため、既存の機能（`pipeline.py`、`streaming/core.py`等）および既存のテストコード（300件）を一切破壊せず、これらと完全に共存する形で新規コンポーネント（`pipeline_supervisor.py`等）を段階的に実装します。新アーキテクチャの全パーツが揃い、新しい E2E テストが完全にパスすることを確認するまで、既存のコードやテストは一切変更しません。これにより開発中も常に既存テストが 100% 合格し続ける状態を保証します。最後に CLI 等の呼び出し先を新システムに切り替え、十分な動作確認ができた後に旧ファイルを安全に削除・整理します。

本フェーズの実装の中で、以下の要件も同時に組み込んでアーキテクチャを完成させる。
- **耐障害性およびメトリクス**: CUDA OOM 等のランタイムエラーからのリカバリ処理（Supervisor層）と、稼働メトリクス計測・通知機能（`on_metrics`）の実装。
- **標準インターフェース準拠**: 出力データモデルの標準化（`RecognizedSegment`）、ステータスクリア機能（`reset()`）、および Factory パターンによる動的 DI 切り替えの実装。

### Phase 15: GPU/デバイス不要テスト基盤の整備
DI 注入による `MockProvider` を全テストモジュールに展開し、GPU なしの CPU 環境でも全テストが実行できるテスト基盤を整備する。

### （将来検討）音響イベント検知
マルチトラック分離設計および事前学習モデルを用いたイベント検知の導入（詳細は設計書参照）


---

## 4. 現在のモジュール構成（Phase 12.7 完了時点）

> 最終更新: 2026-08-16（Phase 12.7 エリアリファクタリング完了後）

### ライブラリ (`src/audio_transcriber/`) — 計 4,412行 / 34ファイル

#### コア・公開 API

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `__init__.py` | 52 | 公開 API のエントリポイント・外部向けエクスポート定義 |
| `models.py` | 177 | 共通データモデル（`TranscribeResult`, `Segment` 等のデータクラス定義） |
| `callbacks.py` | 73 | コールバックインターフェース定義（`on_segment`, `on_error` 等の Protocol） |
| `compat.py` | 50 | ライブラリ間バージョン差異吸収・互換レイヤー（Adapter/Shim） |

#### 設定

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `config.py` | 257 | TOML 設定ファイルのパース・ロード処理 |
| `config_models.py` | 258 | 設定データクラス定義（`VadConfig`, `SttConfig`, `StreamContextConfig` 等） |

#### STT（音声認識）

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `stt.py` | 266 | `FasterWhisperProvider` コア実装（Whisper モデルロード・推論・`transcribe_stream`） |
| `stt_types.py` | 96 | STT Provider Protocol 定義・型エイリアス（`TranscriberProvider` インターフェース） |
| `stt_vad.py` | 40 | Silero VAD ラッパー（VAD モデルロード・発話区間検出ロジック） |

#### ストリーミング

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `streaming/core.py` | 274 | `AudioStreamPipeline` — ストリーミング入力の統合パイプライン（VAD・推論・文脈管理の連携） |
| `streaming/managers.py` | 197 | `StreamingVadManager`（リングバッファ・チャンク切り出し）・`ContextManager`（文脈管理・タイムアウト） |
| `streaming/__init__.py` | 4 | streaming サブパッケージのエクスポート定義 |

#### パイプライン

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `pipeline.py` | 199 | ファイル入力パイプライン Facade（デノイズ→STT→後処理→エクスポートの統合） |
| `pipeline_events.py` | 13 | パイプラインイベント再エクスポート（後方互換窓口） |
| `pipeline_event_types.py` | 9 | イベント型定義（`PipelineEventType` 列挙など） |
| `pipeline_events_collector.py` | 290 | イベント収集・集約ロジック（VAD/Whisper/後処理各イベントの収集・発火） |
| `pipeline_export.py` | 53 | パイプライン出力エクスポート処理（SRT/WAV への書き出し分離） |
| `timing.py` | 194 | タイムスタンプ調整・無音タイマー確定方式（`end_padding` 遅延・重複防止ロジック） |

#### 音声・メディア処理

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `media.py` | 27 | メディア処理再エクスポート（後方互換窓口） |
| `media_probe.py` | 142 | ffprobe による音声・動画メタデータ取得（コーデック情報、ストリーム情報解析） |
| `media_ffmpeg.py` | 114 | ffmpeg による音声抽出・動画リマックス処理 |

#### ノイズ除去

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `denoise/base.py` | 26 | デノイズエンジン Protocol（`DenoiseEngine` インターフェース定義） |
| `denoise/factory.py` | 47 | デノイズエンジンの Factory（設定値に基づく DI・インスタンス生成） |
| `denoise/engines/rnnoise.py` | 140 | RNNoise エンジン実装（FFI 経由の C ライブラリ呼び出し・ノイズ除去処理） |
| `denoise/engines/passthrough.py` | 46 | パススルーエンジン（デノイズ無効時のスタブ実装） |
| `denoise/__init__.py` | 15 | denoise サブパッケージのエクスポート定義 |

#### テキスト処理

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `sanitizer.py` | 8 | サニタイザー再エクスポート（後方互換窓口） |
| `sanitizer_types.py` | 31 | 除外・短縮理由の型定義（`DropReason` 列挙・`SanitizeResult` データクラス） |
| `sanitizer_core.py` | 254 | サニタイズロジック（`no_speech`/`speed`/`loop`/`empty`/`repeat` 各フィルター処理） |
| `postprocess.py` | 168 | テキスト後処理（正規化・置換・フィルタリングパイプライン） |
| `exporter.py` | 167 | SRT・WAV ファイル出力（DaVinci Resolve 仕様準拠フォーマッター） |

#### CLI

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `cli.py` | 280 | CLI エントリポイント・コマンド振り分けロジック |
| `cli_options.py` | 209 | CLI オプション定義・バリデーション（Click デコレータ群） |
| `cli_ui.py` | 236 | CLI UI 出力（Rich パネル・`STREAMING_LOG` true/false 両モードのログハンドラ） |

---

### テスト (`tests/`) — 計 7,498行 / 43ファイル

#### 共通・基本

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `conftest.py` | 55 | 共通フィクスチャ定義（モック・ダミーデータ） |
| `test_basic.py` | 11 | パッケージ import・基本動作スモークテスト |
| `test_callbacks.py` | 23 | `callbacks.py` — コールバック Protocol の型検証 |
| `test_compat.py` | 27 | `compat.py` — 互換レイヤーの動作検証 |
| `test_models.py` | 161 | `models.py` — データクラスの生成・等価性・境界値検証 |

#### 設定

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `test_config_models.py` | 116 | 設定データクラスのフィールド・デフォルト値検証 |
| `test_config_parse.py` | 288 | TOML パース処理・設定ロードの正常系・異常系 |
| `test_config_stress_ranges.py` | 102 | 設定値の境界値・範囲外ストレステスト |
| `test_config_stress_types.py` | 285 | 設定値の型不整合ストレステスト |

#### STT・VAD

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `test_stt.py` | 269 | `stt.py` — Whisper Provider の推論・モードロード・エラーハンドリング |
| `test_stt_vad.py` | 137 | `stt_vad.py` — Silero VAD ラッパーの発話検出動作検証 |

#### ストリーミング

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `test_streaming_lifecycle.py` | 186 | `AudioStreamPipeline` のライフサイクル（開始・停止・再起動） |
| `test_streaming_managers.py` | 210 | `StreamingVadManager` / `ContextManager` の状態遷移・境界値 |
| `test_streaming_pipeline.py` | 266 | ストリーミングパイプライン統合（チャンク入力→コールバック発火の結合テスト） |

#### パイプライン

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `test_pipeline_run.py` | 233 | `pipeline.py` — ファイル入力パイプラインの正常系・異常系実行 |
| `test_pipeline_events.py` | 201 | `pipeline_events_collector.py` — イベント収集・発火タイミング検証 |
| `test_pipeline_export.py` | 198 | `pipeline_export.py` — SRT/WAV 出力処理の正確性 |
| `test_timing_adjust.py` | 181 | `timing.py` — タイムスタンプ調整・`end_padding` 遅延確定の境界値 |
| `test_timing_split.py` | 97 | `timing.py` — セグメント分割ロジックの検証 |

#### メディア処理

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `test_media_extract.py` | 226 | `media_ffmpeg.py` / `media_probe.py` — 音声抽出・メタデータ取得の正常系・異常系 |
| `test_media_remux.py` | 150 | `media_ffmpeg.py` — 動画リマックス処理・コーデック維持検証 |

#### ノイズ除去

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `test_denoise.py` | 254 | `denoise/` — 各エンジン（RNNoise/passthrough）の動作・Factory の DI 切り替え |

#### テキスト処理

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `test_sanitizer_basic.py` | 234 | `sanitizer_core.py` — 基本フィルター（`no_speech`/`speed`/`empty`）の正常系・境界値 |
| `test_sanitizer_repeat.py` | 116 | `sanitizer_core.py` — 繰り返し検出（`loop`/`repeat`）フィルターの境界値 |
| `test_sanitizer_result.py` | 127 | `sanitizer_types.py` — `SanitizeResult` / `DropReason` の型検証 |
| `test_postprocess.py` | 144 | `postprocess.py` — テキスト後処理パイプラインの正確性 |
| `test_exporter.py` | 184 | `exporter.py` — SRT フォーマット・WAV 出力の仕様準拠検証 |

#### CLI

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `test_cli.py` | 146 | `cli.py` — CLI コマンド実行・エラー表示の結合テスト |
| `test_cli_options.py` | 243 | `cli_options.py` — オプション解析・バリデーション境界値 |
| `test_cli_ui_format.py` | 132 | `cli_ui.py` — `STREAMING_LOG=true` インデントログ出力フォーマット |
| `test_cli_ui_panels.py` | 77 | `cli_ui.py` — Rich パネル表示の検証 |
| `test_cli_ui_simple.py` | 89 | `cli_ui.py` — `STREAMING_LOG=false` シンプル出力の検証 |

#### E2E（エンドツーエンド結合）

| ファイル | 行数 | 担当内容 |
|---|---|---|
| `test_e2e_pipeline.py` | 256 | パイプライン全体 E2E（実ファイル入力〜出力ファイル生成） |
| `test_e2e_cli.py` | 178 | CLI 経由 E2E（サブプロセス実行〜終了コード・出力確認） |
| `test_e2e_scenarios.py` | 292 | 実業務シナリオ E2E（動画・長尺音声・多言語等の複合ケース） |
| `test_e2e_combinations.py` | 250 | オプション組み合わせ E2E（デノイズ有無・モデル切り替え等） |
| `test_e2e_config.py` | 194 | 設定ファイルバリエーション E2E（TOML 各設定値での動作確認） |
| `test_e2e_exporters.py` | 180 | 出力形式 E2E（SRT / WAV の内容・ファイル命名規則確認） |
| `test_e2e_models.py` | 169 | Whisper モデルサイズ切り替え E2E |
| `test_e2e_postprocess.py` | 173 | 後処理ルール適用 E2E（置換・除外の実挙動確認） |
| `test_e2e_sanitizer.py` | 266 | サニタイズルール適用 E2E（各フィルターの実挙動確認） |
| `test_e2e_timing.py` | 171 | タイミング調整 E2E（`end_padding` 遅延・重複防止の実挙動確認） |
| `test_e2e_hardening.py` | 201 | 堅牢性 E2E（破損ファイル・空音声・極端なパラメータ等の異常系） |


