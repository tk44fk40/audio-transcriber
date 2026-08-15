"""Configuration management and TOML loading for audio-transcriber.

設定管理およびTOML設定ファイルの読み込み機能を提供します。
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_FILENAME = "config.toml"


def _normalize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """辞書のキーを再帰的に小文字化して正規化する。

    Args:
        data: 任意のキー命名形式を持つ辞書。

    Returns:
        全キーが小文字に変換された新しい辞書。
    """
    normalized: dict[str, Any] = {}
    for k, v in data.items():
        lower_k = k.lower()
        normalized[lower_k] = _normalize_dict(v) if isinstance(v, dict) else v
    return normalized


def _get_val(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """辞書から最初に見つかった非Noneのキーの値を返す。

    Args:
        d: 探索対象の辞書。
        *keys: 優先度順のキー名リスト (小文字)。
        default: いずれのキーも存在しない場合のデフォルト値。

    Returns:
        最初に見つかった値、またはデフォルト値。
    """
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _get_path(
    d: dict[str, Any], *keys: str, default: Path | None = None
) -> Path | None:
    """辞書から最初に見つかった非Noneのキーの値をPathとして返す。"""
    val = _get_val(d, *keys)
    return Path(val) if val is not None else default


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


@dataclass
class ModelConfig:
    """Whisper推論モデル設定。"""

    model_size: str = "small"
    device: str = "cuda"
    compute_type: str = "float16"


@dataclass
class VadConfig:
    """Silero-VAD 音声区間検出設定。"""

    vad_filter: bool = True
    min_silence_duration_ms: int = 500
    vad_threshold: float = 0.5


@dataclass
class TranscribeConfig:
    """音声文字起こし・Whisper推論設定。"""

    language: str = "ja"
    beam_size: int = 5
    condition_on_previous_text: bool = True
    no_speech_threshold: float = 0.6
    initial_prompt: str | None = None
    vad: VadConfig = field(default_factory=VadConfig)


@dataclass
class PostProcessConfig:
    """テキスト後処理およびサニタイズ設定。"""

    replace_terms: bool = True
    lower: bool = False
    remove_punct: bool = False
    no_speech_threshold: float = 0.6
    max_chars_per_second: float = 12.0


@dataclass
class SubtitleConfig:
    """字幕タイミング補正および出力フォーマット設定。"""

    end_padding: float = 1.0
    min_duration: float = 1.5
    min_gap: float = 0.05
    formats: list[str] = field(default_factory=lambda: ["srt", "vtt", "json"])


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


def parse_config_dict(data: dict[str, Any]) -> AppConfig:
    """TOMLから読み込んだ辞書をAppConfigインスタンスに変換する。

    大文字・小文字を正規化し、セクションごとの設定をパースします。

    Args:
        data: 設定辞書。

    Returns:
        設定値が反映された AppConfig インスタンス。
    """
    norm = _normalize_dict(data)

    # Path settings ([path] / [paths])
    path_d = norm.get("path") or norm.get("paths") or {}
    output_dir = Path(_get_val(path_d, "output_dir", default="./output"))
    default_video = _get_path(path_d, "default_video_path", "default_video")
    debug_output = _get_path(path_d, "debug_output_dir", "debug_dir")
    custom_dict = _get_path(
        path_d, "custom_dict_path", "custom_dictionary_path", "dictionary_path"
    )

    paths = PathConfig(
        output_dir=output_dir,
        default_video_path=default_video,
        debug_output_dir=debug_output,
        custom_dict_path=custom_dict,
    )

    # Pipeline
    pipe_d = norm.get("pipeline", {})
    pipeline = PipelineConfig(remux=bool(_get_val(pipe_d, "remux", default=True)))

    # Denoise
    denoise_d = norm.get("denoise", {})
    denoise = DenoiseConfig(
        enabled=bool(_get_val(denoise_d, "enabled", default=True)),
        engine=str(_get_val(denoise_d, "engine", default="rnnoise")),
        model_path=_get_path(denoise_d, "model_path", "model"),
    )

    # Media
    media_d = norm.get("media", {})
    media = MediaConfig(
        mic_track=int(_get_val(media_d, "mic_track", default=2)),
        sample_rate=int(_get_val(media_d, "sample_rate", default=48000)),
    )

    # Model
    model_d = norm.get("model", {})
    model = ModelConfig(
        model_size=str(_get_val(model_d, "model_size", default="small")),
        device=str(_get_val(model_d, "device", default="cuda")),
        compute_type=str(_get_val(model_d, "compute_type", default="float16")),
    )

    # Transcribe & VAD
    trans_d = norm.get("transcribe", {})
    vad_d = trans_d.get("vad") or norm.get("vad", {})
    vad = VadConfig(
        vad_filter=bool(_get_val(vad_d, "vad_filter", default=True)),
        min_silence_duration_ms=int(
            _get_val(vad_d, "min_silence_duration_ms", default=500)
        ),
        vad_threshold=float(_get_val(vad_d, "vad_threshold", default=0.5)),
    )
    raw_prompt = _get_val(trans_d, "initial_prompt", "prompt")
    initial_prompt = str(raw_prompt).strip() if raw_prompt is not None else None

    transcribe = TranscribeConfig(
        language=str(_get_val(trans_d, "language", default="ja")),
        beam_size=int(_get_val(trans_d, "beam_size", default=5)),
        condition_on_previous_text=bool(
            _get_val(trans_d, "condition_on_previous_text", default=True)
        ),
        no_speech_threshold=float(
            _get_val(trans_d, "no_speech_threshold", default=0.6)
        ),
        initial_prompt=initial_prompt,
        vad=vad,
    )

    # Post process
    post_d = (
        norm.get("post_process")
        or norm.get("postprocess")
        or norm.get("post_processing")
        or {}
    )
    post_process = PostProcessConfig(
        replace_terms=bool(_get_val(post_d, "replace_terms", default=True)),
        lower=bool(_get_val(post_d, "lower", default=False)),
        remove_punct=bool(_get_val(post_d, "remove_punct", default=False)),
        no_speech_threshold=float(_get_val(post_d, "no_speech_threshold", default=0.6)),
        max_chars_per_second=float(
            _get_val(post_d, "max_chars_per_second", default=12.0)
        ),
    )

    # Subtitle
    sub_d = norm.get("subtitle") or norm.get("subtitles") or {}
    raw_fmt = _get_val(
        sub_d,
        "formats",
        "subtitle_formats",
        "output_formats",
        default=["srt", "vtt", "json"],
    )
    if isinstance(raw_fmt, str):
        parsed_formats = [f.strip().lower() for f in raw_fmt.split(",") if f.strip()]
    elif isinstance(raw_fmt, list):
        parsed_formats = [str(f).strip().lower() for f in raw_fmt if str(f).strip()]
    else:
        parsed_formats = ["srt", "vtt", "json"]

    subtitle = SubtitleConfig(
        end_padding=float(_get_val(sub_d, "end_padding", default=1.0)),
        min_duration=float(_get_val(sub_d, "min_duration", default=1.5)),
        min_gap=float(_get_val(sub_d, "min_gap", default=0.05)),
        formats=parsed_formats,
    )

    return AppConfig(
        paths=paths,
        pipeline=pipeline,
        denoise=denoise,
        media=media,
        model=model,
        transcribe=transcribe,
        post_process=post_process,
        subtitle=subtitle,
    )


def load_config(config_path: Path | str | None = None) -> AppConfig:
    """TOMLファイルから設定を読み込み、存在しない場合はデフォルト設定を返す。

    Args:
        config_path: 設定ファイルのパス。None の場合はカレントディレクトリの config.toml を確認。

    Returns:
        読み込まれた AppConfig インスタンス。

    Raises:
        FileNotFoundError: 明示的に指定された設定ファイルが存在しない場合。
        ValueError: TOMLファイルの構文エラーが発生した場合。
    """
    if config_path is not None:
        target_path = Path(config_path)
        if not target_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
    else:
        default_file = Path(DEFAULT_CONFIG_FILENAME)
        target_path = default_file if default_file.is_file() else None

    if target_path is None:
        logger.debug("No configuration file found; using default configuration.")
        return AppConfig()

    logger.info(f"Loading configuration from {target_path}")
    try:
        with open(target_path, "rb") as f:
            return parse_config_dict(tomllib.load(f))
    except tomllib.TOMLDecodeError as e:
        raise ValueError(
            f"Failed to parse TOML configuration '{target_path}': {e}"
        ) from e
