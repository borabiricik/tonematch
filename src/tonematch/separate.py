"""Guitar stem separation (audio-separator: BS-Roformer-SW, fallback htdemucs_6s)."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from .config import MODELS_DIR, SEPARATION_MODELS

log = logging.getLogger(__name__)

STEMS = ("guitar", "drums", "bass", "vocals", "piano", "other")


def separate(wav: Path, out_dir: Path, model: str | None = None) -> dict[str, Path]:
    """Return {stem: path}. Cached in out_dir/stems."""
    stem_dir = out_dir / "stems"
    info = stem_dir / "model.json"
    if info.exists():
        cached = json.loads(info.read_text())
        paths = {k: Path(v) for k, v in cached["stems"].items()}
        if all(p.exists() for p in paths.values()) and "guitar" in paths:
            return paths

    from audio_separator.separator import Separator

    from .ingest import _ffmpeg

    _ffmpeg()  # puts ffmpeg on PATH for audio-separator
    stem_dir.mkdir(parents=True, exist_ok=True)
    last_err: Exception | None = None
    for m in ([model] if model else SEPARATION_MODELS):
        try:
            log.info("separating with %s", m)
            sep = Separator(output_dir=str(stem_dir), model_file_dir=str(MODELS_DIR), output_format="WAV",
                            log_level=logging.WARNING)
            sep.load_model(model_filename=m)
            files = sep.separate(str(wav))
            paths: dict[str, Path] = {}
            for f in files:
                fp = Path(f) if Path(f).is_absolute() else stem_dir / f
                low = fp.stem.lower()
                stem = next((s for s in STEMS if f"({s})" in low or low.endswith(f"_{s}")), None)
                if stem:
                    dst = stem_dir / f"{stem}.wav"
                    shutil.move(str(fp), dst)
                    paths[stem] = dst
            if "guitar" not in paths:
                raise RuntimeError(f"{m} produced no guitar stem: {files}")
            info.write_text(json.dumps({"model": m, "stems": {k: str(v) for k, v in paths.items()}}, indent=1))
            return paths
        except Exception as e:  # try the next model
            log.warning("separation with %s failed: %s", m, e)
            last_err = e
    raise RuntimeError(f"guitar separation failed: {last_err}")
