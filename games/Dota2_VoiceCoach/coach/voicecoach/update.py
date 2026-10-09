"""Обновление файлов игры с GitHub (решение Д14) — для копии без git: ИГРАТЬ.bat, скачанный отдельно, или ZIP.

  python update.py <папка игры>

Игрокам раздаётся не последний коммит ветки, а проверенный выпуск: файл RELEASE в папке игры на ветке хранит хеш
коммита, на котором прошли тесты (недоделанная работа на ветке к игрокам не уезжает). Ветку слили или удалили —
выпуск ищется на основной ветке. Список файлов папки игры этого коммита — два запроса к API GitHub (без ключа: до 60
запросов в час), сами файлы — с raw.githubusercontent.com, только новые и изменившиеся (папки coach/ и game/):
сверка по хешу git (SHA-1 от «blob <размер>\\0<содержимое>»), им же проверяется скачанное. Заменяются файлы только
после того, как скачались все: обрыв посреди обновления не смешивает старые файлы с новыми. Свои файлы (logs,
.runtime) не трогает. Нет сети — оставляет как есть. Только стандартная библиотека: запускается и без остального
кода игры.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = "131ymm-commits/Neu"
BRANCHES = ("ccr-9d6c6e9e-yuegyb", "main")          # рабочая ветка игры; её слили или удалили — основная
BRANCH = BRANCHES[0]
PREFIX = "games/Dota2_VoiceCoach/"
RELEASE = "RELEASE"                                  # в папке игры на ветке: хеш проверенного коммита
PARTS = ("coach/", "game/", "ИГРАТЬ.bat")
SKIP = ("coach/logs/", "coach/tests/", "game/tests/")       # тесты игре не нужны; журналы — свои
API = f"https://api.github.com/repos/{REPO}"
RAW = f"https://raw.githubusercontent.com/{REPO}/"
HEADERS = {"User-Agent": "DotaCoach-updater", "Accept": "application/vnd.github+json"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class NoRelease(OSError):
    """На GitHub нет файла RELEASE: выпуск не опубликован (дело не в интернете)."""


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _get(url: str, opener, timeout: float = 30, tries: int = 4, wait=time.sleep) -> bytes:
    """Тело ответа целиком. Обрыв связи или ответа, 429 и 5xx — повторить (до tries раз, с паузой): на 65 файлов
    разовый обрыв — обычное дело, а без повтора он отменял бы всё обновление. 404 и прочие 4xx — сразу ошибка."""
    for attempt in range(tries):
        try:
            with opener(urllib.request.Request(url, headers=HEADERS), timeout=timeout) as r:
                data = r.read()
                n = (getattr(r, "headers", None) or {}).get("Content-Length")
            if n is not None and str(n).isdigit() and int(n) != len(data):
                raise OSError(f"{url}: ответ оборвался ({len(data)} из {n} байт)")
            return data
        except urllib.error.HTTPError as e:
            if (e.code < 500 and e.code != 429) or attempt == tries - 1:
                raise
        except (OSError, http.client.HTTPException):
            if attempt == tries - 1:
                raise
        wait(1.0 + 2.0 * attempt)
    raise OSError(f"{url}: не скачалось")                # сюда не дойдёт: последняя попытка поднимает ошибку


def release(opener=urllib.request.urlopen) -> str:
    """Хеш выпуска: файл RELEASE рабочей ветки, а если ветки нет — основной."""
    for ref in BRANCHES:
        try:
            text = _get(RAW + urllib.parse.quote(ref) + "/" + urllib.parse.quote(PREFIX + RELEASE), opener)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
        sha = text.decode("ascii", "replace").split()[0] if text.strip() else ""
        if SHA_RE.match(sha):
            return sha
        raise ValueError(f"в RELEASE ветки {ref} не хеш коммита: {sha[:60]!r}")
    raise NoRelease("выпуск игры на GitHub не опубликован (нет файла RELEASE)")


def subtree(sha: str, opener=urllib.request.urlopen) -> dict:
    """Дерево папки игры в коммите sha: хеш папки — из списка её родителя, потом рекурсивное дерево только её."""
    parent, name = PREFIX.rstrip("/").rsplit("/", 1)
    listing = json.loads(_get(f"{API}/contents/{urllib.parse.quote(parent)}?ref={sha}", opener).decode("utf-8"))
    tree_sha = next((x.get("sha") for x in listing if isinstance(x, dict) and x.get("name") == name
                     and x.get("type") == "dir"), None)
    if not tree_sha:
        raise OSError(f"в выпуске {sha[:7]} нет папки {PREFIX}")
    tree = json.loads(_get(f"{API}/git/trees/{tree_sha}?recursive=1", opener).decode("utf-8"))
    if tree.get("truncated"):
        raise OSError("GitHub отдал неполный список файлов игры")
    return tree


def wanted(tree: dict) -> list[tuple[str, str]]:
    """(путь в папке игры, хеш git) файлов, которые нужны игре. Пути дерева — от папки игры."""
    out = []
    for t in tree.get("tree") or []:
        rel = str(t.get("path") or "")
        if t.get("type") != "blob":
            continue
        if any(rel.startswith(p) for p in PARTS) and not any(rel.startswith(s) for s in SKIP) and ".." not in rel:
            out.append((rel, str(t.get("sha"))))
    return out


def sync(dest: Path, opener=urllib.request.urlopen, log=print, workers: int = 4) -> tuple[int, int, str]:
    """Привести папку игры к выпуску на GitHub. → (скачано файлов, всего файлов игры, хеш выпуска).
    Любой сбой — исключение, и тогда ни один файл не заменён."""
    sha = release(opener)
    files = wanted(subtree(sha, opener))
    todo = []
    for rel, want in files:
        p = dest / rel
        try:
            if p.is_file() and blob_sha(p.read_bytes()) == want:
                continue
        except OSError:
            pass
        todo.append((rel, want))

    def get(item):
        rel, want = item
        data = _get(RAW + sha + "/" + urllib.parse.quote(PREFIX + rel), opener, timeout=60)
        if blob_sha(data) != want:
            raise OSError(f"{rel}: файл скачался не целиком")
        return rel, data

    if todo:
        log(f"Обновляю файлы игры: {len(todo)} из {len(files)}…")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            got = list(pool.map(get, todo))              # сбой любого файла — исключение здесь, до записи
        staged = []
        try:
            for rel, data in got:
                p = dest / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                tmp = p.with_name(p.name + ".part")
                tmp.write_bytes(data)
                staged.append((tmp, p))
            for tmp, p in staged:
                replace(tmp, p)
        finally:
            for tmp, _ in staged:
                tmp.unlink(missing_ok=True)              # недописанное не оставлять; заменённых .part уже нет
    return len(todo), len(files), sha


def replace(tmp: Path, p: Path, tries: int = 10, wait=time.sleep) -> None:
    """Заменить файл. Антивирус или облачная папка (OneDrive) держат файл секунду-другую — тогда повторить."""
    for attempt in range(tries):
        try:
            tmp.replace(p)
            return
        except PermissionError:
            if attempt == tries - 1:
                raise
            wait(0.5)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dest = Path(argv[0] if argv else Path(__file__).resolve().parents[2]).resolve()
    have = (dest / "coach" / "voicecoach" / "play.py").exists()
    try:
        n, total, sha = sync(dest)
        print(f"Файлы игры свежие (выпуск {sha[:7]}, файлов {total})." if not n
              else f"Обновлено файлов: {n} (выпуск {sha[:7]}).")
        return 0
    except Exception as e:                               # noqa: BLE001 — сеть, обрыв, лимит API, диск: играть дальше
        print(f"Не удалось обновить файлы игры с GitHub: {e}")
        if have:
            print("Играем на тех, что уже есть.")
            return 0
        print("Файлов игры нет — " + ("выпуск ещё не готов: запустите позже." if isinstance(e, NoRelease)
                                      else "проверьте интернет и запустите ещё раз."))
        return 1


if __name__ == "__main__":
    sys.exit(main())
