#!/usr/bin/env python3
"""
curate_pack.py
==============

Turns the raw OpenGameArt download (``racing_pack/``) into a clean, curated
``racing_pack_curated/`` containing only racing cars + the modular racetrack,
with a manifest, credits and a readme. Everything is CC0.

Selection
---------
* ``racing_assets_v1`` — 63 racing vehicles (7 models x 9 colours), .obj + .mtl
* a hand-picked set of distinct racers from the other CC0 packs
* ``modular_racetrack_keith`` — the 20-piece modular track kit

Run after ``fetch_external_pack.py``.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "racing_pack"
BUILD = ROOT / "racing_pack_curated"

# Distinct racers picked from the other CC0 packs: (path under racing_pack/, pack, author)
EXTRAS = [
    ("cars/kenney_car_kit/race.glb", "kenney_car_kit", "Kenney"),
    ("cars/kenney_car_kit/race-future.glb", "kenney_car_kit", "Kenney"),
    ("cars/kenney_car_kit/kart-oobi.glb", "kenney_car_kit", "Kenney"),
    ("cars/kenney_toy_car_kit/vehicle-drag-racer.glb", "kenney_toy_car_kit", "Kenney"),
    ("cars/kenney_toy_car_kit/vehicle-racer.glb", "kenney_toy_car_kit", "Kenney"),
    ("cars/quaternius_carpack/RaceCar.obj", "quaternius_carpack", "Quaternius"),
    ("cars/quaternius_carpack/RaceCar.mtl", "quaternius_carpack", "Quaternius"),
    ("cars/rgsdev_vehicles_pack/Sports.fbx", "rgsdev_vehicles_pack", "rgsdev"),
]

MODEL_EXTS = (".glb", ".gltf", ".obj", ".fbx")


def main() -> int:
    if not SRC.exists():
        print(f"error: {SRC} not found — run fetch_external_pack.py first", file=sys.stderr)
        return 1
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)

    rows: list[dict] = []

    def add(src: Path, rel: str, pack: str, author: str, source: str):
        dst = BUILD / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        rows.append(dict(file=rel, pack=pack, licence="CC0-1.0", author=author,
                         source=source, bytes=dst.stat().st_size,
                         sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))

    # 1. the dedicated racing pack (63 vehicles)
    ra = SRC / "cars" / "racing_assets_v1"
    ra_src = "https://opengameart.org/content/racing-assets-v1"
    for obj in sorted(ra.glob("car-*.obj")):
        add(obj, f"cars/racing_assets_v1/{obj.name}", "racing_assets_v1",
            "OpenGameArt contributor", ra_src)
        mtl = ra / (obj.stem + ".mtl")
        if mtl.exists():
            add(mtl, f"cars/racing_assets_v1/{mtl.name}", "racing_assets_v1",
                "OpenGameArt contributor", ra_src)

    # 2. hand-picked extras
    for rel, pack, author in EXTRAS:
        s = SRC / rel
        if s.exists():
            add(s, rel, pack, author, "https://opengameart.org/")
        else:
            print(f"  note: {rel} not present, skipping")

    # 3. the modular racetrack
    rt = SRC / "race_tracks" / "modular_racetrack_keith"
    rt_src = "https://opengameart.org/content/modular-racetrack-3d-models"
    for p in sorted(rt.iterdir()) if rt.exists() else []:
        add(p, f"race_tracks/modular_racetrack_keith/{p.name}",
            "modular_racetrack_keith", "Keith at Fertile Soil Productions", rt_src)

    cars = [r for r in rows if r["file"].startswith("cars/") and Path(r["file"]).suffix.lower() in MODEL_EXTS]
    tracks = [r for r in rows if r["file"].startswith("race_tracks/") and Path(r["file"]).suffix.lower() in MODEL_EXTS]

    (BUILD / "manifest.json").write_text(json.dumps({
        "pack": "Racing Cars Mega Pack",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "racing_cars": len(cars), "track_pieces": len(tracks),
        "total_files": len(rows), "all_cc0": True,
        "assets": sorted(rows, key=lambda r: r["file"]),
    }, indent=2) + "\n")

    packs: dict[str, dict] = {}
    for r in rows:
        packs.setdefault(r["pack"], {"n": 0, "author": r["author"], "source": r["source"]})
        packs[r["pack"]]["n"] += 1
    lines = ["# Racing Cars Mega Pack - Credits & Licences", "",
             "**Every model in this pack is CC0 1.0 (public domain).**",
             "No attribution required; credits given as a courtesy.", "",
             "| Pack | Files | Author | Licence | Source |", "|---|---|---|---|---|"]
    for k, v in sorted(packs.items()):
        lines.append(f"| {k} | {v['n']} | {v['author']} | CC0-1.0 | {v['source']} |")
    (BUILD / "CREDITS.md").write_text("\n".join(lines) + "\n")

    (BUILD / "README.txt").write_text(
        f"Racing Cars Mega Pack\n{'='*20}\n"
        f"{len(cars)} racing car models + {len(tracks)} modular track pieces. All CC0 (public domain).\n\n"
        "cars/racing_assets_v1/    63 racing cars (7 models x 9 colours): Formula, Group C x2,\n"
        "                          Kart, and 3 sports cars. .obj + .mtl\n"
        "cars/kenney_car_kit/      race.glb, race-future.glb, kart-oobi.glb\n"
        "cars/kenney_toy_car_kit/  vehicle-drag-racer.glb, vehicle-racer.glb\n"
        "cars/quaternius_carpack/  RaceCar.obj + .mtl\n"
        "cars/rgsdev_vehicles_pack/ Sports.fbx\n"
        "race_tracks/modular_racetrack_keith/  20 snap-together pieces. .obj + .mtl\n\n"
        "Import into Blender / Unity / Unreal / Godot. Licence: CC0 - use freely.\n"
    )

    print(f"curated: {len(cars)} cars, {len(tracks)} track pieces, {len(rows)} files -> {BUILD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
