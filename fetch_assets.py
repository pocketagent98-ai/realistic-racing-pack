#!/usr/bin/env python3
"""
fetch_assets.py
===============

Autonomous, licence-aware asset fetcher for the **Realistic Racing Mega Pack**.

It downloads 3D models and PBR materials from open, programmatically
accessible repositories, validates the file format of everything it saves,
files it into the ``assets/`` tree, and writes a machine-readable manifest
plus a human-readable credits file.

Providers
---------
khronos    Khronos glTF-Sample-Assets (github.com/KhronosGroup/glTF-Sample-Assets).
           Realistic concept cars and car-paint / carbon-fibre material samples.
           Licences: CC0-1.0 (ToyCar, ClearCoatCarPaint) and CC-BY-4.0
           (CarConcept, CarbonFibre). No credentials required.
polyhaven  Poly Haven (polyhaven.com). 100% CC0 photoscanned PBR textures and
           models, served by a free public API. No credentials required, but a
           descriptive User-Agent is mandatory per their API terms.
ambientcg  ambientCG (ambientcg.com). 100% CC0 photoscanned PBR materials.
           No credentials required.  (opt-in)
sketchfab  Sketchfab CC0 filter. Realistic CC0 concept cars and wheel/tyre
           kits. Requires an OAuth token in ``SKETCHFAB_TOKEN``.  (opt-in)

Usage
-----
    python fetch_assets.py                          # default: khronos + polyhaven
    python fetch_assets.py --providers khronos polyhaven ambientcg
    python fetch_assets.py --only cars pbr_materials
    python fetch_assets.py --resolution 2k
    python fetch_assets.py --dry-run
    python fetch_assets.py --list                   # show what each provider offers

Design notes
------------
* Everything is idempotent: a file that already exists with a valid format is
  skipped unless ``--force`` is passed.
* Every downloaded file is format-checked by magic bytes, not by extension.
* Nothing is written into ``assets/`` until its bytes are fully downloaded and
  validated (downloads land in a ``.part`` file first).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

ROOT = Path(__file__).resolve().parent
ASSETS_DIR = ROOT / "assets"
CATEGORIES = ("cars", "wheels_and_rims", "race_tracks", "pbr_materials")

USER_AGENT = os.environ.get(
    "ASSET_FETCH_USER_AGENT",
    "RealisticRacingMegaPack/1.0 "
    "(+https://github.com/; contact: agentpocket0@gmail.com)",
)

DEFAULT_PROVIDERS = ("khronos", "polyhaven")
MAX_RETRIES = 3
TIMEOUT = 180

# --------------------------------------------------------------------------- #
# Format validation (magic bytes)
# --------------------------------------------------------------------------- #

# extension -> tuple of acceptable byte signatures (None = "any text/JSON")
MAGIC = {
    ".glb": (b"glTF",),
    ".gltf": (b"{", b"["),
    ".fbx": (b"Kaydara FBX Binary", b"; FBX"),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}

MODEL_EXTS = (".glb", ".gltf", ".fbx")
IMAGE_EXTS = (".png", ".jpg", ".jpeg")


def sniff(path: Path) -> str | None:
    """Return the file extension implied by the file's magic bytes, or None."""
    with open(path, "rb") as fh:
        head = fh.read(64).lstrip(b"\xef\xbb\xbf \t\r\n")
    for ext, sigs in MAGIC.items():
        for sig in sigs:
            if head.startswith(sig):
                return ext
    return None


def validate(path: Path, allowed: tuple[str, ...]) -> str:
    """Validate a downloaded file and return its sniffed extension."""
    if not path.exists() or path.stat().st_size == 0:
        raise ValueError(f"{path.name}: empty file")
    detected = sniff(path)
    if detected is None:
        raise ValueError(f"{path.name}: unrecognised binary format")
    if detected not in allowed:
        raise ValueError(
            f"{path.name}: format {detected} not in allowed set {allowed}"
        )
    return detected


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #


def _request(url: str, accept: str | None = None) -> urllib.request.Request:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    return urllib.request.Request(url, headers=headers)


def http_json(url: str):
    with urllib.request.urlopen(_request(url, "application/json"), timeout=TIMEOUT) as r:
        return json.load(r)


def http_download(url: str, dest: Path, allowed: tuple[str, ...], force: bool) -> bool:
    """Download *url* to *dest*, validating format. Returns True if fetched."""
    if dest.exists() and not force:
        try:
            validate(dest, allowed)
            print(f"    = skip (exists, valid)  {dest.relative_to(ROOT)}")
            return True
        except ValueError:
            print(f"    ! replacing invalid    {dest.relative_to(ROOT)}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    last_err: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(_request(url), timeout=TIMEOUT) as r, open(
                part, "wb"
            ) as fh:
                shutil.copyfileobj(r, fh, length=1 << 16)
            detected = validate(part, allowed)
            os.replace(part, dest)
            size = dest.stat().st_size
            print(f"    + {size/1e6:7.2f} MB  {dest.relative_to(ROOT)}  [{detected}]")
            return True
        except Exception as exc:  # noqa: BLE001 - we retry any failure
            last_err = exc
            part.unlink(missing_ok=True)
            if attempt < MAX_RETRIES:
                time.sleep(1.5 * attempt)

    raise RuntimeError(f"download failed after {MAX_RETRIES} tries: {url} ({last_err})")


# --------------------------------------------------------------------------- #
# Manifest bookkeeping
# --------------------------------------------------------------------------- #


class Manifest:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def add(self, **kw) -> None:
        path = Path(kw.pop("path"))
        kw["bytes"] = path.stat().st_size
        kw["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        kw["filename"] = str(path.relative_to(ASSETS_DIR))
        self.records.append(kw)

    def write(self) -> None:
        self.records.sort(key=lambda r: (r["category"], r["filename"]))
        (ASSETS_DIR / "manifest.json").write_text(
            json.dumps(
                {
                    "pack": "Realistic Racing Mega Pack",
                    "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "asset_count": len(self.records),
                    "assets": self.records,
                },
                indent=2,
            )
            + "\n"
        )
        self._write_credits()

    def _write_credits(self) -> None:
        lines = [
            "# Asset Credits & Licences",
            "",
            "This file is generated by `fetch_assets.py`. Every asset below is",
            "released under a CC0-1.0 (public domain) or CC-BY-4.0 licence. Where a",
            "licence requires attribution (CC-BY-4.0) the author is named.",
            "",
            "> CC0-1.0 assets need no attribution. CC-BY-4.0 assets require the",
            "> credit shown, retained in any redistribution.",
            "",
        ]
        for cat in CATEGORIES:
            rows = [r for r in self.records if r["category"] == cat]
            if not rows:
                continue
            lines += [f"## {cat}", "", "| File | Licence | Author / Credit | Source |",
                      "|---|---|---|---|"]
            for r in rows:
                lines.append(
                    f"| `{r['filename']}` | {r['license']} | {r.get('author','—')} "
                    f"| {r.get('source','—')} |"
                )
            lines.append("")
        (ASSETS_DIR / "CREDITS.md").write_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------------- #
# Provider: Khronos glTF-Sample-Assets
# --------------------------------------------------------------------------- #

_KHRONOS_RAW = (
    "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models"
)

# Curated, licence-verified assets. Licences checked against each model's
# LICENSE.md on 2026-10-01.
KHRONOS_ASSETS = [
    {
        "category": "cars",
        "name": "toy_car",
        "url": f"{_KHRONOS_RAW}/ToyCar/glTF-Binary/ToyCar.glb",
        "license": "CC0-1.0",
        "author": "3dimentional (via Khronos glTF-Sample-Assets)",
        "source": "https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/ToyCar",
        "exts": MODEL_EXTS,
    },
    {
        "category": "cars",
        "name": "car_concept",
        "url": f"{_KHRONOS_RAW}/CarConcept/glTF-Binary/CarConcept.glb",
        "license": "CC-BY-4.0",
        "author": "Darmstadt Graphics Group / Eric Chadwick (based on a CC0 model by Unity Fan)",
        "source": "https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/CarConcept",
        "exts": MODEL_EXTS,
    },
    {
        "category": "pbr_materials",
        "name": "clearcoat_car_paint",
        "url": f"{_KHRONOS_RAW}/ClearCoatCarPaint/glTF-Binary/ClearCoatCarPaint.glb",
        "license": "CC0-1.0",
        "author": "Khronos glTF-Sample-Assets (Ed Mackey)",
        "source": "https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/ClearCoatCarPaint",
        "exts": MODEL_EXTS,
    },
    {
        "category": "pbr_materials",
        "name": "carbon_fibre",
        "url": f"{_KHRONOS_RAW}/CarbonFibre/glTF-Binary/CarbonFibre.glb",
        "license": "CC-BY-4.0",
        "author": "Wayfair / Eric Chadwick",
        "source": "https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/CarbonFibre",
        "exts": MODEL_EXTS,
    },
]


def fetch_khronos(manifest: Manifest, only: set[str], force: bool, **_):
    print("\n[khronos] Khronos glTF-Sample-Assets (CC0-1.0 / CC-BY-4.0)")
    for a in KHRONOS_ASSETS:
        if only and a["category"] not in only:
            continue
        dest = ASSETS_DIR / a["category"] / f"{a['name']}{Path(a['url']).suffix}"
        if http_download(a["url"], dest, a["exts"], force):
            manifest.add(
                category=a["category"], path=dest, provider="khronos",
                license=a["license"], author=a["author"],
                source=a["source"], asset_url=a["url"],
            )


# --------------------------------------------------------------------------- #
# Provider: Poly Haven
# --------------------------------------------------------------------------- #

_PH_API = "https://api.polyhaven.com"

# Keywords used to pick relevant CC0 textures per category.
TEXTURE_KEYWORDS = {
    "pbr_materials": (
        "metal", "paint", "plastic", "carbon", "car", "asphalt", "concrete",
        "rubber", "fabric", "leather", "steel", "aluminium", "aluminum",
    ),
}
MODEL_KEYWORDS = {
    "cars": ("car", "vehicle", "automobile"),
    "wheels_and_rims": ("wheel", "rim", "tyre", "tire"),
}

# Texture map types we want, in preference order (Poly Haven naming).
TEXTURE_MAPS = (
    ("Diffuse", ("Diffuse", "diffuse", "diff", "albedo", "basecolor")),
    ("Normal", ("nor_gl", "nor_dx", "Normal", "normal")),
    ("Roughness", ("Rough", "roughness", "rough")),
    ("AO", ("AO", "ao", "occlusion")),
    ("Metalness", ("Metal", "metalness", "metallic")),
    ("Height", ("Displacement", "displacement", "height")),
)


def _ph_list(kind: str) -> dict:
    return http_json(f"{_PH_API}/assets?t={kind}")


def _ph_files(asset_id: str) -> dict:
    return http_json(f"{_PH_API}/files/{asset_id}")


def _ph_pick(map_names: tuple[str, ...], files: dict, resolution: str):
    """Find a download URL for one of the given map names at a resolution."""
    for key, node in files.items():
        if key.lower() not in {m.lower() for m in map_names}:
            continue
        if not isinstance(node, dict):
            continue
        for res in (resolution, "2k", "1k", "4k", "8k"):
            res_node = node.get(res)
            if not isinstance(res_node, dict):
                continue
            for fmt in ("png", "jpg", "jpeg", "webp"):
                if fmt in res_node and isinstance(res_node[fmt], dict):
                    return res_node[fmt].get("url")
    return None


def fetch_polyhaven(manifest: Manifest, only: set[str], force: bool,
                    resolution: str = "1k", limit: int = 4, **_):
    print("\n[polyhaven] Poly Haven public API (CC0-1.0)")

    # ---- textures -> pbr_materials ------------------------------------- #
    if not only or "pbr_materials" in only:
        try:
            textures = _ph_list("textures")
        except Exception as exc:  # noqa: BLE001
            print(f"  ! could not list textures: {exc}")
            textures = {}

        kws = TEXTURE_KEYWORDS["pbr_materials"]
        picked = []
        for slug, meta in textures.items():
            hay = " ".join([slug, meta.get("name", "")] + list(meta.get("tags", []))).lower()
            if any(k in hay for k in kws):
                picked.append(slug)
        picked = sorted(picked)[:limit]
        print(f"  textures matched: {picked}")

        for slug in picked:
            try:
                files = _ph_files(slug)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {slug}: {exc}")
                continue
            for label, names in TEXTURE_MAPS:
                url = _ph_pick(names, files, resolution)
                if not url:
                    continue
                ext = Path(urllib.parse.urlparse(url).path).suffix or ".png"
                dest = ASSETS_DIR / "pbr_materials" / slug / f"{slug}_{label}{ext}"
                try:
                    if http_download(url, dest, IMAGE_EXTS, force):
                        manifest.add(
                            category="pbr_materials", path=dest, provider="polyhaven",
                            license="CC0-1.0", author="Poly Haven",
                            source=f"https://polyhaven.com/a/{slug}", asset_url=url,
                        )
                except Exception as exc:  # noqa: BLE001
                    print(f"  ! {slug}/{label}: {exc}")

    # ---- models -> cars / wheels_and_rims ------------------------------ #
    want_model_cats = {c for c in MODEL_KEYWORDS if not only or c in only}
    if want_model_cats:
        try:
            models = _ph_list("models")
        except Exception as exc:  # noqa: BLE001
            print(f"  ! could not list models: {exc}")
            models = {}

        for cat in sorted(want_model_cats):
            kws = MODEL_KEYWORDS[cat]
            matched = []
            for slug, meta in models.items():
                hay = " ".join([slug, meta.get("name", "")] + list(meta.get("tags", []))).lower()
                if any(k in hay for k in kws):
                    matched.append(slug)
            matched = sorted(matched)[:limit]
            print(f"  models matched for {cat}: {matched}")
            for slug in matched:
                try:
                    files = _ph_files(slug)
                except Exception as exc:  # noqa: BLE001
                    print(f"  ! {slug}: {exc}")
                    continue
                # Poly Haven models expose a 'gltf' (or 'glb') bundle.
                url = None
                for key in ("gltf", "glb"):
                    node = files.get(key)
                    if isinstance(node, dict):
                        for fmt, val in node.items():
                            if isinstance(val, dict) and val.get("url"):
                                url = val["url"]
                                break
                    if url:
                        break
                if not url:
                    continue
                ext = Path(urllib.parse.urlparse(url).path).suffix or ".gltf"
                dest = ASSETS_DIR / cat / f"{slug}{ext}"
                try:
                    if http_download(url, dest, MODEL_EXTS, force):
                        manifest.add(
                            category=cat, path=dest, provider="polyhaven",
                            license="CC0-1.0", author="Poly Haven",
                            source=f"https://polyhaven.com/a/{slug}", asset_url=url,
                        )
                except Exception as exc:  # noqa: BLE001
                    print(f"  ! {slug}: {exc}")


# --------------------------------------------------------------------------- #
# Provider: ambientCG (opt-in)
# --------------------------------------------------------------------------- #

_AC_API = "https://ambientcg.com/api/v2/full_json"

AC_QUERIES = ("Metal", "PaintedMetal", "Plastic", "Asphalt", "Rubber")


def fetch_ambientcg(manifest: Manifest, only: set[str], force: bool, **_):
    print("\n[ambientcg] ambientCG API (CC0-1.0)")
    if only and "pbr_materials" not in only:
        return
    for query in AC_QUERIES:
        url = f"{_AC_API}?type=Material&q={urllib.parse.quote(query)}&limit=1&include=downloadData"
        try:
            data = http_json(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! query '{query}': {exc}")
            continue
        for asset in data.get("foundAssets", []):
            asset_id = asset.get("assetId", "unknown")
            # Pick the smallest PNG zip bundle available.
            links = []
            for folder in asset.get("downloadFolders", {}).values():
                cats = folder.get("downloadFiletypeCategories", {})
                for dl in cats.get("zip", {}).get("downloads", []):
                    links.append(dl)
            if not links:
                continue
            # prefer 1K, then 2K
            def rank(dl):
                n = dl.get("fileName", "").upper()
                return (0 if "1K" in n else 1 if "2K" in n else 2, dl.get("size", 0))
            chosen = sorted(links, key=rank)[0]
            dl_url = chosen.get("downloadLink")
            if not dl_url:
                continue
            ext = Path(urllib.parse.urlparse(dl_url).path).suffix or ".zip"
            dest = ASSETS_DIR / "pbr_materials" / f"{asset_id}{ext}"
            try:
                if http_download(dl_url, dest, (".zip",), force):
                    manifest.add(
                        category="pbr_materials", path=dest, provider="ambientcg",
                        license="CC0-1.0", author="ambientCG",
                        source=f"https://ambientcg.com/view?id={asset_id}",
                        asset_url=dl_url,
                    )
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {asset_id}: {exc}")


# --------------------------------------------------------------------------- #
# Provider: Sketchfab CC0 (opt-in, needs SKETCHFAB_TOKEN)
# --------------------------------------------------------------------------- #

_SF_API = "https://api.sketchfab.com/v3"

# Curated CC0 Sketchfab models (UIDs verified from public listings).
SKETCHFAB_ASSETS = [
    {
        "category": "wheels_and_rims",
        "name": "rims_n_tyres_kit",
        "uid": "97c7a90210974cb089f15ee7682e4d65",
        "license": "CC0-1.0",
        "author": "britdawgmasterfunk",
        "source": "https://sketchfab.com/3d-models/rims-n-tyres-kit-10-cc0-97c7a90210974cb089f15ee7682e4d65",
    },
]


def fetch_sketchfab(manifest: Manifest, only: set[str], force: bool, **_):
    print("\n[sketchfab] Sketchfab CC0 filter")
    token = os.environ.get("SKETCHFAB_TOKEN")
    if not token:
        print("  - SKETCHFAB_TOKEN not set; skipping (this provider is opt-in).")
        return
    for a in SKETCHFAB_ASSETS:
        if only and a["category"] not in only:
            continue
        dl_url = f"{_SF_API}/models/{a['uid']}/download"
        try:
            req = urllib.request.Request(
                dl_url,
                headers={"User-Agent": USER_AGENT, "Authorization": f"Token {token}"},
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                payload = json.load(r)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {a['name']}: {exc}")
            continue
        # The download endpoint returns a signed archive URL.
        url = payload.get("gltf", {}).get("url") or payload.get("url")
        if not url:
            print(f"  ! {a['name']}: no download URL in response")
            continue
        ext = Path(urllib.parse.urlparse(url).path).suffix or ".glb"
        dest = ASSETS_DIR / a["category"] / f"{a['name']}{ext}"
        try:
            if http_download(url, dest, MODEL_EXTS, force):
                manifest.add(
                    category=a["category"], path=dest, provider="sketchfab",
                    license=a["license"], author=a["author"],
                    source=a["source"], asset_url=url,
                )
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {a['name']}: {exc}")


# --------------------------------------------------------------------------- #
# Registry + CLI
# --------------------------------------------------------------------------- #

PROVIDERS = {
    "khronos": fetch_khronos,
    "polyhaven": fetch_polyhaven,
    "ambientcg": fetch_ambientcg,
    "sketchfab": fetch_sketchfab,
}


def ensure_tree() -> None:
    for cat in CATEGORIES:
        d = ASSETS_DIR / cat
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").touch()


def print_listing() -> None:
    print("Provider      Licence(s)         Categories                        Auth")
    print("-" * 78)
    print("khronos       CC0-1.0 / CC-BY-4.0 cars, pbr_materials               none")
    print("polyhaven     CC0-1.0            pbr_materials, cars, wheels...    none")
    print("ambientcg     CC0-1.0            pbr_materials                     none")
    print("sketchfab     CC0-1.0            cars, wheels_and_rims             SKETCHFAB_TOKEN")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--providers", nargs="+", default=list(DEFAULT_PROVIDERS),
                    choices=list(PROVIDERS), help="Providers to run.")
    ap.add_argument("--only", nargs="+", default=[], choices=list(CATEGORIES),
                    help="Restrict to these asset categories.")
    ap.add_argument("--resolution", default="1k",
                    help="Preferred texture resolution for Poly Haven (1k/2k/4k/8k).")
    ap.add_argument("--limit", type=int, default=4,
                    help="Max assets per keyword group per provider.")
    ap.add_argument("--force", action="store_true",
                    help="Re-download even if a valid file exists.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show the plan without downloading.")
    ap.add_argument("--list", action="store_true", help="List providers and exit.")
    args = ap.parse_args(argv)

    if args.list:
        print_listing()
        return 0

    ensure_tree()
    only = set(args.only)

    print("Realistic Racing Mega Pack — asset fetcher")
    print(f"  providers  : {', '.join(args.providers)}")
    print(f"  categories : {', '.join(args.only) if args.only else 'all'}")
    print(f"  resolution : {args.resolution}")

    if args.dry_run:
        for p in args.providers:
            print(f"  would run provider: {p}")
        return 0

    manifest = Manifest()
    failures = 0
    for name in args.providers:
        try:
            PROVIDERS[name](manifest=manifest, only=only, force=args.force,
                            resolution=args.resolution, limit=args.limit)
        except Exception as exc:  # noqa: BLE001 - keep going across providers
            failures += 1
            print(f"  !! provider '{name}' failed: {exc}")

    manifest.write()

    # Summary
    print("\nSummary")
    for cat in CATEGORIES:
        n = len(list((ASSETS_DIR / cat).rglob("*.*")))
        print(f"  {cat:16s}: {n} file(s)")
    print(f"  manifest        : assets/manifest.json "
          f"({len(manifest.records)} recorded assets)")
    print(f"  credits         : assets/CREDITS.md")

    if not manifest.records and failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
