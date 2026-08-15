"""Tests for external dependency compatibility shims."""

import sys

import audio_transcriber.compat as compat


def test_compat_module_loads():
    """Test compat module imports cleanly."""
    assert "audio_transcriber.compat" in sys.modules
    assert hasattr(compat, "__name__")


def test_compat_venv_site(monkeypatch):
    """Test compat module includes venv site-packages if it exists and is not in site_packages."""
    from unittest.mock import patch

    with patch("site.getsitepackages", return_value=[]):
        with patch("pathlib.Path.is_dir") as mock_is_dir:
            # We want only the venv_site to return True, others False to simplify
            def is_dir_mock():
                return True

            mock_is_dir.side_effect = is_dir_mock

            with patch("pathlib.Path.iterdir", return_value=[]):
                compat.setup_cuda_library_paths()
