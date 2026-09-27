from pathlib import Path
from shutil import copyfile
import sys

# Allow `python -m scripts.seed_cli` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal, init_db
from scripts.seed import seed_database


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        print(seed_database(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
