"""Игра вдвоём одним файлом (решение Д14). Слова автора, 09.10.2026: «все очень сложно сделай нормальный вход и
конект. это просто ужас. придумай сам как сделать. я должен запустить один файл и опонент должен запустить один
файл все остальное делаеш ты».

Хост запускает ИГРАТЬ.bat — он находит или скачивает Python, обновляет файлы игры и запускает этот лаунчер:
  1. Claude для героев (Д23): есть ключ API — по ключу (быстро: модель без думания, ответ за секунды, платно); ключа
     нет — один вопрос (вставить ключ; Enter — по подписке, спросит снова; 0 — больше не спрашивать), дальше — вход
     подпиской в Claude Code (Д15: лаунчер ставит Claude Code и запускает вход; из общих лимитов подписки, ответ
     5–8 с); не вышло — правила. --rules — правила (бесплатно, не Claude); --api — только ключ; --ask-key — сменить ключ;
  2. ставит кастомку в Доту (папку Доты ищет сам, не нашёл — спрашивает);
  3. скачивает cloudflared (туннель Cloudflare) в .runtime/ — один раз;
  4. запускает сервер тренера, пульт Тьмы и туннель; ссылку на пульт кладёт в ящик (rendezvous.py) и копирует;
     туннель упал — поднимает заново;
  5. делает файл соперника ДЛЯ_ДРУГА.html — один раз, подходит ко всем играм — и показывает его в Проводнике;
  6. запускает Доту с инструментами и сразу кастомку (так запускает аддоны шаблон ModDota: dota2.exe -tools -addon).
Соперник открывает ДЛЯ_ДРУГА.html: файл находит игру в ящике и открывает пульт; перезапуск игры пульт переживает.
Закончить игру — Enter два раза в окне лаунчера.
"""
from __future__ import annotations

import argparse
import atexit
import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from . import rendezvous as RV
from . import learning as LRN
from . import report as RPT
from .agents import AgentHub, ApiBackend, CliBackend, make_backend
from .ai_coach import AICoach, ClaudeCoach, RulesCoach
from .console import console_url, load_keys, serve_console, start_tunnel
from .server import LOGS, serve

COACH = Path(__file__).resolve().parent.parent
PROJECT = COACH.parent
WEB = COACH / "web"
RUNTIME = PROJECT / ".runtime"
CONFIG = LOGS / "play.json"
FRIEND_FILE = "ДЛЯ_ДРУГА.html"
ADDON = "voicecoach"
GAME_PORT, CONSOLE_PORT = 8787, 8788          # 8787 — адрес, который знает кастомка (coach_game.lua)
HEALTH = f"http://127.0.0.1:{GAME_PORT}/api/health"
REMOTE = "dire"                                # хост в Доте — тренер Света, друг — Тьмы
MAX_CALLS = 15000                              # по ключу API: вызовов на сторону за запуск (≈ 75 минут без пауз)
# по ключу API — быстро (Д23, слова автора: «в общем если мы не можем сделать по апи смысла нет слишком большое время на
# принятие решения»): думание модели выключено (по подписке Claude Code его не выключает), решение — сразу после
# прошлого ответа, все 10 сразу
API_PACE = {"period": 0.0, "dead_period": 5.0, "min_gap": 0.5, "error_gap": 5.0, "max_inflight": 10}
API_THINKING = "disabled"                      # у быстрой модели принимается при effort не выше high
API_EFFORT = "low"
# $ за 1M токенов быстрой модели (Haiku 5.5, справка claude-api от 06.10.2026): для оценки расхода в окне
API_PRICES = {"in": 0.10, "out": 0.50, "cache_read": 0.01, "cache_write": 0.125}
API_CALL_USD = 0.00026                         # оценка одного решения: ~8000 токенов промпта из кэша, ~1000 входа, ~150 выхода
TRIAL_OBS = {"team": "radiant", "pos": 1, "hero": "npc_dota_hero_sniper", "clock": 60, "alive": True, "lvl": 1,
             "hp": [560, 560], "mp": [255, 255], "gold": 300, "where": "бот, своя половина", "doing": "фарм бот",
             "stats": {"lh": 0, "dn": 0, "k": 0, "d": 0, "a": 0, "seen": 0, "idle": 0}, "enemies": [], "allies": [],
             "abilities": [], "items": [], "events": [], "coach": [],
             "enemy_team": ["luna", "lina", "bristleback", "witch_doctor", "jakiro"]}
SUB_MAX_CALLS = 3000                           # по подписке: вызовов на сторону за запуск (≈ час непрерывной игры); дальше
                                               # руки и правила — лимиты подписки общие с чатом автора (Д22)
# максимально быстро по подписке (Д22, слова автора: «нет давай максимально быстро без апи»): каждый герой спрашивает
# Claude, как только пришёл прошлый ответ, все 10 сразу; руки выполняют решение 4 раза в секунду. Замер 11.10.2026
# (Claude Code 2.1.296, быстрая модель, промпт «СКОРОСТЬ» и --effort low): ответ — медиана 4.9 с (2.8–15.4 с);
# игра держит решение 20 с — запасной исполнитель не перехватывает героев между решениями
SUB_PACE = {"period": 0.0, "dead_period": 10.0, "min_gap": 0.5, "error_gap": 10.0, "max_inflight": 10}
SUB_EFFORT = "low"                             # меньше думания у быстрой модели: ответ быстрее (замер Д22)
CLAUDE_FAST = "haiku"                          # имя линии быстрых моделей для `claude --model`
COACH_MAX_CALLS = 60                           # ИИ-тренер соперника: вызовов Claude за запуск (≈ раз в минуту), дальше правила
KEY_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")   # по подписке их нельзя отдавать claude: -p платит ключом
CREDITS_PAGE = "https://claude.ai/settings/billing"        # подписка Max → «API credits»: привязать организацию Console
KEYS_PAGE = "https://platform.claude.com/settings/keys"    # Console → API Keys → Create Key
# ключ со Scope «Organization» (без рабочей области) требует заголовок anthropic-workspace-id в каждом запросе, иначе 400
# (справка Authentication, 12.10.2026); лаунчер его не шлёт — нужен ключ со Scope «Default workspace» (ERRORS №113)
WORKSPACE_ERR = "anthropic-workspace-id"
WORKSPACE_HINT = ("ключ создан на всю организацию (Scope: Organization) — создайте ключ со Scope: Default workspace "
                  "(platform.claude.com → API Keys → Create Key)")
# ключ в файле рядом с ИГРАТЬ.bat — когда вставка в окно лаунчера не работает (ERRORS №114): папка bat — над папкой игры,
# если bat скачан один (DotaCoach рядом с ним), или сама папка игры
KEY_FILES = ("ключ.txt", "key.txt", "ключ.txt.txt", "key.txt.txt")
_KEY_RE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}")
KEY_ASK = 23                                   # с Д23 "api_key": "" — «0, больше не спрашивать ключ»; до Д23 это было
                                               # «без Claude»: выпуски 4351ded и b6988a1 писали его на Enter, меню Д15 и
                                               # выпуски c1e0689…fd2c348 (--api, --ask-key) — на «0»; такой play.json —
                                               # спросить ключ ещё один раз
open_page = webbrowser.open
MODELS_API = "https://api.anthropic.com/v1/models"
FAST_LINE = "haiku"                            # линия самых быстрых моделей: ищется в имени (id) модели из списка
CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
DETACHED = 0x00000008 | 0x00000200            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: Дота живёт без окна
LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({})).open   # свой ПК — мимо прокси системы


_SAY = threading.Lock()
_LOG = None                                            # копия окна хоста в coach\logs\launcher_*.log (ERRORS №103)


def say(text: str = "") -> None:
    """Строка в окно хоста. Пишут несколько потоков (журнал Доты, ожидание Workshop Tools, сводка) — одной записью
    под замком, чтобы строки не склеивались (рецензия 7)."""
    out = sys.stdout
    with _SAY:
        if _LOG is not None:                           # копия окна — без ключа пульта друга, имени пользователя
            try:                                       # и адреса туннеля: её присылают (рецензия 11б)
                _LOG.write(f"{RPT.scrub(text)}\n")
            except (OSError, ValueError):
                pass
        if out is None:                                # без консоли (pythonw) писать некуда — как print()
            return
        out.write(f"{text}\n")
        out.flush()


def open_window_log(path: Path) -> Path | None:
    """Окно хоста — ещё и в файл: по нему видно, что было на старте (шаг 1/6: Claude или правила), когда окно
    закрыто (ERRORS №103: причину, почему героями правили правила, по снимку конца окна было не узнать)."""
    global _LOG
    with _SAY:
        if _LOG is not None:
            try:
                _LOG.close()
            except OSError:
                pass
            _LOG = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            _LOG = open(path, "a", encoding="utf-8", buffering=1)
        except OSError:
            return None
    return path


def close_window_log() -> None:
    """Файл окна закрыть (конец main: иначе на Windows папку с ним не удалить, пока жив процесс)."""
    global _LOG
    with _SAY:
        if _LOG is not None:
            try:
                _LOG.close()
            except OSError:
                pass
            _LOG = None


def _ask(ask, prompt: str) -> str | None:
    """Ответ человека. Ctrl+C или окно без ввода (запуск не из консоли) — None: человек ничего не выбрал."""
    try:
        return (ask(prompt) or "").strip()
    except (EOFError, KeyboardInterrupt):
        return None


def flush_input() -> None:
    """Windows: выбросить нажатое заранее — Enter, нажатый во время закачки, не должен ни на что ответить."""
    if os.name != "nt":
        return
    try:
        import msvcrt  # noqa: PLC0415
        while msvcrt.kbhit():
            msvcrt.getwch()
    except Exception:                                   # noqa: BLE001 — не консоль: нечего чистить
        pass


# --- настройки ---

def load_config(path: Path | None = None) -> dict:
    path = path or CONFIG
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(cfg: dict, path: Path | None = None) -> None:
    path = path or CONFIG
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


# --- Claude ---

def mask(key: str) -> str:
    """Ключ для экрана: начало и четыре последних знака (окно хоста могут прислать в чат — ключ туда не попадёт)."""
    return f"{key[:7]}…{key[-4:]}" if len(key) > 16 else "…"


def api_error(e: urllib.error.HTTPError) -> str:
    """Ошибка API Anthropic словами: код и текст из ответа ({"error": {"message": …}})."""
    text = ""
    try:
        body = json.loads(e.read().decode("utf-8", "replace"))
        text = str(((body or {}).get("error") or {}).get("message") or "")
    except Exception:                                   # noqa: BLE001 — нет тела или не JSON
        pass
    hint = {401: "ключ не принят", 403: "ключу запрещён доступ"}.get(e.code, "ошибка API")
    return f"{hint} (HTTP {e.code}{': ' + text[:200] if text else ''})"


def pick_model(api_key: str, opener=urllib.request.urlopen) -> tuple[str | None, str, str]:
    """Самая новая модель линии быстрых из списка моделей, доступных ключу.
    → (модель или None, почему нет, вид сбоя: "" — всё хорошо, "key" — ключ не принят (401/403),
       "net" — нет связи или сбой API, "none" — среди моделей нет быстрой линии)."""
    if not looks_like_key(api_key):                     # «нет», кириллица, пробелы — не ключ, а не «нет связи»
        return None, "это не ключ API (русские буквы, пробелы или слишком коротко)", "key"
    req = urllib.request.Request(MODELS_API + "?limit=100",
                                 headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"})
    try:
        with opener(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        why = api_error(e)
        if WORKSPACE_ERR in why:                        # ключ на всю организацию: лаунчер не шлёт рабочую область
            return None, WORKSPACE_HINT, "key"
        return None, why, "key" if e.code in (401, 403) else "net"
    except UnicodeError:                                # кириллица или пробелы в «ключе» — заголовок не собрать
        return None, "это не ключ API (в нём русские буквы или пробелы)", "key"
    except (OSError, ValueError) as e:
        return None, f"нет связи с API Anthropic ({e})", "net"
    models = [m for m in (data.get("data") if isinstance(data, dict) else None) or []
              if isinstance(m, dict) and m.get("id")]
    fast = [m for m in models if FAST_LINE in str(m["id"]).lower()]
    if not fast:
        return None, "среди моделей ключа нет быстрой линии", "none"
    return max(fast, key=lambda m: str(m.get("created_at") or ""))["id"], "", ""


def probe_key(key: str, model: str, opener=urllib.request.urlopen) -> tuple[bool, str]:
    """Есть ли у ключа кредит: крошечный запрос (1 токен ответа, доли цента). Список моделей отвечает и без
    кредита — без этой пробы весь матч прошёл бы на паузе «кредит кончился». → (можно играть, почему нет)."""
    body = json.dumps({"model": model, "max_tokens": 1, "messages": [{"role": "user", "content": "ok"}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST",
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    try:
        with opener(req, timeout=30) as r:
            r.read()
        return True, ""
    except urllib.error.HTTPError as e:
        why = api_error(e)
        if "credit balance" in why.lower():
            return False, "nocredit"
        if WORKSPACE_ERR in why:
            return False, WORKSPACE_HINT
        return e.code not in (400, 401, 403), why        # 429, 5xx — ключ рабочий, просто занято
    except UnicodeError:
        return False, "это не ключ API"
    except (OSError, ValueError) as e:
        return True, f"нет связи ({e})"                  # проверим в игре


def no_credit_help(saved: bool = True) -> None:
    say("  На балансе организации Console, где создан этот ключ, нет денег на API. В подписку Max входит кредит на API")
    say("  (claude.ai в браузере → Settings → Billing → «API credits»); он приходит в одну организацию — ключ нужен из неё")
    say("  (platform.claude.com, вверху переключить организацию). Без кредита — пополнить: platform.claude.com → Billing.")
    if saved:
        say("  Этот ключ сохранил: как только на балансе появятся деньги, герои заработают по ключу.")


def looks_like_key(key: str) -> bool:
    """Похоже ли на ключ API: латиница, цифры и знаки, без пробелов, не короче 20 знаков."""
    return len(key) >= 20 and key.isascii() and key.isprintable() and not any(c.isspace() for c in key)


def clipboard_text() -> str:
    """Текст из буфера обмена Windows: WinAPI через ctypes, запасной путь — PowerShell Get-Clipboard; не Windows или не
    вышло — пустая строка."""
    if os.name != "nt":
        return ""
    opened = False
    try:
        import ctypes                                    # noqa: PLC0415
        from ctypes import wintypes                      # noqa: PLC0415
        user32, kernel32 = ctypes.WinDLL("user32"), ctypes.WinDLL("kernel32")
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        if user32.OpenClipboard(None):
            opened = True
            try:
                handle = user32.GetClipboardData(13)      # CF_UNICODETEXT
                ptr = kernel32.GlobalLock(handle) if handle else None
                if ptr:
                    try:
                        return ctypes.wstring_at(ptr)
                    finally:
                        kernel32.GlobalUnlock(handle)
            finally:
                user32.CloseClipboard()
    except Exception:                                    # noqa: BLE001 — нет буфера, не текст, другая ОС
        opened = False
    if opened:                                           # буфер открылся, текста в нём нет
        return ""
    try:                                                 # запасной путь: PowerShell (есть в Windows 10 и 11)
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Clipboard -Raw"],
                           capture_output=True, stdin=subprocess.DEVNULL, timeout=10,
                           creationflags=0x08000000)     # CREATE_NO_WINDOW
        return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""
    except Exception:                                    # noqa: BLE001
        return ""


def read_secret(prompt: str, getch=None, putch=None, clipboard=None) -> str:
    """Скрытый ввод ключа. Windows: вместо знаков — звёздочки (видно, что вставка сработала); Ctrl+V вставляет из буфера
    обмена сам лаунчер — в классической консоли Windows Ctrl+V приходит символом 0x16, а не текстом (ERRORS №114).
    Пробелы и переводы строк не берутся; стрелки и F-клавиши не пишутся; Ctrl+C — KeyboardInterrupt.
    Не Windows или не консоль — getpass."""
    if getch is None:
        if os.name != "nt" or not sys.stdin.isatty():
            return getpass.getpass(prompt)
        import msvcrt                                    # noqa: PLC0415
        getch, putch = msvcrt.getwch, msvcrt.putwch
    for c in prompt:
        putch(c)
    chars: list[str] = []
    while True:
        c = getch()
        if c in ("\r", "\n"):
            break
        if c == "\x03":
            raise KeyboardInterrupt
        if c in ("\x00", "\xe0"):                         # стрелки, F1…: следом — код клавиши
            getch()
            continue
        if c == "\b":
            if chars:
                chars.pop()
                for x in "\b \b":
                    putch(x)
            continue
        text = c
        if c == "\x16":                                  # Ctrl+V в классической консоли: буфер обмена — сами
            text = ((clipboard or clipboard_text)() or "")[:1000]
            if not text.strip():
                for x in " (в буфере обмена нет текста) ":
                    putch(x)
        for x in text:
            if x.isprintable() and not x.isspace():
                chars.append(x)
                putch("*")
    putch("\r")
    putch("\n")
    return "".join(chars)


def user_dirs() -> list[Path]:
    """Куда Блокнот сохраняет сам: Документы, Рабочий стол, Загрузки — и они же в OneDrive."""
    roots = [Path.home()] + [Path(os.environ[v]) for v in ("OneDrive", "OneDriveConsumer") if os.environ.get(v)]
    names = ("Documents", "Desktop", "Downloads", "Документы", "Рабочий стол", "Загрузки")
    return [r / n for r in roots for n in names]


def key_mark(key: str) -> str:
    """Отпечаток ключа (не сам ключ): запомнить в настройках ключ, который не подошёл, — чтобы не предлагать его снова."""
    return hashlib.sha256(key.encode("utf-8", "replace")).hexdigest()[:16]


def forget_bad(cfg: dict, key: str) -> None:
    cfg["bad_key"] = key_mark(key)
    try:
        save_config(cfg)
    except OSError:
        pass


def key_files(dirs=None) -> list[Path]:
    """Файлы с ключом, какие есть: ключ.txt (key.txt) в папке игры, потом над ней — там лежит ИГРАТЬ.bat, если он скачан
    один (игра — в папке DotaCoach рядом с ним); потом «ключ.txt» в Документах, на рабочем столе и в Загрузках (Блокнот
    сохраняет туда, если папку не выбрать; key.txt там — чужой)."""
    places = [(Path(d), KEY_FILES) for d in (dirs or (PROJECT, PROJECT.parent))]
    if dirs is None:
        places += [(d, KEY_FILES[0::2]) for d in user_dirs()]
    found = []
    for d, names in places:
        for name in names:
            try:
                if (d / name).is_file() and d / name not in found:
                    found.append(d / name)
            except OSError:                              # нет доступа к папке — дальше
                continue
    return found


def read_key_text(path: Path) -> str:
    """Текст файла Блокнота: UTF-8 с BOM и без, ANSI, «Юникод» (UTF-16)."""
    raw = path.read_bytes()[:20000]
    return (raw.decode("utf-16", "replace") if raw[:2] in (b"\xff\xfe", b"\xfe\xff")
            else raw.decode("utf-8-sig", "replace"))


def take_key_file(cfg: dict, opener=urllib.request.urlopen, probe=probe_key, dirs=None):
    """Ключ из файла «ключ.txt» — для окна, где вставка в скрытый ввод не работает (ERRORS №114); новый файл заменяет и
    сохранённый ключ. Берётся только строка вида sk-ant-… (key.txt без неё — чужой файл: не трогать, никуда не слать).
    Подошёл — ключ в настройках игры; файл удаляется, если в нём только ключ (ключ не лежит открыто рядом с игрой).
    → None — файла с ключом нет; (ключ, модель) — играть по ключу; (None, None) — файл есть, по ключу не вышло."""
    path = key = None
    only = False
    near = [Path(d) for d in (dirs or (PROJECT, PROJECT.parent))]
    empty = None                                         # «ключ.txt» у игры без ключа: сказать, если ключа нет нигде
    for p in key_files(dirs):
        try:
            text = read_key_text(p)
        except OSError:
            continue
        m = _KEY_RE.search(text)
        if m and looks_like_key(m.group(0)):
            path, key, only = p, m.group(0), text.strip() == m.group(0)
            break
        if p.name.startswith("ключ") and p.parent in near and empty is None:
            empty = p                                    # в Документах и прочих — чужой файл: молча мимо
    if path is None:
        if empty is None:
            return None
        say(f"  В файле «{empty.name}» в папке «{empty.parent.name}» не ключ: ключ — длинная строка латиницей, начинается")
        say("  с sk-ant-. Откройте файл Блокнотом, вставьте ключ (Ctrl+V), сохраните и запустите ИГРАТЬ.bat снова.")
        return None, None
    where = f"«{path.name}» в папке «{path.parent.name}»"
    if key == cfg.get("api_key") and cfg.get("model"):  # этот ключ уже в настройках: файл не нужен
        if only:
            try:
                path.unlink()
            except OSError:
                pass
        return None
    model, why, kind = pick_model(key, opener)
    if not model:
        if kind == "net":                                # прежний рабочий ключ непроверенным не затирать
            say(f"  Ключ {mask(key)} из файла {where} проверить не смог: {why}. Файл оставил — проверю при")
            say("  следующем запуске.")
        else:
            say(f"  Ключ {mask(key)} из файла {where} не подошёл: {why}.")
            say("  Создайте новый ключ (platform.claude.com → API Keys, Scope — Default workspace), вставьте его в файл вместо")
            say("  старого и запустите ИГРАТЬ.bat снова.")
        return None, None
    cfg["api_key"], cfg["model"] = key, model
    save_config(cfg)
    if not only:
        note = "в файле есть и другой текст — файл не трогал, уберите из него ключ сами"
    else:
        try:
            path.unlink()
            note = "файл удалил"
        except OSError:
            note = "файл удалить не смог — удалите его сами"
    say(f"  Ключ {mask(key)} из файла {where} сохранён в настройках игры; {note}.")
    ok, why = probe(key, model, opener)
    if why == "nocredit":
        no_credit_help()
        return None, None
    if not ok:
        say(f"  Пробный запрос по ключу не прошёл: {why}. В этот раз — без ключа.")
        return None, None
    say("  Ключ принят.")
    return key, model


def ask_key(cfg: dict, ask, opener, keep: bool = False, probe=probe_key, clipboard=None,
            rejected: str | None = None) -> tuple[str | None, str | None] | None:
    """Спросить ключ; он проверяется списком моделей и крошечным запросом (есть ли кредит).
    Пустой Enter — «не сейчас» (ничего не запоминается; при смене ключа, keep=True, — оставить как было → None);
    «0» — без Claude (запоминается). Нет связи — новый ключ сохраняется (проверится в следующий раз), но рабочий
    прежний им не затирается; Ctrl+C — ничего не менять."""
    flush_input()                                        # Enter, нажатый во время закачки, — не ответ
    if not cfg.get("api_key"):
        say("  Быстрые агенты — по ключу API: Claude отвечает за 1–2 с (оценка; по подписке — 5–8 с), герой решает раз в")
        say("  1,5–2 с. Настоящее время ответа лаунчер покажет пробой сразу после ключа.")
        say("  Цена — около $3–4 за 40-минутный матч (оценка). В подписку Max входит кредит на API ($100 в месяц у Max 5x):")
        say("  claude.ai в браузере → Settings → Billing → «API credits»; без него — пополнить: platform.claude.com → Billing.")
        say(f"  Ключ: {KEYS_PAGE} → Create Key (Scope — Default workspace), скопировать.")
    found = _KEY_RE.search((clipboard or clipboard_text)() or "")   # ключ скопирован — вставлять не нужно (№114)
    clip_key = found.group(0) if found and looks_like_key(found.group(0)) else None
    if clip_key and (clip_key in (cfg.get("api_key"), rejected) or key_mark(clip_key) == cfg.get("bad_key")):
        clip_key = None                                  # тот, что уже не подошёл, — не предлагать
    flush_input()                                        # Enter, нажатый, пока читался буфер, — не ответ
    if clip_key:
        say(f"  В буфере обмена есть ключ {mask(clip_key)}. Взять его — просто Enter; не брать — н и Enter.")
        a = _ask(ask, "  > ")
        if a is None:
            return None if keep else (None, None)        # Ctrl+C
        if looks_like_key(a):                            # вставили ключ сами — его и взять
            clip_key = a
        elif a and a.lower() not in ("д", "да", "y", "yes"):   # Enter, «д», «да» — взять
            clip_key = None

    def howto():
        say("  Скопируйте ключ (Ctrl+C) и запустите ИГРАТЬ.bat снова — лаунчер возьмёт его из буфера обмена сам. Или вставьте")
        say("  ключ сюда (правый щелчок мыши или Ctrl+V) и нажмите Enter — вместо ключа на экране будут звёздочки.")
        say(f"  Не вставляется — закройте это окно, сохраните ключ Блокнотом в файл «{KEY_FILES[0]}» рядом с ИГРАТЬ.bat и")
        say("  запустите ИГРАТЬ.bat снова.")
        if keep:
            say("  Оставить как было — просто Enter. Больше не играть по ключу — 0 и Enter.")
        else:
            say("  Ключа нет — просто Enter: сыграют агенты по подписке (медленнее), ключ спрошу при следующем запуске.")
            say("  Больше не спрашивать ключ — 0 и Enter.")
    if not clip_key:
        howto()
    for _ in range(3):
        key, from_clip, clip_key = clip_key or _ask(ask, "  ключ> "), bool(clip_key), None
        if key is None or (not key and keep):
            return None if keep else (None, None)        # Ctrl+C или «оставить как было»
        if not key:
            say("  Хорошо, в этот раз без ключа. Ключ спрошу при следующем запуске.")
            return None, None
        if key == "0":
            cfg["api_key"] = ""                          # «без Claude»: при запуске можно будет сменить
            save_config(cfg)
            return None, None
        if not looks_like_key(key):
            say(f"  Это не похоже на ключ (пришло знаков: {len(key)}): ключ — длинная строка латиницей, начинается с sk-ant-.")
            say("  Скопируйте его ещё раз на platform.claude.com → API Keys (при создании он показывается один раз) и вставьте")
            say(f"  сюда; не вставляется — файл «{KEY_FILES[0]}» рядом с ИГРАТЬ.bat (см. выше).")
            continue
        model, why, kind = pick_model(key, opener)
        if model:
            cfg["api_key"], cfg["model"] = key, model
            save_config(cfg)
            ok, why = probe(key, model, opener)
            if why == "nocredit":
                no_credit_help()
                say("  Вставьте ключ из организации с деньгами на балансе — или Enter: в этот раз без ключа.")
                continue
            if not ok:
                say(f"  Ключ {mask(key)} сохранил, но пробный запрос не прошёл: {why}. В этот раз — без ключа.")
                return None, None
            say(f"  Ключ {mask(key)} принят.")
            return key, model
        if kind == "net":
            if keep and cfg.get("api_key"):
                say(f"  Не смог проверить новый ключ: {why}. Оставляю прежний — смените при следующем запуске.")
                return None
            cfg["api_key"] = key
            save_config(cfg)
            say(f"  Ключ {mask(key)} сохранил, но проверить не смог: {why}.")
            say("  В этот раз — без ключа, по ключу — со следующего запуска.")
            return None, None
        if kind == "key":
            forget_bad(cfg, key)                         # из буфера его больше не предлагать
        say(f"  Ключ {mask(key)} не подошёл: {why}. Вставьте другой" + (" или Enter — оставить как было."
                                                                       if keep else " или Enter — не сейчас."))
        if from_clip:
            howto()
    if keep:
        say("  Ключи не подошли — оставляю прежний.")
        return None
    say("  Ключи не подошли — в этот раз без ключа. Ключ спрошу при следующем запуске.")
    return None, None


def setup_claude(cfg: dict, args, ask=None, opener=urllib.request.urlopen,
                 probe=probe_key) -> tuple[str | None, str | None]:
    """Ключ и модель для агентов. → (ключ, модель) или (None, None) — играть на правилах."""
    ask = ask or read_secret
    if args.rules:
        return None, None
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        key = cfg.get("api_key")
        if key is None:
            return ask_key(cfg, ask, opener, probe=probe)
        if args.ask_key:                                 # сменить ключ (Enter — оставить как было)
            got = ask_key(cfg, ask, opener, keep=bool(key), probe=probe)
            if got is not None:
                return got
            say("  Оставляю как было.")
    if not key:
        return None, None
    model, why, kind = pick_model(key, opener)
    if model:
        if model != cfg.get("model"):
            cfg["model"] = model
            save_config(cfg)
        ok, why = probe(key, model, opener)
        if why == "nocredit":
            env = bool(os.environ.get("ANTHROPIC_API_KEY"))
            no_credit_help(saved=not env)
            if not env:
                say("  Можно сразу вставить ключ из организации с кредитом.")
                got = ask_key(cfg, ask, opener, keep=True, probe=probe)
                if got is not None:
                    return got
            say("  В этот раз — без ключа.")
            return None, None
        if not ok:
            say(f"  Пробный запрос к Claude не прошёл: {why}. В этот раз — без ключа.")
            return None, None
        return key, model
    if kind == "key" and not os.environ.get("ANTHROPIC_API_KEY"):
        say(f"  Сохранённый ключ {mask(key)} не подошёл: {why}.")
        cfg.pop("api_key", None)
        forget_bad(cfg, key)
        return ask_key(cfg, ask, opener, probe=probe, rejected=key)
    if kind == "net" and cfg.get("model"):
        say(f"  Список моделей недоступен ({why}) — беру прошлую модель.")
        return key, cfg["model"]
    say(f"  Claude по ключу: {why} — в этот раз без ключа.")
    return None, None


# --- Claude по подписке (Claude Code) ---

def find_claude(which=shutil.which, home: Path | None = None) -> str | None:
    """Claude Code: из PATH или из папки, куда его ставит официальный установщик (~/.local/bin) — PATH окна
    лаунчера после установки ещё старый."""
    home = home or Path(os.environ.get("USERPROFILE") or Path.home())
    for name in ("claude.exe", "claude"):                  # сначала родной claude от установщика Anthropic
        cand = home / ".local" / "bin" / name
        if cand.is_file():
            return str(cand)
    found = which("claude")
    if found and not found.lower().endswith((".cmd", ".bat")):   # обёртку npm запускает cmd.exe — ломает кавычки
        return found
    return None


def install_claude(run=subprocess.run) -> bool:
    """Поставить Claude Code официальным установщиком Anthropic (Windows, PowerShell; его вывод — в этом окне)."""
    if os.name != "nt":
        return False
    try:
        return run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                    "irm https://claude.ai/install.ps1 | iex"], timeout=900).returncode == 0
    except Exception:                                   # noqa: BLE001 — нет PowerShell, таймаут: скажем хосту
        return False


def no_key_env() -> dict:
    """Окружение для claude без ключей API: с ключом в окружении `claude -p` платит ключом, а не подпиской."""
    return {k: v for k, v in os.environ.items() if k not in KEY_VARS}


def claude_auth(exe: str, run=subprocess.run) -> dict:
    """`claude auth status` → {"loggedIn": …, "authMethod": …}; не разобрали — {}."""
    try:
        p = run([exe, "auth", "status"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30, env=no_key_env())
        data = json.loads(p.stdout)
    except Exception:                                   # noqa: BLE001 — старая версия, не запустился
        return {}
    return data if isinstance(data, dict) else {}


def claude_login(exe: str, run=subprocess.run) -> bool:
    """Вход подпиской: `claude auth login --claudeai` — откроет браузер; лаунчер ждёт, пока человек войдёт."""
    try:
        return run([exe, "auth", "login", "--claudeai"], timeout=900, env=no_key_env()).returncode == 0
    except Exception:                                   # noqa: BLE001
        return False


def claude_update(exe: str, run=subprocess.run) -> bool:
    """`claude update` — обновить Claude Code (старая версия не знает ключей, с которыми игра его зовёт)."""
    try:
        return run([exe, "update"], timeout=600, env=no_key_env()).returncode == 0
    except Exception:                                   # noqa: BLE001
        return False


PROBE_SCHEMA = {"type": "object", "properties": {"ready": {"type": "boolean"}}, "required": ["ready"],
                "additionalProperties": False}


def claude_check(exe: str, run=subprocess.run) -> tuple[bool, str]:
    """Пробный вызов `claude -p` быстрой моделью теми же ключами, что у агентов (файл системного промпта, схема ответа,
    запрет MCP): старая версия, не знающая одного из них, пробу не пройдёт, и лаунчер её обновит (рецензия 11б).
    5–15 с, капля лимита подписки."""
    cli = CliBackend(model=CLAUDE_FAST, claude=exe, timeout=120, subscription=True, which=lambda n: None,
                     effort=SUB_EFFORT)
    try:
        p = run(cli.argv("Проверка связи игры: ответь по схеме, ready = true.", PROBE_SCHEMA, "Готов?"), input="",
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, cwd=cli.cwd,
                env=no_key_env())
    except Exception as e:                              # noqa: BLE001 — не запустился, завис
        return False, f"не запустился ({e})"
    try:
        data = json.loads(p.stdout)
    except ValueError:
        return False, ((p.stderr or p.stdout or "").strip() or f"код выхода {p.returncode}")[:300]
    if not isinstance(data, dict) or data.get("is_error"):
        return False, str((data or {}).get("result") or "ошибка")[:300]
    return True, ""


def setup_subscription(find=find_claude, install=install_claude, auth=claude_auth, login=claude_login,
                       check=claude_check, update=claude_update) -> str | None:
    """Claude Code со входом подпиской: найти или поставить, войти (браузер), проверить пробным вызовом.
    → путь к claude или None (в этот раз — правила). Ctrl+C на любом шаге — пропустить: в этот раз правила."""
    try:
        return _setup_subscription(find, install, auth, login, check, update)
    except KeyboardInterrupt:
        say("")
        say("  Пропускаю Claude Code — в этот раз героев ведут правила; поставлю при следующем запуске.")
        return None


def _setup_subscription(find, install, auth, login, check, update=lambda exe: False) -> str | None:
    exe = find()
    if exe is None:
        say("  Игре нужен Claude Code для командной строки — отдельная маленькая программа Anthropic, входит в")
        say("  подписку. Приложение Claude её не заменяет: игра сама запускает Claude Code на каждый ход героя.")
        say("  Ставлю один раз, 1–2 минуты — не прерывайте (Ctrl+C — пропустить, тогда в этот раз правила)…")
        install()
        exe = find()
        if exe is None:
            say("  Claude Code не поставился. Поставьте его сами (claude.com/product/claude-code) и запустите снова;")
            say("  в этот раз героев ведут правила.")
            return None
    st = auth(exe)
    if st and not st.get("loggedIn"):                       # {} — старая версия без `auth status`: судит проба
        say("  Вход подпиской: сейчас откроется браузер — войдите в аккаунт Claude, где у вас подписка")
        say("  (пропустить — Ctrl+C).")
        login(exe)
        st = auth(exe)
        if st and not st.get("loggedIn"):
            say("  Вход не получился — в этот раз героев ведут правила. Попробую при следующем запуске.")
            return None
    if st.get("authMethod") == "api_key":
        say("  Внимание: Claude Code вошёл ключом API, а не подпиской — вызовы пойдут в оплату по ключу.")
    say("  Проверяю Claude Code пробным вопросом…")
    ok, why = check(exe)
    if not ok and why.startswith("не запустился"):     # битый файл (прервали установку) — поставить заново один раз
        say(f"  Claude Code не запускается ({why}) — ставлю заново…")
        install()
        exe = find() or exe
        ok, why = check(exe)
    if not ok and "unknown option" in why.lower():     # старая версия не знает ключей игры — обновить один раз
        say(f"  Claude Code старый ({why[:120]}) — обновляю (claude update)…")
        update(exe)
        ok, why = check(exe)
    if ok:
        return exe
    say(f"  Claude Code не ответил: {why}")
    say("  В этот раз героев ведут правила.")
    return None


def api_trial(backend) -> tuple[bool, str, float]:
    """Одно решение героя боевым запросом (тот же промпт, схема, effort, без думания): → (прошло, почему нет, секунд).
    Ctrl+C — проба не прошла (игра идёт дальше)."""
    t0 = time.monotonic()
    try:
        from .agents import system_prompt, user_prompt, parse_decision    # noqa: PLC0415
        reply = backend.decide(system_prompt("radiant", 1, TRIAL_OBS["hero"]), user_prompt(TRIAL_OBS, [], [], "проба"),
                               TRIAL_OBS)
        data = reply.get("data") if reply.get("data") is not None else reply.get("text") or ""
        decision, _ = parse_decision(data, TRIAL_OBS)
        if decision is None:
            return False, "ответ не разобрался как решение", time.monotonic() - t0
        return True, "", time.monotonic() - t0
    except KeyboardInterrupt:
        return False, "прервано (Ctrl+C)", time.monotonic() - t0
    except Exception as e:                                # noqa: BLE001 — сеть, 4xx, нет денег
        text = str(e)
        if "на балансе" in text:                          # без «вернутся через минуту»: дальше — без ключа
            return False, "на балансе API нет денег (platform.claude.com → Billing)", time.monotonic() - t0
        return False, f"{type(e).__name__}: {text}"[:200], time.monotonic() - t0


def setup_agents(cfg: dict, args, ask_secret=None, opener=urllib.request.urlopen, subscription=setup_subscription,
                 probe=probe_key):
    """Мотор героев. Слова автора, 10.10.2026: «Не нужно меню с выбиранием системы использования, всегда будет 2»; 12.10.2026
    (Д23): «в общем если мы не можем сделать по апи смысла нет слишком большое время на принятие решения». Поэтому: есть
    ключ API — по ключу (быстро); ключа нет — один вопрос (вставить ключ; Enter — подписка, спрошу снова; 0 — больше не
    спрашивать), дальше — Claude через вход подпиской в Claude Code; --rules — правила; --api — только ключ.
    → ("sub", путь к claude) | ("key", (ключ, модель)) | ("off", None)."""
    if args.rules:
        return "off", None
    if cfg.get("key_ask") != KEY_ASK:                             # play.json из выпуска до Д23
        cfg["key_ask"] = KEY_ASK
        if cfg.get("api_key") == "":                              # прежнее «без Claude» — не «больше не спрашивать»
            cfg.pop("api_key")
            try:
                save_config(cfg)
            except OSError:                                       # файл занят: спросить и в этот раз, и в следующий
                pass
    filed = take_key_file(cfg, opener, probe)                     # файл «ключ.txt» — явная просьба играть по ключу
    if filed is not None:
        if filed[0]:
            return "key", filed
        if args.api:
            return "off", None
        say("  Дальше — по подписке (Claude Code).")
        exe = subscription()
        return ("sub", exe) if exe else ("off", None)
    if (args.api or args.ask_key) and cfg.get("api_key") == "":   # «больше не спрашивать» — но ключ просят
        cfg.pop("api_key")
    if args.api or args.ask_key or os.environ.get("ANTHROPIC_API_KEY") or cfg.get("api_key") or "api_key" not in cfg:
        key, model = setup_claude(cfg, args, ask_secret or read_secret, opener, probe=probe)
        if key:
            return "key", (key, model)
        if args.api:
            return "off", None
        say("  Дальше — по подписке (Claude Code).")
    exe = subscription()
    return ("sub", exe) if exe else ("off", None)


# --- загрузки ---

def download(url: str, dest: Path, opener=urllib.request.urlopen, label: str = "") -> None:
    """Скачать в dest через dest.part. Обрыв посреди ответа (пришло меньше Content-Length) — OSError, файла нет."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    try:
        with opener(url, timeout=60) as r, open(part, "wb") as f:
            total, done, shown = int(r.headers.get("Content-Length") or 0), 0, -1
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total and label and (pct := done * 100 // total) // 20 != shown:
                    shown = pct // 20
                    say(f"  {label}: {pct}%")
        if total and done != total:
            raise OSError(f"скачалось {done} байт из {total} — связь оборвалась")
        os.replace(part, dest)
    except BaseException:
        try:
            part.unlink()
        except OSError:
            pass
        raise


def runs(exe: str, run=subprocess.run) -> bool:
    """Запускается ли программа: `<exe> --version` с кодом 0 (битый или недокачанный exe — нет)."""
    try:
        return run([exe, "--version"], capture_output=True, timeout=30).returncode == 0
    except Exception:                                   # noqa: BLE001 — WinError 193, нет файла, таймаут
        return False


def ensure_cloudflared(opener=urllib.request.urlopen, which=shutil.which, windows: bool = os.name == "nt",
                       check=runs) -> str | None:
    """cloudflared: из PATH, свой в .runtime/ или скачать (Windows). Свой проверяется запуском; не запустился —
    удалить и скачать заново. → путь или None (не Windows и в PATH нет)."""
    found = which("cloudflared")
    if found:
        return found
    local = RUNTIME / ("cloudflared.exe" if windows else "cloudflared")
    if local.exists():
        if check(str(local)):
            return str(local)
        local.unlink()
    if not windows:
        return None
    for attempt in range(2):                            # разовый обрыв связи — повторить один раз
        try:
            download(CLOUDFLARED_URL, local, opener, "туннель Cloudflare")
            break
        except OSError:
            if attempt:
                raise
            say("  Связь оборвалась — качаю ещё раз…")
    if not check(str(local)):
        local.unlink()
        raise OSError("скачанный cloudflared не запускается")
    return str(local)


# --- Дота ---

def _install_module():
    sys.path.insert(0, str(PROJECT / "game" / "custom_game"))
    sys.path.insert(0, str(PROJECT / "game" / "prototype_oha"))
    import install_game  # noqa: PLC0415 — модуль установщика кастомки
    return install_game


def find_dota(cfg: dict, args, ask=input, prompt: bool = True) -> Path | None:
    def ok(p) -> bool:
        return bool(p) and (Path(p) / "game" / "dota").exists()

    for p in (args.dota, cfg.get("dota")):
        if ok(p):
            return Path(p)
    found = _install_module().find_dota()
    if found or not prompt:
        return found
    say("  Не нашёл Dota 2. Вставьте путь к папке «dota 2 beta» (например D:\\SteamLibrary\\steamapps\\common\\dota 2 beta)")
    say("  или Enter — без Доты (пульт и сервер всё равно запустятся).")
    p = (_ask(ask, "  папка> ") or "").strip('"')
    if ok(p):
        cfg["dota"] = p
        save_config(cfg)
        return Path(p)
    return None


def _running(image: str, run=subprocess.run) -> bool:
    """Запущена ли программа (Windows, tasklist). Вывод tasklist — в кодировке консоли (на русской Windows — cp866,
    с кириллицей), поэтому читаем байты и ищем латинское имя образа, а не разбираем текст."""
    if os.name != "nt" and run is subprocess.run:
        return False
    try:
        out = run(["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"], capture_output=True,
                  timeout=10).stdout or b""
    except Exception:                                   # noqa: BLE001 — нет tasklist, таймаут: считаем «не запущена»
        return False
    return f'"{image}"'.lower().encode("ascii") in out.lower()


def dota_argv(dota: Path) -> list[str]:
    """-condebug — консоль в console.log (её читает окно хоста), -conclearlog — с чистого листа на каждый запуск
    (так запускает Доту с инструментами Windy10v10AI, поиск 10.10.2026)."""
    exe = dota / "game" / "bin" / "win64" / "dota2.exe"
    return [str(exe), "-novid", "-tools", "-addon", ADDON, "-condebug", "-conclearlog", "+dota_launch_custom_game",
            ADDON, "dota"]


# что должно появиться после сборки интерфейса (Panorama: .xml → .vxml_c, .js → .vjs_c, .css → .vcss_c)
PANORAMA_OUT = ("layout/custom_game/custom_ui_manifest.vxml_c", "layout/custom_game/coach_hud.vxml_c",
                "scripts/custom_game/coach_hud.vjs_c", "styles/custom_game/coach_hud.vcss_c")
NO_WINDOW = 0x08000000                         # CREATE_NO_WINDOW: сборщик без своего окна


def compile_panorama(dota: Path, run=subprocess.run, timeout: float = 180.0, log_dir: Path | None = None) -> tuple[bool, str]:
    """Собрать интерфейс тренера (Panorama) до запуска Доты. → (собран ли, что сказать).

    Первый живой матч (10.10.2026): вместо нашей панели — обычная панель героя. В pak01 самой Доты есть свой
    panorama/layout/custom_game/custom_ui_manifest.vxml_c: если наш манифест не собран, Дота молча берёт его (вывод
    поиска, не проверен). Собирает ли режим инструментов Panorama сам — источники расходятся, а установщик кастомки
    каждый раз стирает собранное, поэтому собираем сами. Команда — как у шаблона x-template, без -pauseiferror (он
    ждёт клавишу) и -verbose."""
    win64 = dota / "game" / "bin" / "win64"
    rc = win64 / "resourcecompiler.exe"
    src = dota / "content" / "dota_addons" / ADDON / "panorama"
    out = dota / "game" / "dota_addons" / ADDON / "panorama"
    if not rc.exists():
        return False, "нет сборщика resourcecompiler.exe (он в Workshop Tools)"
    if not src.is_dir():
        return False, f"нет исходников {src}"
    argv = [str(rc), "-game", str(dota / "game" / "dota"), "-r", "-i", str(src / "*")]
    kw = {"creationflags": NO_WINDOW} if os.name == "nt" else {}
    stray = [dota / "game" / "dota" / "panorama" / x for x in PANORAMA_OUT]
    # вывод — во временный файл, не в трубу: на Windows run() после убийства по таймауту ждёт трубу без срока, если
    # её держит дочерний процесс сборщика (повторная проверка); ввод — пустой: окно хоста сборщику не отдаём
    with tempfile.TemporaryFile() as log:
        try:
            p = run(argv, cwd=str(win64), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    timeout=timeout, **kw)
        except (OSError, subprocess.SubprocessError) as e:
            p, failed = None, f"сборщик не запустился или не уложился в {timeout:.0f} с: {e}"
        else:
            failed = None
        finally:
            if stray[1].exists():              # собрал в папку самой Доты, а не аддона — убрать: манифест там
                for f in stray:                # заменил бы стандартный интерфейс всем кастомкам
                    try:
                        f.unlink()
                    except OSError:
                        pass
                failed = "сборщик положил файлы в папку самой Доты, а не кастомки — убрал их"
        if failed:
            return False, failed
        missing = [x for x in PANORAMA_OUT if not (out / x).exists()]
        if missing:
            log.seek(0)
            text = log.read().decode("utf-8", "replace")
            said = [line.strip() for line in text.splitlines() if line.strip()]
            # строки с ошибками — до итоговой (живой матч 11.10.2026: окно показало только «2 failed», без причины)
            errs = [x for x in said if re.search(r"error|fail|ошибк", x, re.I) and not x.startswith(("|", "-"))][:4]
            tail = " | ".join(errs or said[-4:])[-500:]
            saved = ""
            if log_dir is not None:
                try:
                    path = log_dir / f"panorama_build_{time.strftime('%Y%m%d_%H%M%S')}.log"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text, encoding="utf-8")
                    saved = f"; весь вывод сборщика — {path}"
                except OSError:
                    pass
            return False, f"нет {', '.join(missing)} (код {p.returncode}){': ' + tail if tail else ''}{saved}"
    return True, "собран"


def install_custom_game(dota: Path, running=_running) -> str:
    """Поставить или обновить кастомку. Открытая Дота держит файлы — тогда не трогаем. → что сказать хосту."""
    if running("dota2.exe"):
        return "Дота уже открыта — кастомку не обновляю (её файлы заняты). Закройте Доту и запустите снова."
    try:
        _install_module().install(dota, log=lambda s: None)
        return f"Установлена: {dota}"
    except (SystemExit, OSError) as e:
        return f"Не установил: {e}"


def has_tools(dota: Path) -> bool:
    """Стоит ли бесплатное дополнение Dota 2 Workshop Tools: его программы лежат рядом с dota2.exe."""
    return (dota / "game" / "bin" / "win64" / "resourcecompiler.exe").exists()


TOOLS_HOW = ("Steam → Библиотека → правый щелчок по Dota 2 → Свойства → Дополнительный контент (DLC) → отметьте "
             "«Dota 2 Workshop Tools DLC»")
TOOLS_MANUAL = ("Если дополнение точно стоит — запустите Доту сами (Steam → Dota 2 → «Launch Dota 2 - Tools») и в её "
                f"консоли:  dota_launch_custom_game {ADDON} dota")
TOOLS_HELP = ("Нет бесплатного дополнения Dota 2 Workshop Tools — без него Дота с кастомкой не запускается (Steam пишет "
              "«файл игры отсутствует или повреждён»). Поставьте его: " + TOOLS_HOW + " — и дождитесь загрузки. "
              + TOOLS_MANUAL)


def launch_dota(dota: Path, popen=subprocess.Popen, running=_running, wait=time.sleep, force: bool = False,
                build=compile_panorama) -> str:
    """Запустить Доту с инструментами и сразу кастомку. → что сказать хосту. force — запускать, даже если признака
    Workshop Tools не видно (хост сказал, что дополнение стоит). Перед запуском — сборка интерфейса тренера."""
    if running("dota2.exe"):
        return ("Дота уже запущена. Закройте её и запустите ИГРАТЬ.bat снова — или введите в консоли Доты:  "
                f"dota_launch_custom_game {ADDON} dota")
    win64 = dota / "game" / "bin" / "win64"
    if not (win64 / "dota2.exe").exists():
        return f"Не нашёл {win64 / 'dota2.exe'} — запустите Доту сами"
    if not force and not has_tools(dota):            # первый живой запуск 10.10.2026: без них Steam даёт ошибку
        return TOOLS_HELP
    if os.name == "nt" and not running("steam.exe"):
        try:
            os.startfile("steam://open/main")              # noqa: S606 — Steam нужен Доте
        except OSError:
            pass
        for _ in range(40):
            if running("steam.exe"):
                break
            wait(1)
        wait(10)
    say("  Собираю интерфейс тренера для Доты (до пары минут)…")
    ok, note = build(dota, log_dir=LOGS) if build is compile_panorama else build(dota)
    if ok:
        say("  Интерфейс тренера собран.")
    else:
        say(f"  Интерфейс тренера не собран: {note}")
        say("  Дота попробует собрать его сама. Если в игре не будет поля «Приказ:» — пишите приказы в чат команды.")
    kw = {"cwd": str(win64), "close_fds": True}
    if os.name == "nt":
        kw["creationflags"] = DETACHED
    try:
        popen(dota_argv(dota), **kw)
    except OSError as e:
        return f"Не запустил Доту: {e}. Запустите её сами и в консоли Доты:  dota_launch_custom_game {ADDON} dota"
    return ("Дота запускается с кастомкой: возьмите любого героя — вы тренер Света. Если Steam напишет «файл игры "
            "отсутствует или повреждён» — Steam → Dota 2 → Свойства → Установленные файлы → «Проверить целостность "
            "файлов» и проверьте галочку Workshop Tools в «Дополнительный контент».")


class DotaStarter:
    """Один запуск Доты на окно лаунчера: и поток ожидания Workshop Tools, и «д» хоста идут сюда, под замком —
    двойного запуска нет. Повторный вызов, пока Дота работает, отвечает «уже запущена»; запуск не удался (Steam:
    «файл отсутствует») — следующий вызов пробует снова."""

    def __init__(self, dota: Path, launch=None, running=None):
        self.dota = dota
        self.launch = launch or launch_dota
        self.running = running or _running
        self.lock = threading.Lock()
        self.started = False

    def start(self, force: bool = False) -> str:
        with self.lock:
            if self.started and self.running("dota2.exe"):
                return "Дота уже запущена — переключитесь на неё."
            msg = self.launch(self.dota, force=force)
            self.started = msg.startswith("Дота запускается")
            return msg


def launch_when_tools(dota: Path, stop: threading.Event, start, has=has_tools, linked=lambda: False,
                      period: float = 10.0, settle: float = 30.0, remind: float = 120.0) -> None:
    """Steam ещё качает Workshop Tools: ждать (окно лаунчера открыто — сервер и туннель уже работают) и, как только
    дополнение на месте, запустить Доту — без второго окна ИГРАТЬ.bat (Д15, дополнение 2). Раз в remind секунд —
    напоминание: окно не зависло. Игра на связи (хост запустил Доту сам или «д») — ждать больше нечего.
    start — DotaStarter.start: «д» хоста ожидание не гасит, двойного запуска нет."""
    waited = 0.0
    while not stop.wait(period):
        if linked():
            return
        waited += period
        if remind and waited >= remind:
            waited = 0.0
            say("  …жду Workshop Tools (Steam → Библиотека → Dota 2 → Свойства → DLC). Окно не зависло. Если дополнение")
            say("  уже стоит — наберите д и Enter, запущу Доту сразу.")
        if has(dota):
            say("  Workshop Tools на месте — через полминуты запускаю Доту (Steam доводит файлы)…")
            if stop.wait(settle) or linked():
                return
            say("  " + start())
            return


# --- журнал Доты: что делает кастомка (первый живой матч, 10.10.2026: «агентов нет» — а окно хоста молчало) ---

# Консоль Доты по -condebug: «…\dota 2 beta\game\dota\console.log», дописывается; -conclearlog очищает её при запуске;
# UTF-8 с BOM, строки «ММ/ДД ЧЧ:ММ:СС [Канал] текст»; print() сервера — канал [VScript], $.Msg() — [PanoramaScript]
# (код Windy10v10AI и других кастомок, строки бинарников Доты — поиск 10.10.2026, journal/ERRORS.md № 98)
CONSOLE_LOG = Path("game") / "dota" / "console.log"
OURS_TAG = "[ТРЕНЕР]"
# ходы игры — реплики агентов и тренеров, приказы с пульта, в том числе ИИ-тренера соперника (Д16: «его приказы в
# окно не пишутся»), покупки: окну хоста не нужны (рецензия 7)
GAME_MOVE = RPT.MOVE
GAME_ERROR = re.compile(r"script runtime error|stack traceback|error running script|script not found", re.I)
OUR_FILES = re.compile(r"coach_|vc_\w+\.lua|voicecoach|custom_ui_manifest|addon_game_mode|custom_game", re.I)
NOTABLE = re.compile(r"error|fail|not found|unable|cannot|exception|ошибк|recompil", re.I)
STAMP = re.compile(r"^\ufeff?(\d\d/\d\d \d\d:\d\d:\d\d )?")


class DotaLog:
    """Новые строки консоли Доты (console.log): строки кастомки «[ТРЕНЕР]» (кроме ходов игры) и ошибки скриптов и
    интерфейса — в окно хоста, всё новое — копией в журнал лаунчера (её можно прислать). Строки прошлых запусков
    не показывает. Одна и та же строка — не чаще раза в repeat секунд; за window секунд — не больше per_window строк
    кастомки и other_window прочих: шум Доты не вытесняет строки кастомки, о скрытых строках окно говорит."""

    MAX_READ = 4_000_000
    HEAD = 64

    def __init__(self, path: Path, copy: Path | None = None, show=None, clock=time.monotonic,
                 per_window: int = 12, other_window: int = 4, window: float = 10.0, repeat: float = 60.0):
        self.path, self.copy = Path(path), Path(copy) if copy else None
        self.show = show or (lambda line: say("  Дота: " + line))
        self.clock = clock
        self.limit = {"ours": per_window, "other": other_window}
        self.window, self.repeat = window, repeat
        try:
            self.pos = self.path.stat().st_size
        except OSError:
            self.pos = 0
        self.head = self._head()
        self.tail = b""
        self.seen: dict[str, float] = {}
        self.win_start, self.count, self.hidden = -1e18, {"ours": 0, "other": 0}, 0
        self.ours = 0                                  # строк «[ТРЕНЕР]» с начала — кастомка пишет в консоль
        self.new_bytes = 0                             # Дота вообще пишет консоль (запущена с -condebug)

    def _head(self) -> bytes:
        try:
            with self.path.open("rb") as f:
                return f.read(self.HEAD)
        except OSError:
            return b""

    @staticmethod
    def wanted(line: str) -> bool:
        if OURS_TAG in line:
            return not GAME_MOVE.search(line)
        return bool(GAME_ERROR.search(line) or (OUR_FILES.search(line) and NOTABLE.search(line)))

    def poll(self) -> int:
        """Дочитать файл; вернуть, сколько строк показано в окне."""
        try:
            size = self.path.stat().st_size
        except OSError:
            return 0
        head = self._head() if size else b""
        n = min(len(head), len(self.head))
        if size < self.pos or head[:n] != self.head[:n]:   # файл начат заново (-conclearlog, новый запуск Доты)
            self.pos, self.tail = 0, b""
        self.head = head
        shown = 0
        if size > self.pos:
            with self.path.open("rb") as f:
                f.seek(self.pos)
                data = f.read(min(size - self.pos, self.MAX_READ))
            self.pos += len(data)
            self.new_bytes += len(data)
            parts = (self.tail + data).split(b"\n")
            self.tail = parts.pop()                    # неполная последняя строка — дочитается в следующий раз
            if len(self.tail) > 100_000:
                self.tail = b""
            lines = [p.decode("utf-8", "replace").rstrip("\r").lstrip("\ufeff") for p in parts]
            if self.copy and lines:
                try:
                    self.copy.parent.mkdir(parents=True, exist_ok=True)
                    with self.copy.open("a", encoding="utf-8") as f:
                        f.write("\n".join(lines) + "\n")
                except OSError:
                    self.copy = None                   # нет места или прав — копию не пишем, окно работает
            for line in lines:
                if OURS_TAG in line:
                    self.ours += 1
                if self.wanted(line) and self._emit(line):
                    shown += 1
        self._flush_hidden()
        return shown

    def _emit(self, line: str) -> bool:
        kind = "ours" if OURS_TAG in line else "other"
        at = line.find(OURS_TAG)
        text = (line[at + len(OURS_TAG):] if at >= 0 else STAMP.sub("", line)).strip()[:240]
        if not text:
            return False
        now = self.clock()
        last = self.seen.get(text)
        if last is not None and now - last < self.repeat:
            return False
        self._flush_hidden()
        if self.count[kind] >= self.limit[kind]:
            self.hidden += 1                           # скрытая строка не запоминается: её повтор покажется позже
            return False
        self.count[kind] += 1
        self.seen[text] = now
        if len(self.seen) > 1000:
            self.seen = {k: v for k, v in self.seen.items() if now - v < self.repeat}
        self.show(text)
        return True

    def _flush_hidden(self, force: bool = False) -> None:
        now = self.clock()
        if not force and now - self.win_start < self.window:
            return
        if self.hidden:
            self.show(f"…и ещё строк: {self.hidden} (весь журнал Доты: {self.copy or self.path})")
        self.win_start, self.count, self.hidden = now, {"ours": 0, "other": 0}, 0

    def finish(self) -> None:
        """Перед выходом: дочитать файл и сказать о скрытых строках."""
        try:
            self.poll()
        except Exception:                              # noqa: BLE001 — выход не должен падать из-за журнала
            pass
        self._flush_hidden(force=True)

    def health(self, linked: bool) -> str | None:
        """Через пару минут после запуска Доты: пишет ли она консоль и есть ли там кастомка. → что сказать хосту."""
        if self.new_bytes == 0:
            return (f"Консоль Доты не пишется в {self.path}. Если Дота запущена не этим окном — закройте её, здесь — "
                    "Enter два раза, и запустите ИГРАТЬ.bat снова; иначе Дота пишет консоль в другое место — пришлите "
                    "снимок этого окна.")
        if self.ours == 0:
            if linked:
                return f"Игра на связи, но строк кастомки в {self.path} нет — Дота пишет консоль в другое место."
            return ("В консоли Доты нет строк кастомки: кастомка не загрузилась (или Дота ещё грузится). Если в Доте "
                    f"главное меню — введите в её консоли  dota_launch_custom_game {ADDON} dota. Пришлите снимок окна.")
        return None


def follow_dota_log(log: DotaLog, stop: threading.Event, period: float = 1.0, started=lambda: True,
                    linked=lambda: False, check_after: float = 300.0, clock=time.monotonic) -> None:
    """Раз в period секунд — новые строки консоли Доты в окно хоста; через check_after секунд после запуска Доты (у
    автора от запуска до матча прошло около 4 минут) — одна проверка, пишет ли Дота консоль и есть ли там кастомка
    (рецензия 7: без файла окно снова молчало). Сбой чтения окно не роняет."""
    told = checked = False
    since = None
    while not stop.wait(period):
        try:
            log.poll()
            if not checked:
                if since is None and (started() or linked()):
                    since = clock()
                if since is not None and clock() - since >= check_after:
                    checked = True
                    msg = log.health(linked())
                    if msg:
                        say("  ! " + msg)
        except Exception as e:                         # noqa: BLE001 — журнал вспомогательный: игра идёт без него
            if not told:
                say(f"  Журнал Доты не читается: {e}")
                told = True


# --- туннель ---

class TunnelKeeper:
    """Туннель для друга. cloudflared упал или оборвался — поднять заново: адрес будет новым, лаунчер положит его в
    ящик, и файл друга или открытый пульт найдут его сами. Падает подряд — пауза растёт до минуты."""

    def __init__(self, port: int, on_url, cloudflared: str, start=start_tunnel, period: float = 5.0,
                 backoff: float = 5.0):
        self.port, self.on_url, self.cf, self.start_fn, self.period = port, on_url, cloudflared, start, period
        self.backoff = backoff                           # с: пауза перед новым запуском растёт с числом падений
        self.proc = None
        self.fails = 0                                   # падений подряд, без нового адреса
        self.stop = threading.Event()

    def _start(self):
        return self.start_fn(self.port, self._url, self.cf, on_error=self._err, on_exit=lambda code, had: None)

    def start(self) -> bool:
        self.proc = self._start()
        if self.proc is None:
            return False
        threading.Thread(target=self._loop, daemon=True, name="tunnel-keeper").start()
        return True

    def _url(self, url: str) -> None:
        self.fails = 0
        self.on_url(url)

    def _err(self, msg: str) -> None:
        if not self.stop.is_set() and self.fails <= 1:    # при повторных падениях — без потока одинаковых строк
            say("  " + msg)

    def _loop(self) -> None:
        while not self.stop.wait(self.period):
            if self.proc.poll() is None:
                continue
            self.fails += 1
            if self.fails == 1:
                say("  Туннель оборвался — поднимаю заново; новый адрес файл друга и пульт найдут сами.")
            if self.stop.wait(min(60.0, self.backoff * self.fails)):
                return
            proc = self._start()
            if proc is None:
                say("  cloudflared не запускается — туннель не поднять. Пульт друга работает только на этом ПК.")
                return
            self.proc = proc
            if self.stop.is_set():                       # закрыли, пока запускали: новый не оставлять
                self.close()
                return

    def close(self) -> None:
        self.stop.set()
        if self.proc is not None:
            try:
                self.proc.terminate()
            except OSError:
                pass


# --- файл друга и мелочи Windows ---

def make_friend_file(path: Path, secret: str, base: str) -> Path:
    html = (WEB / "friend.html").read_text(encoding="utf-8")
    html = (html.replace("/*__RV_JS__*/", (WEB / "rv.js").read_text(encoding="utf-8"))
            .replace("__RV_BASE__", base).replace("__SECRET__", secret))
    path.write_text(html, encoding="utf-8")
    return path


def copy_text(text: str) -> bool:
    """В буфер обмена Windows (clip). Ссылка — латиница: её clip понимает в любой кодировке консоли."""
    if os.name != "nt":
        return False
    try:
        subprocess.run(["clip"], input=text.encode("ascii", "replace"), timeout=5, check=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def reveal(path: Path) -> None:
    if os.name == "nt":
        try:
            subprocess.Popen(["explorer", "/select,", str(path)])
        except OSError:
            pass


def quickedit_off() -> None:
    """Windows: выделение мышью в окне (QuickEdit) останавливает вывод программы, а с ним и чтение журнала
    cloudflared — туннель встанет. На время игры выключаем; ссылка на пульт и так копируется сама."""
    if os.name != "nt":
        return
    try:
        import ctypes  # noqa: PLC0415
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-10)                         # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if k.GetConsoleMode(h, ctypes.byref(mode)):
            old = mode.value
            k.SetConsoleMode(h, (old | 0x0080) & ~0x0040)   # ENABLE_EXTENDED_FLAGS, без ENABLE_QUICK_EDIT_MODE
            atexit.register(k.SetConsoleMode, h, old)
    except Exception:                                   # noqa: BLE001 — не консоль: и не нужно
        pass


def already_running(opener=LOCAL) -> bool:
    """Отвечает ли на этом ПК сервер тренера (второй запуск ИГРАТЬ.bat, пока первый идёт)."""
    try:
        with opener(HEALTH, timeout=2) as r:
            return json.loads(r.read().decode("utf-8")).get("ok") is True
    except Exception:                                   # noqa: BLE001 — не отвечает: значит, не запущен
        return False


def bind(make, port: int, who: str, tries: int = 10, wait=time.sleep, ours=None):
    """Занять порт: make() → сервер. Занят — это наш же сервер (второе окно; ours() — проверка) или порт ещё не
    отпустило только что закрытое окно: подождать до ~20 с. → сервер или None (хосту уже сказано, что делать)."""
    for attempt in range(tries):
        try:
            return make()
        except OSError as e:
            if ours is not None and ours():
                say("  Игра уже запущена в другом окне ИГРАТЬ.bat — переключитесь на него (второе окно не нужно).")
                say("  Перезапустить игру: в том окне Enter два раза, потом ИГРАТЬ.bat снова.")
                return None
            if attempt == tries - 1:
                say(f"  Порт {port} занят другой программой ({e}) — {who} некуда встать. Закройте её или "
                    "перезагрузите ПК и запустите снова.")
                return None
            if attempt == 0:
                say(f"  Порт {port} пока занят — жду, пока его отпустят…")
            wait(2.0)
    return None


def wait_enter(stop: threading.Event, ask=input, window: float = 5.0, clock=time.monotonic, on_word=None) -> None:
    """Закончить игру — Enter два раза (второй — за window секунд): один случайный Enter не обрывает игру друга.
    «д» и Enter (в любой раскладке: д, l, d) — on_word: запустить Доту сразу. Окно без ввода — ждать только Ctrl+C."""
    first = None
    while not stop.is_set():
        try:
            line = ask("")
        except (EOFError, OSError):
            return
        except KeyboardInterrupt:
            break
        if on_word is not None and str(line or "").strip().lower() in ("д", "l", "d"):
            on_word()
            first = None
            continue
        now = clock()
        if first is not None and now - first <= window:
            break
        first = now
        say(f"  Закончить игру? Нажмите Enter ещё раз в ближайшие {window:.0f} секунд.")
    stop.set()


# --- главное ---

def parse(argv=None):
    ap = argparse.ArgumentParser(description="Тренер Доты: игра вдвоём одним файлом (ИГРАТЬ.bat)")
    ap.add_argument("--rules", action="store_true", help="агенты на правилах (без Claude, бесплатно)")
    ap.add_argument("--api", action="store_true",
                    help="только Claude по ключу API (без ключа — правила, а не подписка)")
    ap.add_argument("--ask-key", action="store_true", help="спросить ключ API заново (сменить или убрать)")
    ap.add_argument("--max-calls", type=int, default=None,
                    help=f"предел вызовов Claude на сторону (по ключу API — {MAX_CALLS}, по подписке — {SUB_MAX_CALLS})")
    ap.add_argument("--dota", help="папка «dota 2 beta», если не нашлась сама")
    ap.add_argument("--no-dota", action="store_true", help="не запускать Доту (запустить самому)")
    ap.add_argument("--no-tunnel", action="store_true", help="без туннеля: пульт только на этом ПК")
    ap.add_argument("--new-friend", action="store_true",
                    help="новый файл для друга: старый перестанет находить игру (и старая ссылка на пульт тоже)")
    ap.add_argument("--rv", default=RV.RV_DEFAULT, help="адрес ящика (сервер ntfy)")
    return ap.parse_args(argv)


def report_info(reports: dict, final: bool = False, learned=None) -> dict:
    """Части отчёта для Claude (просьба автора 11.10.2026: «зделай общюю систему»): окно, агенты, консоль Доты."""
    room, dlog = reports.get("room"), reports.get("dlog")
    hub = getattr(room, "agents", None)
    info = {"Окно лаунчера": RPT.read_text(reports.get("wlog"))}
    if hub is not None:
        try:
            info["Агенты сейчас"] = hub.progress()
            if final:
                info["Итоги агентов"] = hub.summary()
        except Exception as e:                                   # noqa: BLE001 — отчёт вспомогательный
            info["Агенты сейчас"] = f"не прочитал: {e}"
    ai = reports.get("ai")
    if ai is not None:
        info["ИИ-тренер соперника"] = {"вызовов Claude": getattr(ai, "claude_calls", 0),
                                       "из них ошибок": getattr(ai, "claude_errors", 0),
                                       "приказов отправлено": getattr(ai, "sent", 0)}
    if learned:
        info["Обучение (Д20)"] = [{k: r.get(k) for k in ("team", "pos", "hero", "match", "row", "verdicts", "added", "say")}
                                  for r in learned]
    if dlog is not None and getattr(dlog, "copy", None) is not None:   # ходы соперника — только после игры (Д16)
        info["Консоль Доты: строки кастомки и ошибки"] = RPT.dota_lines(RPT.read_text(dlog.copy), moves=final)
    if final:
        text, counts = RPT.agent_samples(reports.get("log"))
        info["Журнал агентов"] = f"{counts}\n{text}"
        errs = [x for x in RPT.read_text(reports.get("coach_log")).splitlines() if '"error": "' in x]
        if errs:
            info["Ошибки ИИ-тренера (первые 5)"] = "\n".join(errs[:5])
        builds = sorted(LOGS.glob("panorama_build_*.log"))
        if builds and time.time() - builds[-1].stat().st_mtime < 6 * 3600:
            info["Сборка интерфейса (последняя неудачная)"] = RPT.read_text(builds[-1])
    return info


def live_reports(reports: dict, stop, every: float = 60.0) -> None:
    """Раз в every секунд — «DotaCoach_сейчас.txt» (в coach\\logs и на Google Диск): Claude видит игру без снимков."""
    while not stop.wait(every):
        try:
            RPT.write(RPT.build(report_info(reports)), LOGS, RPT.LIVE_NAME, reports.get("drive"))
        except Exception:                                        # noqa: BLE001 — отчёт не роняет игру
            pass


def final_report(reports: dict, learned=None, reveal_file=None) -> list:
    """Итоговый отчёт игры: файл с датой и «сейчас»; без Google Диска — открыть папку с файлом."""
    try:
        text = RPT.build(report_info(reports, final=True, learned=learned))
        drive = reports.get("drive")
        done = RPT.write(text, LOGS, RPT.final_name(), drive)
        RPT.write(text, LOGS, RPT.LIVE_NAME, drive)
    except Exception as e:                                       # noqa: BLE001
        say(f"Отчёт для Claude не записан: {type(e).__name__}: {e}")
        return []
    if not done:
        return []
    if drive is not None and any(drive in p.parents for p in done):
        say("Отчёт для Claude — на Google Диске (папка DotaCoach): напишите Claude «посмотри отчёт».")
    else:
        say(f"Отчёт для Claude: {done[0]} — перетащите этот файл в чат Claude.")
        (reveal_file or reveal)(done[0])
    return done


def learning_report(hub, backend, timeout: float = 90.0) -> list[dict]:
    """Конец игры (Д20): незаписанные матчи героев — в память и на разбор агентами; в окно — итоги своей стороны
    (Света): числа к 10:00, новые уроки, что код решил об уроках; соперника (Д16) — только сколько уроков; всё — в
    coach\\logs\\match_*.md."""
    try:
        if not getattr(backend, "free", False) and any(not a.recorded for a in hub.agents.values()):
            say("Разбор матча агентами (до полутора минут)…")
        hub.finish_match(timeout=timeout)
        results = list(hub.finished)
    except Exception as e:                                      # noqa: BLE001 — разбор не роняет выход
        say(f"Разбор матча не получился: {type(e).__name__}: {e}")
        return []
    if not results:
        return []
    say("Обучение агентов (Д20):")
    lines = ["# Матч: обучение агентов", ""]
    for r in sorted(results, key=lambda x: (x["team"], x["pos"])):
        side = {"radiant": "Свет", "dire": "Тьма"}.get(r["team"], r["team"])
        row = f"{side} {r['pos']} {r['hero']} (матч героя №{r['match']}): {LRN.row_text(r['row'])}"
        lines.append(f"- {row}")
        for x in r["added"]:
            lines.append(f"  - новый урок: {x}")
        for v in r["verdicts"]:
            lines.append(f"  - {v}")
        if r["say"]:
            lines.append(f"  - сказал: {r['say']}")
        if r["team"] == "radiant":
            say("  " + row)
            for x in r["added"]:
                say(f"    новый урок: {x}")
            for v in r["verdicts"]:
                say(f"    {v}")
            if r["say"]:
                say(f"    {r['hero']}: «{r['say']}»")
    dire = [r for r in results if r["team"] != "radiant"]
    if dire:
        say(f"  Тьма: героев {len(dire)}, новых уроков {sum(len(r['added']) for r in dire)} (подробно — в отчёте).")
    path = LOGS / f"match_{time.strftime('%Y%m%d_%H%M%S')}.md"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        say(f"  Отчёт: {path}. Память героев: {LOGS.parent / 'memory'}.")
    except OSError:
        pass
    return results


def rules_ok(ask) -> bool:
    """Claude не включился: сказать крупно и спросить, играть ли на правилах (матч автора 11.10.2026 прошёл на
    правилах, а окно писало «агенты ведут героев» — ERRORS №103). → играть ли дальше."""
    say("")
    say("  !!! ВНИМАНИЕ: Claude не включился — героями будут править простые правила, а не агенты Claude.")
    say("  !!! Почему — строками выше. Исправьте и запустите ИГРАТЬ.bat снова; снимок этих строк поможет найти причину.")
    flush_input()                                      # Enter, нажатый во время установки, — не ответ (рецензия 11б)
    try:
        ask("  Enter — всё равно играть на правилах, Ctrl+C — выйти: ")
    except EOFError:                                   # без консоли спросить нельзя — играть
        return True
    except KeyboardInterrupt:
        say("")
        say("  Выхожу. Запустите ИГРАТЬ.bat снова, когда Claude Code будет готов.")
        return False
    return True


def main(argv=None, ask=input, ask_secret=read_secret, enter=input) -> int:
    try:
        return _main(argv, ask, ask_secret, enter)
    finally:
        close_window_log()


def _main(argv, ask, ask_secret, enter) -> int:
    args = parse(argv)
    wlog = open_window_log(LOGS / f"launcher_{time.strftime('%Y%m%d_%H%M%S')}.log")
    say("=== Тренер Доты: игра вдвоём ===")
    if already_running():
        say("Игра уже запущена в другом окне ИГРАТЬ.bat — переключитесь на него (второе окно не нужно).")
        say("Перезапустить игру: в том окне Enter два раза, потом ИГРАТЬ.bat снова.")
        return 1
    cfg = load_config()
    if args.new_friend or not cfg.get("secret"):
        cfg["secret"] = RV.new_secret()
        save_config(cfg)
    secret = cfg["secret"]

    say("[1/6] Агенты героев")
    try:
        mode, info = setup_agents(cfg, args, ask_secret)
    except KeyboardInterrupt:                                     # Ctrl+C на проверке (сеть медленная)
        say("")
        mode, info = "off", None
    pace = {}
    key_backend = None
    if mode == "key":                                             # проба боевым запросом (рецензия 13): 400 — здесь,
        key, model = info                                         # а не в матче; заодно — настоящее время ответа
        key_backend = ApiBackend(model, api_key=key, thinking=API_THINKING, effort=API_EFFORT, timeout=20.0)
        ok, why, cold = api_trial(key_backend)
        if ok:                                                    # первый ответ холодный (кэш промпта пишется) —
            ok2, _, warm = api_trial(key_backend)                 # штатное время — по второму (рецензия 13)
            say(f"  Проба по ключу: ответ Claude за {warm if ok2 else cold:.1f} с (первый, холодный — {cold:.1f} с)" +
                (f"; модель не приняла: {', '.join(key_backend.dropped)}." if key_backend.dropped else "."))
        elif args.api:                                            # --api — только ключ: без него правила
            say(f"  Проба по ключу не прошла: {why}.")
            mode, info = "off", None
        else:
            say(f"  Проба по ключу не прошла: {why}. Дальше — по подписке (Claude Code).")
            exe = setup_subscription()
            mode, info = ("sub", exe) if exe else ("off", None)
    if mode == "sub":
        backend = CliBackend(model=CLAUDE_FAST, claude=info, subscription=True, effort=SUB_EFFORT)
        pace = SUB_PACE
        max_calls = args.max_calls or SUB_MAX_CALLS
        say("  Героев ведёт Claude через вход подпиской (Claude Code, быстрая модель): из общих лимитов подписки.")
        say("  Каждый герой спрашивает Claude, как только пришёл прошлый ответ (≈ раз в 5 с), все 10 сразу; руки выполняют"
            f" решение 4 раза в секунду. Предел — {max_calls} вызовов на сторону за запуск.")
        say("  Кончится лимит подписки — герои доиграют на правилах. Остаток лимитов — в приложении Claude: Settings → Usage.")
    elif mode == "key":
        backend = key_backend                           # ключ — только агентам, не в окружение Доты и cloudflared
        pace = API_PACE
        max_calls = args.max_calls or MAX_CALLS
        say("  Героев ведёт Claude по ключу API (быстрая модель, без думания): каждый герой решает сразу после прошлого")
        say("  ответа, все 10 одновременно; руки выполняют решение 4 раза в секунду.")
        say(f"  Расход — около $3–4 за 40-минутный матч, за запуск — около ${2 * max_calls * API_CALL_USD:.0f} при работающем "
            f"кэше промпта (предел {max_calls} вызовов на сторону; оценка). В сводке раз в 5 минут и в конце — сколько потрачено;")
        say("  точно — platform.claude.com → Billing.")
    else:
        backend = make_backend("rules")
        max_calls = args.max_calls or MAX_CALLS
        if args.rules:
            say("  Героев ведут правила (не Claude) — так просили (--rules).")
        elif args.api:
            say("  Героев ведут правила (не Claude): ключ API не готов (см. выше).")
        else:
            say("  Героев ведут правила (не Claude).")             # почему — сказал setup_subscription
        if not args.rules and not rules_ok(ask):                   # ERRORS №103: без Claude — не молча
            return 1

    say("[2/6] Кастомка в Доте")
    dota = find_dota(cfg, args, ask, prompt=not args.no_dota)
    if dota:
        say("  " + install_custom_game(dota))
        if not has_tools(dota):
            say("  Внимание: нет дополнения Dota 2 Workshop Tools — без него Дота с кастомкой не запустится.")
            say("  Поставьте его сейчас: " + TOOLS_HOW + ".")
            say("  Пока оно качается, лаунчер доделает остальное, а Доту запустит, когда дополнение будет готово.")
    elif args.no_dota:
        say("  Доту не нашёл (запуск Доты выключен).")
    else:
        say("  Доту не нашёл — спрошу путь при следующем запуске.")
    quickedit_off()                                                 # вопросов больше не будет

    say("[3/6] Сервер тренера")
    log = LOGS / f"agents_local_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    memory = LRN.Memory(LOGS.parent / "memory")                   # память героев между матчами (Д20)
    prices = API_PRICES if mode == "key" else None
    srv = bind(lambda: serve("127.0.0.1", GAME_PORT, lambda room: AgentHub(
        {"radiant": backend, "dire": backend}, max_calls=max_calls, log_path=log, memory=memory, prices=prices,
        **pace)), GAME_PORT,
        "серверу тренера", ours=already_running)
    if srv is None:
        return 1
    threading.Thread(target=srv.serve_forever, daemon=True, name="game").start()
    room = srv.hub.room("local")
    room.rules_why = "так просили (--rules)" if args.rules else RULES_WHY   # почему правят правила — для окна
    keys = load_keys((REMOTE,), new=args.new_friend)
    console = bind(lambda: serve_console(srv.hub, "127.0.0.1", CONSOLE_PORT, "local", keys, rv_origin=args.rv),
                   CONSOLE_PORT, "пульту друга")
    if console is None:
        srv.shutdown()
        srv.server_close()
        return 1
    threading.Thread(target=console.serve_forever, daemon=True, name="console").start()
    local_link = console_url(f"http://127.0.0.1:{CONSOLE_PORT}", keys[REMOTE])
    say(f"  Работает. Пульт друга на этом ПК: {local_link}")

    say("[4/6] Связь для друга через интернет")
    friend = make_friend_file(PROJECT / FRIEND_FILE, secret, args.rv)
    warned = []

    def on_publish(ok, what):
        if not ok and what.get("url") and not warned:              # о недоступном ящике — один раз
            warned.append(1)
            say("  Ящик игры (ntfy.sh) недоступен: если у друга файл не найдёт игру — отправьте ему ссылку на пульт "
                "(она скопирована).")
    pub = RV.Publisher(secret, args.rv, on_result=on_publish)
    keeper = None
    if not args.no_tunnel:
        cf = None
        try:
            cf = ensure_cloudflared()
        except Exception as e:                                      # noqa: BLE001 — обрыв, битый файл, нет места
            say(f"  Не скачал туннель Cloudflare: {e}")
        if cf:
            def on_url(url):
                link = console_url(url, keys[REMOTE])
                pub.set_url(link)
                say(f"  Готово. Ссылка на пульт друга{' (скопирована)' if copy_text(link) else ''}: {link}")
                say(f"  Друг открывает файл {FRIEND_FILE} — пульт откроется сам.")
            keeper = TunnelKeeper(CONSOLE_PORT, on_url, cf)
            if keeper.start():
                atexit.register(keeper.close)
                say("  Туннель поднимается — несколько секунд…")
            else:
                keeper = None
    if keeper is None:
        say("  Без туннеля: пульт открывается только на этом ПК.")

    say("[5/6] Файл для друга")
    say(f"  {friend}")
    if cfg.get("friend_version") != RV.FRIEND_VERSION or args.new_friend:
        if cfg.get("friend_version") or cfg.get("friend_shown"):
            say("  Файл для друга обновился — отправьте его другу ЗАНОВО (в мессенджере, как документ): старый может")
            say("  не найти игру. Показываю файл в Проводнике.")
        else:
            say("  Отправьте этот файл другу ОДИН раз (в мессенджере, как документ). Он подходит ко всем следующим")
            say("  играм: друг открывает его двойным щелчком, файл сам находит вашу игру. Показываю файл в Проводнике.")
        reveal(friend)
        cfg["friend_version"] = RV.FRIEND_VERSION
        save_config(cfg)
    else:
        say("  Друг уже получал этот файл — пусть просто откроет его.")

    say("[6/6] Дота")
    stop = threading.Event()
    on_word = None
    dlog = starter = None
    if dota and not args.no_dota:
        starter = DotaStarter(dota)
    if dota:                                                      # консоль Доты (-condebug) — в окно и копией в журнал
        dlog = DotaLog(dota / CONSOLE_LOG, LOGS / f"dota_console_{time.strftime('%Y%m%d_%H%M%S')}.log")
        threading.Thread(target=follow_dota_log, args=(dlog, stop), daemon=True, name="dota-log",
                         kwargs={"started": (lambda: starter.started) if starter else (lambda: False),
                                 "linked": room.game_linked}).start()
        say("  Что делает кастомка (строки «[ТРЕНЕР]») и её ошибки покажу здесь, с пометкой «Дота:».")
    if starter is not None:
        def on_word():                                            # «д» и Enter: запустить сейчас
            if not has_tools(dota):
                say("  Признака Workshop Tools не вижу — запускаю всё равно. Если Steam напишет «файл отсутствует»,")
                say("  дополнение ещё не готово: окно продолжит ждать и запустит Доту, когда Steam его докачает.")
            say("  " + starter.start(force=True))
    if dota and not args.no_dota and not has_tools(dota):
        say("  Жду дополнение Workshop Tools: не закрывайте это окно — как только Steam его докачает, Дота запустится")
        say("  сама. Если дополнение уже стоит — наберите д и Enter, запущу Доту сразу.")
        threading.Thread(target=launch_when_tools, args=(dota, stop, starter.start),
                         kwargs={"linked": room.game_linked}, daemon=True, name="tools").start()
    elif dota and not args.no_dota:
        say("  " + starter.start())
    else:
        say(f"  Запустите Доту с инструментами и в её консоли:  dota_launch_custom_game {ADDON} dota")

    coach_log = LOGS / f"ai_coach_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    ai = AICoach(room, REMOTE, ClaudeCoach(info, CLAUDE_FAST) if mode == "sub" else RulesCoach(), log_path=coach_log,
                 max_calls=COACH_MAX_CALLS)
    ai.start()
    say("  Соперник: Тьмой командует ИИ-тренер (" + ("Claude" if mode == "sub" else "правила, не Claude") +
        ") — пока друг не откроет пульт; откроет — ИИ-тренер замолчит. Его приказы в окно не пишутся.")

    drive = RPT.drive_folder()
    live_stop = threading.Event()
    reports = {"wlog": wlog, "dlog": dlog, "room": room, "log": log, "drive": drive, "ai": ai, "coach_log": coach_log}
    if drive is not None:
        say(f"  Отчёты для Claude: на Google Диск ({drive}) — раз в минуту и в конце; Claude прочитает их сам.")
    else:
        say("  Отчёты для Claude: coach\\logs (Google Диска для компьютера нет — в конце откроется папка с отчётом:"
            " перетащите файл в чат Claude).")
    threading.Thread(target=live_reports, args=(reports, live_stop), daemon=True, name="report").start()

    say("")
    say("Окно не закрывайте, пока играете. Закончить игру — Enter два раза.")
    flush_input()                                                 # Enter, нажатый раньше, игру не закончит
    threading.Thread(target=wait_enter, args=(stop, enter), kwargs={"on_word": on_word}, daemon=True,
                     name="enter").start()
    try:
        watch(room, stop=stop.is_set, sleep=stop.wait)
    except KeyboardInterrupt:
        pass
    say("Заканчиваю…")
    if dlog is not None:
        dlog.finish()                                             # последние строки Доты и «…и ещё строк»
    ai.close()
    if keeper is not None:                                        # сначала входы: туннель, пульт, игра —
        keeper.close()
    for server in (console, srv):                                 # тогда новый тик не придёт к закрытым агентам
        server.shutdown()
        server.server_close()
    live_stop.set()
    learned = []
    if room.agents is not None:
        learned = learning_report(room.agents, backend)           # Д20: матч героев — в память, разбор, итог
        room.agents.close()                                       # вызовы из очереди не ждём и не оплачиваем
    pub.close()
    if room.agents is not None:
        s = room.agents.summary()
        say(f"Вызовов Claude: {s.get('paid_calls', 0)} (герои, ошибок {s.get('errors', 0)}) + {ai.claude_calls} "
            f"(ИИ-тренер, ошибок {ai.claude_errors}), задержка (медиана): {s.get('latency_p50_s')} с. Журнал: {log}")
        if s.get("cost_usd_est"):
            say(f"Потрачено по ключу API ≈ ${s['cost_usd_est']:.2f} (оценка по ценам быстрой модели; точно — "
                "platform.claude.com → Billing).")
        if getattr(backend, "free", False):
            say("Героями в этой игре правили правила, а не агенты Claude (" +
                ("так просили: --rules)." if args.rules else
                 "Claude Code не включился — см. начало окна или coach\\logs\\launcher_*.log)."))
    if dlog is not None and dlog.copy is not None and dlog.copy.exists():
        say(f"Журнал Доты за эту игру: {dlog.copy}")
    final_report(reports, learned)
    if room.agents is not None:
        time.sleep(0.2)
        if any(t.name.startswith("agent") and t.is_alive() for t in threading.enumerate()):
            say(f"Жду, пока агенты закончат начатые ходы (до {getattr(backend, 'timeout', 30):.0f} с)…")
    return 0


SIDE_OF = {"radiant": "Света", "dire": "Тьмы"}
RULES_WHY = "Claude Code не включился (см. шаг 1/6)"
ERRORS_SHOWN = 3                                   # ошибок агентов стороны в окне хоста — дальше они только в журнале


def hero_counts(tick) -> dict:
    """Сколько героев каждой стороны игра отдала агентам в последнем обмене."""
    out = {"radiant": 0, "dire": 0}
    heroes = tick.get("heroes") if isinstance(tick, dict) else None
    for o in heroes if isinstance(heroes, list) else []:
        if isinstance(o, dict) and isinstance(o.get("team"), str) and o["team"] in out:
            out[o["team"]] += 1
    return out


def report_agents(room, told: dict, now: float, every: float = 300.0) -> None:
    """Агенты стороны приняли первое решение; ошибка агента (первые ERRORS_SHOWN); пауза стороны; раз в every
    секунд — сводка: окно хоста показывает, что агенты ведут героев, а не только что сервер работает."""
    hub = getattr(room, "agents", None)
    if hub is None or not hasattr(hub, "progress"):
        return
    prog = hub.progress()
    for team, p in prog.items():
        side = SIDE_OF.get(team, team)
        base = told.setdefault(("base", team), 0)                         # решений на начало этого матча
        if p["decisions"] > base and not told.get(("first", team)):
            told[("first", team)] = True
            model = p.get("model") or ""                              # имя модели — как его назвал Claude Code
            if p.get("claude") is False:                              # ERRORS №103: правила — сказать прямо
                why = getattr(room, "rules_why", None) or RULES_WHY
                say(f"  ! Героями {side} правят ПРАВИЛА, а не агенты Claude: {why}.")
            else:
                say(f"  ● Агенты Claude {side} ведут героев: первые решения пришли" +
                    (f" (модель: {model})." if model else "."))
        if p["error"] and p["error"] != told.get(("error", team)):
            told[("error", team)] = p["error"]
            n = told.get(("errors", team), 0) + 1
            told[("errors", team)] = n
            if n <= ERRORS_SHOWN:
                say(f"  ! Агент {side} {p['error'][:160]}")
            if n == ERRORS_SHOWN:
                say(f"    Дальше ошибки агентов {side} — только в журнале агентов (coach\\logs\\agents_local_*.jsonl).")
        pause = p.get("pause") or ""
        if pause != told.get(("pause", team), ""):
            told[("pause", team)] = pause
            if pause:
                say(f"  ! Агенты {side} на паузе: {pause}. Пока героями правит запасной исполнитель (приказы тренера).")
        if p.get("limit") and not told.get(("limit", team)):             # рецензия 7: иначе снова «агентов нет»
            told[("limit", team)] = True
            say(f"  ! Агенты {side} выбрали предел вызовов Claude на этот запуск ({p.get('max_calls')}): дальше "
                "героями правит запасной исполнитель по приказам тренера.")
    if now - told.get("summary_t", now) >= every:
        def part(t, p):
            side = SIDE_OF.get(t, t)
            if p.get("claude") is False:
                return f"{side} — ПРАВИЛА, не Claude (решений {p['decisions']})"
            calls = f", вызовов Claude {p['paid_calls']}" if "paid_calls" in p else ""
            return f"{side} — решений {p['decisions']}{calls}, ошибок {p['errors']}"
        cost = ""
        try:                                                    # по ключу — оценка расхода по ценам быстрой модели
            est = hub.summary().get("cost_usd_est") if hasattr(hub, "summary") else None
            cost = f" Потрачено по ключу ≈ ${est:.2f}." if est else ""
        except Exception:                                       # noqa: BLE001 — сводка вспомогательная
            pass
        say("  Агенты: " + "; ".join(part(t, p) for t, p in prog.items()) + "." + cost)
        told["summary_t"] = now
    told.setdefault("summary_t", now)


def watch(room, period: float = 2.0, stop=lambda: False, sleep=time.sleep, clock=time.time,
          empty_after: float = 15.0) -> None:
    """Сообщать хосту, что изменилось: друг открыл пульт; игра на связи и сколько героев отдала агентам (ни одного
    дольше empty_after секунд — сказать прямо); агенты ведут героев, их ошибки и паузы."""
    friend_on = game_on = False
    heroes = None
    linked_at = 0.0
    told: dict = {}
    game = None
    while not stop():
        now = clock()
        gid = getattr(room, "game_id", None)
        if gid != game:                                # новый матч: снова сказать про героев и первые решения
            if game is not None:
                told, heroes, linked_at = {}, None, now
                try:                                   # решения считаются с запуска лаунчера — запомнить начало
                    for team, p in room.agents.progress().items():
                        told[("base", team)] = p["decisions"]
                except Exception:                      # noqa: BLE001 — без агентов начало — ноль
                    pass
            game = gid
        f = now - room.console_seen.get(REMOTE, 0) < 10
        g = room.game_linked()
        if f != friend_on:
            say("  ● Друг открыл пульт." if f else "  ○ Пульт друга закрыт или потерял связь.")
            friend_on = f
        if g != game_on:
            game_on = g
            if g:
                linked_at, heroes = now, hero_counts(getattr(room, "last_tick", None))
                say(f"  ● Игра на связи с сервером тренера. Героев у агентов: Свет {heroes['radiant']}, "
                    f"Тьма {heroes['dire']}.")
            else:
                heroes = None
                say("  ○ Игра не отвечает (матч кончился или Дота закрыта).")
        elif g:
            n = hero_counts(getattr(room, "last_tick", None))
            if n != heroes:
                heroes = n
                say(f"  ● Героев у агентов: Свет {n['radiant']}, Тьма {n['dire']}.")
            if not any(n.values()) and now - linked_at >= empty_after and not told.get("empty"):
                told["empty"] = True
                say("  ! Игра на связи, но героев агентам не отдаёт: кастомка не нашла героев ботов. Пришлите снимок")
                say("    этого окна — строки «Дота: …» покажут причину.")
        if g:
            try:
                report_agents(room, told, now)
            except Exception as e:                    # noqa: BLE001 — сводка вспомогательная: окно и игра живут
                if not told.get("broken"):
                    told["broken"] = True
                    say(f"  (не смог прочитать состояние агентов: {type(e).__name__}: {e})")
        sleep(period)


if __name__ == "__main__":
    sys.exit(main())
