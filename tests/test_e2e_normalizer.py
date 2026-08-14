"""NumberNormalizer (数字正規化) の E2E・単体テストモジュール。

Feature 10 (6段階数字正規化: 漢数字・ローマ数字・丸数字・半角/全角変換)
に対する Tier 1 & Tier 2 要件駆動テスト。
"""

import pytest

from audio_transcriber.number_normalizer import NumberNormalizer


@pytest.mark.e2e
def test_normalizer_halfwidth_digits_to_fullwidth() -> None:
    """半角アラビア数字から全角数字への変換テスト (Tier 1)。"""
    # Arrange
    raw_text = "2026年の売上は12345円です。"

    # Act
    result = NumberNormalizer.normalize(raw_text)

    # Assert
    assert result == "２０２６年の売上は１２３４５円です。"


@pytest.mark.e2e
def test_normalizer_circled_digits_conversion() -> None:
    """丸数字 (①〜⑳) から全角数字への変換テスト (Tier 1)。"""
    # Arrange
    raw_text = "①番、⑤番、⑩番、⑳番の選手"

    # Act
    result = NumberNormalizer.normalize(raw_text)

    # Assert
    assert result == "１番、５番、１０番、２０番の選手"


@pytest.mark.e2e
def test_normalizer_roman_numerals_longest_first() -> None:
    """ASCII ローマ数字 (最長一致: VIII -> 8, IV -> 4 等) の変換テスト (Tier 1)。"""
    # Arrange
    raw_text = "第I章、第IV節、第VIII幕、第X巻"

    # Act
    result = NumberNormalizer.normalize(raw_text)

    # Assert
    assert result == "第１章、第４節、第８幕、第１０巻"


@pytest.mark.e2e
def test_normalizer_kanji_simple_and_zero() -> None:
    """漢数字 (一〜九、〇、ゼロ) の変換テスト (Tier 1)。"""
    # Arrange
    raw_text = "一、二、三、四、五、六、七、八、九、〇、ゼロ"

    # Act
    result = NumberNormalizer.normalize(raw_text)

    # Assert
    assert result == "１、２、３、４、５、６、７、８、９、０、０"


@pytest.mark.e2e
def test_normalizer_kanji_teens_correction() -> None:
    """十番台の漢数字 (十、十一〜十九) の正規化テスト (Tier 1)。"""
    # Arrange
    raw_text = "十個、十一回、十五日、十九歳"

    # Act
    result = NumberNormalizer.normalize(raw_text)

    # Assert
    assert result == "１０個、１１回、１５日、１９歳"


@pytest.mark.e2e
def test_normalizer_unicode_roman_numerals() -> None:
    """Unicode 専用ローマ数字記号 (Ⅰ〜Ⅹ) の変換テスト (Tier 2)。"""
    # Arrange
    raw_text = "Ⅰ Ⅱ Ⅲ Ⅳ Ⅴ Ⅵ Ⅶ Ⅷ Ⅸ Ⅹ"

    # Act
    result = NumberNormalizer.normalize(raw_text)

    # Assert
    assert result == "１ ２ ３ ４ ５ ６ ７ ８ ９ １０"


@pytest.mark.e2e
def test_normalizer_complex_mixed_text() -> None:
    """漢数字、ローマ数字、丸数字、アラビア数字が混在する複合文の変換テスト (Tier 2)。"""
    # Arrange
    raw_text = "第III期計画: ①番ブースで十五名が100点満点を獲得した。"

    # Act
    result = NumberNormalizer.normalize(raw_text)

    # Assert
    assert result == "第３期計画: １番ブースで１５名が１００点満点を獲得した。"


@pytest.mark.e2e
def test_normalizer_no_numbers_and_empty_string() -> None:
    """数字を含まない文字列および空文字列の不変テスト (Tier 2)。"""
    # Arrange
    empty = ""
    plain = "本日は晴天なり。日本語のみのテキストです。"

    # Act
    res_empty = NumberNormalizer.normalize(empty)
    res_plain = NumberNormalizer.normalize(plain)

    # Assert
    assert res_empty == ""
    assert res_plain == plain


@pytest.mark.e2e
def test_normalizer_roman_substring_collision_safety() -> None:
    """ローマ数字の短縮形衝突 (V が VIII の一部を誤変換しない) の検証テスト (Tier 2)。"""
    # Arrange
    raw_text = "VIII と V と III"

    # Act
    result = NumberNormalizer.normalize(raw_text)

    # Assert
    assert result == "８ と ５ と ３"


@pytest.mark.e2e
def test_normalizer_unsupported_special_circled_numbers() -> None:
    """⑳ を超える丸数字 (㉑ 等) が正規化マップ外として安全に保持されるテスト (Tier 2)。"""
    # Arrange
    raw_text = "㉑番目のアイテム"

    # Act
    result = NumberNormalizer.normalize(raw_text)

    # Assert
    assert "㉑" in result
