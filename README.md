# audio-transcriber

DaVinci Resolve での動画編集（YouTubeゲーム実況等）やリアルタイム配信向けに設計された、**高品質な音声認識・前処理を提供する Python ライブラリ / CLI ツール** です。
「**ファイル入力（バッチ・動画結合）**」と「**ストリーム入力（リアルタイム・低遅延）**」の両方に対応したアーキテクチャを備えています。

## 概要と主な特徴

本ライブラリは、用途に合わせて最適化された2つの入力フローを提供します。

### 1. ファイル入力（バッチ処理・動画結合）
- **マルチトラック動画のダイレクト処理＆無劣化リマックス**:
  - OBS等で録画したゲーム音・マイク音のマルチトラック動画（MP4, MKV 等）を直接入力可能。
  - 映像およびゲーム音声は無劣化（Stream Copy）で保持しつつ、マイク音声トラックのみマスタリング・ノイズ除去した音声に差し替えたクリーン動画（`{stem}_clean.mp4` 等）を自動生成。
- **マスタリング前処理 & RNNoise ノイズ除去**:
  - FFmpeg フィルタチェーンによるマスタリング（ノイズゲート ➔ 1段目リミッター ➔ ラウドネスノーマライズ ➔ 最終リミッター）および RNNoise による高品質な背景ノイズ・環境音除去。
- **高精度な一括文字起こし & 字幕生成**:
  - 独自 VAD による正確な発話チャンク制御（Faster-Whisper 内蔵 VAD は `vad_filter=False` 固定）により、タイムスタンプズレを防止。
  - 字幕フォーマット（SRT / VTT / JSON）へのエクスポート、DaVinci Resolve のインポート仕様（ミリ秒表記 `00:00:00,000`、UTF-8、改行コード LF）に完全対応。

### 2. ストリーム入力（リアルタイム・低遅延）
- **`AudioStreamPipeline` による低遅延リアルタイム文字起こし**:
  - マイク入力や配信システム（OBS等）からの音声ストリームチャンクをリングバッファ経由で逐次処理。
  - ストリーミング時はノイズ除去・マスタリングをバイパスし、二重処理による音質劣化・遅延を防止。
- **独自ステートマシンによる発話区間切り出し**:
  - リアルタイム VAD（`StreamingVadManager`）による発話開始・終了の即時検知。最大長（強制分割）や最小長（誤検知防止）ガードを備えた高信頼なチャンク制御。
- **文脈履歴プロンプト管理 (`ContextManager`)**:
  - 過去の認識結果を `initial_prompt` として適応的に管理。最大文字数制限や一定時間無音時の自動リセットにより、ハルシネーション（幻覚）を抑制しながら文脈を維持。
- **サニタイズ ＆ テキスト後処理**:
  - 無音・無効セグメントの破棄、無限ループ・重複テキスト除去、カスタム辞書による用語置換。
- **非同期コールバック通知**:
  - 発話状態変更 (`on_vad_state_change`)、発話開始/終了 (`on_speech_start`/`on_speech_end`)、セグメント認識確定 (`on_segment_recognized`) などを非同期通知。

### 3. 技術スタック・設計思想
- **ノイズ除去**: RNNoise（軽量かつ低遅延なリカレントニューラルネットワークによるノイズ抑制）。
- **STT (音声認識)**: Faster-Whisper（CTranslate2 バックエンド）。
  - ※ 内蔵 VAD (`vad_filter=True`) は無音区間を挟んだ複数チャンクの誤結合やタイムスタンプズレを誘発するため、本ライブラリでは **`vad_filter=False` 固定** とし、独自実装の VAD により発話区間ごとに Whisper を発火させて正確なタイムスタンプ制御を実現しています。
- **推論プロバイダーの抽象化 (Strategy / DI)**: `TranscriberProvider` インターフェースを通じて、ローカル GPU 推論 (`FasterWhisperProvider`) や Mock などを柔軟に切り替え可能。

---

## インストール

```bash
# uv を使用して依存関係を同期・インストール
uv sync
```

---

## 使い方 (CLI)

### 1. ゲーム実況動画（マルチトラックMP4/MKV）の処理
OBS等で録画した動画（Track 1: ゲーム音、Track 2: マイク音）を指定して実行します。

```bash
uv run audio-transcriber /path/to/gameplay.mp4 -t 2 -o ./output
```

出力結果（`./output/` 配下）:
- `gameplay_clean.mp4`: マイク音声トラックのみノイズ除去・マスタリング済み音声に差し替えた動画（映像・ゲーム音は無劣化コピー）
- `gameplay_clean.wav`: ノイズ除去・マスタリングされたクリーンなマイク音声
- `gameplay.srt`: DaVinci Resolve の字幕トラックにそのままドラッグ＆ドロップできる字幕ファイル（設定に応じて `.vtt`, `.json` も出力）

### 2. 単体音声ファイル（WAV, MP3 等）の処理

```bash
uv run audio-transcriber /path/to/mic_audio.wav -o ./output
```

出力結果（`./output/` 配下）:
- `mic_audio_clean.wav`: クリーンマイク音声
- `mic_audio.srt`: SRT 字幕ファイル

### 3. 主な CLI オプション

| オプション | 短縮 | デフォルト | 説明 |
| :--- | :--- | :--- | :--- |
| `--config` | `-C` | `./config.toml` | TOML設定ファイルのパス（存在する場合自動ロード） |
| `--output-dir` | `-o` | `./output` | 出力先ディレクトリ |
| `--mic-track` | `-t` | `2` | 動画内のマイク音声トラック番号 (1-indexed) |
| `--remux / --no-remux` | | `True` | 動画入力時にマイク差し替え動画を生成するかどうか |
| `--model-size` | `-m` | `small` | Whisperモデルサイズ (`tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`) |
| `--device` | `-d` | `cuda` | 実行デバイス (`cuda` または `cpu`) |
| `--compute-type` | `-c` | `float16` | 計算精度 (`float16`, `int8_float16`, `int8`, `float32`) |
| `--language` | `-l` | `ja` | 音声認識言語 |
| `--prompt` | `-p` | なし | 初期プロンプト（ゲーム用語・固有名詞などの誘導） |
| `--min-silence-ms` | | `500` | VAD（無音検出）発話区切り閾値 (ms) |
| `--denoise-only` | | `False` | ノイズ除去のみ実行 |
| `--transcribe-only` | | `False` | 文字起こしのみ実行 |
| `--denoise / --no-denoise` | | `True` | ノイズ除去の有効/無効 |
| `--denoise-engine` | | `rnnoise` | ノイズ除去エンジン |
| `--denoise-model-path` | | なし | カスタム RNNoise モデルパス |
| `--media-sample-rate` | | `48000` | 抽出・処理時のサンプリングレート (Hz) |
| `--beam-size` | | `5` | Whisper ビームサーチ幅 |
| `--condition-on-previous-text / --no-condition-on-previous-text` | | `True` | Whisper 直前文脈への依存 |
| `--transcribe-no-speech-threshold` | | `0.6` | Whisper 無音判定閾値 |
| `--vad-threshold` | | `0.5` | VAD 検出閾値 |
| `--replace-terms / --no-replace-terms` | | `True` | カスタム辞書による用語置換 |
| `--lower / --no-lower` | | `False` | 英字の小文字化 |
| `--remove-punct / --no-remove-punct` | | `False` | 句読点等の記号削除 |
| `--pp-no-speech-threshold` | | `0.6` | 後処理の無音確率閾値 |
| `--max-chars-per-second` | | `12.0` | 後処理の上限文字数/秒 (ハルシネーション抑制) |
| `--end-padding` | | `1.0` | 字幕の発話終了後の余韻表示秒数 |
| `--min-duration` | | `1.5` | 字幕の最小表示秒数 |
| `--min-gap` | | `0.05` | 字幕間の最小隙間秒数 |
| `--subtitle-formats` | | `srt,vtt,json` | 出力字幕フォーマットリスト |
| `--mastering-enabled / --no-mastering` | | `False` | マスタリング前処理を有効化するかどうか |
| `--noise-gate-threshold` | | `0.04` | ノイズゲートの閾値 |
| `--loudness-i` | | `-16.0` | ノーマライズの目標ラウドネス (LUFS) |
| `--loudness-tp` | | `-2.0` | トゥルーピークリミット (dBTP) |
| `--loudness-lra` | | `11.0` | ラウドネスレンジ (LU) |
| `--final-limit-db` | | `-2.0` | 最終ハードリミッター上限 (dB) |
| `--chunk-size-ms` | | `100` | ストリーミングチャンクのサイズ (ms) |
| `--buffer-size-seconds` | | `10.0` | バッファの最大保持秒数 |
| `--stream-sample-rate` | | `16000` | ストリーミングサンプリングレート (Hz) |
| `--flush-timeout-ms` | | `1000` | バッファフラッシュタイムアウト (ms) |
| `--word-gap-split-threshold` | | `1.0` | 単語ギャップによるセグメント強制分割秒数 |
| `--streaming-log / --no-streaming-log` | | `False` | リアルタイムログ出力モード |
| `--debug-output-dir` | | なし | デバッグ用中間ファイル出力ディレクトリ |
| `--custom-dict-path` | | なし | カスタム辞書ファイルのパス |

---

## 設定ファイル (`config.toml`) によるカスタマイズ

カレントディレクトリに `config.toml` を配置するか、`--config / -C` で指定することで、用語辞書プロンプトや環境設定を一括管理できます。
（詳細は [`config.example.toml`](./config.example.toml) を参照してください）

```bash
# サンプル設定ファイルをコピーして使用
cp config.example.toml config.toml
```

**主要セクション構成例 (`config.toml`):**
```toml
# パス設定
[path]
output_dir = "./output"
default_video_path = "data/test_videos/sample.mov"
custom_dict_path = "data/custom_dictionary.toml"

# パイプライン設定
[pipeline]
remux = true

# ノイズ除去設定 (RNNoise)
[denoise]
enabled = true
engine = "rnnoise"
model_path = "data/models/sh.rnnn"

# メディア・トラック設定
[media]
mic_track = 2
sample_rate = 48000

# Whisper 推論モデル・デバイス設定
[model]
model_size = "small"
device = "cuda"
compute_type = "float16"

# 文字起こし・Whisper推論設定
[transcribe]
language = "ja"
beam_size = 5
condition_on_previous_text = true
no_speech_threshold = 0.6
initial_prompt = """
以下はゲーム実況の音声です。
用語: Apex Legends, ヴァルキリー, クレーバー, ノックダウン
"""

# VAD (音声区間検出) 設定
[transcribe.vad]
min_silence_duration_ms = 500
vad_threshold = 0.5

# テキスト後処理設定
[post_process]
replace_terms = true
lower = false
remove_punct = false
no_speech_threshold = 0.6
max_chars_per_second = 12.0

# 字幕表示タイミング調整・出力フォーマット設定
[subtitle]
end_padding = 1.0
min_duration = 1.5
min_gap = 0.05
formats = ["srt", "vtt", "json"]

# ストリーミング設定
[stream]
chunk_size_ms = 100
buffer_size_seconds = 10.0
sample_rate = 16000
flush_timeout_ms = 1000
word_gap_split_threshold = 1.0
streaming_log = false
chunk_min_seconds = 1.0
chunk_max_seconds = 30.0

# ストリーミング文脈管理設定
[stream.context]
context_max_length = 200
context_timeout_seconds = 3.0

# マスタリング前処理設定
[mastering]
enabled = false
noise_gate_threshold = 0.04
loudness_i = -16.0
loudness_tp = -2.0
loudness_lra = 11.0
final_limit_db = -2.0
```

---

## 💻 ライブラリとしての組み込み利用 (Python API)

本プロジェクトは Python ライブラリとして他のアプリケーション（例: 配信支援ツール、音声認識サービス等）に組み込んで利用可能です。

### 1. ストリーミング入力の組み込み例 (`AudioStreamPipeline`)

マイク入力や OBS、WebRTC 等から逐次届く音声チャンク（`float32` または `int16` の numpy 配列やバイト列）を投入し、自前 VAD による発話区間切り出しと文脈プロンプト連携を行いながら、非同期コールバックでリアルタイムに認識結果を受け取ります。

```python
import asyncio
import numpy as np
from audio_transcriber.callbacks import BasePipelineCallbacks
from audio_transcriber.config import load_config
from audio_transcriber.models import RecognizedSegment, VadState
from audio_transcriber.streaming import AudioStreamPipeline
from audio_transcriber.stt import FasterWhisperProvider


class MyCallbacks(BasePipelineCallbacks):
    """ストリーミングイベントを受け取るコールバッククラス。"""

    def on_vad_state_change(self, state: VadState) -> None:
        print(f"[VAD] 状態変更: {state}")

    def on_speech_start(self, timestamp: float) -> None:
        print(f"[VAD] 発話開始検知: {timestamp:.2f}s")

    def on_speech_end(self, timestamp: float) -> None:
        print(f"[VAD] 発話終了検知: {timestamp:.2f}s")

    def on_segment_recognized(self, segment: RecognizedSegment) -> None:
        print(f"[字幕確定] [{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")

    def on_error(self, error: Exception) -> None:
        print(f"[エラー] {error}")


async def main() -> None:
    # 1. 設定のロード（TOMLパス指定、または省略してデフォルト）
    cfg = load_config("config.toml")

    # 2. 推論プロバイダーの初期化（常駐ロード）
    transcriber = FasterWhisperProvider(
        model_size=cfg.model.model_size,
        device=cfg.model.device,
        compute_type=cfg.model.compute_type,
        language=cfg.transcribe.language,
        initial_prompt=cfg.transcribe.initial_prompt,
    )

    # 3. ストリーミングパイプラインの構築
    pipeline = AudioStreamPipeline(
        transcriber=transcriber,
        callbacks=MyCallbacks(),
        app_config=cfg,
        timecode_offset=0.0,  # 親システムとの同期用オフセット秒数
    )

    # 4. パイプライン開始
    await pipeline.start()

    try:
        # 例: 100ms分の音声データ (16kHz PCM Float32) をシミュレートして逐次投入
        sample_rate = 16000
        chunk_samples = int(sample_rate * 0.1)  # 100ms = 1600 samples
        dummy_chunk = np.zeros(chunk_samples, dtype=np.float32)

        for _ in range(50):
            # is_speech フラグは外部VAD結果またはTrueを指定
            await pipeline.feed_chunk(dummy_chunk, is_speech=True)
            await asyncio.sleep(0.1)
    finally:
        # 5. 終了時に残余バッファをフラッシュして停止
        await pipeline.stop()


if __name__ == "__main__":
    asyncio.run(main())
```

### 2. ファイル入力の組み込み例 (`run_pipeline`)

動画ファイルや音声ファイルを一括処理し、マスタリング、RNNoise ノイズ除去、文字起こし、字幕出力、動画再結合 (Remux) を実行します。

```python
from audio_transcriber.config import load_config
from audio_transcriber.pipeline import run_pipeline

# 1. 設定のロード
cfg = load_config("config.toml")

# コード上で動的に設定を上書きすることも可能
cfg.paths.output_dir = "./custom_output"
cfg.model.model_size = "medium"
cfg.mastering.enabled = True

# 2. パイプラインの一括実行
result = run_pipeline(
    input_path="input_video.mp4",
    cfg=cfg,
    denoise=True,
    transcribe=True,
)

print(f"クリーン動画: {result.remuxed_video}")
print(f"クリーン音声: {result.denoised_audio}")
print(f"SRT 字幕: {result.srt_file}")
print(f"全文テキスト:\n{result.transcript_text}")
```

---

## 開発・品質チェック

```bash
# 全自動検証（Ruff check/format, basedpyright, pytest + カバレッジ）
uv run pre-commit run --all-files -v

# 個別実行
uv run pytest
uv run ruff check .
uv run basedpyright
```

## 📄 ライセンス (License)

This project is licensed under the Apache License 2.0 - see the [LICENSE](./LICENSE) file for details.
