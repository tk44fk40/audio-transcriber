"""Tests for external dependency compatibility shims."""

import sys

import audio_transcriber.compat as compat


def test_compat_module_loads():
    """Test compat module imports cleanly."""
    assert "audio_transcriber.compat" in sys.modules
    assert hasattr(compat, "__name__")
