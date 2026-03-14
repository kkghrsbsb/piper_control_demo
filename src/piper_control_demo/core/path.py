from pathlib import Path

def find_project_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p
    raise RuntimeError("Project root not found")

# .git 为根目录
ROOT = find_project_root(Path(__file__).resolve())

ASSETS_DIR = ROOT / "assets"
CONFIG_DIR = ROOT / "configs"

ROBOTS_DIR = ASSETS_DIR / "robots"

PIPER_DESCRIPTION_DIR = ROBOTS_DIR / "piper_description"

# ./assets/robots/piper_description/urdf
PIPER_DESCRIPTION_URDF_DIR = PIPER_DESCRIPTION_DIR / "urdf"