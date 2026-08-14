"""NumberNormalizer の単体テスト。"""

from audio_transcriber.number_normalizer import NumberNormalizer


class TestNumberNormalizerFullWidth:
    """全角数字の正規化テスト。"""

    def test_fullwidth_digits_unchanged(self) -> None:
        """全角数字は全角数字のまま出力されること（変換後も全角に戻る）。"""
        text = "０１２３４５６７８９"
        result = NumberNormalizer.normalize(text)
        assert result == "０１２３４５６７８９"

    def test_halfwidth_digits_to_fullwidth(self) -> None:
        """半角数字が全角数字に変換されること。"""
        result = NumberNormalizer.normalize("2026年")
        assert result == "２０２６年"

    def test_empty_string_unchanged(self) -> None:
        """空文字列は変換されずそのまま返ること。"""
        assert NumberNormalizer.normalize("") == ""

    def test_no_numbers_unchanged(self) -> None:
        """数字を含まないテキストはそのまま返ること。"""
        text = "こんにちは"
        assert NumberNormalizer.normalize(text) == "こんにちは"


class TestNumberNormalizerMaru:
    """丸数字の正規化テスト。"""

    def test_maru_single_digit(self) -> None:
        """①〜⑨が全角数字に変換されること。"""
        assert NumberNormalizer.normalize("①") == "１"
        assert NumberNormalizer.normalize("⑨") == "９"

    def test_maru_double_digit(self) -> None:
        """⑩〜⑳が全角数字に変換されること。"""
        assert NumberNormalizer.normalize("⑩") == "１０"
        assert NumberNormalizer.normalize("⑳") == "２０"


class TestNumberNormalizerRoman:
    """ローマ数字の正規化テスト。"""

    def test_ascii_roman(self) -> None:
        """ASCII ローマ数字が全角数字に変換されること。"""
        assert NumberNormalizer.normalize("VIII") == "８"
        assert NumberNormalizer.normalize("IV") == "４"
        assert NumberNormalizer.normalize("X") == "１０"

    def test_unicode_roman(self) -> None:
        """Unicode ローマ数字が全角数字に変換されること。"""
        assert NumberNormalizer.normalize("Ⅳ") == "４"

    def test_roman_longer_matched_first(self) -> None:
        """長いローマ数字が先に変換されること（III が I×3 に誤変換されない）。"""
        result = NumberNormalizer.normalize("III")
        assert result == "３"


class TestNumberNormalizerKanji:
    """漢数字の正規化テスト。"""

    def test_single_kanji_digit(self) -> None:
        """一〜九が全角数字に変換されること。"""
        assert NumberNormalizer.normalize("一") == "１"
        assert NumberNormalizer.normalize("九") == "９"

    def test_zero_variants(self) -> None:
        """〇とゼロが全角０に変換されること。"""
        assert NumberNormalizer.normalize("〇") == "０"
        assert NumberNormalizer.normalize("ゼロ") == "０"

    def test_juu(self) -> None:
        """十が全角１０に変換されること。"""
        assert NumberNormalizer.normalize("十") == "１０"

    def test_mixed_text(self) -> None:
        """数字混じりのテキストが正しく変換されること。"""
        result = NumberNormalizer.normalize("第三回")
        assert "３" in result
