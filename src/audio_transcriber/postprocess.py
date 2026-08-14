"""テキスト後処理・正規化パイプラインモジュール。

置換辞書 (TOML / JSON / YAML) による単語置換と、Unicode (NFKC) 正規化、
数字正規化、英小文字化、句読点クリーン処理を一括で行うクラスを提供します。
"""

import json
import logging
import re
import tomllib
import unicodedata
from pathlib import Path
from typing import Any

from audio_transcriber.models import SubtitleSegment
from audio_transcriber.number_normalizer import NumberNormalizer

logger = logging.getLogger(__name__)


class TextPostProcessor:
    """テキストおよび字幕セグメントに対する後処理・正規化クラス。"""

    def __init__(
        self,
        dictionary_path: Path | None = None,
        to_hankaku: bool = False,
        normalize_nums: bool = True,
        lower: bool = False,
        remove_punct: bool = False,
    ) -> None:
        """TextPostProcessor を初期化します。

        Args:
            dictionary_path (Path | None): 置換辞書ファイルのパス (.toml / .yaml / .json)。
            to_hankaku (bool): 全角英数・全角記号を半角に変換するか (デフォルト: False)。
            normalize_nums (bool): 数字正規化を行うか (デフォルト: True)。
            lower (bool): 英小文字化を行うか (デフォルト: False)。
            remove_punct (bool): 句読点・記号・余白の除去を行うか (デフォルト: False)。
        """
        self.to_hankaku = to_hankaku
        self.normalize_nums = normalize_nums
        self.lower = lower
        self.remove_punct = remove_punct

        self.dictionary: dict[str, str] = {}
        if dictionary_path and dictionary_path.exists():
            self.dictionary = self.load_dictionary(dictionary_path)

        # 競合防止のため文字数の長い順にソートしたキーリストを保持
        self._sorted_keys: list[str] = sorted(
            self.dictionary.keys(), key=len, reverse=True
        )

    @staticmethod
    def load_dictionary(file_path: Path) -> dict[str, str]:
        """置換辞書ファイル (.toml / .json / .yaml / .yml) を読み込みます。

        Args:
            file_path (Path): 辞書ファイルのパス。

        Returns:
            dict[str, str]: 置換マップ (置換前文字列 → 置換後文字列)。

        Raises:
            FileNotFoundError: 指定されたパスにファイルが存在しない場合。
            ValueError: ファイル内容が文字列ペアの辞書形式でない場合。
        """
        if not file_path.exists():
            raise FileNotFoundError(f"辞書ファイルが存在しません: {file_path}")

        suffix = file_path.suffix.lower()
        content = file_path.read_text(encoding="utf-8")
        data: Any = None

        if suffix == ".toml":
            raw = tomllib.loads(content)
            # [replacements] テーブルがあればそれを使用、なければルートを使用
            data = raw.get("replacements", raw)
        elif suffix == ".json":
            data = json.loads(content)
        elif suffix in (".yaml", ".yml"):
            try:
                import yaml  # type: ignore[import-untyped]

                data = yaml.safe_load(content)
            except ImportError:
                logger.warning(
                    "yaml パッケージが未インストールのため YAML 辞書を読み込めません: %s",
                    file_path,
                )
                return {}
        else:
            # 拡張子不明の場合は TOML として試行
            raw = tomllib.loads(content)
            data = raw.get("replacements", raw)

        if not isinstance(data, dict):
            raise ValueError(
                f"辞書ファイルの形式が正しくありません (dict 形式が必要): {file_path}"
            )

        return {str(k): str(v) for k, v in data.items()}

    def normalize_text(self, text: str) -> str:
        """設定フラグに従ってテキストの正規化処理を適用します。

        Args:
            text (str): 対象文字列。

        Returns:
            str: 正規化済みの文字列。
        """
        if not text:
            return text

        result = text

        if self.normalize_nums:
            result = NumberNormalizer.normalize(result)

        if self.to_hankaku:
            result = unicodedata.normalize("NFKC", result)

        if self.remove_punct:
            result = re.sub(r"[、。！？!?\s\r\n]", "", result)
        else:
            result = re.sub(r"[\r\n]+", " ", result).strip()

        if self.lower:
            result = result.lower()

        return result

    def apply_to_text(self, text: str) -> str:
        """単一の文字列に対して辞書置換および正規化を適用します。

        Args:
            text (str): 処理対象の文字列。

        Returns:
            str: 後処理・正規化適用後の文字列。
        """
        if not text:
            return text

        result = text

        # 1. 単語置換辞書の適用 (1パス: 長いキーを優先してマッチ、置換後文字列への再適用を防ぐ)
        if self.dictionary and self._sorted_keys:
            pattern = re.compile("|".join(re.escape(k) for k in self._sorted_keys))
            result = pattern.sub(lambda m: self.dictionary[m.group(0)], result)

        # 2. テキスト正規化の適用
        result = self.normalize_text(result)

        return result

    def apply_to_segments(
        self,
        segments: list[SubtitleSegment],
    ) -> list[SubtitleSegment]:
        """字幕セグメントリストの各テキストに後処理・正規化を適用します。

        Args:
            segments (list[SubtitleSegment]): 元の字幕セグメントリスト。

        Returns:
            list[SubtitleSegment]: 後処理・正規化適用後の字幕セグメントリスト。
        """
        if not segments:
            return segments

        result: list[SubtitleSegment] = []
        for seg in segments:
            new_text = self.apply_to_text(seg.text)
            if new_text:
                result.append(
                    SubtitleSegment(start=seg.start, end=seg.end, text=new_text)
                )

        return result
