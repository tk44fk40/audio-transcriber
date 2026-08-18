"""Configuration data models and validation for audio-transcriber.

設定データクラスおよび境界値バリデーションを定義します。
各設定項目には、エディタ上でのホバー表示で
単位や意味が明確に伝わるよう詳細なdocstringを記述しています。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PathConfig:
    """入出力および各種ファイルパス設定。"""

    output_dir: Path = field(default_factory=lambda: Path("./output"))
    """認識結果（テキスト）や字幕ファイルなどの成果物を出力するディレクトリパス。"""

    default_video_path: Path | None = None
    """デフォルトの入力動画ファイルのパス。"""

    debug_output_dir: Path | None = None
    """デバッグ用の中間音声ファイル（抽出音声や
    ノイズ除去後音声など）を出力するディレクトリパス。
    Noneの場合は出力されません。"""

    custom_dict_path: Path | None = None
    """テキスト置換や優先認識に用いる
    カスタムユーザー辞書（CSVまたはJSONなど）のファイルパス。"""


@dataclass
class MediaConfig:
    """メディア抽出・動画再結合設定。"""

    mic_track: int = 2
    """動画ファイルからマイク音声（実況やナレーションなど）を
    抽出する際の対象音声トラック番号（1ベース）。"""

    sample_rate: int = 48000
    """入力メディアファイルのデフォルト音声サンプリングレート（Hz）。
    通常は 48000 Hz。"""

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
    """使用するWhisperモデルのサイズ
    （"tiny", "base", "small", "medium", "large-v3"など）。"""

    device: str = "cuda"
    """推論を実行する演算デバイス（"cuda" または "cpu"）。"""

    compute_type: str = "float16"
    """推論時の浮動小数点演算精度（"float16", "float32", "int8", "int8_float16"など）。"""


@dataclass
class VadConfig:
    """Silero-VAD 音声区間検出設定。"""

    min_silence_duration_ms: int = 500
    """無音とみなして発話区間を区切る（セグメントを分割する）
    ための最小連続無音時間（ミリ秒）。"""

    vad_threshold: float = 0.5
    """VAD（音声活動検出）が音声（発話）であると
    判断する確率のしきい値（0.0〜1.0）。
    これを超えると音声区間と判定されます。"""

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
    """音声認識の対象言語コード（日本語は "ja"）。"""

    beam_size: int = 5
    """ビームサーチの幅（ビームサイズ）。
    大きいほど精度は向上しますが推論時間は長くなります。"""

    condition_on_previous_text: bool = True
    """前回の認識テキストをコンテキスト（プロンプト）として
    次の認識に引き継ぎ、文字起こしの文脈一貫性を保つかどうか。"""

    no_speech_threshold: float = 0.6
    """発話がない（無音、環境音、ノイズのみ）と
    判断する確率のしきい値（0.0〜1.0）。"""

    initial_prompt: str | None = None
    """認識精度向上のため、Whisper推論の最初の文脈として
    与える初期プロンプトテキスト。"""

    vad: VadConfig = field(default_factory=VadConfig)
    """Silero-VADによる音声区間検出のコンフィギュレーションオブジェクト。"""

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
    """カスタム辞書（custom_dict）を用いた特定単語・用語の
    テキスト置換を有効にするかどうか。"""

    lower: bool = False
    """英語アルファベット文字をすべて小文字に統一するかどうか。"""

    remove_punct: bool = False
    """句読点（、。,.など）を除去してプレーンなテキストにするかどうか。"""

    no_speech_threshold: float = 0.6
    """Whisper推論結果の `no_speech_prob` に基づく
    サニタイズしきい値（0.0〜1.0）。これを超える場合は
    ハルシネーションとみなしテキストを破棄します。"""

    max_chars_per_second: float = 12.0
    """1秒あたりの最大文字数。これを超える密度のセグメントは
    ハルシネーション（異常な同一語繰り返し等）と判断して
    破棄します（文字/秒）。"""

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
    """字幕の表示終了時刻を延長する時間（秒）。
    発話終了後の余韻を持たせるために追加します。"""

    min_duration: float = 1.5
    """1つの字幕が表示される最小時間（秒）。短すぎる字幕を
    読みやすくするためにこの長さまで表示を延長します。"""

    min_gap: float = 0.05
    """隣り合う字幕間の最小時間間隔（秒）。これより短い
    間隔のギャップは埋められ、直前の字幕が次の字幕の
    直前まで表示されます。"""

    formats: list[str] = field(default_factory=lambda: ["srt", "vtt", "json"])
    """出力する字幕・書き起こしフォーマットのリスト。例: `["srt", "vtt", "json"]`。"""

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
    """音声ノイズ除去（RNNoiseなど）を前処理として有効にするかどうか。"""

    engine: str = "rnnoise"
    """使用するノイズ除去エンジンの名前。デフォルトは "rnnoise"。"""

    model_path: Path | None = None
    """ノイズ除去エンジン用のカスタムモデル（`.rnnn` ファイルなど）へのパス。"""


@dataclass
class PipelineConfig:
    """パイプライン実行制御設定。"""

    remux: bool = True
    """音声抽出および再結合（マルチプレクス）処理を行うかどうか。"""


@dataclass
class MasteringConfig:
    """音声マスタリング前処理設定。"""

    enabled: bool = False
    """音声ファイルのマスタリング処理（音圧調整や
    ラウドネス正規化）を有効にするかどうか。"""

    noise_gate_threshold: float = 0.04
    """ノイズゲートを適用する振幅しきい値。このしきい値未満の
    微小音声振幅は完全な無音（0.0）に減衰されます。"""

    loudness_i: float = -16.0
    """目標とする統合ラウドネス値（LUFS / LKFS）。デフォルトは -16.0 LUFS。"""

    loudness_tp: float = -2.0
    """目標とするトゥルーピークレベル（dBTP）。クリッピングを防ぐための上限値。デフォルトは -2.0 dBTP。"""

    loudness_lra: float = 11.0
    """ラウドネスレンジ（LRA）。音量のダイナミックレンジ。デフォルトは 11.0。"""

    final_limit_db: float = -2.0
    """最終出力の音量がこれを超えないように適用するリミッター制限（dB）。デフォルトは -2.0 dB。"""

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
    """Whisperの文脈（プロンプト履歴）として引き継ぐ
    過去の認識テキストの最大合計文字数。"""

    context_timeout_seconds: float = 3.0
    """発話がない無音時間がこの秒数（秒）を超えた場合、
    過去の認識文脈履歴をクリアして新しい文脈として開始します。"""

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
    """マイク等から一度に読み込んで処理キューに供給する
    音声フレーム（チャンク）の長さ（ミリ秒）。"""

    buffer_size_seconds: float = 10.0
    """内部で使用する音声一時保持リングバッファの総容量（秒）。"""

    sample_rate: int = 16000
    """ストリーミング処理およびWhisper、Silero-VADモデルの推奨入力音声サンプリングレート（Hz）。通常は 16000 Hz（16kHz）。"""

    flush_timeout_ms: int = 1000
    """最後に発話が検出されてから、強制的にバッファを
    フラッシュして音声認識（推論）をトリガーする時間（ミリ秒）。"""

    word_gap_split_threshold: float = 1.0
    """単語ごとのタイムスタンプ間ギャップがこのしきい値（秒）
    を超えた場合に、セグメントを別々に分割する判断基準。"""

    streaming_log: bool = False
    """ストリーミング処理の進捗状態やVAD判定ログを
    詳細に標準出力に表示するかどうか。"""

    chunk_min_seconds: float = 1.0
    """Whisperに入力して音声認識を行う発話データの
    最小秒数（秒）。短すぎる誤検出の排除に用います。"""

    chunk_max_seconds: float = 30.0
    """Whisperに入力して音声認識を行う発話データの
    最大秒数（秒）。この長さに達した場合、発話が続いていても
    セグメントを区切って推論を起動します。"""

    context: StreamContextConfig = field(default_factory=StreamContextConfig)
    """ストリーミング処理における文脈履歴管理（コンテキスト管理）の設定オブジェクト。"""

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
    """各種入出力ファイルパスの設定。"""

    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    """動画音声の抽出・再結合パイプライン制御設定。"""

    denoise: DenoiseConfig = field(default_factory=DenoiseConfig)
    """ノイズ除去前処理の設定。"""

    media: MediaConfig = field(default_factory=MediaConfig)
    """メディア抽出・サンプリングレート設定。"""

    model: ModelConfig = field(default_factory=ModelConfig)
    """Whisper推論エンジンモデルのロード設定。"""

    transcribe: TranscribeConfig = field(default_factory=TranscribeConfig)
    """音声文字起こし・Whisperパラメータ・VAD設定。"""

    post_process: PostProcessConfig = field(default_factory=PostProcessConfig)
    """認識結果テキストのサニタイズ・置換後処理設定。"""

    subtitle: SubtitleConfig = field(default_factory=SubtitleConfig)
    """字幕フォーマット・時間調整・間隔補正設定。"""

    stream: StreamConfig = field(default_factory=StreamConfig)
    """リアルタイムストリーミング音声処理および文脈管理設定。"""

    mastering: MasteringConfig = field(default_factory=MasteringConfig)
    """音声マスタリング（音圧調整・ラウドネス正規化）前処理設定。"""

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
