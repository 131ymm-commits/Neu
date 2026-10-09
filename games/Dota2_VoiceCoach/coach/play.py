"""Точка входа лаунчера «игра вдвоём» (решение Д14): ИГРАТЬ.bat запускает  python play.py.
Путь к пакету — свой: у переносного Python из .runtime чужие папки в sys.path не попадают."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from voicecoach.play import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
