# audio-transcriber

DaVinci Resolve での動画編集（YouTubeゲーム実況等）向けに設計された、**マルチトラック動画対応・マイク音声ノイズ除去** および **Whisperによる自動SRT字幕生成** ツールです。

## 特徴

- **マルチトラック動画のダイレクト処理＆無劣化リマックス**:
  - OBS等で録画したゲーム音・マイク音のマルチトラック動画（MP4, MKV 等）を直接入力可能。
  - 映像およびゲーム音声は無劣化（Stream Copy）で保持しつつ、マイク音声トラックのみノイズ除去後WAVに差し替えたクリーン動画（`{stem}_clean.mp4` 等）を自動生成。
- **DeepFilterNet による強力なノイズ除去**:
  - キーボードの打鍵音、コントローラーの操作音、ファン音・環境音を人の声から高精度に分離・除去します。
- **faster-whisper (CUDA + Silero-VAD) による高速・高精度文字起こし**:
  - GPU（CUDA）を活用し、VAD（音声区間検出）により打鍵音による誤認識を抑制しながら、DaVinci Resolve に直接取り込める `.srt` 字幕ファイルを生成します。
- **ワンコマンド実行**:
  - 1つのコマンドで「差し替え済みクリーン動画」「ノイズ除去済みWAV」「SRT字幕ファイル」を同時生成します。

## 使い方

### 1. ゲーム実況動画（マルチトラックMP4/MKV）の処理

OBS等で録画した動画（Track 1: ゲーム音、Track 2: マイク音）を指定して実行します。

```bash
uv run audio-transcriber /path/to/gameplay.mp4 -t 2 -o ./output
```

出力結果（`./output/` 配下）:
- `gameplay_clean.mp4`: マイク音声トラックのみノイズ除去音声に差し替えた動画（映像・ゲーム音は無劣化コピー）
- `gameplay_clean.wav`: ノイズ除去されたクリーンなマイク音声
- `gameplay.srt`: DaVinci Resolve の字幕トラックにそのままドラッグ＆ドロップできる字幕ファイル

### 2. 単体音声ファイル（WAV, MP3 等）の処理

```bash
uv run audio-transcriber /path/to/mic_audio.wav -o ./output
```

出力結果（`./output/` 配下）:
- `mic_audio_clean.wav`: ノイズ除去されたクリーンなマイク音声
- `mic_audio.srt`: SRT 字幕ファイル

### 主なオプション

| オプション | 短縮 | デフォルト | 説明 |
| :--- | :--- | :--- | :--- |
| `--config` | `-C` | `./config.toml` | TOML設定ファイルのパス（存在する場合自動ロード） |
| `--output-dir` | `-o` | `./output` | 出力先ディレクトリ |
| `--mic-track` | `-t` | `2` | 動画内のマイク音声トラック番号 (1-indexed) |
| `--remux / --no-remux` | | `True` | 動画入力時にマイク差し替え動画を生成するかどうか |
| `--model-size` | `-m` | `small` | Whisperモデルサイズ (`tiny`, `base`, `small`, `medium`, `large-v3`) |
| `--device` | `-d` | `cuda` | 実行デバイス (`cuda` または `cpu`) |
| `--compute-type` | `-c` | `float16` | 計算精度 (`float16`, `int8_float16`, `int8`, `float32`) |
| `--language` | `-l` | `ja` | 音声認識言語 |
| `--prompt` | `-p` | なし | 初期プロンプト（ゲーム用語・固有名詞などの誘導） |
| `--min-silence-ms` | | `500` | VAD（無音検出）発話区切り閾値 (ms) |
| `--denoise-only` | | `False` | ノイズ除去のみ実行 |
| `--transcribe-only` | | `False` | 文字起こしのみ実行 |
| `--mastering-enabled / --no-mastering` | | `False` | マスタリング前処理を有効化するかどうか |
| `--noise-gate-threshold` | | `0.04` | ノイズゲートの閾値 |
| `--loudness-i` | | `-16.0` | ノーマライズの目標ラウドネス (LUFS) |
| `--loudness-tp` | | `-2.0` | トゥルーピークリミット (dBTP) |
| `--loudness-lra` | | `11.0` | ラウドネスレンジ (LU) |
| `--final-limit-db` | | `-2.0` | 最終ハードリミッター上限 (dB) |
| `--debug-output-dir` | | なし | デバッグ用出力ディレクトリ |
| `--custom-dict-path` | | なし | カスタム辞書のパス |
| `--denoise-engine` | | `rnnoise` | ノイズ除去エンジン |
| `--denoise-model-path` | | なし | カスタムノイズ除去モデルパス |
| `--media-sample-rate` | | `48000` | 抽出・処理時のサンプリングレート |
| `--beam-size` | | `5` | Whisperビームサーチ幅 |
| `--condition-on-previous-text / --no-condition-on-previous-text` | | `True` | Whisper直前文脈への依存 |
| `--transcribe-no-speech-threshold` | | `0.6` | Whisper無音判定閾値 |
| `--vad-threshold` | | `0.5` | VAD検出閾値 |
| `--replace-terms / --no-replace-terms` | | `True` | カスタム辞書による用語置換 |
| `--lower / --no-lower` | | `False` | 英字の小文字化 |
| `--remove-punct / --no-remove-punct` | | `False` | 句読点等の記号削除 |
| `--pp-no-speech-threshold` | | `0.6` | 後処理の無音確率閾値 |
| `--max-chars-per-second` | | `12.0` | 後処理の上限文字数/秒 |
| `--end-padding` | | `1.0` | 字幕の発話終了後の余韻表示秒数 |
| `--min-duration` | | `1.5` | 字幕の最小表示秒数 |
| `--min-gap` | | `0.05` | 字幕間の最小隙間秒数 |
| `--subtitle-formats` | | `srt,vtt,json` | 出力字幕フォーマットリスト |
| `--chunk-size-ms` | | `100` | ストリーミングチャンクのサイズ (ms) |
| `--buffer-size-seconds` | | `10.0` | バッファの最大保持秒数 |
| `--stream-sample-rate` | | `16000` | ストリーミングサンプリングレート (Hz) |
| `--flush-timeout-ms` | | `1000` | バッファフラッシュタイムアウト (ms) |
| `--word-gap-split-threshold` | | `1.0` | 単語ギャップによるセグメント強制分割秒数 |
| `--streaming-log / --no-streaming-log` | | `False` | リアルタイムログ出力モード |

### 3. 設定ファイル (`config.toml`) によるカスタマイズ

カレントディレクトリに `config.toml` を配置するか、`--config / -C` で指定することで、用語辞書プロンプトや環境設定を一括管理できます。

```bash
# サンプル設定ファイルをコピーして使用
cp config.example.toml config.toml
```

**設定例 (`config.toml`):**
```toml
output_dir = "./output"
remux = true

[media]
mic_track = 2

[model]
model_size = "small"
device = "cuda"
compute_type = "float16"

[transcribe]
language = "ja"
initial_prompt = """
以下はゲーム実況の音声です。
用語: Apex Legends, ヴァルキリー, クレーバー, ノックダウン
"""

[transcribe.vad]
vad_filter = true
min_silence_duration_ms = 500

[mastering]
enabled = false
noise_gate_threshold = 0.04
loudness_i = -16.0
loudness_tp = -2.0
loudness_lra = 11.0
final_limit_db = -2.0
```


### 💻 ライブラリとしての組み込み利用 (API)

本プロジェクトは Python ライブラリとして他のスクリプトからインポートして利用することも可能です。
設定のロードには `load_config()` 関数を利用でき、**任意の場所に配置した TOML ファイル** を読み込ませることが可能です。

```python
from audio_transcriber.config import load_config
from audio_transcriber.pipeline import run_pipeline

# 任意のパスにあるカスタムTOMLファイルを読み込む
# （引数なしの場合はカレントディレクトリの config.toml が自動で使われます）
cfg = load_config("/path/to/my_custom_settings.toml")

# コード上で動的に一部の設定だけ上書きすることも可能
cfg.model.model_size = "large-v3-turbo"
cfg.stream.streaming_log = True

# パイプラインを実行
result = run_pipeline(input_path="my_video.mp4", cfg=cfg, denoise=True, transcribe=True)
```

### 開発・品質チェック

```bash
# テスト実行
uv run pytest --cov=audio_transcriber

# リント / フォーマットチェック
uv run ruff check .

# 型チェック
uv run basedpyright
```

## 📄 ライセンス (License)

This project is licensed under the Apache License 2.0 - see the [LICENSE](./LICENSE) file for details.
