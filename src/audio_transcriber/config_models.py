"""Configuration data models and validation for audio-transcriber.

設定データクラスおよび境界値バリデーションを定義します。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PathConfig:
    """入出力および各種ファイルパス設定。"""

    output_dir: Path = field(default_factory=lambda: Path("./output"))
    default_video_path: Path | None = None
    debug_output_dir: Path | None = None
    custom_dict_path: Path | None = None


@dataclass
class MediaConfig:
    """メディア抽出・動画再結合設定。"""

    mic_track: int = 2
    sample_rate: int = 48000

    def __post_init__(self) -> None:
        """設定値の境界値バリデーションを実行します。"""
        if self.mic_track < 1:
            raise ValueError(f"mic_track must be >= 1, got {self.mic_track}")
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be > 0, got {self.sample_rate}")


@dataclass
class ModelConfig:
    """Whisper推論モデル設定。"""

    model_size: str = "small"
    device: str = "cuda"
    compute_type: str = "float16"


@dataclass
class VadConfig:
    """Silero-VAD 音声区間検出設定。"""

    min_silence_duration_ms: int = 500
    vad_threshold: float = 0.5

    def __post_init__(self) -> None:
        """設定値の境界値バリデーションを実行します。"""
        if self.min_silence_duration_ms <= 0:
            raise ValueError(
                f"min_silence_duration_ms must be > 0, got {self.min_silence_duration_ms}"
            )
        if not (0.0 <= self.vad_threshold <= 1.0):
            raise ValueError(
                f"vad_threshold must be between 0.0 and 1.0, got {self.vad_threshold}"
            )


@dataclass
class TranscribeConfig:
    """音声文字起こし・Whisper推論設定。"""

    language: str = "ja"
    beam_size: int = 5
    condition_on_previous_text: bool = True
    no_speech_threshold: float = 0.6
    initial_prompt: str | None = None
    vad: VadConfig = field(default_factory=VadConfig)

    def __post_init__(self) -> None:
        """設定値の境界値バリデーションを実行します。"""
        if self.beam_size < 1:
            raise ValueError(f"beam_size must be >= 1, got {self.beam_size}")
        if not (0.0 <= self.no_speech_threshold <= 1.0):
            raise ValueError(
                f"no_speech_threshold must be between 0.0 and 1.0, got {self.no_speech_threshold}"
            )


@dataclass
class PostProcessConfig:
    """テキスト後処理およびサニタイズ設定。"""

    replace_terms: bool = True
    lower: bool = False
    remove_punct: bool = False
    no_speech_threshold: float = 0.6
    max_chars_per_second: float = 12.0

    def __post_init__(self) -> None:
        """設定値の境界値バリデーションを実行します。"""
        if not (0.0 <= self.no_speech_threshold <= 1.0):
            raise ValueError(
                f"no_speech_threshold must be between 0.0 and 1.0, got {self.no_speech_threshold}"
            )
        if self.max_chars_per_second <= 0:
            raise ValueError(
                f"max_chars_per_second must be > 0, got {self.max_chars_per_second}"
            )


@dataclass
class SubtitleConfig:
    """字幕タイミング補正および出力フォーマット設定。"""

    end_padding: float = 1.0
    min_duration: float = 1.5
    min_gap: float = 0.05
    formats: list[str] = field(default_factory=lambda: ["srt", "vtt", "json"])

    def __post_init__(self) -> None:
        """設定値の境界値バリデーションを実行します。"""
        if self.end_padding < 0:
            raise ValueError(f"end_padding must be >= 0, got {self.end_padding}")
        if self.min_duration <= 0:
            raise ValueError(f"min_duration must be > 0, got {self.min_duration}")
        if self.min_gap < 0:
            raise ValueError(f"min_gap must be >= 0, got {self.min_gap}")


@dataclass
class DenoiseConfig:
    """ノイズ除去設定。"""

    enabled: bool = True
    engine: str = "rnnoise"
    model_path: Path | None = None


@dataclass
class PipelineConfig:
    """パイプライン実行制御設定。"""

    remux: bool = True


@dataclass
class MasteringConfig:
    """音声マスタリング前処理設定。"""

    enabled: bool = False
    noise_gate_threshold: float = 0.04
    loudness_i: float = -16.0
    loudness_tp: float = -2.0
    loudness_lra: float = 11.0
    final_limit_db: float = -2.0

    def __post_init__(self) -> None:
        """設定値の境界値バリデーションを実行します。"""
        if self.noise_gate_threshold < 0:
            raise ValueError(
                f"noise_gate_threshold must be >= 0, got {self.noise_gate_threshold}"
            )


@dataclass
class StreamContextConfig:
    """ストリーミングの文脈管理設定。"""

    context_max_length: int = 200
    context_timeout_seconds: float = 3.0

    def __post_init__(self) -> None:
        """設定値の境界値バリデーションを実行します。"""
        if self.context_max_length <= 0:
            raise ValueError(
                f"context_max_length must be > 0, got {self.context_max_length}"
            )
        if self.context_timeout_seconds <= 0:
            raise ValueError(
                f"context_timeout_seconds must be > 0, got {self.context_timeout_seconds}"
            )


@dataclass
class StreamConfig:
    """ストリーミング処理設定。"""

    chunk_size_ms: int = 100
    buffer_size_seconds: float = 10.0
    sample_rate: int = 16000
    flush_timeout_ms: int = 1000
    word_gap_split_threshold: float = 1.0
    streaming_log: bool = False

    chunk_min_seconds: float = 1.0
    chunk_max_seconds: float = 30.0
    context: StreamContextConfig = field(default_factory=StreamContextConfig)

    def __post_init__(self) -> None:
        """設定値の境界値バリデーションを実行します。"""
        if self.chunk_size_ms <= 0:
            raise ValueError(f"chunk_size_ms must be > 0, got {self.chunk_size_ms}")
        if self.buffer_size_seconds <= 0:
            raise ValueError(
                f"buffer_size_seconds must be > 0, got {self.buffer_size_seconds}"
            )
        if self.sample_rate <= 0:
            raise ValueError(f"sample_rate must be > 0, got {self.sample_rate}")
        if self.flush_timeout_ms <= 0:
            raise ValueError(
                f"flush_timeout_ms must be > 0, got {self.flush_timeout_ms}"
            )
        if self.word_gap_split_threshold < 0:
            raise ValueError(
                f"word_gap_split_threshold must be >= 0, got {self.word_gap_split_threshold}"
            )
        if self.chunk_min_seconds <= 0:
            raise ValueError(
                f"chunk_min_seconds must be > 0, got {self.chunk_min_seconds}"
            )
        if self.chunk_max_seconds < self.chunk_min_seconds:
            raise ValueError(
                f"chunk_max_seconds ({self.chunk_max_seconds}) must be >= "
                f"chunk_min_seconds ({self.chunk_min_seconds})"
            )


@dataclass
class AppConfig:
    """アプリケーション全体の設定。"""

    paths: PathConfig = field(default_factory=PathConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    denoise: DenoiseConfig = field(default_factory=DenoiseConfig)
    media: MediaConfig = field(default_factory=MediaConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    transcribe: TranscribeConfig = field(default_factory=TranscribeConfig)
    post_process: PostProcessConfig = field(default_factory=PostProcessConfig)
    subtitle: SubtitleConfig = field(default_factory=SubtitleConfig)
    stream: StreamConfig = field(default_factory=StreamConfig)
    mastering: MasteringConfig = field(default_factory=MasteringConfig)

    @property
    def output_dir(self) -> Path:
        """出力先ディレクトリパスへのショートカット。"""
        return self.paths.output_dir

    @property
    def default_video_path(self) -> Path | None:
        """デフォルト入力動画パスへのショートカット。"""
        return self.paths.default_video_path

    @property
    def debug_output_dir(self) -> Path | None:
        """デバッグ出力ディレクトリパスへのショートカット。"""
        return self.paths.debug_output_dir

    @property
    def custom_dict_path(self) -> Path | None:
        """カスタム辞書パスへのショートカット。"""
        return self.paths.custom_dict_path
