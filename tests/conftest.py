"""Pytest conftest.py."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from audio_transcriber.config import AppConfig
from audio_transcriber.stt import TranscriberProvider


class DummyTranscriberProvider(TranscriberProvider):
    """ダミートランスクライバープロバイダー。"""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def transcribe_file(
        self,
        file_path: Path | str,
        on_segment: Callable[[dict[str, Any]], None] | None = None,
        on_progress: Callable[[str, str], None] | None = None,
    ) -> list[dict[str, Any]]:
        seg = {"start": 0.0, "end": 1.0, "text": "テスト"}
        if on_segment:
            on_segment(seg)
        if on_progress:
            on_progress("progress", "completed")
        return [seg]


@pytest.fixture
def dummy_provider_class() -> type[DummyTranscriberProvider]:
    """DI 用のダミートランスクライバープロバイダーのクラスを返します。"""
    return DummyTranscriberProvider


@pytest.fixture
def base_config(tmp_path: Path) -> AppConfig:
    """テスト用の基本設定を返します。"""
    cfg = AppConfig()
    cfg.paths.output_dir = tmp_path / "output"
    return cfg
