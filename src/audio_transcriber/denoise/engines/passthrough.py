"""Pass-through (no-op) denoiser implementation."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class PassThroughDenoiser:
    """ノイズ除去を実行せずに入力音声をそのまま複製・出力するプロバイダー。"""

    def denoise(self, input_path: Path, output_path: Path) -> Path:
        """入力音声をそのまま出力先に複製します。

        Args:
            input_path: 入力音声ファイルのパス。
            output_path: 出力先音声ファイルのパス。

        Returns:
            出力音声ファイルのパス。

        Raises:
            RuntimeError: 入力ファイルが存在しないか、コピーに失敗した場合。
        """
        in_p = Path(input_path).resolve()
        out_p = Path(output_path).resolve()

        if not in_p.exists():
            raise RuntimeError(f"入力音声ファイルが存在しません: {in_p}")

        out_p.parent.mkdir(parents=True, exist_ok=True)
        logger.info(
            "PassThrough: ノイズ除去をスキップして音声を複製します: %s -> %s",
            in_p.name,
            out_p.name,
        )

        try:
            shutil.copy2(in_p, out_p)
        except Exception as e:
            raise RuntimeError(f"音声ファイルのコピーに失敗しました: {e}") from e

        return out_p
