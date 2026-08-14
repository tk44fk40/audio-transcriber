"""Audio denoiser protocol and base definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class AudioDenoiser(Protocol):
    """音声ノイズ除去エンジンのプロトコル。"""

    def denoise(self, input_path: Path, output_path: Path) -> Path:
        """音声ファイルのノイズ除去を行い出力ファイルパスを返します。

        Args:
            input_path: 入力音声ファイルのパス。
            output_path: 出力先音声ファイルのパス。

        Returns:
            処理済み出力音声ファイルのパス。

        Raises:
            RuntimeError: ノイズ除去処理に失敗した場合。
        """
        ...
