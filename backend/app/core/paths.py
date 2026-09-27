from pathlib import Path


def project_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in (
        Path("/app"),
        here.parents[3],  # .../app/core/paths.py -> repo root locally
        here.parents[2],
        Path.cwd(),
    ):
        if (candidate / "data" / "knowledge").exists() or (candidate / "app").exists():
            if (candidate / "data").exists():
                return candidate
    return Path("/app") if Path("/app/data").exists() else here.parents[3]


def data_dir() -> Path:
    return project_root() / "data"


def knowledge_dir() -> Path:
    return data_dir() / "knowledge"


def seed_dir() -> Path:
    return data_dir() / "seed"
