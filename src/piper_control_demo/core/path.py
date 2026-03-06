from pathlib import Path

def find_project_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p
    raise RuntimeError("Project root not found")

# .git 为根目录
ROOT = find_project_root(Path(__file__).resolve())
