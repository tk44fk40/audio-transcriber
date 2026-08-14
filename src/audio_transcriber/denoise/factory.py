"""Factory function for creating audio denoisers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from audio_transcriber.denoise.base import AudioDenoiser
from audio_transcriber.denoise.engines.passthrough import PassThroughDenoiser
from audio_transcriber.denoise.engines.rnnoise import RNNoiseDenoiser

if TYPE_CHECKING:
    from audio_transcriber.config import DenoiseConfig

logger = logging.getLogger(__name__)


def create_denoiser(config: DenoiseConfig | None = None) -> AudioDenoiser:
    """設定に基づいて適切な AudioDenoiser インスタンスを生成して返します。

    Args:
        config: ノイズ除去設定 (DenoiseConfig)。None の場合は既定の RNNoiseDenoiser を生成。

    Returns:
        AudioDenoiser プロトコルを実装したノイズ除去エンジンインスタンス。

    Raises:
        ValueError: 未知のノイズ除去エンジン名が指定された場合。
    """
    if config is None:
        return RNNoiseDenoiser()

    if not config.enabled:
        logger.info(
            "ノイズ除去が無効化されているため PassThroughDenoiser を使用します。"
        )
        return PassThroughDenoiser()

    engine_name = config.engine.lower().strip()
    if engine_name in ("rnnoise", "ffmpeg-arnndn", "default"):
        return RNNoiseDenoiser(model_path=config.model_path)
    elif engine_name in ("none", "passthrough", "disabled"):
        return PassThroughDenoiser()
    else:
        raise ValueError(
            f"サポートされていないノイズ除去エンジンです: {config.engine} (利用可能: 'rnnoise', 'none')"
        )
