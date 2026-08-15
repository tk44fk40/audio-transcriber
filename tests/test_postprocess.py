"""TextPostProcessor の単体テスト。"""

import json
from pathlib import Path

import pytest

from audio_transcriber.models import SubtitleSegment
from audio_transcriber.postprocess import TextPostProcessor


def _make_seg(text: str, start: float = 0.0, end: float = 1.0) -> SubtitleSegment:
    return SubtitleSegment(start=start, end=end, text=text)


class TestTextPostProcessorInit:
    """初期化テスト。"""

    def test_default_init(self) -> None:
        """デフォルト引数で初期化できること。"""
        processor = TextPostProcessor()
        assert processor.dictionary == {}

    def test_dictionary_loaded_from_json(self, tmp_path: Path) -> None:
        """JSON 辞書ファイルを読み込めること。"""
        # Arrange
        d = tmp_path / "dict.json"
        d.write_text(json.dumps({"ゲーム": "Game"}), encoding="utf-8")
        # Act
        processor = TextPostProcessor(dictionary_path=d)
        # Assert
        assert processor.dictionary == {"ゲーム": "Game"}

    def test_dictionary_loaded_from_toml(self, tmp_path: Path) -> None:
        """TOML 辞書ファイルを読み込めること。"""
        # Arrange
        d = tmp_path / "dict.toml"
        d.write_text('[replacements]\n"誤り" = "正解"\n', encoding="utf-8")
        # Act
        processor = TextPostProcessor(dictionary_path=d)
        # Assert
        assert processor.dictionary.get("誤り") == "正解"

    def test_missing_dictionary_raises(self, tmp_path: Path) -> None:
        """存在しない辞書ファイルを指定すると FileNotFoundError が発生すること。"""
        with pytest.raises(FileNotFoundError):
            TextPostProcessor.load_dictionary(tmp_path / "nonexistent.json")

    def test_yaml_import_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """YAMLパーサーがない場合は空の辞書が返る。"""
        d = tmp_path / "dict.yaml"
        d.write_text("a: b\n", encoding="utf-8")

        # モックで ImportError を発生させる
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("No module named yaml")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        processor = TextPostProcessor(dictionary_path=d)
        assert processor.dictionary == {}

    def test_unknown_extension_fallback_to_toml(self, tmp_path: Path) -> None:
        """不明な拡張子の場合は TOML として処理される。"""
        d = tmp_path / "dict.txt"
        d.write_text('[replacements]\n"未知" = "既知"\n', encoding="utf-8")
        processor = TextPostProcessor(dictionary_path=d)
        assert processor.dictionary.get("未知") == "既知"

    def test_not_dict_raises(self, tmp_path: Path) -> None:
        """辞書形式でない場合はValueErrorが発生する。"""
        d = tmp_path / "dict.json"
        d.write_text('["list", "not", "dict"]', encoding="utf-8")
        with pytest.raises(ValueError):
            TextPostProcessor.load_dictionary(d)


class TestTextPostProcessorApplyToText:
    """apply_to_text メソッドのテスト。"""

    def test_empty_string_unchanged(self) -> None:
        """空文字列はそのまま返ること。"""
        processor = TextPostProcessor()
        assert processor.apply_to_text("") == ""
        assert processor.normalize_text("") == ""

    def test_dictionary_replacement_applied(self) -> None:
        """辞書置換が正しく適用されること。"""
        # Arrange
        processor = TextPostProcessor()
        processor.dictionary = {"abc": "ABC"}
        processor._sorted_keys = ["abc"]
        # Act
        result = processor.apply_to_text("テスト abc です")
        # Assert
        assert "ABC" in result

    def test_longer_key_matched_first(self) -> None:
        """長いキーが優先的にマッチすること。"""
        processor = TextPostProcessor()
        processor.dictionary = {"ab": "SHORT", "abc": "LONG"}
        processor._sorted_keys = sorted(
            processor.dictionary.keys(), key=len, reverse=True
        )
        result = processor.apply_to_text("abc")
        assert result == "LONG"

    def test_lower_applied(self) -> None:
        """英字小文字化が適用されること。"""
        processor = TextPostProcessor(lower=True)
        result = processor.apply_to_text("Hello")
        assert result == "hello"


class TestTextPostProcessorApplyToSegments:
    """apply_to_segments メソッドのテスト。"""

    def test_empty_list_returns_empty(self) -> None:
        """空リストを渡すと空リストが返ること。"""
        processor = TextPostProcessor()
        assert processor.apply_to_segments([]) == []

    def test_timestamps_preserved(self) -> None:
        """タイムスタンプが変更されないこと。"""
        processor = TextPostProcessor()
        seg = _make_seg("テスト", start=1.5, end=3.0)
        result = processor.apply_to_segments([seg])
        assert result[0].start == 1.5
        assert result[0].end == 3.0

    def test_empty_text_segment_dropped(self) -> None:
        """後処理後にテキストが空になったセグメントは除外されること。"""
        processor = TextPostProcessor(remove_punct=True)
        seg = _make_seg("、。！")  # 句読点のみ → 除去後に空になる
        result = processor.apply_to_segments([seg])
        assert result == []
