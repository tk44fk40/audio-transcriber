"""VAD進捗通知のハンドラモジュール。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

__all__ = ["VadProgressHandler"]


class VadProgressHandler(logging.Handler):
    """Faster-Whisper の内部ロガーから VAD チャンク出力を横取りして通知するハンドラ。"""

    def __init__(self, on_progress: Callable[[str, Any], None] | None) -> None:
        """初期化します。"""
        super().__init__()
        self.on_progress = on_progress
        self.setLevel(logging.DEBUG)

    def emit(self, record: logging.LogRecord) -> None:
        """ログレコードを受け取り、VAD出力があればコールバックに送ります。"""
        if not self.on_progress:
            return
        msg = record.getMessage()
        if "VAD filter kept the following audio segments:" in msg:
            import re

            chunks_str = msg.replace(
                "VAD filter kept the following audio segments:", ""
            ).strip()
            pattern = re.compile(r"([\d\.]+)s\s*-\s*([\d\.]+)s")
            vad_chunks = [
                (
                    float(m.group(1)) / (16000.0 if float(m.group(1)) > 10000 else 1.0),
                    float(m.group(2)) / (16000.0 if float(m.group(2)) > 10000 else 1.0),
                )
                for m in pattern.finditer(chunks_str)
            ]
            self.on_progress("vad_chunks", vad_chunks)
