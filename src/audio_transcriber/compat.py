"""Compatibility shims and environment configuration for external dependencies."""

from __future__ import annotations

import os
import site
import sys
from pathlib import Path


def setup_cuda_library_paths() -> None:
    """Python 仮想環境内の nvidia.* パッケージから CUDA 共有ライブラリパスを検索し環境変数に追加します。"""
    search_dirs: list[Path] = []

    # site-packages 配下の nvidia ディレクトリを探索
    for site_pkg in site.getsitepackages():
        p = Path(site_pkg) / "nvidia"
        if p.is_dir():
            search_dirs.append(p)

    # 実行中の Python の仮想環境パスも探索
    venv_site = (
        Path(sys.prefix)
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
        / "nvidia"
    )
    if venv_site.is_dir() and venv_site not in search_dirs:
        search_dirs.append(venv_site)

    added_paths: list[str] = []
    for nvidia_dir in search_dirs:
        for sub_pkg in nvidia_dir.iterdir():
            lib_dir = sub_pkg / "lib"
            if lib_dir.is_dir():
                added_paths.append(str(lib_dir))

    if added_paths:
        current_ld = os.environ.get("LD_LIBRARY_PATH", "")
        # 重複を避けて先頭に追加
        unique_new = [p for p in added_paths if p not in current_ld]
        if unique_new:
            os.environ["LD_LIBRARY_PATH"] = ":".join(unique_new) + (
                ":" + current_ld if current_ld else ""
            )


# モジュールインポート時に自動実行
setup_cuda_library_paths()
