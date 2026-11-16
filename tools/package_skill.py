"""Zip the skill into dist/vinci.zip for uploading to Claude.

The zip holds one folder, vinci/, with SKILL.md at its root.

    python tools/package_skill.py
"""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "vinci"


def main() -> None:
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / "vinci.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(SKILL.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.name != ".DS_Store":
                zf.write(f, Path("vinci") / f.relative_to(SKILL))
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
