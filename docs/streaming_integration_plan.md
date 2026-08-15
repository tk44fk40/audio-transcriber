# Lumi Companion ストリーミング連携 音声処理ライブラリ拡張 実装計画書

## 1. 概要と目的

本ドキュメントは、`lumi_companion`（るみぽん！）における要件仕様書 [`AUDIO_LIBRARY_REQUIREMENTS.md`](file:///home/tk44/ghq/github.com/tk44fk40/lumi_companion/docs/AUDIO_LIBRARY_REQUIREMENTS.md) の仕様に準拠し、`audio-transcriber` を **「リアルタイムストリーミング対応の音声処理 Python ライブラリ」** として拡張し、同時に **「音声品質向上のためのマスタリング処理」** などを追加するための技術設計書です。

- **参照元 要件仕様書**: [`lumi_companion/docs/AUDIO_LIBRARY_REQUIREMENTS.md`](file:///home/tk44/ghq/github.com/tk44fk40/lumi_companion/docs/AUDIO_LIBRARY_REQUIREMENTS.md)

既存の高品質な単体モジュール群（RNNoise ノイズ除去、ドメイン辞書置換、漢数字正規化、字幕タイミング補正、サニタイズ）を活かしながら、モデル常駐型推論コアとストリーミングパイプラインを追加し、さらに前処理としてマスタリングフィルタを統合します。

---

## 2. アーキテクチャ構成

```text
┌────────────────────────────────────────────────────────────────────────┐
│ Layer 1: ストリーミング統合パイプライン (AudioStreamPipeline)          │
│                                                                        │
│   feed_chunk() ➔ 内部リングバッファ ➔ 16kHz Float32 正規化             │
│        │                                                               │
│        ▼                                                               │
│   DenoiseFilter (RNNoise / Bypass) + Mastering Filter (Gate/Limiter)   │
│        │                                                               │
│        ▼                                                               │
│   SpeechTranscriber (Silero-VAD ＋ Faster-Whisper モデル常駐推論)      │
│        │                                                               │
│        ▼                                                               │
│   後処理 (SegmentSanitizer ➔ TextPostProcessor ➔ SubtitleTimingAdjuster)│
│        │                                                               │
│        ▼                                                               │
│   PipelineCallbacks (on_segment, on_partial, on_vad_state_change)      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 実装フェーズとタスク一覧

### Phase 1: モデル常駐型 VAD+Whisper コア ＆ 共通データモデル (完了済)
* **目的**: 毎回のモデルロードによる遅延を排除し、常駐型で低遅延な推論基盤を構築する。
* **対象ファイル**: `src/audio_transcriber/stt.py`, `src/audio_transcriber/models.py`
* **主な仕様**:
  * 初期化時に Faster-Whisper モデルおよび Silero-VAD をロード・常駐化（Pre-warmed）。
  * `transcribe_waveform` / `transcribe_file` メソッドの実装。
  * `unload()` / `close()` による安全な VRAM 解放。

### Phase 2: ストリーミング統合パイプライン ＆ 非同期コールバック (完了済)
* **目的**: リアルタイム音声チャンクの逐次投入とコールバック通知インターフェースを提供。
* **対象ファイル**: `src/audio_transcriber/streaming.py`, `src/audio_transcriber/callbacks.py`
* **主な仕様**:
  * `feed_chunk(chunk)` による非ブロッキング音声投入と内部バッファリング。
  * VAD 発話開始・終了検知と非同期コールバック発火（`on_segment`, `on_vad_state_change` 等）。

### Phase 3: 設定・公開 API 統合 (完了済)
* **目的**: バッチ処理とストリーミング処理の共存・統合。
* **対象ファイル**: `src/audio_transcriber/config.py`, `src/audio_transcriber/__init__.py`
* **主な仕様**:
  * `AudioPipelineConfig`, `StreamConfig` 等の設定モデル追加。
  * 公開シンボルのエクスポート。

### Phase 4: 音声品質向上のためのマスタリング前処理追加
* **目的**: 入力音声の S/N 比・解像度を向上させ、VAD や Whisper が長すぎるセグメントを生成する問題を防ぐ。
* **対象ファイル**: `config.toml`, `config.py`, `rnnoise.py`, `cli.py`
* **追加パラメータと対応するCLIオプション**:
  設定ファイル (`config.toml` の `[mastering]` セクション) およびコマンドライン引数として以下を追加します。
  * `ENABLED` / `--mastering-enabled` (フラグ): マスタリング有効/無効
  * `NOISE_GATE_THRESHOLD` / `--noise-gate-threshold`: ノイズゲート閾値 (例: 0.04)
  * `LOUDNESS_I` / `--loudness-i`: ノーマライズ目標ラウドネス (例: -16.0)
  * `LOUDNESS_TP` / `--loudness-tp`: ピークリミット (例: -2.0)
  * `LOUDNESS_LRA` / `--loudness-lra`: ラウドネスレンジ (例: 11.0)
  * `FINAL_LIMIT_DB` / `--final-limit-db`: 最終ハードリミッター上限 (例: -2.0)
* **実装仕様**:
  * FFmpeg フィルタチェーンを `ノイズ除去 ➔ ノイズゲート ➔ 1段目リミッター ➔ ノーマライズ ➔ 最終リミッター` の順に直列連結する。

### Phase 5: CLI・パイプラインのストリーミング対応改修
* **目的**: CLI 実行時においても処理が終わるまで待たず、リアルタイムに順次出力・補正処理を行う。
* **対象ファイル**: `config.toml`, `config.py`, `pipeline.py`, `cli.py`, `sanitizer.py`, `postprocess.py`
* **追加パラメータと対応するCLIオプション**:
  設定ファイル (`config.toml` の `[pipeline]` または `[stream]` セクション) およびコマンドライン引数として以下を追加します。
  * `WORD_GAP_SPLIT_THRESHOLD` / `--word-gap-split-threshold`: 単語間の無音ギャップによるセグメント強制分割秒数
  * `STREAMING_LOG` / `--streaming-log` (フラグ): リアルタイムログ出力モード (true=ツリー表示, false=生テキストのシンプル出力)
* **実装仕様**:
  * `pipeline.py` の `_internal_on_segment` で、単一セグメントごとに遅延バッファリングによる重複防止とサニタイズを行う。
  * CLI における一括結果表示を廃止し、ストリーミング出力へ移行する。

### Phase 6: VADタイムスタンプバグ修正
* **対象ファイル**: `stt.py`
* **実装仕様**: `faster_whisper` の VAD タイムスタンプがサンプル数で返る問題を、サンプリングレート `16000.0` で割って秒数へ変換するように修正。

---

## 4. ライブラリ利用を想定したパラメータ引き渡し設計

CLIからだけでなく、Python スクリプトからライブラリとして利用される場合でも正しくパラメータが反映されるよう、以下の設計ルールを遵守します。

### 4.1 設計ルール
1. **設定オブジェクトを経由した引き渡し**:
   CLIからの引数や `config.toml` の値はすべて `AppConfig` などの **設定オブジェクト（データクラス / Pydanticモデル）** にまとめられます。
2. **関数・クラスへのコンストラクタ注入 (DI)**:
   ライブラリ利用者はこの設定オブジェクトをインスタンス化し、パイプライン初期化時や各モジュールの関数へ引数として直接渡します。
3. **グローバルステートの排除**:
   内部処理において `typer` のコンテキストやグローバル変数を直接参照せず、渡された設定オブジェクトのプロパティを読み取ります。

### 4.2 ライブラリ利用時のコード例 (想定)

```python
from pathlib import Path
from audio_transcriber.config import AppConfig, StreamConfig, MasteringConfig
from audio_transcriber.streaming import AudioStreamPipeline
from audio_transcriber.stt import TranscriberProvider

# 1. パラメータを明示的に指定して設定オブジェクトを生成
config = AppConfig(
    mastering=MasteringConfig(
        enabled=True,
        noise_gate_threshold=0.04,
        loudness_i=-16.0,
        loudness_tp=-2.0,
        loudness_lra=11.0,
        final_limit_db=-2.0,
    ),
    stream=StreamConfig(word_gap_split_threshold=1.0, streaming_log=False),
)

# 2. パイプラインへの引き渡し (コンストラクタ注入)
transcriber = TranscriberProvider(model_path=Path("model.bin"))
pipeline = AudioStreamPipeline(
    transcriber=transcriber,
    config=config.stream,  # 生成した設定オブジェクトを直接渡す
)
```

---

## 5. 音響イベント検知 (将来検討)

### 5.1 マルチトラック入力分離
「マイク音トラック」と「ゲーム音・環境音トラック」を完全に別系統で入力・処理する設計を採用します。これにより、ゲーム音を音声認識（STT）に入れてしまうことによるハルシネーションや誤判定を防止します。

### 5.2 イベント検知手法
* **手法 1 (RMS/dBFS解析)**: 軽量な音圧ピーク検知。叫び声や突発ノイズの即時検知。
* **手法 3 (事前学習モデル YAMNet)**: ONNX 版の軽量モデルを用いた笑い声や拍手などの高度な分類検知。
