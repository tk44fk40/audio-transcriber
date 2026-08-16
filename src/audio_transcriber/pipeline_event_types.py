"""パイプラインイベントの型定義モジュール。"""

from __future__ import annotations

from typing import Any

__all__ = ["ProcessingEventDict"]

type ProcessingEventDict = dict[str, Any]
