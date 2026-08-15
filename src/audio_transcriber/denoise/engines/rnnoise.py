"""RNNoise-based denoiser implementation using FFmpeg arnndn filter."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from audio_transcriber.config import MasteringConfig

logger = logging.getLogger(__name__)

# デフォルトで探索する RNNoise モデルパス候補
DEFAULT_MODEL_CANDIDATES = [
    Path("data/models/sh.rnnn"),
    Path("data/models/cb.rnnn"),
]


class RNNoiseDenoiser:
    """FFmpeg の arnndn フィルタ（RNNoise）を用いた低遅延・軽量ノイズ除去エンジン。"""

    def __init__(
        self,
        model_path: Path | str | None = None,
        mastering_config: MasteringConfig | None = None,
    ) -> None:
        """RNNoiseDenoiser を初期化します。

        Args:
            model_path: RNNoise モデルファイル (.rnnn) のパス。
            mastering_config: マスタリング処理の設定。
        """
        self.model_path: Path | None = (
            Path(model_path).resolve() if model_path is not None else None
        )
        self.mastering_config = mastering_config

    @staticmethod
    def _find_default_model() -> Path | None:
        """プロジェクト内のデフォルト RNNoise モデルを探索します。"""
        for candidate in DEFAULT_MODEL_CANDIDATES:
            if candidate.is_file():
                return candidate.resolve()
        return None

    def denoise(self, input_path: Path | str, output_path: Path | str) -> Path:
        """FFmpeg arnndn フィルタを用いて音声のノイズ除去を実行します。

        Args:
            input_path: 入力音声ファイルのパス。
            output_path: 出力先 WAV ファイルのパス。

        Returns:
            ノイズ除去後の音声ファイル Path。

        Raises:
            RuntimeError: 入力ファイルが存在しない、または FFmpeg 処理に失敗した場合。
        """
        in_p = Path(input_path).resolve()
        out_p = Path(output_path).resolve()

        if not in_p.exists():
            raise RuntimeError(f"入力音声ファイルが存在しません: {in_p}")

        out_p.parent.mkdir(parents=True, exist_ok=True)

        if self.model_path is not None:
            if not self.model_path.exists():
                raise RuntimeError(
                    f"指定された RNNoise モデルファイルが見つかりません: {self.model_path}"
                )
            resolved_model: Path | None = self.model_path
        else:
            resolved_model = self._find_default_model()

        filter_parts = ["aresample=48000"]

        if resolved_model is not None and resolved_model.is_file():
            filter_parts.append(f"arnndn=m={resolved_model}")
            logger.info(
                "RNNoise (FFmpeg arnndn: %s) でノイズ除去を開始: %s -> %s",
                resolved_model.name,
                in_p.name,
                out_p.name,
            )
        else:
            logger.warning(
                "RNNoise モデルファイルが見つかりません。ノイズ除去をバイパスして 48kHz 変換のみ行います。"
            )

        if self.mastering_config is not None and self.mastering_config.enabled:
            m = self.mastering_config
            # Noise gate (compand) -> 1st limiter -> loudnorm -> final limiter
            gate_db = -100 * (1.0 - m.noise_gate_threshold)
            compand_str = f"compand=attacks=0:decays=0.1:points=-80/-80|{gate_db}/-80|{gate_db + 1}/{gate_db + 1}|0/0"
            filter_parts.append(compand_str)
            filter_parts.append("alimiter=level_in=1:level_out=1:limit=-1.0")
            filter_parts.append(
                f"loudnorm=I={m.loudness_i}:TP={m.loudness_tp}:LRA={m.loudness_lra}"
            )
            filter_parts.append(
                f"alimiter=level_in=1:level_out=1:limit={m.final_limit_db}"
            )

        filter_str = ",".join(filter_parts)

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(in_p),
            "-af",
            filter_str,
            "-ar",
            "48000",
            "-ac",
            "1",
            str(out_p),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as e:
            raise RuntimeError(f"FFmpeg の起動に失敗しました: {e}") from e

        if result.returncode != 0:
            logger.error("FFmpeg arnndn 実行エラー:\n%s", result.stderr)
            raise RuntimeError(
                f"RNNoise ノイズ除去処理に失敗しました (exit {result.returncode}): {result.stderr}"
            )

        return out_p
