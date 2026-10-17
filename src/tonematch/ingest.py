"""Download audio (YouTube or any yt-dlp source) or import a local file -> 44.1 kHz stereo WAV."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

from .config import SR, TRACKS_DIR

log = logging.getLogger(__name__)


def _ffmpeg() -> str:
    """Locate ffmpeg and make sure it is on PATH (audio-separator calls it by name).

    A fresh winget install only reaches PATH in newly opened terminals, so also look in winget's folders.
    """
    import os

    exe = shutil.which("ffmpeg")
    if not exe:
        roots = [Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "Microsoft/WinGet",
                 Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "WinGet"]
        exe = next((str(p) for r in roots for p in r.glob("**/ffmpeg.exe")), None)
        if not exe:
            raise RuntimeError("ffmpeg not found (winget install Gyan.FFmpeg)")
        os.environ["PATH"] = str(Path(exe).parent) + os.pathsep + os.environ.get("PATH", "")
    return exe


def track_dir(track_id: str) -> Path:
    d = TRACKS_DIR / track_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _to_wav(src: Path, dst: Path) -> None:
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", str(src), "-ac", "2", "-ar", str(SR),
                    "-c:a", "pcm_f32le", str(dst)], check=True)


YT_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})")
BROWSERS = ("firefox", "chrome", "edge", "brave")


def _ydl(opts: dict, action):
    """Run a yt-dlp action; on YouTube's bot check retry with cookies from installed browsers."""
    import os

    import yt_dlp

    attempts = [dict(opts)]
    if os.environ.get("TONEMATCH_COOKIES"):
        attempts.insert(0, {**opts, "cookiefile": os.environ["TONEMATCH_COOKIES"]})
    attempts += [{**opts, "cookiesfrombrowser": (b,)} for b in BROWSERS]
    last: Exception | None = None
    for i, o in enumerate(attempts):
        try:
            with yt_dlp.YoutubeDL(o) as y:
                return action(y)
        except Exception as e:  # yt_dlp.DownloadError, cookie DB locked/missing, ...
            last = e
            msg = str(e)
            if i == 0 and "confirm you" not in msg and "cookies" not in msg.lower():
                raise
            log.debug("yt-dlp attempt %d failed: %s", i, msg[:200])
    raise RuntimeError(
        "YouTube is asking to confirm you're not a bot. Log in to YouTube in Firefox (or close Chrome/Edge "
        "so their cookie DB is readable) and retry, or export cookies.txt and set TONEMATCH_COOKIES=<path>. "
        f"Last error: {str(last)[:300]}")


def ingest(source: str) -> tuple[str, Path, dict]:
    """Return (track_id, wav_path, meta). Cached per track id."""
    p = Path(source)
    if p.exists():
        tid = "file_" + hashlib.sha1(str(p.resolve()).encode()).hexdigest()[:10]
        d = track_dir(tid)
        wav = d / "source.wav"
        if not wav.exists():
            _to_wav(p, wav)
        meta = {"title": p.stem, "artist": "", "source": str(p)}
        (d / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
        return tid, wav, meta

    m = YT_ID.search(source)
    if m:  # already processed -> fully offline
        d = TRACKS_DIR / m.group(1)
        if (d / "source.wav").exists() and (d / "meta.json").exists():
            return m.group(1), d / "source.wav", json.loads((d / "meta.json").read_text(encoding="utf-8"))

    info = _ydl({"quiet": True, "noplaylist": True, "skip_download": True},
                lambda y: y.extract_info(source, download=False))
    if "entries" in info:  # ytsearch: / playlist -> first entry
        info = info["entries"][0]
    tid = re.sub(r"[^A-Za-z0-9_-]", "_", info["id"])
    d = track_dir(tid)
    wav = d / "source.wav"
    meta = {
        "title": info.get("track") or info.get("title") or "",
        "artist": info.get("artist") or info.get("creator") or info.get("uploader") or "",
        "video_title": info.get("title", ""),
        "channel": info.get("channel") or info.get("uploader") or "",
        "album": info.get("album"), "release_year": info.get("release_year"),
        "duration": info.get("duration"), "url": info.get("webpage_url") or source,
        "description": (info.get("description") or "")[:600],
    }
    (d / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    if not wav.exists():
        log.info("downloading %s", meta["video_title"])
        opts = {"quiet": True, "noplaylist": True, "format": "bestaudio/best",
                "outtmpl": str(d / "download.%(ext)s"), "ffmpeg_location": str(Path(_ffmpeg()).parent)}
        _ydl(opts, lambda y: y.download([meta["url"]]))
        dl = next(d.glob("download.*"))
        _to_wav(dl, wav)
        dl.unlink(missing_ok=True)
    return tid, wav, meta
