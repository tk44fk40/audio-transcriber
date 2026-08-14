"""RNNoise-based denoiser implementation using FFmpeg arnndn filter."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class RNNoiseDenoiser:
    """FFmpeg の arnndn フィルタ（RNNoise）を用いた低遅延・軽量ノイズ除去エンジン。"""

    def __init__(self, model_path: Path | str | None = None) -> None:
        """RNNoiseDenoiser を初期化します。

        Args:
            model_path: RNNoise モデルファイル (.rnnn) のパス。None の場合はフィルタ既定またはモデルなしで動作。
        """
        self.model_path = Path(model_path).resolve() if model_path is not None else None

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

        # フィルタ文字列の構築: 48kHz にリサンプル後に arnndn を適用
        if self.model_path is not None:
            if not self.model_path.exists():
                raise RuntimeError(
                    f"指定された RNNoise モデルファイルが見つかりません: {self.model_path}"
                )
            filter_str = f"aresample=48000,arnndn=m={self.model_path}"
        else:
            filter_str = "aresample=48000,arnndn"

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

        logger.info(
            "RNNoise (FFmpeg arnndn) でノイズ除去を開始します: %s -> %s",
            in_p.name,
            out_p.name,
        )

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
