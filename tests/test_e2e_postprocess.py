"""TextPostProcessor (テキスト後処理) の E2E・単体テストモジュール。

Features 11-13 (TOML/YAML/JSON 辞書読み込み、最長一致単語置換、
NFKC/小文字化/句読点除去フラグ) に対する Tier 1 & Tier 2 要件駆動テスト。
"""

import json
from pathlib import Path

import pytest

from audio_transcriber.models import SubtitleSegment
from audio_transcriber.postprocess import TextPostProcessor


@pytest.mark.e2e
def test_post_processor_load_dictionary_toml(tmp_path: Path) -> None:
    """TOML 辞書ファイル ([replacements] テーブルおよびフラット形式) の読み込みテスト (Tier 1)。"""
    # Arrange
    toml_file = tmp_path / "dict.toml"
    toml_file.write_text(
        '[replacements]\n"大田使用量" = "クォータ使用量"\n"Sスイッチ" = "萌えスイッチ"\n',
        encoding="utf-8",
    )

    # Act
    processor = TextPostProcessor(dictionary_path=toml_file)

    # Assert
    assert processor.dictionary == {
        "大田使用量": "クォータ使用量",
        "Sスイッチ": "萌えスイッチ",
    }


@pytest.mark.e2e
def test_post_processor_load_dictionary_json_and_yaml(tmp_path: Path) -> None:
    """JSON および YAML 形式の置換辞書ファイルの読み込みテスト (Tier 1)。"""
    # Arrange
    json_file = tmp_path / "dict.json"
    json_file.write_text(
        json.dumps({"AI": "人工知能", "ML": "機械学習"}), encoding="utf-8"
    )

    yaml_file = tmp_path / "dict.yaml"
    yaml_file.write_text("GPU: グラフィックボード\nCPU: プロセッサ\n", encoding="utf-8")

    # Act
    proc_json = TextPostProcessor(dictionary_path=json_file)
    proc_yaml = TextPostProcessor(dictionary_path=yaml_file)

    # Assert
    assert proc_json.dictionary == {"AI": "人工知能", "ML": "機械学習"}
    assert proc_yaml.dictionary == {"GPU": "グラフィックボード", "CPU": "プロセッサ"}


@pytest.mark.e2e
def test_post_processor_longest_first_replacement(tmp_path: Path) -> None:
    """部分一致の競合を防ぐ最長一致順 (Longest-First) 単語置換のテスト (Tier 1)。"""
    # Arrange
    dict_file = tmp_path / "dict.json"
    # "AIツール" (len 5) と "AI" (len 2)
    dict_file.write_text(
        json.dumps({"AI": "人工知能", "AIツール": "AI支援ツール"}),
        encoding="utf-8",
    )
    processor = TextPostProcessor(dictionary_path=dict_file)

    # Act
    result = processor.apply_to_text("最新のAIツールを活用するAI")

    # Assert
    assert result == "最新のAI支援ツールを活用する人工知能"


@pytest.mark.e2e
def test_post_processor_normalization_flags_combined() -> None:
    """小文字化、句読点削除フラグの複合動作テスト (Tier 1)。"""
    # Arrange
    processor = TextPostProcessor(
        lower=True,  # 英字小文字化
        remove_punct=True,  # 句読点・空白除去
    )
    raw = "第I章: Hello WORLD! 一個の林檎。"

    # Act
    result = processor.apply_to_text(raw)

    # Assert
    # lowerで helloworld, 句読点除去
    assert "helloworld" in result
    assert "、" not in result and "。" not in result and " " not in result


@pytest.mark.e2e
def test_post_processor_apply_to_segments(tmp_path: Path) -> None:
    """SubtitleSegment リストに対する一括変換および空セグメント除外のテスト (Tier 1)。"""
    # Arrange
    dict_file = tmp_path / "dict.json"
    dict_file.write_text(json.dumps({"Whisper": "ウィスパー"}), encoding="utf-8")
    processor = TextPostProcessor(dictionary_path=dict_file)

    segments = [
        SubtitleSegment(start=1.0, end=3.0, text="Whisperの性能"),
        SubtitleSegment(start=3.5, end=5.0, text="音声認識モデル"),
    ]

    # Act
    output = processor.apply_to_segments(segments)

    # Assert
    assert len(output) == 2
    assert output[0].text == "ウィスパーの性能"
    assert output[1].text == "音声認識モデル"


@pytest.mark.e2e
def test_post_processor_dictionary_not_found(tmp_path: Path) -> None:
    """存在しない辞書ファイル指定時の FileNotFoundError 送出テスト (Tier 2)。"""
    # Arrange
    missing_file = tmp_path / "non_existent_dict.toml"

    # Act & Assert
    with pytest.raises(FileNotFoundError):
        TextPostProcessor.load_dictionary(missing_file)


@pytest.mark.e2e
def test_post_processor_dictionary_invalid_structure(tmp_path: Path) -> None:
    """dict 型以外の不正な辞書ファイル指定時の ValueError 送出テスト (Tier 2)。"""
    # Arrange
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text(json.dumps(["item1", "item2"]), encoding="utf-8")

    # Act & Assert
    with pytest.raises(ValueError):
        TextPostProcessor.load_dictionary(invalid_file)


@pytest.mark.e2e
def test_post_processor_whitespace_and_newline_handling() -> None:
    """改行・連続空白の正規化挙動テスト (Tier 2)。"""
    # Arrange
    proc_keep_punct = TextPostProcessor(remove_punct=False)
    proc_remove_punct = TextPostProcessor(remove_punct=True)

    raw_text = "こんにちは。\r\n\r\n世界! \t テスト"

    # Act
    res_keep = proc_keep_punct.apply_to_text(raw_text)
    res_clean = proc_remove_punct.apply_to_text(raw_text)

    # Assert
    # remove_punct=False の場合改行は空白1文字へ置換され strip される
    assert "\r\n" not in res_keep
    assert "こんにちは。 世界! \t テスト" == res_keep
    # remove_punct=True の場合句読点・空白がすべて除去される
    assert res_clean == "こんにちは世界テスト"


@pytest.mark.e2e
def test_post_processor_empty_and_null_inputs() -> None:
    """空文字列および空セグメントリストの安全な処理テスト (Tier 2)。"""
    # Arrange
    processor = TextPostProcessor()

    # Act
    text_res = processor.apply_to_text("")
    segs_res = processor.apply_to_segments([])

    # Assert
    assert text_res == ""
    assert segs_res == []
