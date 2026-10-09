"""Обновление файлов игры с GitHub (решение Д14) — для копии без git: ИГРАТЬ.bat, скачанный отдельно, или ZIP.

  python update.py <папка игры>

Берёт список файлов ветки одним запросом к API GitHub (git/trees, без ключа: до 60 запросов в час) и качает с
raw.githubusercontent.com только новые и изменившиеся файлы папок coach/ и game/ — сверяет по хешу git (SHA-1 от
«blob <размер>\\0<содержимое>»), им же проверяет скачанное. Свои файлы (logs, .runtime) не трогает. Нет сети —
оставляет как есть. Только стандартная библиотека: запускается и без остального кода игры.
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = "131ymm-commits/Neu"
BRANCH = "ccr-9d6c6e9e-yuegyb"
PREFIX = "games/Dota2_VoiceCoach/"
PARTS = ("coach/", "game/", "ИГРАТЬ.bat")
SKIP = ("coach/logs/", "coach/tests/", "game/tests/")       # тесты игре не нужны; журналы — свои
API = f"https://api.github.com/repos/{REPO}/git/trees/{urllib.parse.quote(BRANCH)}?recursive=1"
RAW = f"https://raw.githubusercontent.com/{REPO}/{urllib.parse.quote(BRANCH)}/"
HEADERS = {"User-Agent": "DotaCoach-updater", "Accept": "application/vnd.github+json"}


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def wanted(tree: dict) -> list[tuple[str, str]]:
    """(путь в папке игры, хеш git) файлов, которые нужны игре."""
    out = []
    for t in tree.get("tree") or []:
        path = str(t.get("path") or "")
        if t.get("type") != "blob" or not path.startswith(PREFIX):
            continue
        rel = path[len(PREFIX):]
        if any(rel.startswith(p) for p in PARTS) and not any(rel.startswith(s) for s in SKIP) and ".." not in rel:
            out.append((rel, str(t.get("sha"))))
    return out


def sync(dest: Path, opener=urllib.request.urlopen, log=print, workers: int = 8) -> tuple[int, int]:
    """Привести папку игры к ветке на GitHub. → (скачано файлов, всего файлов игры)."""
    with opener(urllib.request.Request(API, headers=HEADERS), timeout=30) as r:
        tree = json.loads(r.read().decode("utf-8"))
    files = wanted(tree)
    todo = []
    for rel, sha in files:
        p = dest / rel
        try:
            if p.is_file() and blob_sha(p.read_bytes()) == sha:
                continue
        except OSError:
            pass
        todo.append((rel, sha))

    def get(item):
        rel, sha = item
        with opener(urllib.request.Request(RAW + urllib.parse.quote(PREFIX + rel), headers=HEADERS), timeout=60) as r:
            data = r.read()
        if blob_sha(data) != sha:
            raise OSError(f"{rel}: файл скачался не целиком")
        p = dest / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".part")
        tmp.write_bytes(data)
        tmp.replace(p)
        return rel

    if todo:
        log(f"Обновляю файлы игры: {len(todo)} из {len(files)}…")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(get, todo))
    return len(todo), len(files)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dest = Path(argv[0] if argv else Path(__file__).resolve().parents[2]).resolve()
    have = (dest / "coach" / "voicecoach" / "play.py").exists()
    try:
        n, total = sync(dest)
        print(f"Файлы игры свежие ({total})." if not n else f"Обновлено файлов: {n}.")
        return 0
    except (OSError, ValueError, KeyError) as e:                  # urllib.error.URLError — подкласс OSError
        print(f"Не удалось обновить файлы игры с GitHub: {e}")
        if have:
            print("Играем на тех, что уже есть.")
            return 0
        print("Файлов игры нет — проверьте интернет и запустите ещё раз.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
