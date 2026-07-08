#!/usr/bin/env python3
"""Assemble the distributable Autodesk App Store bundle for fusion360-football.

Produces, under ``dist/``:
  - ``fusion360-football.bundle/``  -- the installable bundle (drop it into
    Fusion's ApplicationPlugins folder), and
  - ``fusion360-football-<version>.zip`` -- a zip of that bundle for GitHub
    releases / manual install.

The add-in source stays at the repo root (so the folder can be linked directly
in Fusion during development); this script copies the runtime pieces into
``<bundle>/Contents/`` and drops in the packaging extras (PackageContents.xml,
Help.html, EULA, privacy policy). No third-party dependencies -- standard
library only, so it runs the same locally and in CI.

Usage:
    python3 packaging/build_bundle.py [--version X.Y.Z]

If --version is omitted the version is read from fusion360-football.manifest.
"""

import argparse
import json
import os
import shutil
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGING_DIR = os.path.join(REPO_ROOT, "packaging")
DIST_DIR = os.path.join(REPO_ROOT, "dist")

BUNDLE_NAME = "fusion360-football.bundle"
MANIFEST_NAME = "fusion360-football.manifest"

# Add-in runtime pieces copied verbatim into <bundle>/Contents/.
RUNTIME_FILES = [
    "config.py",
    "fusion360-football.py",
    MANIFEST_NAME,
]
RUNTIME_DIRS = [
    "commands",
    "lib",
]

# Never ship these, wherever they appear in a copied tree.
EXCLUDE_NAMES = {"__pycache__", ".DS_Store", ".pytest_cache"}


def normalize_version4(version):
    """'0.1.0' -> '0.1.0.0'; pads/truncates to a four-part numeric version."""
    parts = [p for p in version.strip().lstrip("v").split(".") if p != ""]
    parts = (parts + ["0", "0", "0", "0"])[:4]
    return ".".join(parts)


def read_manifest_version():
    with open(os.path.join(REPO_ROOT, MANIFEST_NAME)) as f:
        return json.load(f)["version"]


def _ignore(_dir, names):
    return [n for n in names if n in EXCLUDE_NAMES]


def build(version):
    version4 = normalize_version4(version)
    version3 = ".".join(version4.split(".")[:3])

    bundle_dir = os.path.join(DIST_DIR, BUNDLE_NAME)
    contents_dir = os.path.join(bundle_dir, "Contents")
    docs_dir = os.path.join(contents_dir, "docs")

    if os.path.exists(bundle_dir):
        shutil.rmtree(bundle_dir)
    os.makedirs(docs_dir)

    # 1. Runtime add-in files/dirs -> Contents/
    for rel in RUNTIME_FILES:
        shutil.copy2(os.path.join(REPO_ROOT, rel), os.path.join(contents_dir, rel))
    for rel in RUNTIME_DIRS:
        shutil.copytree(
            os.path.join(REPO_ROOT, rel),
            os.path.join(contents_dir, rel),
            ignore=_ignore,
        )

    # 2. Stamp the release version into the bundled manifest (source untouched).
    bundled_manifest = os.path.join(contents_dir, MANIFEST_NAME)
    with open(bundled_manifest) as f:
        manifest = json.load(f)
    manifest["version"] = version3
    with open(bundled_manifest, "w") as f:
        json.dump(manifest, f, indent=4)
        f.write("\n")

    # 3. Packaging extras.
    shutil.copy2(os.path.join(PACKAGING_DIR, "Help.html"), os.path.join(docs_dir, "Help.html"))
    shutil.copy2(os.path.join(REPO_ROOT, "LICENSE"), os.path.join(contents_dir, "LICENSE"))
    shutil.copy2(os.path.join(PACKAGING_DIR, "EULA.txt"), os.path.join(contents_dir, "EULA.txt"))
    shutil.copy2(os.path.join(PACKAGING_DIR, "PRIVACY_POLICY.md"),
                 os.path.join(contents_dir, "PRIVACY_POLICY.md"))

    # 4. PackageContents.xml at the bundle root, with the version injected.
    with open(os.path.join(PACKAGING_DIR, "PackageContents.xml")) as f:
        package_xml = f.read().replace("{{VERSION4}}", version4)
    with open(os.path.join(bundle_dir, "PackageContents.xml"), "w") as f:
        f.write(package_xml)

    # 5. Zip the bundle (paths inside the zip start with the .bundle folder).
    zip_path = os.path.join(DIST_DIR, "fusion360-football-%s.zip" % version3)
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(bundle_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_NAMES]
            for name in files:
                abs_path = os.path.join(root, name)
                arcname = os.path.relpath(abs_path, DIST_DIR)
                zf.write(abs_path, arcname)

    print("Built bundle: %s" % bundle_dir)
    print("Built zip   : %s" % zip_path)
    return zip_path


def main():
    parser = argparse.ArgumentParser(description="Build the fusion360-football bundle + zip.")
    parser.add_argument("--version", help="Release version, e.g. 0.1.0. "
                                          "Defaults to the manifest version.")
    args = parser.parse_args()
    version = args.version or read_manifest_version()
    build(version)


if __name__ == "__main__":
    main()
