# Phase 11 ストリーミングアーキテクチャ クラス図

現在の `audio-transcriber` ライブラリにおいて、設定管理・ストリーミングパイプライン・推論エンジン・文脈・チャンク制御の各コンポーネントがどのように連携するかを整理したクラス図です。

```mermaid
classDiagram
    %% --- 設定管理 (Config) ---
    class AppConfig {
        +paths: PathConfig
        +pipeline: PipelineConfig
        +stream: StreamConfig
        +transcribe: TranscribeConfig
        +...
    }
    
    class StreamConfig {
        +chunk_size_ms: int
        +context: StreamContextConfig
    }
    
    class StreamContextConfig {
        +context_max_length: int
        +context_timeout_seconds: float
        +chunk_min_seconds: float
        +chunk_max_seconds: float
    }
    
    AppConfig "1" *-- "1" StreamConfig : 保有
    StreamConfig "1" *-- "1" StreamContextConfig : 新設

    %% --- ストリーミング用パイプライン ---
    class AudioStreamPipeline {
        -transcriber: TranscriberProvider
        -vad_manager: StreamingVadManager
        -context_manager: ContextManager
        -config: StreamConfig
        +start()
        +stop()
        +process_audio_chunk(chunk: bytes)
        +reset()
    }

    %% --- ストリーミング制御 (新設) ---
    class ContextManager {
        -max_length: int
        -timeout_seconds: float
        -history: list~str~
        +get_prompt() str
        +add_text(text: str)
        +reset_if_timeout(silence_duration: float) bool
        +clear()
    }

    class StreamingVadManager {
        -chunk_min_seconds: float
        -chunk_max_seconds: float
        -buffer: list~np.ndarray~
        +feed_chunk(chunk: np.ndarray) np.ndarray | None
        +reset()
    }

    %% --- 推論エンジン (STT) ---
    class TranscriberProvider {
        <<Protocol>>
        +transcribe_file(file_path: Path, on_segment, on_progress) list~dict~
        +transcribe_stream(audio_chunk: np.ndarray, initial_prompt: str) list~dict~
    }

    class FasterWhisperProvider {
        -model: WhisperModelProtocol
        +transcribe_file(...) list~dict~
        +transcribe_stream(...) list~dict~
    }
    
    class WhisperModelProtocol {
        <<Protocol>>
        +transcribe(...) tuple
    }

    %% --- 依存関係・関連 ---
    AudioStreamPipeline "1" o-- "1" TranscriberProvider : コンストラクタ注入 (DI)
    AudioStreamPipeline "1" o-- "1" StreamConfig : コンストラクタ注入 (DI)
    AudioStreamPipeline "1" *-- "1" StreamingVadManager : ストリーミング時のVAD制御
    AudioStreamPipeline "1" *-- "1" ContextManager : 逐次推論時の文脈保持
    
    TranscriberProvider <|.. FasterWhisperProvider : インターフェース実装
    FasterWhisperProvider "1" *-- "1" WhisperModelProtocol : バックエンド(faster-whisper)
```

## 各コンポーネントの責務分離（Phase 11 の要点）

1. **`AppConfig` と `StreamConfig`**:
   CLI引数やTOMLから読み込まれた値は全てこのデータクラス群に集約され、各パイプラインやモジュールの生成時に外から注入 (DI) されます。
2. **`AudioStreamPipeline` (全体オーケストレーター)**:
   ストリーミング入力の統括を行います。ここには複雑な音声処理のロジックは書かず、各マネージャーやプロバイダーを連携させる Facade として機能します。
3. **`StreamingVadManager` (チャンク制御)**:
   細かく入力されてくる音声チャンクを繋ぎ合わせ、Silero-VADの判定と `chunk_max_seconds` 等の制約に基づいて、「Whisperに渡すべき確定した発話チャンク (np.ndarray)」を切り出す責務のみを持ちます。
4. **`ContextManager` (文脈制御)**:
   ストリーミング特休の「過去の会話をどこまで記憶させるか（ハルシネーション対策）」を管理します。無音時間の長さや文字数上限によって、動的にプロンプト（`initial_prompt`）の長さを切り詰めたりリセットしたりします。
5. **`TranscriberProvider` (推論実行)**:
   純粋に「渡された音声（ファイルまたは波形チャンク）」を文字に変換する責務のみを持ちます。前処理や文脈の管理などは行わず、`transcribe_stream` では渡された `audio_chunk` と `initial_prompt` を元に推論を即座に実行します。
