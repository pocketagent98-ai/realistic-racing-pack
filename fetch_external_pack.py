#!/usr/bin/env python3
"""
fetch_external_pack.py
======================

Builds the **Racing Cars Mega Pack** from two community sources the user
requested:

* **OpenGameArt** — "Modular Racetrack" by Keith (Fertile Soil Productions),
  CC0. A kit of modular .obj track pieces. No credentials required.
* **Poly Pizza** — poly.pizza, a catalogue of 10,000+ free low-poly CC0 /
  CC-BY models. Used to collect ~60-70 racing car models.

Poly Pizza access requires a free API key (https://poly.pizza/settings/api),
supplied via the ``POLY_PIZZA_API_KEY`` environment variable. Without it the
Poly Pizza provider is skipped and only the OpenGameArt track is fetched.

Output tree
-----------
    racing_pack/
    ├── cars/          <slug>.glb + <slug>.json   (Poly Pizza)
    └── race_tracks/   modular .obj track kit     (OpenGameArt)

A ``manifest.json`` and ``CREDITS.md`` are written alongside, with per-asset
licence and attribution.

Usage
-----
    python fetch_external_pack.py                       # default providers
    python fetch_external_pack.py --providers opengameart
    python fetch_external_pack.py --cars 70
    python fetch_external_pack.py --list
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "racing_pack"

USER_AGENT = os.environ.get(
    "ASSET_FETCH_USER_AGENT",
    "RacingCarsMegaPack/1.0 (+https://github.com/; contact: agentpocket0@gmail.com)",
)
TIMEOUT = 180
MAX_RETRIES = 3

# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #


def _req(url: str, extra: dict | None = None) -> urllib.request.Request:
    headers = {"User-Agent": USER_AGENT}
    if extra:
        headers.update(extra)
    return urllib.request.Request(url, headers=headers)


def http_bytes(url: str, extra: dict | None = None) -> bytes:
    with urllib.request.urlopen(_req(url, extra), timeout=TIMEOUT) as r:
        return r.read()


def http_json(url: str, extra: dict | None = None):
    with urllib.request.urlopen(_req(url, extra), timeout=TIMEOUT) as r:
        return json.load(r)


def http_text(url: str, extra: dict | None = None) -> str:
    return http_bytes(url, extra).decode("utf-8", "replace")


def download(url: str, dest: Path, extra: dict | None = None, force: bool = False) -> bool:
    if dest.exists() and not force and dest.stat().st_size > 0:
        print(f"    = skip (exists)  {dest.relative_to(ROOT)}")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    last = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(_req(url, extra), timeout=TIMEOUT) as r, open(part, "wb") as fh:
                shutil.copyfileobj(r, fh, length=1 << 16)
            if part.stat().st_size == 0:
                raise IOError("empty response")
            os.replace(part, dest)
            print(f"    + {dest.stat().st_size/1e6:7.2f} MB  {dest.relative_to(ROOT)}")
            return True
        except Exception as exc:  # noqa: BLE001
            last = exc
            part.unlink(missing_ok=True)
            if attempt < MAX_RETRIES:
                time.sleep(1.5 * attempt)
    print(f"    ! failed: {url} ({last})")
    return False


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #


class Manifest:
    def __init__(self):
        self.rows: list[dict] = []

    def add(self, path: Path, **kw):
        kw["file"] = str(path.relative_to(OUT))
        kw["bytes"] = path.stat().st_size
        kw["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.rows.append(kw)

    def write(self):
        (OUT / "manifest.json").write_text(
            json.dumps(
                {
                    "pack": "Racing Cars Mega Pack",
                    "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "asset_count": len(self.rows),
                    "assets": sorted(self.rows, key=lambda r: r["file"]),
                },
                indent=2,
            )
            + "\n"
        )
        lines = [
            "# Racing Cars Mega Pack — Credits & Licences",
            "",
            "Every model below is CC0-1.0 (public domain) or CC-BY (attribution",
            "required). CC-BY entries name the author, as the licence requires.",
            "",
        ]
        for cat in ("cars", "race_tracks"):
            rows = [r for r in self.rows if r["category"] == cat]
            if not rows:
                continue
            lines += [f"## {cat}", "", "| File | Licence | Author | Source |", "|---|---|---|---|"]
            for r in rows:
                lines.append(
                    f"| `{r['file']}` | {r.get('licence','?')} | {r.get('author','?')} | {r.get('source','?')} |"
                )
            lines.append("")
        (OUT / "CREDITS.md").write_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------------- #
# Provider: OpenGameArt (CC0, no auth)
# --------------------------------------------------------------------------- #

# Every entry below is CC0 (public domain) and downloadable without a login.
OGA_ASSETS = [
    # ---- Racing / sports / muscle cars (CC0) ----
    {"page": "https://opengameart.org/content/racing-assets-v1", "category": "cars",
     "name": "racing_assets_v1", "licence": "CC0-1.0", "author": "OpenGameArt contributor"},
    {"page": "https://opengameart.org/content/car-kit", "category": "cars",
     "name": "kenney_car_kit", "licence": "CC0-1.0", "author": "Kenney"},
    {"page": "https://opengameart.org/content/free-low-poly-vehicles-pack", "category": "cars",
     "name": "rgsdev_vehicles_pack", "licence": "CC0-1.0", "author": "rgsdev"},
    {"page": "https://opengameart.org/content/low-poly-cars-0", "category": "cars",
     "name": "quaternius_carpack", "licence": "CC0-1.0", "author": "Quaternius"},
    {"page": "https://opengameart.org/content/low-poly-car-update-pack", "category": "cars",
     "name": "byzmod3d_car_2023", "licence": "CC0-1.0", "author": "byzmod3d"},
    {"page": "https://opengameart.org/content/3d-vehicles-pack", "category": "cars",
     "name": "mehrasaur_vehicles", "licence": "CC0-1.0", "author": "mehrasaur"},
    {"page": "https://opengameart.org/content/toy-car-kit", "category": "cars",
     "name": "kenney_toy_car_kit", "licence": "CC0-1.0", "author": "Kenney"},
    # ---- Modular racetrack (CC0) ----
    {"page": "https://opengameart.org/content/modular-racetrack-3d-models", "category": "race_tracks",
     "name": "modular_racetrack_keith", "licence": "CC0-1.0",
     "author": "Keith at Fertile Soil Productions"},
]

MODEL_EXTS = (".glb", ".gltf", ".obj", ".fbx")
ALL_EXTS = MODEL_EXTS + (".mtl", ".png", ".jpg", ".jpeg")


def _oga_zip_url(page: str) -> str | None:
    """Scrape an OpenGameArt content page for its primary download link."""
    html = http_text(page)
    # OGA file links look like /sites/default/files/<name>.zip (sometimes the
    # leading slash is omitted, so match loosely and urljoin afterwards).
    links = re.findall(
        r'href="([^"]*sites/default/files/[^"]+\.(?:zip|7z|tar\.gz))"', html
    )
    if not links:
        return None
    # Prefer the first .zip
    for l in links:
        if l.endswith(".zip"):
            return urllib.parse.urljoin("https://opengameart.org", l)
    return urllib.parse.urljoin("https://opengameart.org", links[0])


def fetch_opengameart(manifest: Manifest, force: bool = False, **_):
    print("\n[opengameart] OpenGameArt (CC0)")
    total_models = 0
    for a in OGA_ASSETS:
        print(f"  {a['name']}: {a['page']}")
        try:
            zip_url = _oga_zip_url(a["page"])
        except Exception as exc:  # noqa: BLE001
            print(f"    ! could not read page: {exc}")
            continue
        if not zip_url:
            print("    ! no download link found on the page")
            continue
        print(f"    download link: {zip_url}")
        tmp = OUT / "_tmp" / Path(urllib.parse.urlparse(zip_url).path).name
        if not download(zip_url, tmp, force=force):
            continue
        # Verify it really is a zip (PK\x03\x04)
        if tmp.read_bytes()[:4] != b"PK\x03\x04":
            print("    ! downloaded file is not a zip; skipping")
            continue
        dest_dir = OUT / a["category"] / a["name"]
        dest_dir.mkdir(parents=True, exist_ok=True)
        kept = models = 0
        with zipfile.ZipFile(tmp) as zf:
            for member in zf.namelist():
                if member.endswith("/"):
                    continue
                ext = Path(member).suffix.lower()
                if ext not in ALL_EXTS:
                    continue
                flat = Path(member).name
                target = dest_dir / flat
                if target.exists():  # avoid clashes across subfolders
                    target = dest_dir / (Path(member).parent.name + "__" + flat)
                with zf.open(member) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
                kept += 1
                if ext in MODEL_EXTS:
                    models += 1
        total_models += models
        print(f"    extracted {kept} file(s), {models} model(s) -> {dest_dir.relative_to(ROOT)}")
        model_files = sorted(p for p in dest_dir.iterdir() if p.suffix.lower() in MODEL_EXTS)
        if model_files:
            manifest.add(
                model_files[0],
                category=a["category"], licence=a["licence"], author=a["author"],
                source=a["page"], note=f"{models} model file(s) in this pack",
            )
        shutil.rmtree(OUT / "_tmp", ignore_errors=True)
    print(f"  [opengameart] total model files extracted: {total_models}")


# --------------------------------------------------------------------------- #
# Provider: Poly Pizza (needs POLY_PIZZA_API_KEY)
# --------------------------------------------------------------------------- #

PP_BASE = "https://api.poly.pizza/v1"

# Search terms aimed at racing-relevant vehicles.
PP_QUERIES = [
    "race car", "racing car", "sports car", "supercar", "formula 1",
    "rally car", "stock car", "drift car", "gt car", "muscle car",
    "go kart", "kart", "hypercar", "prototype race car", "touring car",
    "buggy", "open wheel", "race track", "cars", "vehicles",
]

# Keep only car-ish results; drop clearly non-car vehicles.
KEEP = re.compile(r"car|racer|racing|kart|formula|gt\b|rally|drift|buggy|supercar|hypercar|f1|stock|muscle|roadster|coupe|sports", re.I)
DROP = re.compile(r"truck|lorry|bus\b|tractor|tank\b|helicopter|boat|yacht|plane|aircraft|motorcycle|bike\b|bicycle|train|scooter|forklift|van\b|ambulance|police|fire|military|army|horse|cart\b", re.I)


def _pp_headers(key: str) -> dict:
    # Docs use X-Auth-Token; some clients use x-api-key. Send both.
    return {"X-Auth-Token": key, "x-api-key": key, "Accept": "application/json"}


def fetch_polypizza(manifest: Manifest, target: int = 70, force: bool = False, **_):
    print("\n[polypizza] Poly Pizza (CC0 / CC-BY)")
    key = os.environ.get("POLY_PIZZA_API_KEY")
    if not key:
        print("  - POLY_PIZZA_API_KEY not set; skipping Poly Pizza cars.")
        print("    Get a free key at https://poly.pizza/settings/api")
        return

    seen: dict[str, dict] = {}
    for q in PP_QUERIES:
        url = f"{PP_BASE}/search/{urllib.parse.quote(q)}?limit=50&format=glb"
        try:
            data = http_json(url, _pp_headers(key))
        except Exception as exc:  # noqa: BLE001
            print(f"  ! search '{q}': {exc}")
            continue
        results = data.get("results", data.get("Results", [])) if isinstance(data, dict) else []
        for m in results:
            mid = m.get("ID") or m.get("id")
            title = (m.get("Title") or m.get("title") or "").strip()
            if not mid or mid in seen:
                continue
            if DROP.search(title) or not KEEP.search(title):
                continue
            seen[mid] = m
        print(f"  search '{q}': {len(results)} hit(s), {len(seen)} racing car(s) so far")
        if len(seen) >= target:
            break

    picks = list(seen.values())[:target]
    print(f"  selected {len(picks)} racing car model(s)")

    cars_dir = OUT / "cars"
    cars_dir.mkdir(parents=True, exist_ok=True)
    for m in picks:
        mid = m.get("ID") or m.get("id")
        title = (m.get("Title") or m.get("title") or mid).strip()
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", title).strip("_").lower() or str(mid)
        slug = f"{slug[:60]}_{mid}"
        creator = m.get("Creator") or {}
        author = creator.get("Username") or m.get("Author") or "Unknown"
        purl = creator.get("PURL") or ""
        licence = m.get("Licence") or m.get("License") or "CC-BY"
        dl = m.get("Download") or m.get("download")
        if not dl:
            continue
        dest = cars_dir / f"{slug}.glb"
        if not download(dl, dest, force=force):
            continue
        # per-model metadata sidecar
        (cars_dir / f"{slug}.json").write_text(
            json.dumps(
                {
                    "id": mid, "title": title, "author": author, "creator_url": purl,
                    "licence": licence, "source": f"https://poly.pizza/m/{mid}",
                    "download": dl, "triangles": m.get("TriangleCount"),
                    "tags": m.get("Tags"),
                },
                indent=2,
            )
            + "\n"
        )
        manifest.add(
            dest, category="cars", licence=licence, author=author,
            source=f"https://poly.pizza/m/{mid}",
        )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

PROVIDERS = {"opengameart": fetch_opengameart, "polypizza": fetch_polypizza}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--providers", nargs="+", default=["opengameart", "polypizza"],
                    choices=list(PROVIDERS))
    ap.add_argument("--cars", type=int, default=70, help="Target number of cars.")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    if args.list:
        print("opengameart : CC0  -> race_tracks  (no auth)")
        print("polypizza   : CC0/CC-BY -> cars     (needs POLY_PIZZA_API_KEY)")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cars").mkdir(exist_ok=True)
    (OUT / "race_tracks").mkdir(exist_ok=True)

    print("Racing Cars Mega Pack — external fetcher")
    print(f"  providers: {', '.join(args.providers)}")

    manifest = Manifest()
    for name in args.providers:
        try:
            PROVIDERS[name](manifest=manifest, target=args.cars, force=args.force)
        except Exception as exc:  # noqa: BLE001
            print(f"  !! provider '{name}' failed: {exc}")

    manifest.write()
    print("\nSummary")
    for cat in ("cars", "race_tracks"):
        n = len([p for p in (OUT / cat).rglob("*") if p.is_file()])
        print(f"  {cat:12s}: {n} file(s)")
    print(f"  manifest    : racing_pack/manifest.json ({len(manifest.rows)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
