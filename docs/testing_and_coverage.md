# テスト方針とカバレッジ管理ナレッジ (Testing & Coverage Guidelines)

本ドキュメントは、`audio-transcriber` プロジェクトにおけるテスト設計方針、モック活用指針、および未カバー箇所の許容／禁止基準（カバレッジ品質ナレッジ）をまとめたものです。

---

## 1. カバレッジ設計の基本方針

本プロジェクトは **「見かけのカバレッジではなく、バグ検出力と堅牢性を保証する実効的テスト」** を最重視します。

1. **実モデル・外部コマンド依存の分離**:
   - 重い AI/ML モデル（`DeepFilterNet`, `faster-whisper`）のロードや GPU 推論、外部 CLI（`ffmpeg`, `ffprobe`）の全実行を単体テストで直接行うと、実行時間肥大化や環境依存の原因となります。
   - モデルや CLI の「呼び出し部分」「パラメータ受け渡し」「返り値のデータ変換」「I/O 処理」は、`unittest.mock` を用いて決定論的かつ高速（ミリ秒単位）に検証します。
2. **異常系・エラーハンドリングの網羅**:
   - CLI ツールやメディア変換基盤において、外部コマンドの失敗や不正入力時のハンドリング（`CalledProcessError` ➔ `RuntimeError` の再送出、終了コード制御）はシステムの可用性の要です。これらをテストスキップすることは厳禁とします。
3. **見かけだけの身のないテストの禁止**:
   - カバレッジ目的で単にPASSさせるだけのテストになっていないか辛口評価して自律的に改善すること。

---

## 2. 未カバー許容基準 vs 禁止基準

テストカバレッジを測定・維持するにあたり、以下の基準を厳格に適用します。

### A. カバレッジ除外（未カバー）にしてよい正当な事例
以下のケースはテストコードから無理に到達させる価値が低く、`pyproject.toml` の `[tool.coverage.report] exclude_lines` による明示的な除外対象とします。

1. **エントリポイントガード**:
   - `if __name__ == "__main__":`
2. **型チェック専用ブロック**:
   - `if TYPE_CHECKING:`
3. **抽象メソッド・Protocol スタブ**:
   - `...` や `raise NotImplementedError` のみのシグネチャ定義
4. **到達不能コード（ディフェンシブガード）**:
   - プラットフォーム固有（OS 別シグナル等）で現在の環境では原理的に到達しない節（※ただし可能な限りモック化を検討）

### B. 「未カバー」の言い訳にしてはならない禁止事例（テスト必須）
以下のケースを「外部依存だから」「重いから」という理由で未カバーのまま放置することは禁止します。

1. **外部 CLI（ffmpeg / ffprobe 等）の呼び出し・異常系**:
   - `subprocess.run` をモック化し、`CalledProcessError` 発生時のエラーログ・例外ラッピング・メッセージ整形を必ずテストする。
2. **具象プロバイダ実装（Whisper, DeepFilterNet 等）**:
   - モデルインスタンスをモック化し、渡されるハイパーパラメータ、テンソル/音声の保存フロー、SRT やセグメント辞書への変換ロジックを必ずテストする。
3. **互換レイヤー（Shim / Compat）のフォールバック**:
   - ライブラリ不在（`ImportError`）や属性不在時の例外補足と代替初期化を `sys.modules` やモックでテストする。
4. **CLI の中断・異常系**:
   - `KeyboardInterrupt` やサブコマンド失敗時に適切な終了コードとメッセージが出力されることをテストする。
5. **バリデーション・ガード節**:
   - 境界値（0 や 最大値超過）の引数が渡された際の `ValueError` 送出をテストする。

---

## 3. 妥当性検証と未カバー許容基準 ・禁止基準のメンテナンス

未カバー箇所については、未カバーであることの妥当性を辛口で評価判定し、カバーすべき場合はテストを追加する。
評価判定結果は、過去の未カバー箇所の辛口評価と対策履歴に記録してナレッジとする。
新たに未カバー許容と判定した場合は、ユーザーの承認を得て、未カバー許容基準に追記する。

---

## 4. テスト実行・カバレッジ検証コマンド

```bash
# Ruff check/format, basedpyright, pytest + カバレッジ出力
uv run pre-commit run --all-files -v
```

## 5. 過去の未カバー箇所の辛口評価と対策履歴

### (2026-08-15)

| 対象モジュール | 未カバーだった行 | 当初の理由 | 評価判定 | 対策内容 |
|---|---|---|---|---|
| `cli.py` | 162-164 | パイプライン例外処理 | **重大な漏れ** | `run_pipeline` の例外送出をモックし、exit code 1 とエラー出力を検証 (`test_cli.py`) |
| `cli.py` | 184 | `if __name__ == '__main__':` | **除外妥当** | `pyproject.toml` の `exclude_lines` に設定 |
| `compat.py` | 36-37 | `torchaudio` 未検出時 `pass` | **検証不足** | `patch.dict(sys.modules, {"torchaudio": None})` によるフォールバックテスト作成 (`test_compat.py`) |
| `denoise.py` | 34-47 | DeepFilterNet 実処理本体 | **重大な漏れ** | `df.enhance` / `init_df` / `load_audio` / `save_audio` をモック化し、内部 I/O と呼び出しを完全網羅 (`test_denoise.py`) |
| `media.py` | 67-69, 143-145, 213-215 | ffmpeg/ffprobe 失敗ハンドリング | **甘え** | `subprocess.CalledProcessError` をモックして `RuntimeError` 再送出を検証 (`test_media.py`) |
| `media.py` | 178 | remux 時のトラック番号境界チェック | **片落ち** | 無効トラック番号（0, 上限超過）テストを追加 (`test_media.py`) |
| `transcribe.py` | 63-92 | WhisperModel 実処理本体 | **重大な漏れ** | `WhisperModel` をモック化し、パラメータ伝達・SRT 保存・辞書変換を完全検証 (`test_transcribe.py`) |

### (2026-08-16)

| 対象モジュール | 未カバーだった行 | 当初の理由 | 評価判定 | 対策内容 |
|---|---|---|---|---|
| `pipeline.py` | L148-158 | パイプライン例外処理行を通すための `try ... except Exception: pass` (assertなし) | **見せかけのテスト (重大)** | 例外握りつぶしを完全排除し、`pytest.raises(RuntimeError, match=...)` による厳密な例外送出・終了状態検証へ改修 (`test_pipeline.py`) |
| `pipeline.py` | - | 単語ギャップ分割後のテキスト置換・重複防止後の具体値検証不足 | **アサーションの甘さ** | 分割後セグメント数 (`len >= 2`) および置換後テキスト (`hello`, `goodword`) の具体値を完全一致検証 (`test_pipeline.py`) |
| `streaming/core.py` | L118-119, L141-142 | キュークリア時の `except QueueEmpty` および `_process_loop` の二重例外ハンドリング | **到達不能コード (KISS違反)** | `while True` + `get_nowait` によるシンプルなキュークリアへ整理し、外側二重 `except` を削除 |
| `test_streaming.py` | L120, L131, L160等 | 非同期処理の完了待機に `await asyncio.sleep(0.05)` / `(0.01)` を使用 | **Flakyテストの温床 (重大)** | `MockCallbacks` に `segment_event`, `speech_start_event`, `speech_end_event`, `error_event` の `asyncio.Event` を導入し、コールバック連動の決定論的同期へ全面移行 |
| `config.py` / `config_models.py` | 全データクラス | 負の閾値や無効サンプルレートがそのまま通る（テストで肯定していた） | **不正値誤認固定 (重大)** | `config_models.py` に `__post_init__` による境界値バリデーション (`ValueError`) を導入し、`test_config_stress.py` で例外送出を網羅検証 |
| `stt.py` | L221-252 | 多次元配列（2Dステレオ、3D以上）に対する処理 | **エッジケース漏れ** | 2次元ステレオの平均モノラル化処理と、3次元以上の不正形状に対する `ValueError` ガードを追加・単体テスト (`test_stt.py`) |
| `streaming/managers.py` | `ContextManager` | スペース区切り結合時に `max_length` を超過する境界値バグ | **境界値漏れ** | 単一長大セグメントのスライス処理およびスペース込みでの文字数評価 (`_trim_over_limit`) を修正・テスト (`test_streaming_managers.py`) |
| `streaming/managers.py` | `StreamingVadManager` | `HOLDING_SHORT_CHUNK` 状態で長時間無音が連続した場合のバッファ蓄積 | **メモリリークリスク** | 無音継続時の安全切り出しフォールバック処理を実装・テスト (`test_streaming_managers.py`) |
| `tests/*_coverage*.py` | 全体 | カバレッジ補填用ファイル乱立および残骸ファイル (15バイトのゾンビファイル等) | **DRY / 保守性違反** | `test_*_coverage*.py`（4ファイル）および `test_transcribe.py` を本体テストファイルへ統廃合・完全削除 |
| `src/audio_transcriber/*.py` | `cli.py` (603行), `pipeline.py` (383行) | 単一モジュールへの処理集中による規模制限超過 (300行上限) | **アーキテクチャ規約違反** | `cli_options.py`, `cli_ui.py`, `pipeline_events.py`, `pipeline_export.py`, `stt_types.py` に責務分割し、全25ファイルを 300 行以下（目標200行以下）に収容した上でカバレッジ 100% を維持 |

### (2026-08-16: Phase 14)

| 対象モジュール | 未カバーだった行 / 改善項目 | 当初の課題 | 評価判定 | 対策内容 |
|---|---|---|---|---|
| `sanitizer.py` | `DropReason`, `SanitizeResult` | ハルシネーション除外理由の判別不可 | **要件漏れ** | `DropReason` (StrEnum), `SanitizeResult` (dataclass) を導入し、理由別判定およびリピート短縮を詳細テスト (`test_sanitizer_result.py`) |
| `stt.py` | `transcribe_file` (VAD連携) | `vad_filter=False` 固定に伴う VAD チャンク通知の消失 | **連携途絶** | `decode_audio` + `get_speech_timestamps` によりファイル処理時も Silero-VAD チャンクを事前検出し `vad_chunks` を通知・単体テスト (`test_stt_vad.py`) |
| `pipeline_events.py` | `handle_segment` | 生認識テキストと後処理イベントの順序不整合 | **イベント順序乱れ** | 生認識 (`whisper_raw`) ➔ リピート短縮 (`postprocess_repeat`) ➔ 各種除外 (`postprocess_drop_*`) ➔ テキスト置換 (`postprocess_replaced`) ➔ 確定テキスト (`text_confirmed`) の順序を厳格化・単体テスト (`test_pipeline_events.py`) |
| `timing.py` | `split_segments_by_word_gap` | `pipeline_events.py` のコード行数肥大化 (335行) | **規模制限違反** | 単語ギャップ分割ロジックを `timing.py` へ移動・整理し、全モジュールを 300行以下（目標200行以下）へ収容 |
| `cli_ui.py` | `create_progress_handler` | `STREAMING_LOG` 設定値による表示フォーマットと抑制ロジック | **UI/UX要件** | `STREAMING_LOG=true` 時のインデントログ (`[VAD]`, `[Whisper]`, `[テキスト置換]`, `[Text]`, `▶ [postprocess_summary]`) と `STREAMING_LOG=false` 時のシンプル出力（`[Text]` のみ表示）を Rich エスケープ対応で完全実装・単体テスト (`test_cli_ui.py`) |

---


