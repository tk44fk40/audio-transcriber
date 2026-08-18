"""動画・音声ファイルのリマックスモジュール。

ノイズ除去された音声トラックを元の動画と結合し、
新しいメディアファイルを生成します。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

FFMPEG_TIMEOUT_SEC: float = 30.0
"""FFmpegリマックス処理の最大待機秒数。"""


class FileRemuxer:
    """メディアファイルのリマックス処理クラス。

    元の動画（映像）と新音声トラックを結合し、
    非同期にメディアファイルを生成します。
    """

    def __init__(self) -> None:
        """FileRemuxer を初期化します。"""
        pass

    async def remux(
        self,
        input_video_path: str | Path,
        denoised_audio_path: str | Path,
        output_video_path: str | Path,
    ) -> None:
        """映像ファイルに新音声トラックをマージ。

        Args:
            input_video_path (str | Path): 元の入力動画ファイルパス。
            denoised_audio_path (str | Path): 差し替える音声ファイルパス。
            output_video_path (str | Path): 出力する動画ファイルパス。

        Raises:
            FileNotFoundError: 入力ファイルが存在しない場合。
            RuntimeError: FFmpegプロセスがエラーで終了、
                またはタイムアウトした場合。
        """
        video_p = Path(input_video_path).resolve()
        audio_p = Path(denoised_audio_path).resolve()
        out_p = Path(output_video_path).resolve()

        if not video_p.exists():
            raise FileNotFoundError(f"Input video not found: {video_p}")
        if not audio_p.exists():
            raise FileNotFoundError(f"Denoised audio not found: {audio_p}")

        # 出力先ディレクトリを自動生成
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # FFmpeg コマンドの構築
        # -map 0:v? は、入力に映像トラックが存在する
        # 場合のみマッピングする指定。
        # 音声のみの入力ソースでも動作を保証します。
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(video_p),
            "-i",
            str(audio_p),
            "-map",
            "0:v?",
            "-map",
            "1:a",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(out_p),
        ]

        logger.info("Executing remux command: %s", " ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            # タイムアウト監視付きで wait
            await asyncio.wait_for(proc.wait(), timeout=FFMPEG_TIMEOUT_SEC)
        except TimeoutError:
            logger.error("FFmpeg remux process timed out. Sending SIGKILL.")
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            raise RuntimeError(
                f"FFmpeg remux timed out after {FFMPEG_TIMEOUT_SEC} seconds."
            ) from None

        # 終了コードの検証
        exit_code = proc.returncode
        if exit_code is None:
            exit_code = await proc.wait()

        if exit_code != 0:
            stderr_bytes = b""
            if proc.stderr:
                stderr_bytes = await proc.stderr.read()
            err_log = stderr_bytes.decode(errors="replace").strip()
            raise RuntimeError(
                f"FFmpeg remux process exited with code {exit_code}. stderr: {err_log}"
            )
