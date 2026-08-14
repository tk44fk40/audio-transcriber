# 後処理機能移植・仕様定義書 (Specification Survey Report)

本ドキュメントは、`lumi_companion` から `audio-transcriber` への音声認識後処理機能（サニタイズ、数字正規化、置換辞書、タイミング調整、3形式字幕出力）の移植にあたり、要求事項、データモデル、アルゴリズム、入出力仕様、設定項目、品質基準を完全・非曖昧に定義した仕様書です。

---

## 1. 発見された機能一覧 (Features Discovered)

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Data Model | `SubtitleSegment` | タイムスタンプ（start/end）とテキストを保持するデータモデル | `start: float`, `end: float`, `text: str` | `SubtitleSegment` インスタンス, `to_dict() -> dict`, `from_dict() -> SubtitleSegment` | 型不整合時 TypeError / float変換エラー | `models/audio.py` |
| 2 | Sanitizer | 無音捏造フィルタ | `no_speech_prob` が閾値超のセグメントをハルシネーションとして除外 | Whisper Segment (`no_speech_prob`, `text`) | フィルタ済みセグメント | 無効セグメントは破棄（ログ記録） | `segment_sanitizer.py` |
| 3 | Sanitizer | 異常発話速度フィルタ | 物理的限界（デフォルト12.0文字/秒）を超える捏造セグメントを除外（4文字以下は保護） | Whisper Segment (`start`, `end`, `text`) | フィルタ済みセグメント | 許容速度超過時は破棄（ログ記録） | `segment_sanitizer.py` |
| 4 | Sanitizer | セグメント内リピート短縮 | 同一フレーズの2等分リピート（4文字以上）かつ圧縮率大/無音確率大の場合に半減短縮 | `text`, `compression_ratio`, `no_speech_prob` | 前半部分のみに短縮されたテキスト | 条件不合致時はそのまま保持 | `segment_sanitizer.py` |
| 5 | Sanitizer | セグメント間ループ重複除外 | 直前セグメントと同一または包含関係にあるテキストが無音時に連続した場合に除外 | `text`, `last_valid_text`, `no_speech_prob` | 重複除外されたセグメントリスト | ループ判定時は破棄（ログ記録） | `segment_sanitizer.py` |
| 6 | Sanitizer | 単語タイムスタンプ補正 | `words` が存在する場合、文頭単語の発声開始時刻を開始時刻に採用 | `segment.words` (`dict` または `Word` オブジェクト) | 発声開始位置に補正された `start` | 単語情報不正時は元の `start` を維持 | `segment_sanitizer.py` |
| 7 | Normalizer | 数字表現正規化 | 漢数字・丸数字・ローマ数字・半角数字を全角数字に統一正規化 | `text: str` | `str` (全角数字に統一) | 空文字時はそのまま返却 | `number_normalizer.py` |
| 8 | PostProcess | カスタム置換辞書 | TOML / YAML / JSON 辞書ファイルを読み込み、長順優先で単語置換 | 辞書ファイルパス (`Path`), `text: str` | 置換適用済み `str` | ファイル不在時 `FileNotFoundError`, 形式不正時 `ValueError` | `post_processor.py`, `ORIGINAL_REQUEST.md` |
| 9 | PostProcess | テキスト正規化オプション | NFKC半角化, 小文字化, 句読点・空白除去を個別フラグで制御 | `text: str`, 各種 boolean フラグ | 正規化済み `str` | 各フラグが独立して動作 | `post_processor.py` |
| 10 | Timing | 字幕余韻パディング | 発話終了後に指定秒数 (`end_padding`) の表示余韻を追加 | `end: float`, `end_padding: float` | 延長された `end: float` | - | `timing_adjuster.py` |
| 11 | Timing | 最小表示時間確保 | 短い発言でも最低表示秒数 (`min_duration`) を下限として保証 | `start: float`, `end: float`, `min_duration: float` | `max(padded_end, start + min_duration)` | - | `timing_adjuster.py` |
| 12 | Timing | 次セグメント重複防止 | 余韻延長が次発話の開始時刻に被らないよう `next_start - min_gap` でクリップ | `next_start: float`, `min_gap: float` | クリップされた `end: float` | 開始時刻以上の終了時刻を保証 | `timing_adjuster.py` |
| 13 | Timing | 総再生時間クリップ | `total_duration` が指定されている場合、メディア終端を超えないようクリップ | `total_duration: float` | クリップされた `end: float` | - | `timing_adjuster.py` |
| 14 | Exporter | DaVinci Resolve互換SRT出力 | ミリ秒カンマ区切り (`00:00:00,000`)・UTF-8・LF改行でSRT出力 | `list[SubtitleSegment]`, 出力パス | `.srt` ファイル | 親ディレクトリ自動生成 | `srt_exporter.py`, `AGENTS.md` |
| 15 | Exporter | WebVTT出力 | `WEBVTT` ヘッダー、ミリ秒ドット区切り (`00:00:00.000`) でVTT出力 | `list[SubtitleSegment]`, 出力パス | `.vtt` ファイル | 親ディレクトリ自動生成 | `srt_exporter.py` |
| 16 | Exporter | JSON出力 | セグメントリスト（`start`, `end`, `text`）を整形JSON形式で出力 | `list[SubtitleSegment]`, 出力パス | `.json` ファイル (`indent=2`) | 親ディレクトリ自動生成 | `srt_exporter.py` |
| 17 | Config/CLI | 後処理パラメータ統合 | パイプライン設定・CLI引数に各種後処理オプションを反映 | CLI引数 / `config.toml` | 設定データクラス (`AppConfig`) | 不正設定値バリデーションエラー | `config.py`, `cli.py` |
| 18 | Config | `MAX_SEGMENT_CHARS` 廃止 | 文節分割除外に伴い `MAX_SEGMENT_CHARS` 設定を完全削除 | - | 設定フィールドおよび解析コードから削除 | - | `ORIGINAL_REQUEST.md` |
| 19 | Pipeline | 3形式同時出力 & 結果格納 | 文字起こしパイプラインで SRT, VTT, JSON を同時生成 | 音声/動画ファイル | `PipelineResult` (`srt_file`, `vtt_file`, `json_file`) | 処理失敗時 RuntimeError / Exception | `pipeline.py` |

---

## 2. エッジケース定義 (Edge Cases)

| # | Feature | Input | Observed / Expected Behavior |
|---|---------|-------|-----------------------------|
| 1 | `SubtitleSegment` | `from_dict({})` (空辞書) | `start=0.0`, `end=0.0`, `text=""` のデフォルト値で初期化される |
| 2 | `SubtitleSegment` | `start > end` または負値 | 型は float として保持されるが、タイミング調整またはエクスポート時に `max(start, end)` / `assert seconds >= 0` 等で安全化 |
| 3 | `SegmentSanitizer` | 空白のみのセグメント (`"   "`) | `text.strip() == ""` により直ちに破棄され、結果リストに含まれない |
| 4 | `SegmentSanitizer` | 極小時間（0.1s）で2文字（「はい」） | 4文字以下の短文は物理速度チェック（12文字/秒）の例外として安全に保持される |
| 5 | `SegmentSanitizer` | 0.3秒で10文字のハルシネーション（33.3文字/秒） | `chars_per_sec > 12.0` かつ `len > 4` のため自動ドロップされる |
| 6 | `SegmentSanitizer` | セグメント内繰り返し（「あいうえおあいうえお」、comp_ratio=2.5） | 前半「あいうえお」に短縮される |
| 7 | `SegmentSanitizer` | 直前と同一セグメントの繰り返し（無音確率 > 0.1） | 直前テキストと完全一致または包含関係にあるためループハルシネーションとして自動ドロップ |
| 8 | `NumberNormalizer` | 「十一」「第I章」「①番」「１２３」 | 「１１」「第１章」「１番」「１２３」に統一変換される |
| 9 | `NumberNormalizer` | 「VIII」と「V」が混在する文字列 | 長順変換により「VIII」が「8」に置換され、「V」の誤置換による「5III」破損を防止 |
| 10 | `TextPostProcessor` | キーワードが重複・部分一致する辞書 (`{"ABC": "123", "AB": "99"}`) | キー長の長い順（`ABC` ➔ `AB`）で置換され、「123」と「99」に正しく置換される |
| 11 | `TextPostProcessor` | 辞書ファイル不在 / 辞書がリスト形式 (`[1, 2]`) | `FileNotFoundError` / `ValueError("辞書ファイルの形式が正しくありません")` を送出 |
| 12 | `TextPostProcessor` | TOML / YAML / JSON 各拡張子の辞書ファイル | 拡張子に応じたパーサー（`tomllib`, `yaml.safe_load`, `json.loads`）で正常に辞書として読み込まれる |
| 13 | `SubtitleTimingAdjuster` | 空のセグメントリスト `[]` | 空リスト `[]` が返却される |
| 14 | `SubtitleTimingAdjuster` | 次セグメントとの隙間が `min_gap` より小さい極小ギャップ（0.02s） | 開始時刻を追い越さず `final_end = min(target_end, next_start)` として矛盾なくクリップ |
| 15 | `SubtitleTimingAdjuster` | `total_duration` を超える余韻延長 | `target_end` が `total_duration` でクリップされる |
| 16 | `SubtitleExporter` | タイムスタンプ 3661.5秒 | SRT: `01:01:01,500`, WebVTT: `01:01:01.500` |
| 17 | `SubtitleExporter` | `save_subtitles` で未対応拡張子 (`.txt`) または未対応 fmt (`invalid`) | `ValueError` を送出 |

---

## 3. 詳細仕様 (Detailed Specifications)

### 3.1. データモデル仕様 (`SubtitleSegment` & `WordTiming`)

#### 配置モジュール
`src/audio_transcriber/models.py`

#### クラス定義: `SubtitleSegment`
```python
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SubtitleSegment:
    """タイムスタンプ付き発言字幕データモデル。

    Attributes:
        start: 発声開始時刻（秒単位、小数点以下3桁に丸め）。
        end: 発声終了時刻（秒単位、小数点以下3桁に丸め）。
        text: サニタイズおよび正規化済みの字幕テキスト。
    """

    start: float
    end: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        """データモデルを辞書形式へ変換します。

        Returns:
            dict[str, Any]: {"start": float, "end": float, "text": str}
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubtitleSegment":
        """辞書データからインスタンスを構築します。

        Args:
            data: {"start": float, "end": float, "text": str} を含む辞書。

        Returns:
            SubtitleSegment: 構築されたインスタンス。
        """
        return cls(
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            text=str(data.get("text", "")),
        )
```

---

### 3.2. テキストサニタイズ仕様 (`SegmentSanitizer`)

#### 配置モジュール
`src/audio_transcriber/sanitizer.py`

#### クラス定義
```python
class SegmentSanitizer:
    def __init__(
        self,
        no_speech_threshold: float = 0.6,
        max_chars_per_second: float = 12.0,
    ) -> None: ...
```

#### 判定・補正アルゴリズム
1. **空文字列判定**:
   - `text = getattr(segment, "text", "").strip()`
   - 空文字列の場合は即座にスキップ。
2. **セグメント内リピート判定**:
   - `len(text) >= 4` かつ `text[:len(text)//2] == text[len(text)//2:]`
   - かつ `no_speech_prob > 0.1` または `compression_ratio > 2.0` の場合、テキストを前半（`text[:len(text)//2]`）に短縮。
3. **単語レベルタイムスタンプ開始位置補正**:
   - `words = getattr(segment, "words", None) or []`
   - `words[0]` に `start` 属性（または辞書キー）が存在する場合、`start` をその時刻に更新。
4. **セグメント間ループ重複除外**:
   - 直前の有効テキスト `last_valid_text` が存在し、かつ `no_speech_prob > 0.1` の場合：
   - `text == last_valid_text` または `text in last_valid_text` ならば当該セグメントを破棄。
5. **無音捏造判定**:
   - `no_speech_prob > self.no_speech_threshold`（デフォルト0.6）の場合、セグメントを破棄。
6. **物理的発話速度判定**:
   - `duration = max(end - start, 0.1)`
   - `chars_per_sec = len(text) / duration`
   - `chars_per_sec > self.max_chars_per_second`（デフォルト12.0）かつ `len(text) > 4` の場合、セグメントを破棄。
   - ※4文字以下（「はい」「ええ」等）は短発話保護のためドロップ対象外。
7. **インスタンス生成 & 履歴更新**:
   - `SubtitleSegment(start=round(start, 3), end=round(end, 3), text=text)` を生成し結果に追加。
   - `last_valid_text = text` を更新。

---

### 3.3. 数字正規化および置換辞書仕様 (`NumberNormalizer` & `TextPostProcessor`)

#### 配置モジュール
- `src/audio_transcriber/normalizer.py` (`NumberNormalizer`)
- `src/audio_transcriber/post_processor.py` (`TextPostProcessor`)

#### 3.3.1 `NumberNormalizer` 変換順序
1. **全角数字 ➔ 半角数字**: `str.maketrans("０１２３４５６７８９", "0123456789")`
2. **丸数字 ➔ 半角数字**: `①` ➔ `1`, `②` ➔ `2`, ..., `⑳` ➔ `20`
3. **ローマ数字 ➔ 半角数字（長順優先）**:
   - `VIII` ➔ `8`, `VII` ➔ `7`, `III` ➔ `3`, `VI` ➔ `6`, `IV` ➔ `4`, `IX` ➔ `9`, `II` ➔ `2`, `V` ➔ `5`, `X` ➔ `10`, `I` ➔ `1`
   - `Ⅷ` ➔ `8`, `Ⅶ` ➔ `7`, `Ⅲ` ➔ `3`, `Ⅵ` ➔ `6`, `Ⅳ` ➔ `4`, `Ⅸ` ➔ `9`, `Ⅱ` ➔ `2`, `Ⅴ` ➔ `5`, `Ⅹ` ➔ `10`, `Ⅰ` ➔ `1`
4. **漢数字 ➔ 半角数字**:
   - `十` ➔ `10`, `九` ➔ `9`, `八` ➔ `8`, `七` ➔ `7`, `六` ➔ `6`, `五` ➔ `5`, `四` ➔ `4`, `三` ➔ `3`, `二` ➔ `2`, `一` ➔ `1`, `〇` ➔ `0`, `ゼロ` ➔ `0`
5. **十代の補正**: `re.sub(r"10([1-9])", r"1\1", text)` （例: 「十1」➔「11」）
6. **全角数字へ統一変換**: `str.maketrans("0123456789", "０１２３４５６７８９")`

#### 3.3.2 `TextPostProcessor` 仕様
- **サポート形式**: TOML (`.toml`), YAML (`.yaml`, `.yml`), JSON (`.json`)
- **読み込み処理 (`load_dictionary`)**:
  - ファイル拡張子を判別し、`.toml` は `tomllib.loads`、`.yaml`/`.yml` は `yaml.safe_load`、`.json` は `json.loads` でパース。
  - パース結果が `dict` でない場合は `ValueError` を送出。
  - 辞書キーを文字数降順（`sorted(keys, key=len, reverse=True)`）で保持。
- **適用順序 (`apply_to_text`)**:
  1. 単語置換辞書の適用（長順優先）
  2. `normalize_nums == True` の場合: `NumberNormalizer.normalize(text)`
  3. `to_hankaku == True` の場合: `unicodedata.normalize("NFKC", text)`
  4. 句読点制御:
     - `remove_punct == True`: `re.sub(r"[、。！？!?\s\r\n]", "", text)`
     - `remove_punct == False`: `re.sub(r"[\r\n]+", " ", text).strip()`
  5. `lower == True` の場合: `text.lower()`

---

### 3.4. 字幕タイミング補正仕様 (`SubtitleTimingAdjuster`)

#### 配置モジュール
`src/audio_transcriber/timing.py`

#### プロトコル & クラス定義
```python
from typing import Protocol, runtime_checkable
from audio_transcriber.models import SubtitleSegment


@runtime_checkable
class TimingAdjusterProtocol(Protocol):
    def adjust_segments(
        self,
        segments: list[SubtitleSegment],
        total_duration: float | None = None,
    ) -> list[SubtitleSegment]: ...


class SubtitleTimingAdjuster:
    def __init__(
        self,
        end_padding: float = 1.0,
        min_duration: float = 1.5,
        min_gap: float = 0.05,
    ) -> None:
        self.end_padding = end_padding
        self.min_duration = min_duration
        self.min_gap = min_gap
```

#### 補正アルゴリズム（セグメント $i$ に対する処理）
1. **余韻パディング付与**: $padded\_end = seg.end + end\_padding$
2. **最小表示時間確保**: $min\_required\_end = seg.start + min\_duration$
3. **目標終了時刻**: $target\_end = \max(padded\_end, min\_required\_end)$
4. **次セグメントとの重複防止クリップ** ($i+1 < N$ の場合):
   - $max\_allowed\_end = next\_start - min\_gap$
   - $max\_allowed\_end > seg.start$ の場合: $target\_end = \min(target\_end, max\_allowed\_end)$
   - それ以外（隙間が極小の場合）: $target\_end = \min(target\_end, next\_start)$
5. **メディア総再生時間クリップ** ($total\_duration > 0$ の場合):
   - $target\_end = \min(target\_end, total\_duration)$
6. **最終下限ガード**: $final\_end = \max(seg.start, target\_end)$
7. **丸めとインスタンス生成**: `SubtitleSegment(start=round(seg.start, 3), end=round(final_end, 3), text=seg.text)`

---

### 3.5. 字幕エクスポート仕様 (`SubtitleExporter`)

#### 配置モジュール
`src/audio_transcriber/exporter.py`

#### フォーマット要件

| 形式 | 拡張子 | ヘッダー | タイムスタンプ書式 | 改行・エンコーディング | 特記事項 |
|---|---|---|---|---|---|
| SRT | `.srt` | なし | `HH:MM:SS,mmm` (カンマ区切り) | LF (`\n`), UTF-8 | DaVinci Resolve 完全互換 |
| WebVTT | `.vtt` | `WEBVTT\n` | `HH:MM:SS.mmm` (ドット区切り) | LF (`\n`), UTF-8 | Web動画・HTML5標準 |
| JSON | `.json` | なし | 数値 (秒単位 float) | LF (`\n`), UTF-8 (`indent=2`) | プログラム連携・分析用 |

#### メソッド構成
- `format_timestamp(seconds: float) -> str`: SRT用タイムスタンプ (`00:00:00,000`)
- `format_vtt_timestamp(seconds: float) -> str`: WebVTT用タイムスタンプ (`00:00:00.000`)
- `save_srt(segments: Sequence[SubtitleSegment], output_path: Path) -> None`
- `save_vtt(segments: Sequence[SubtitleSegment], output_path: Path) -> None`
- `save_json(segments: Sequence[SubtitleSegment], output_path: Path) -> None`
- `save_subtitles(segments: Sequence[SubtitleSegment], output_path: Path, fmt: str | None = None) -> None`: 拡張子自動判定または明示フォーマット指定保存

---

### 3.6. 設定およびCLIパラメータ変更仕様

#### 3.6.1 廃止項目
- `MAX_SEGMENT_CHARS` / `max_segment_chars`:
  - `config.toml`, `config.example.toml` から削除。
  - `PostProcessConfig` および `parse_config_dict` から完全削除。

#### 3.6.2 設定データクラス構造 (`config.py`)
```python
@dataclass
class PostProcessConfig:
    replace_terms: bool = True
    to_hankaku: bool = False
    normalize_nums: bool = True
    lower: bool = False
    remove_punct: bool = False


@dataclass
class SubtitleConfig:
    end_padding: float = 1.0
    min_duration: float = 1.5
    min_gap: float = 0.05


@dataclass
class TranscribeConfig:
    language: str = "ja"
    beam_size: int = 5
    condition_on_previous_text: bool = True
    no_speech_threshold: float = 0.6
    initial_prompt: str | None = None
    vad: VadConfig = field(default_factory=VadConfig)
    word_timestamps: bool = True


@dataclass
class AppConfig:
    output_dir: Path = field(default_factory=lambda: Path("./output"))
    default_video_path: Path | None = None
    debug_output_dir: Path | None = None
    custom_dictionary_path: Path | None = None
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    media: MediaConfig = field(default_factory=MediaConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    transcribe: TranscribeConfig = field(default_factory=TranscribeConfig)
    post_process: PostProcessConfig = field(default_factory=PostProcessConfig)
    subtitle: SubtitleConfig = field(default_factory=SubtitleConfig)
```

#### 3.6.3 `config.example.toml` の `[post_process]` & `[subtitle]` 記述例
```toml
# ==============================================================================
# テキスト後処理設定
# ==============================================================================
[post_process]
# カスタム辞書による用語置換を行うか
POST_PROCESS_REPLACE_TERMS = true

# 全角英数字を半角に統一するか (NFKC)
POST_PROCESS_TO_HANKAKU = false

# 漢数字等を正規化するか
POST_PROCESS_NORMALIZE_NUMS = true

# 英字を小文字化するか
POST_PROCESS_LOWER = false

# 句読点等の記号を削除するか
POST_PROCESS_REMOVE_PUNCT = false

# ==============================================================================
# 字幕表示タイミング調整設定
# ==============================================================================
[subtitle]
# 発話終了後の余韻表示秒数
SUBTITLE_END_PADDING = 1.0

# 字幕の最小表示秒数
SUBTITLE_MIN_DURATION = 1.5

# 連続する字幕セグメント間の最小隙間秒数
SUBTITLE_MIN_GAP = 0.05
```

#### 3.6.4 CLI (`cli.py`) の追加・更新オプション
- `--dict-path` (`-D`, `Path | None`): 置換辞書ファイルパス
- `--end-padding` (`float | None`): 字幕余韻秒数
- `--min-duration` (`float | None`): 最小表示秒数
- `--min-gap` (`float | None`): 最小ギャップ秒数
- `--to-hankaku / --no-to-hankaku` (`bool | None`)
- `--normalize-nums / --no-normalize-nums` (`bool | None`)
- `--lower / --no-lower` (`bool | None`)
- `--remove-punct / --no-remove-punct` (`bool | None`)
- CLI 実行結果サマリー表に `SRT Subtitle`, `WebVTT Subtitle`, `JSON Transcript` の各行を出力。

---

### 3.7. パイプライン統合および `PipelineResult` 仕様

#### 3.7.1 `PipelineResult`
```python
@dataclass
class PipelineResult:
    """Result of audio/video processing pipeline."""

    input_file: Path
    denoised_audio: Path | None
    srt_file: Path | None
    vtt_file: Path | None
    json_file: Path | None
    transcript_text: str | None
    remuxed_video: Path | None = None
```

#### 3.7.2 `run_pipeline` 実行フロー
1. 入力メディアの検証および音声トラック抽出（動画入力時）。
2. 音声ノイズ除去（`denoise=True` の場合、DeepFilterNet を適用して `{stem}_clean.wav` を出力）。
3. 音声認識 & 後処理（`transcribe=True` の場合）：
   - `WhisperModel.transcribe(..., word_timestamps=True)` で認識を実行。
   - `SegmentSanitizer.sanitize_segments` で無音捏造・異常速度・重複を除外。
   - `TextPostProcessor.apply_to_segments` で置換辞書およびテキスト正規化を適用。
   - `SubtitleTimingAdjuster.adjust_segments` で余韻・最小表示・重複防止を適用。
   - `SubtitleExporter` を用いて以下の3形式ファイルを一括出力：
     - `{stem}.srt`
     - `{stem}.vtt`
     - `{stem}.json`
   - 全セグメントのテキストを結合し `transcript_text` を生成。
4. 動画再結合（`is_video and remux` の場合、クリーン音声で置換した `{stem}_clean{ext}` を出力）。
5. `PipelineResult` インスタンスを構築して返却。

---

### 3.8. 品質基準・検証規範

1. **モジュール行数制限**:
   - 1ファイル最大300行以下（目標200行以下）を厳守。
   - 責務ごとにモジュールを明確に分割：
     - `models.py` (~50行)
     - `sanitizer.py` (~150行)
     - `normalizer.py` (~100行)
     - `post_processor.py` (~170行)
     - `timing.py` (~130行)
     - `exporter.py` (~150行)
     - `transcribe.py` (~100行)
     - `pipeline.py` (~140行)
     - `config.py` (~230行)
     - `cli.py` (~230行)
2. **Docstring & コーディング規約**:
   - Google スタイルの日本語 Docstring を全公開モジュール/クラス/関数に記述（`Args`, `Returns`, `Raises` 完備）。
   - Python 3.11+ 厳格な型注釈。
3. **静的解析・リント検証**:
   - `uv run basedpyright` で型エラー 0 件。
   - `uv run ruff check .` および `uv run ruff format --check .` で違反 0 件。
4. **テスト規範**:
   - 各モジュールに対応する `tests/test_*.py` を配置。
   - AAA (Arrange-Act-Assert) パターンを徹底。
   - 外部モデル・CLI は `unittest.mock` を用いて決定論的にテスト。
   - `uv run pytest --cov=audio_transcriber --cov-report=term-missing` で全テストがパスすること。
