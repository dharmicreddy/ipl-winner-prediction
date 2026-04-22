"""Cricsheet downloader.

Fetches the IPL JSON archive from Cricsheet, caches it locally, and extracts
only the seasons we care about.

Respects ADR-006: identifiable User-Agent, retry with backoff, cache-before-parse.
"""

from __future__ import annotations

import json
import logging
import shutil
import zipfile
from pathlib import Path

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

CRICSHEET_IPL_URL = "https://cricsheet.org/downloads/ipl_json.zip"
USER_AGENT = "ipl-prediction/0.1 (+https://github.com/dharmicreddy/ipl-winner-prediction)"

# Data directory — kept at repo root and gitignored (see .gitignore: "data/")
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CACHE_DIR = DATA_DIR / "cache"
EXTRACT_DIR = DATA_DIR / "cricsheet" / "ipl_json"
CACHED_ZIP = CACHE_DIR / "ipl_json.zip"


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)
def _download_zip(url: str, dest: Path) -> None:
    """Stream the zip to disk with retry on network errors."""
    logger.info("Downloading %s", url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream(
        "GET",
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=60.0,
        follow_redirects=True,
    ) as response:
        response.raise_for_status()
        with dest.open("wb") as f:
            for chunk in response.iter_bytes(chunk_size=64 * 1024):
                f.write(chunk)
    logger.info("Downloaded %s bytes to %s", dest.stat().st_size, dest)


def fetch_cricsheet_zip(force: bool = False) -> Path:
    """Ensure the IPL zip is on disk. Returns the path to it.

    If already cached and force=False, this is a no-op.
    """
    if CACHED_ZIP.exists() and not force:
        logger.info("Using cached zip at %s (%s bytes)", CACHED_ZIP, CACHED_ZIP.stat().st_size)
        return CACHED_ZIP
    _download_zip(CRICSHEET_IPL_URL, CACHED_ZIP)
    return CACHED_ZIP


def extract_seasons(zip_path: Path, seasons: set[str], clean: bool = True) -> list[Path]:
    """Extract only match files matching the given seasons.

    Each Cricsheet match JSON has info.season set (e.g. "2024" or "2007/08" for
    historical splits). We filter in memory — only matching files are written
    to disk.

    Args:
        zip_path: path to the Cricsheet zip.
        seasons: set of season strings to keep, e.g. {"2022", "2023", "2024"}.
        clean: if True, wipe EXTRACT_DIR before extracting.

    Returns:
        List of paths to extracted JSON files.
    """
    if clean and EXTRACT_DIR.exists():
        logger.info("Cleaning %s", EXTRACT_DIR)
        shutil.rmtree(EXTRACT_DIR)
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    extracted: list[Path] = []
    skipped_non_json = 0
    skipped_wrong_season = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if not name.endswith(".json"):
                skipped_non_json += 1
                continue
            # The zip contains a top-level README and per-match JSON files.
            # Cricsheet's bundle also includes "all_matches.csv" style files we skip.
            with zf.open(name) as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    logger.warning("Skipping unparseable file: %s", name)
                    continue

            season = str(data.get("info", {}).get("season", ""))
            if season not in seasons:
                skipped_wrong_season += 1
                continue

            out_path = EXTRACT_DIR / Path(name).name
            with out_path.open("w", encoding="utf-8") as out:
                json.dump(data, out)
            extracted.append(out_path)

    logger.info(
        "Extracted %d files (skipped %d non-json, %d wrong-season)",
        len(extracted),
        skipped_non_json,
        skipped_wrong_season,
    )
    return extracted


def download_and_extract(seasons: set[str], force: bool = False) -> list[Path]:
    """Top-level entrypoint: fetch zip (using cache) + extract matching seasons."""
    zip_path = fetch_cricsheet_zip(force=force)
    return extract_seasons(zip_path, seasons=seasons)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    paths = download_and_extract(seasons={"2022", "2023", "2024"})
    print(f"Extracted {len(paths)} match files")
