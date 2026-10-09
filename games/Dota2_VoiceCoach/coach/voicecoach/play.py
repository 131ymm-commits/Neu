"""Игра вдвоём одним файлом (решение Д14). Слова автора, 09.10.2026: «все очень сложно сделай нормальный вход и
конект. это просто ужас. придумай сам как сделать. я должен запустить один файл и опонент должен запустить один
файл все остальное делаеш ты».

Хост запускает ИГРАТЬ.bat — он находит или скачивает Python, обновляет файлы игры и запускает этот лаунчер:
  1. ключ API Anthropic — спрашивает один раз и запоминает (coach/logs/play.json, вне git); без ключа агенты играют
     на правилах (бесплатно, не Claude); модель — самая новая из линии быстрых по списку моделей ключа; сменить ключ
     можно при каждом запуске — нажать любую клавишу, пока лаунчер это предлагает;
  2. ставит кастомку в Доту (папку Доты ищет сам, не нашёл — спрашивает);
  3. скачивает cloudflared (туннель Cloudflare) в .runtime/ — один раз;
  4. запускает сервер тренера, пульт Тьмы и туннель; ссылку на пульт кладёт в ящик (rendezvous.py) и копирует;
     туннель упал — поднимает заново;
  5. делает файл соперника ДЛЯ_ДРУГА.html — один раз, подходит ко всем играм — и показывает его в Проводнике;
  6. запускает Доту с инструментами и сразу кастомку (так запускает аддоны шаблон ModDota: dota2.exe -tools -addon).
Соперник открывает ДЛЯ_ДРУГА.html: файл находит игру в ящике и открывает пульт; перезапуск игры пульт переживает.
Закончить игру — Enter в окне лаунчера.
"""
from __future__ import annotations

import argparse
import atexit
import getpass
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import rendezvous as RV
from .agents import AgentHub, ApiBackend, make_backend
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
MAX_CALLS = 3000                               # платных вызовов на сторону: ≈ 30–40 минут игры
MODELS_API = "https://api.anthropic.com/v1/models"
FAST_LINE = "haiku"                            # линия самых быстрых моделей: ищется в имени (id) модели из списка
CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
DETACHED = 0x00000008 | 0x00000200            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: Дота живёт без окна
OFFER_S = 3.0                                  # с: сколько ждать нажатия «сменить ключ» при запуске
LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({})).open   # свой ПК — мимо прокси системы


def say(text: str = "") -> None:
    print(text, flush=True)


def _ask(ask, prompt: str) -> str | None:
    """Ответ человека. Ctrl+C или окно без ввода (запуск не из консоли) — None: человек ничего не выбрал."""
    try:
        return (ask(prompt) or "").strip()
    except (EOFError, KeyboardInterrupt):
        return None


def offer(text: str, seconds: float = OFFER_S) -> bool:
    """Предложить действие одной клавишей: нажата ли любая клавиша за seconds секунд. Только окно Windows; иначе — нет.
    Раскладка не важна (любая клавиша), нажатое раньше не считается."""
    if os.name != "nt":
        return False
    try:
        import msvcrt  # noqa: PLC0415 — есть только на Windows
        if not sys.stdin.isatty():
            return False
        while msvcrt.kbhit():
            msvcrt.getwch()
        say(text)
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if msvcrt.kbhit():
                msvcrt.getwch()
                return True
            time.sleep(0.05)
    except Exception:                                   # noqa: BLE001 — меню не должно ронять запуск
        return False
    return False


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
    req = urllib.request.Request(MODELS_API + "?limit=100",
                                 headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"})
    try:
        with opener(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return None, api_error(e), "key" if e.code in (401, 403) else "net"
    except (OSError, ValueError) as e:
        return None, f"нет связи с API Anthropic ({e})", "net"
    models = [m for m in (data.get("data") if isinstance(data, dict) else None) or []
              if isinstance(m, dict) and m.get("id")]
    fast = [m for m in models if FAST_LINE in str(m["id"]).lower()]
    if not fast:
        return None, "среди моделей ключа нет быстрой линии", "none"
    return max(fast, key=lambda m: str(m.get("created_at") or ""))["id"], "", ""


def ask_key(cfg: dict, ask, opener) -> tuple[str | None, str | None]:
    """Спросить ключ. Пустой Enter — «без Claude» (запоминается); ключ проверяется списком моделей. Нет связи —
    ключ всё равно сохраняется (проверится в следующий раз); Ctrl+C — ничего не запоминать."""
    say("  Ключ API Anthropic: вставьте его (Ctrl+V или правый щелчок мыши) и нажмите Enter. На экране ключ")
    say("  не появится — так и задумано. Ключ берут на console.anthropic.com → API Keys.")
    say("  Без ключа просто нажмите Enter: агенты сыграют на правилах — бесплатно, но это не Claude.")
    for _ in range(3):
        key = _ask(ask, "  ключ> ")
        if key is None:
            say("  Ключ не ввели — в этот раз правила, спрошу при следующем запуске.")
            return None, None
        if not key:
            cfg["api_key"] = ""                          # «без Claude»: при запуске можно будет сменить
            save_config(cfg)
            return None, None
        model, why, kind = pick_model(key, opener)
        if model:
            cfg["api_key"], cfg["model"] = key, model
            save_config(cfg)
            say(f"  Ключ {mask(key)} принят.")
            return key, model
        if kind == "net":
            cfg["api_key"] = key
            save_config(cfg)
            say(f"  Ключ {mask(key)} сохранил, но проверить не смог: {why}.")
            say("  В этот раз агенты сыграют на правилах, Claude — со следующего запуска.")
            return None, None
        say(f"  Ключ {mask(key)} не подошёл: {why}. Вставьте другой или Enter — без Claude.")
    say("  Ключи не подошли — в этот раз правила. Ключ спрошу при следующем запуске.")
    return None, None


def setup_claude(cfg: dict, args, ask=getpass.getpass, opener=urllib.request.urlopen,
                 offer=offer) -> tuple[str | None, str | None]:
    """Ключ и модель для агентов. → (ключ, модель) или (None, None) — играть на правилах."""
    if args.rules:
        return None, None
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        key = cfg.get("api_key")
        if key is not None and not args.ask_key:        # решение уже есть — показать и дать сменить одной клавишей
            shown = f"ключ {mask(key)}" if key else "выключен — агенты на правилах"
            if offer(f"  Claude: {shown}. Сменить ключ — нажмите любую клавишу в ближайшие {OFFER_S:.0f} секунды…"):
                key = None
        if key is None or args.ask_key:
            return ask_key(cfg, ask, opener)
    if not key:
        return None, None
    model, why, kind = pick_model(key, opener)
    if model:
        if model != cfg.get("model"):
            cfg["model"] = model
            save_config(cfg)
        return key, model
    if kind == "key" and not os.environ.get("ANTHROPIC_API_KEY"):
        say(f"  Сохранённый ключ {mask(key)} не подошёл: {why}.")
        return ask_key(cfg, ask, opener)
    if kind == "net" and cfg.get("model"):
        say(f"  Список моделей недоступен ({why}) — беру прошлую модель.")
        return key, cfg["model"]
    say(f"  Claude: {why} — в этот раз агенты сыграют на правилах.")
    return None, None


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
    exe = dota / "game" / "bin" / "win64" / "dota2.exe"
    return [str(exe), "-novid", "-tools", "-addon", ADDON, "-condebug", "+dota_launch_custom_game", ADDON, "dota"]


def install_custom_game(dota: Path, running=_running) -> str:
    """Поставить или обновить кастомку. Открытая Дота держит файлы — тогда не трогаем. → что сказать хосту."""
    if running("dota2.exe"):
        return "Дота уже открыта — кастомку не обновляю (её файлы заняты). Закройте Доту и запустите снова."
    try:
        _install_module().install(dota, log=lambda s: None)
        return f"Установлена: {dota}"
    except (SystemExit, OSError) as e:
        return f"Не установил: {e}"


def launch_dota(dota: Path, popen=subprocess.Popen, running=_running, wait=time.sleep) -> str:
    """Запустить Доту с инструментами и сразу кастомку. → что сказать хосту."""
    if running("dota2.exe"):
        return ("Дота уже запущена. Закройте её и запустите ИГРАТЬ.bat снова — или введите в консоли Доты:  "
                f"dota_launch_custom_game {ADDON} dota")
    win64 = dota / "game" / "bin" / "win64"
    if not (win64 / "dota2.exe").exists():
        return f"Не нашёл {win64 / 'dota2.exe'} — запустите Доту сами"
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
    kw = {"cwd": str(win64), "close_fds": True}
    if os.name == "nt":
        kw["creationflags"] = DETACHED
    try:
        popen(dota_argv(dota), **kw)
    except OSError as e:
        return f"Не запустил Доту: {e}. Запустите её сами и в консоли Доты:  dota_launch_custom_game {ADDON} dota"
    note = "" if (win64 / "resourcecompiler.exe").exists() else (
        " Если кастомка не откроется — поставьте бесплатное дополнение Dota 2 Workshop Tools: Steam → Dota 2 → "
        "Свойства → DLC.")
    return "Дота запускается с кастомкой: возьмите любого героя — вы тренер Света." + note


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


def wait_enter(stop: threading.Event, ask=input) -> None:
    """Enter в окне — закончить игру. Окно без ввода — ждать только Ctrl+C."""
    try:
        ask("")
    except (EOFError, OSError):
        return
    except KeyboardInterrupt:
        pass
    stop.set()


# --- главное ---

def parse(argv=None):
    ap = argparse.ArgumentParser(description="Тренер Доты: игра вдвоём одним файлом (ИГРАТЬ.bat)")
    ap.add_argument("--rules", action="store_true", help="агенты на правилах (без Claude, бесплатно)")
    ap.add_argument("--ask-key", action="store_true", help="спросить ключ API заново")
    ap.add_argument("--max-calls", type=int, default=MAX_CALLS, help="предел платных вызовов на сторону")
    ap.add_argument("--dota", help="папка «dota 2 beta», если не нашлась сама")
    ap.add_argument("--no-dota", action="store_true", help="не запускать Доту (запустить самому)")
    ap.add_argument("--no-tunnel", action="store_true", help="без туннеля: пульт только на этом ПК")
    ap.add_argument("--new-friend", action="store_true",
                    help="новый файл для друга: старый перестанет находить игру (и старая ссылка на пульт тоже)")
    ap.add_argument("--rv", default=RV.RV_DEFAULT, help="адрес ящика (сервер ntfy)")
    return ap.parse_args(argv)


def main(argv=None, ask=input, ask_secret=getpass.getpass, offer=offer, enter=input) -> int:
    args = parse(argv)
    say("=== Тренер Доты: игра вдвоём ===")
    if already_running():
        say("Игра уже запущена в другом окне ИГРАТЬ.bat — переключитесь на него (второе окно не нужно).")
        return 1
    cfg = load_config()
    if args.new_friend or not cfg.get("secret"):
        cfg["secret"] = RV.new_secret()
        save_config(cfg)
    secret = cfg["secret"]

    say("[1/6] Агенты героев")
    key, model = setup_claude(cfg, args, ask_secret, offer=offer)
    if key:
        backend = ApiBackend(model, api_key=key)        # ключ — только агентам, не в окружение Доты и cloudflared
        say(f"  Героев ведёт Claude (быстрая модель), предел {args.max_calls} вызовов на сторону. Платите вы.")
    else:
        backend = make_backend("rules")
        say("  Героев ведут правила (не Claude). Подключить Claude: при следующем запуске нажмите любую клавишу,")
        say("  когда лаунчер предложит сменить ключ.")

    say("[2/6] Кастомка в Доте")
    dota = find_dota(cfg, args, ask, prompt=not args.no_dota)
    if dota:
        say("  " + install_custom_game(dota))
    else:
        say("  Доту не нашёл — спрошу путь при следующем запуске.")
    quickedit_off()                                                 # вопросов больше не будет

    say("[3/6] Сервер тренера")
    log = LOGS / f"agents_local_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    try:
        srv = serve("127.0.0.1", GAME_PORT, lambda room: AgentHub(
            {"radiant": backend, "dire": backend}, max_calls=args.max_calls, log_path=log))
    except OSError as e:
        say(f"  Порт {GAME_PORT} занят другой программой ({e}) — серверу тренера некуда встать. Закройте её и "
            "запустите снова.")
        return 1
    threading.Thread(target=srv.serve_forever, daemon=True, name="game").start()
    room = srv.hub.room("local")
    keys = load_keys((REMOTE,), new=args.new_friend)
    try:
        console = serve_console(srv.hub, "127.0.0.1", CONSOLE_PORT, "local", keys, rv_origin=args.rv)
    except OSError as e:
        srv.shutdown()
        srv.server_close()
        say(f"  Порт {CONSOLE_PORT} занят другой программой ({e}) — пульту друга некуда встать. Закройте её и "
            "запустите снова.")
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
    if dota and not args.no_dota:
        say("  " + launch_dota(dota))
    else:
        say(f"  Запустите Доту с инструментами и в её консоли:  dota_launch_custom_game {ADDON} dota")

    say("")
    say("Окно не закрывайте, пока играете. Закончить игру — Enter.")
    stop = threading.Event()
    threading.Thread(target=wait_enter, args=(stop, enter), daemon=True, name="enter").start()
    try:
        watch(room, stop=stop.is_set, sleep=stop.wait)
    except KeyboardInterrupt:
        pass
    say("Заканчиваю…")
    if room.agents is not None:
        room.agents.close()                                       # вызовы из очереди не ждём и не оплачиваем
    pub.close()
    if keeper is not None:
        keeper.close()
    for server in (console, srv):
        server.shutdown()
        server.server_close()
    if room.agents is not None:
        s = room.agents.summary()
        say(f"Вызовов Claude: {s.get('paid_calls', 0)}, ошибок: {s.get('errors', 0)}, "
            f"задержка (медиана): {s.get('latency_p50_s')} с. Журнал: {log}")
    return 0


def watch(room, period: float = 2.0, stop=lambda: False, sleep=time.sleep) -> None:
    """Сообщать хосту, что изменилось: друг открыл пульт, игра на связи."""
    friend_on = game_on = False
    while not stop():
        now = time.time()
        f = now - room.console_seen.get(REMOTE, 0) < 10
        g = room.game_linked()
        if f != friend_on:
            say("  ● Друг открыл пульт." if f else "  ○ Пульт друга закрыт или потерял связь.")
            friend_on = f
        if g != game_on:
            say("  ● Игра на связи с сервером тренера." if g else "  ○ Игра не отвечает (матч кончился или Дота закрыта).")
            game_on = g
        sleep(period)


if __name__ == "__main__":
    sys.exit(main())
