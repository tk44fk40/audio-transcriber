# Lumi Companion ストリーミング連携 音声処理ライブラリ拡張 実装計画書

## 1. 概要と目的

本ドキュメントは、`lumi_companion`（るみぽん！）における要件仕様書 [AUDIO_LIBRARY_REQUIREMENTS.md](file:///home/tk44/ghq/github.com/tk44fk40/lumi_companion/docs/AUDIO_LIBRARY_REQUIREMENTS.md) の仕様に準拠し、`audio-transcriber` を **「リアルタイムストリーミング対応の音声処理 Python ライブラリ」** として拡張するための技術計画書です。

- **参照元 要件仕様書**: [lumi_companion/docs/AUDIO_LIBRARY_REQUIREMENTS.md](file:///home/tk44/ghq/github.com/tk44fk40/lumi_companion/docs/AUDIO_LIBRARY_REQUIREMENTS.md)

既存の高品質な単体モジュール群（RNNoise ノイズ除去、ドメイン辞書置換、漢数字正規化、字幕タイミング補正、サニタイズ）を活かしながら、**「モデル常駐型推論コア」** と **「ストリーミング非同期パイプライン」** を追加実装します。

---

## 2. アーキテクチャ構成

```text
┌────────────────────────────────────────────────────────────────────────┐
│ Layer 1: ストリーミング統合パイプライン (AudioStreamPipeline)          │
│                                                                        │
│   feed_chunk() ➔ 内部リングバッファ ➔ 16kHz Float32 正規化             │
│        │                                                               │
│        ▼                                                               │
│   DenoiseFilter (RNNoise / Bypass)                                     │
│        │                                                               │
│        ▼                                                               │
│   SpeechTranscriber (Silero-VAD ＋ Faster-Whisper モデル常駐推論)     │
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

### Phase 1: モデル常駐型 VAD+Whisper コア ＆ 共通データモデル
* **目的**: 毎回のモデルロードによる遅延を排除し、常駐型で低遅延な推論基盤を構築する。
* **対象ファイル**:
  * `src/audio_transcriber/stt.py` (`SpeechTranscriber` クラス)
  * `src/audio_transcriber/models.py` (`RecognizedSegment`, `VadState`, `SoundEvent` 追加)
* **主な仕様**:
  * 初期化時に Faster-Whisper モデルおよび Silero-VAD をロード・常駐化（Pre-warmed）。
  * `transcribe_waveform(waveform: np.ndarray) -> list[RecognizedSegment]`
  * `transcribe_file(file_path: Path | str) -> list[RecognizedSegment]`
  * `unload()` / `close()` による安全な VRAM 解放（`torch.cuda.empty_cache()`）。

### Phase 2: ストリーミング統合パイプライン ＆ 非同期コールバック
* **目的**: リアルタイム音声チャンクの逐次投入とコールバック通知インターフェースを提供。
* **対象ファイル**:
  * `src/audio_transcriber/streaming.py` (`AudioStreamPipeline`)
  * `src/audio_transcriber/callbacks.py` (`PipelineCallbacks`, `BasePipelineCallbacks`)
* **主な仕様**:
  * `feed_chunk(chunk: np.ndarray | bytes)` による非ブロッキング音声投入。
  * 内部ワーカースレッド / キューによる音声バッファリングと 16kHz Float32 リサンプリング。
  * VAD 発話開始・終了イベント検知と、確定セグメントの後処理自動適用。
  * 非同期コールバック発火（`on_segment`, `on_partial`, `on_vad_state_change`, `on_error` 等）。
  * `start()`, `flush()`, `reset()`, `close()` のライフサイクル管理。

### Phase 3: 設定・公開 API 統合 ＆ テスト拡充
* **目的**: バッチ処理（DaVinci Resolve用CLI）とストリーミング処理（Lumi用ライブラリ）の共存・統合。
* **対象ファイル**:
  * `src/audio_transcriber/config.py` (`AudioPipelineConfig`, `SttConfig`, `VadConfig` 等の追加/統合)
  * `src/audio_transcriber/__init__.py` (公開シンボルのエクスポート)
  * `tests/test_stt.py`, `tests/test_streaming.py`, `tests/test_callbacks.py`
* **主な仕様**:
  * 既存 CLI 機能および単体テストとの 100% 互換性維持。
  * モックを活用した高速・決定論的なストリーミング単体テスト。

---

## 4. 音響イベント検知 (Sound Event Detection) の実現手法メモ

音響イベント検知（叫び声・大音量SE・笑い声・沈黙等）は将来フェーズで検討・導入予定です。以下に実現に向けた代表的な手法、マルチトラック入力設計、および技術選定案を整理します。

### 4.1 マルチトラック入力分離（マイク音 vs ゲーム・環境音）

音声認識（STT）と音響イベント検知を共存させる場合、**「マイク音トラック」と「ゲーム音・環境音トラック」を完全に別系統で入力・処理する設計** を採用します。

```text
[マイク音声トラック] ──➔ ノイズ除去 ──➔ VAD + Whisper (STT) ──➔ 配信者声イベント検知 (叫び/笑い)
                                                             │
                                                             ▼
[ゲーム音声トラック] ─────────────➔ ゲームSE・環境音イベント検知 (爆発/銃声/歓声/BGM)
                                                             │
                                                             ▼
                                                    【AudioEvent / コールバック】
```

#### トラック分離のメリット
1. **誤判定・干渉の防止**:
   * ゲームの爆発音を実況者の叫び声と誤認したり、ゲーム内BGM/SEによって Whisper が誤認識・ハルシネーションを起こすリスクを根本的に排除。
2. **計算リソース（GPU/CPU）の最適化**:
   * ゲーム音トラックには重い Whisper や RNNoise を通さず、軽量な音圧検知・SE分類モデルのみを適用するため、処理負荷を最小化。
3. **入力インターフェース案**:
   ```python
   # マルチトラック対応のチャンク投入インターフェース案
   await pipeline.feed_chunk(
       mic_chunk=mic_pcm_bytes,  # ➔ STT + 配信者感情/声検知へ
       game_chunk=game_pcm_bytes,  # ➔ ゲームSE/環境音検知へ (任意)
   )
   ```

---

### 4.2 イベント検知の実現手法

#### 手法 1: 短時間 RMS / dBFS エネルギー解析（軽量・即時検知）
* **アプローチ**: 音声チャンクごとに二乗平均平方根（RMS）から dBFS を算出し、`peak_threshold_dbfs`（例: `-5.0 dBFS`）超過を検知。
* **長所**: 計算コストが極めて小さい（CPU負荷 < 0.1%）、遅延ゼロ（1チャンク内で即判定可能）。
* **用途**: **「叫び声」「大音量リアクション」「突発ノイズ」** の即時割り込み通知。

#### 手法 2: ピッチ（基本周波数 F0）+ エネルギー複合判定（簡易分類）
* **アプローチ**: `pyin` やゼロ交差率（ZCR）、スペクトル重心を組み合わせ、高エネルギーかつ高ピッチな区間を「叫び声/悲鳴」、高周波帯域の断続的ピークを「笑い声」としてルールベース判定。
* **長所**: 追加モデル（重みファイル）不要で軽量。
* **用途**: 単純な音圧ピークと声の感情ピークの分離。

#### 手法 3: 軽量事前学習分類モデル（高度分類: YAMNet / Audio Spectrogram Transformer）
* **アプローチ**: TensorFlow Lite または ONNX 版の **YAMNet**（521クラスの環境音分類モデル、モデルサイズ約3.5MB）をバックグラウンド実行。
* **長所**: 「Laughter（笑い声）」「Screaming（叫び声）」「Applause（拍手）」などを高い信頼度で識別可能。
* **用途**: **「笑い声検知」** や **「配信中の環境音・ゲーム音SE検知」**。

> [!NOTE]
> **初期導入時の推奨方針**:
> まずは **手法 1（短時間 RMS / dBFS 閾値判定）** を `SoundEventDetector` に実装してマイク音/ゲーム音それぞれの即時ピーク検知を低負荷で実現し、その後必要に応じて **手法 3（ONNX版 YAMNet）** による笑い声・ゲームSE分類を追加するのが最も実用的です。
