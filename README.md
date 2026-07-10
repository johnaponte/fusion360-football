# fusion360-football

A Fusion 360 Add-In that generates a parametric football (soccer ball), built
as a truncated icosahedron: 12 pentagon panels + 20 hexagon panels, each
created as its own independent, printable solid body.

## Status

Functional. Not yet run inside Fusion 360 (this environment has no way to
drive the Fusion UI); the underlying geometry math is covered by a
standalone test (see [Testing the geometry](#testing-the-geometry-without-fusion)
below). Please report any issues seen when actually running it in Fusion.

## What it builds

Running the command creates 32 solid bodies in the active design:
`Pentagon_01`..`Pentagon_12` and `Hexagon_01`..`Hexagon_20`. Each panel is
a frustum-like shape:

- The **outer face** is either the flat pentagon/hexagon plane, or (in
  "Rounded" mode) that same plane further carved by the ball's circumsphere,
  so the panel center bulges into a dome while its corners stay exactly on
  the true polyhedron vertices.
- The **inner face** is a flat plane at the requested depth.
- The **sides** are mitered (angle-bisector cut) to the exact dihedral angle
  shared with each neighboring panel, so the 32 pieces meet flush when
  assembled, regardless of panel depth. Because the cut uses each edge's own
  neighbor, a hexagon's edges that meet other hexagons (dihedral 138.19°) and
  those that meet pentagons (142.62°) are mitered at their own correct angles.
- With a non-zero **print tolerance**, each mitered side face is inset by half
  the tolerance, leaving that much total clearance between neighboring panels.
- Pentagons and hexagons each get their own solid color appearance (built from
  a matte plastic base so the chosen RGB shows accurately) applied to the bodies.

### Where the bodies are placed

- In an **Assembly** document, each run creates its own component named
  `Football` (then `Football (2)`, `Football (3)`, ...), so you can keep several
  balls in one design, cleanly organized in the browser and timeline.
- In a **Part** document (which Fusion limits to a single component), the bodies
  are created directly in the root component instead. Everything still works;
  you just don't get a separate component per run.

## Dialog parameters

| Parameter | Default | Notes |
|---|---|---|
| Hexagon side | 44 mm | Edge length of the truncated icosahedron (all edges are this length, pentagons included). |
| Face deep | 5 mm | Panel thickness measured at the edges. |
| Print tolerance (gap) | 0 mm | Total clearance left between adjacent panels for 3D printing. 0 = panels touch exactly; ~0.1 mm is a typical real-world fit. |
| External face | Flat | Flat keeps the outer face planar; Rounded carves it with the ball's circumsphere. |
| Pentagon color | RGB (0, 0, 0) — black | Three 0-255 spinners (Fusion dialogs have no color-swatch picker). |
| Hexagon color | RGB (255, 255, 255) — white | Three 0-255 spinners. |

## Requirements

- Autodesk Fusion 360
- Python (bundled with Fusion 360's API)

## Installation

### For users — install a released bundle

1. Download `fusion360-football-<version>.zip` from the
   [Releases](https://github.com/johnaponte/fusion360-football/releases) page.
2. Unzip it into Fusion's **ApplicationPlugins** folder:
   - **macOS:** `~/Library/Application Support/Autodesk/ApplicationPlugins/`
   - **Windows:** `%APPDATA%\Autodesk\ApplicationPlugins\`

   You should end up with `.../ApplicationPlugins/fusion360-football.bundle/`.
3. Restart Fusion. A **Football** button appears in the Solid tab's **Create**
   menu. Click it, set the parameters, and click OK.

### For development — link the source folder

1. In Fusion, go to **Utilities > Add-Ins > Scripts and Add-Ins**.
2. On the **Add-Ins** tab, click the green **+** and select this repo's folder.
3. Select the add-in and click **Run**. Edits to the source are picked up the
   next time you run it.

## Releases & packaging

The add-in source lives at the repo root so the folder can be linked directly
in Fusion during development. The distributable **bundle** is assembled from
that source by `packaging/build_bundle.py`:

```
python3 packaging/build_bundle.py --version 0.1.0
```

This writes `dist/fusion360-football.bundle/` (the installable bundle, with a
generated `PackageContents.xml`) and `dist/fusion360-football-<version>.zip`.

On GitHub, publishing a Release (from a tag like `v0.1.0`) triggers
`.github/workflows/release.yml`, which runs the geometry test, builds the zip,
and attaches it to that release automatically.

### Submitting to the Autodesk App Store (not yet done)

The bundle is structured for the [Autodesk App Store](https://aps.autodesk.com/app-store/publisher-center/fusion-360)
but has not been submitted. Before submitting you still need to: register as a
publisher, fill in the `TODO` contact field in `packaging/PackageContents.xml`,
review `packaging/EULA.txt` (currently pointing at the MIT license) and the
placeholder `packaging/PRIVACY_POLICY.md`, and provide store-listing assets
(icon, screenshots, description). The `UpgradeCode` GUID in
`PackageContents.xml` must stay constant across versions once published.

## Project layout

```
fusion360-football.py        Add-in entry point (run/stop)
fusion360-football.manifest  Add-in manifest
config.py                    Shared add-in-wide constants
commands/
  build_football/entry.py    Command dialog + execute handler
lib/
  icosahedron_geometry.py    Pure-Python truncated icosahedron math (no Fusion dependency)
  ball_builder.py            Fusion API calls that build the 32 panel bodies
  appearance_utils.py        RGB -> Fusion Appearance helper
  fusionAddInUtils/          Autodesk's standard add-in event/logging helpers
packaging/
  build_bundle.py            Assembles dist/<bundle> + zip from the source
  PackageContents.xml        App Store package descriptor (version injected at build)
  Help.html                  Help page shipped inside the bundle
  EULA.txt, PRIVACY_POLICY.md  Placeholders to fill before store submission
.github/workflows/
  release.yml                Builds + attaches the zip when a Release is published
tests/
  test_icosahedron_geometry.py  Standalone check of the geometry module
```

## Testing the geometry without Fusion

`lib/icosahedron_geometry.py` has no Fusion or third-party dependency, so its
vertex/face/adjacency math can be checked with plain `python3`:

```
python3 tests/test_icosahedron_geometry.py
```

This verifies vertex/face counts, edge lengths, face planarity, uniform
circumradius, pentagon/hexagon adjacency, and the two known dihedral angles
of a truncated icosahedron (142.6° and 138.2°). The Fusion-specific code in
`ball_builder.py` and `appearance_utils.py` can only be exercised inside
Fusion itself.

## Development

This add-in follows the standard Fusion 360 Add-In layout (manifest file +
Python entry point matching the folder name), based on Autodesk's own
"Create Add-in" template.

## License

Released under the [MIT License](LICENSE).
