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
