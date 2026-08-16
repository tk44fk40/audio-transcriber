# Phase 11 ストリーミングアーキテクチャ 状態遷移図 (Statechart)

ストリーミングパイプラインを構成する各マネージャークラスの厳密な状態遷移図です。

## 補足: 図中の VAD=0 / VAD=1 について
図中に登場する「VAD」とは **Voice Activity Detection（音声区間検出）** の略称です。AIモデルが入力された短い音声チャンクを分析し、人の声が含まれているかを判定した結果を表します。

* **`VAD=1` (発話あり)**: 人の声が含まれていると判定された状態。システムは「発話中」と判断し、音声を蓄積します。
* **`VAD=0` (無音・声なし)**: 無音、または環境ノイズのみで人の声は含まれていないと判定された状態。話の合間の息継ぎや、発話の終了タイミングでこの値になります。

## 1. StreamingVadManager (チャンク制御) の状態遷移図
音声のチャンク入力を受け取り、発話区間を切り出して推論へ渡す役割を持つクラスです。`min_silence_duration` による発話終了の猶予と、`chunk_min_seconds` 未満の短い音声を保留・結合する状態を持ちます。

```mermaid
stateDiagram-v2
    [*] --> Idle

    state "無音待機 (Idle)" as Idle
    state "発話蓄積中 (SpeechActive)" as SpeechActive
    state "終了判定中 (TrailingSilence)" as TrailingSilence
    state "短チャンク保留 (HoldingShortChunk)" as HoldingShortChunk

    %% Idle状態
    Idle --> Idle : [イベント] audio_in \n [条件] VAD=0
    Idle --> SpeechActive : [イベント] audio_in \n [条件] VAD=1 \n / アクション: 蓄積開始

    %% SpeechActive状態
    SpeechActive --> SpeechActive : [イベント] audio_in \n [条件] VAD=1
    SpeechActive --> TrailingSilence : [イベント] audio_in \n [条件] VAD=0 \n / アクション: 無音タイマー開始
    
    %% TrailingSilence (発話終了の猶予期間)
    TrailingSilence --> SpeechActive : [イベント] audio_in \n [条件] VAD=1 \n / アクション: 無音タイマーリセット(発話再開)
    TrailingSilence --> TrailingSilence : [イベント] audio_in \n [条件] VAD=0 AND 無音時間 < min_silence
    
    %% 発話終了確定時の分岐 (最小チャンク長の判定)
    TrailingSilence --> Idle : [イベント] audio_in \n [条件] VAD=0 AND 無音時間 >= min_silence \n AND 蓄積時間 >= chunk_min_seconds \n / アクション: 確定チャンクを yield
    TrailingSilence --> HoldingShortChunk : [イベント] audio_in \n [条件] VAD=0 AND 無音時間 >= min_silence \n AND 蓄積時間 < chunk_min_seconds \n / アクション: yieldせずバッファに保留

    %% HoldingShortChunk (短いチャンクを次と結合するため待機)
    HoldingShortChunk --> HoldingShortChunk : [イベント] audio_in \n [条件] VAD=0
    HoldingShortChunk --> SpeechActive : [イベント] audio_in \n [条件] VAD=1 \n / アクション: 蓄積再開 (前のチャンクと結合)

    %% 強制切り出し (チャンク最大長)
    SpeechActive --> SpeechActive : [イベント] audio_in \n [条件] 蓄積時間 >= chunk_max_seconds \n / アクション: 強制的に yield し、\n残りで新しいバッファ開始
    TrailingSilence --> Idle : [イベント] audio_in \n [条件] 蓄積時間 >= chunk_max_seconds \n / アクション: 強制的に yield

    %% タイムアウト/終了時のフラッシュ
    HoldingShortChunk --> Idle : [イベント] flush() または reset() \n / アクション: 強制的に yield (または破棄)
```

## 2. ContextManager (文脈管理) の状態遷移図
Whisperに渡す `initial_prompt`（過去の会話履歴）を保持・管理し、ハルシネーションを防ぐ役割を持つクラスです。文字数の上限到達時（Trim）や、パイプラインから渡される無音時間に基づくタイムアウト判定を行います。

```mermaid
stateDiagram-v2
    [*] --> Empty

    state "文脈なし (Empty)" as Empty
    state "文脈保持 (ActiveContext)" as ActiveContext

    %% Empty状態
    Empty --> ActiveContext : [イベント] add_text() \n / アクション: テキストを追加
    Empty --> Empty : [イベント] check_timeout() または clear()

    %% ActiveContext状態 (文字数制限の判定)
    ActiveContext --> ActiveContext : [イベント] add_text() \n [条件] 合計文字数 <= max_length \n / アクション: 末尾に追加
    ActiveContext --> ActiveContext : [イベント] add_text() \n [条件] 合計文字数 > max_length \n / アクション: 末尾に追加し、上限に収まるまで\n 最も古い発話単位(セグメント)の履歴を破棄

    %% ActiveContext状態 (タイムアウト判定)
    ActiveContext --> ActiveContext : [イベント] check_timeout(silence_duration) \n [条件] silence_duration < timeout_seconds
    ActiveContext --> Empty : [イベント] check_timeout(silence_duration) \n [条件] silence_duration >= timeout_seconds \n / アクション: 文脈履歴をクリア
    
    ActiveContext --> Empty : [イベント] clear() \n / アクション: 文脈履歴を強制クリア
```
