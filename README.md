# 🏎️ Realistic Racing Mega Pack

A curated, **automatically-built** collection of realistic racing 3D assets —
sports/GT/concept car meshes, wheels & rims, modular track pieces and
PBR car-paint materials — sourced only from open repositories and released
under **CC0-1.0 (public domain)** or **CC-BY-4.0 (attribution)**.

Everything is fetched, format-validated and packaged by
[`fetch_assets.py`](fetch_assets.py), then published as a single ZIP by a
GitHub Actions workflow.

<p align="left">
  <a href="https://github.com/pocketagent98-ai/realistic-racing-pack/actions/workflows/build_racing_pack.yml">
    <img alt="Build status" src="https://github.com/pocketagent98-ai/realistic-racing-pack/actions/workflows/build_racing_pack.yml/badge.svg">
  </a>
</p>

## ⬇️ One-click download

> **[Download `Realistic_Racing_Mega_Pack.zip`](https://github.com/pocketagent98-ai/realistic-racing-pack/releases/latest/download/Realistic_Racing_Mega_Pack.zip)**

That link always resolves to the newest release. Every release is produced by
the workflow in [`.github/workflows/build_racing_pack.yml`](.github/workflows/build_racing_pack.yml).

## 📁 Repository structure

```
.
├── assets/
│   ├── cars/                # Realistic sports / GT / concept car meshes (.glb)
│   ├── wheels_and_rims/     # Modular rims, sports tyres, alloy wheels
│   ├── race_tracks/         # Modular road pieces, curbs, barriers, turns
│   ├── pbr_materials/       # Car-paint, carbon-fibre and photoscanned PBR maps
│   ├── manifest.json        # Machine-readable index: file, size, SHA-256, licence
│   └── CREDITS.md           # Per-asset attribution (auto-generated)
├── fetch_assets.py          # The fetcher / organiser / validator
├── requirements.txt
└── .github/workflows/build_racing_pack.yml
```

Formats used: **`.glb`**, **`.gltf`** and **`.fbx`** for meshes; **`.png` / `.jpg`**
for PBR maps. Every downloaded file is validated by its **magic bytes**, not
its extension.

## 🖼️ Asset previews

Previews are rendered from the upstream glTF sample viewer (image credit: Khronos Group, CC-BY-4.0).

| Asset | Category | Preview | Licence |
|---|---|---|---|
| **Toy Car** | `cars` | ![Toy Car](https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/ToyCar/screenshot/screenshot_large.jpg) | **CC0-1.0** |
| **Car Concept** | `cars` | ![Car Concept](https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/CarConcept/screenshot/screenshot_Large.jpg) | CC-BY-4.0 |
| **Clear Coat Car Paint** | `pbr_materials` | ![Car Paint](https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/ClearCoatCarPaint/screenshot/screenshot_large.jpg) | **CC0-1.0** |
| **Carbon Fibre** | `pbr_materials` | ![Carbon Fibre](https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/CarbonFibre/screenshot/screenshot_large.jpg) | CC-BY-4.0 |

## ⚖️ Licensing — read this before shipping

This pack mixes two open licences. Both allow commercial use; only one needs credit.

| Licence | What it means | Attribution |
|---|---|---|
| **CC0-1.0** | Public domain. No copyright reserved. | **Not required** |
| **CC-BY-4.0** | Free to use, modify, redistribute, commercially. | **Required** — keep the credit |

The exact licence for every individual file is listed in
[`assets/CREDITS.md`](assets/CREDITS.md) and `assets/manifest.json`. The MIT
[`LICENSE`](LICENSE) in this repo covers the **tooling only**, not the assets.

### Where the assets come from

| Provider | Licence | Needs credentials | What it supplies |
|---|---|---|---|
| **Khronos glTF-Sample-Assets** | CC0-1.0 / CC-BY-4.0 | No | Realistic concept cars, car-paint & carbon-fibre material samples |
| **Poly Haven** | CC0-1.0 | No | Photoscanned PBR textures & models |
| **ambientCG** | CC0-1.0 | No | Photoscanned PBR materials *(opt-in)* |
| **Sketchfab (CC0 filter)** | CC0-1.0 | `SKETCHFAB_TOKEN` | Realistic CC0 concept cars & wheel/tyre kits *(opt-in)* |

> **Honest note on availability.** Truly realistic *GT/supercar* meshes, *alloy
> rims* and *modular race tracks* released under pure CC0 are genuinely scarce
> — most high-fidelity car models are paid, manufacturer-trademarked, or
> non-commercial. This pipeline therefore ships what cleanly-licensed realistic
> assets actually exist, and leaves the door open (via the Poly Haven and
> Sketchfab providers) to add more without ever touching a non-open licence.
> Low-poly / blocky / cartoon kits, construction vehicles, tractors and
> commercial trucks are deliberately **excluded**, per the project's scope.

## 🔧 Using the fetcher locally

No third-party packages are needed — it is standard-library only.

```bash
# Default providers (khronos + polyhaven)
python fetch_assets.py

# Pick providers and categories
python fetch_assets.py --providers khronos polyhaven ambientcg --only cars pbr_materials

# Higher-resolution textures, or force a re-download
python fetch_assets.py --resolution 2k --force

# See what's available without downloading
python fetch_assets.py --list
python fetch_assets.py --dry-run
```

Running it is **idempotent**: valid files already on disk are skipped, and the
manifest is rebuilt from whatever is present.

## 🚀 The release pipeline

[`.github/workflows/build_racing_pack.yml`](.github/workflows/build_racing_pack.yml) runs on:

- **`workflow_dispatch`** — the manual, 1-click "Run workflow" button (with
  optional `providers` / `resolution` inputs), and
- **`push`** to `main` that touches the fetcher, the workflow, or `assets/`.

It then:

1. installs dependencies and runs `fetch_assets.py`,
2. compresses the entire `assets/` directory into **`Realistic_Racing_Mega_Pack.zip`**,
3. publishes a new **GitHub Release** with that ZIP attached, and
4. commits the refreshed assets back to the branch.

To enable the optional Sketchfab provider, add a repository secret named
`SKETCHFAB_TOKEN`.

## ➕ Adding your own assets

Drop a CC0/CC-BY mesh into the matching folder under `assets/` (or add a new
entry to the provider tables in `fetch_assets.py`), then push. The workflow
re-validates, re-packs and re-releases automatically. Add the new asset's
licence and author to the `CREDITS.md` table so downstream users stay compliant.

---

*Built and maintained by the Realistic Racing Mega Pack pipeline.*
