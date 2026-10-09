"""Игра вдвоём одним файлом (решение Д14). Слова автора, 09.10.2026: «все очень сложно сделай нормальный вход и
конект. это просто ужас. придумай сам как сделать. я должен запустить один файл и опонент должен запустить один
файл все остальное делаеш ты».

Хост запускает ИГРАТЬ.bat — он находит или скачивает Python, обновляет файлы игры и запускает этот лаунчер:
  1. ключ API Anthropic — спрашивает один раз и запоминает (coach/logs/play.json, вне git); без ключа агенты играют
     на правилах (бесплатно, не Claude); модель — самая новая из линии быстрых по списку моделей ключа;
  2. ставит кастомку в Доту (папку Доты ищет сам, не нашёл — спрашивает один раз);
  3. скачивает cloudflared (туннель Cloudflare) в .runtime/ — один раз;
  4. запускает сервер тренера, пульт Тьмы и туннель; ссылку на пульт кладёт в ящик (rendezvous.py) и копирует;
  5. делает файл соперника ДЛЯ_ДРУГА.html — один раз, подходит ко всем играм — и показывает его в Проводнике;
  6. запускает Доту с инструментами и сразу кастомку (так запускает аддоны шаблон ModDota: dota2.exe -tools -addon).
Соперник открывает ДЛЯ_ДРУГА.html: файл находит игру в ящике и открывает пульт; перезапуск игры пульт переживает.
"""
from __future__ import annotations

import argparse
import atexit
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
from .agents import AgentHub, make_backend
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
REMOTE = "dire"                                # хост в Доте — тренер Света, друг — Тьмы
MAX_CALLS = 3000                               # платных вызовов на сторону: ≈ 30–40 минут игры
MODELS_API = "https://api.anthropic.com/v1/models"
FAST_LINE = "haiku"                            # линия самых быстрых моделей в списке моделей API (поле line)
CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
DETACHED = 0x00000008 | 0x00000200            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: Дота живёт без окна


def say(text: str = "") -> None:
    print(text, flush=True)


def _ask(ask, prompt: str) -> str:
    """Ответ человека; окно без ввода (запуск не из консоли) — пустой ответ, а не падение."""
    try:
        return (ask(prompt) or "").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


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

def pick_model(api_key: str, opener=urllib.request.urlopen) -> tuple[str | None, str]:
    """Самая новая модель линии быстрых из списка моделей, доступных ключу. → (имя модели или None, почему нет)."""
    req = urllib.request.Request(MODELS_API + "?limit=100",
                                 headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"})
    try:
        with opener(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return None, "ключ не подошёл" if e.code in (401, 403) else f"API ответил HTTP {e.code}"
    except (OSError, ValueError) as e:
        return None, f"нет связи с API Anthropic ({e})"
    models = [m for m in data.get("data") or [] if isinstance(m, dict) and m.get("id")]
    fast = [m for m in models if m.get("line") == FAST_LINE] or [m for m in models if FAST_LINE in str(m["id"])]
    if not fast:
        return None, "среди моделей ключа нет быстрой линии"
    return max(fast, key=lambda m: str(m.get("created_at") or ""))["id"], ""


def setup_claude(cfg: dict, args, ask=input, opener=urllib.request.urlopen) -> tuple[str | None, str | None]:
    """Ключ и модель для агентов. → (ключ, модель) или (None, None) — играть на правилах."""
    if args.rules:
        return None, None
    key = os.environ.get("ANTHROPIC_API_KEY") or cfg.get("api_key")
    if key is None or args.ask_key:
        say("  Ключ API Anthropic: вставьте его (Ctrl+V или правый щелчок мыши) и нажмите Enter.")
        say("  Ключ берут на console.anthropic.com → API Keys. Без ключа просто нажмите Enter —")
        say("  агенты сыграют на правилах: бесплатно, но это не Claude. Ключ запоминается — спрошу один раз.")
        for _ in range(3):
            key = _ask(ask, "  ключ> ")
            if not key:
                break
            model, why = pick_model(key, opener)
            if model:
                cfg["api_key"], cfg["model"] = key, model
                save_config(cfg)
                return key, model
            say(f"  Не вышло: {why}. Попробуйте ещё раз или Enter — без Claude.")
        cfg["api_key"] = ""                                  # выбрали «без Claude» — больше не спрашиваем
        save_config(cfg)
        return None, None
    if not key:
        return None, None
    model, why = pick_model(key, opener)
    if model:
        if model != cfg.get("model"):
            cfg["model"] = model
            save_config(cfg)
        return key, model
    if cfg.get("model") and why.startswith("нет связи"):
        return key, cfg["model"]                              # список моделей недоступен — берём прошлую
    say(f"  Claude: {why} — агенты сыграют на правилах. Сменить ключ: ИГРАТЬ.bat --ask-key")
    return None, None


# --- загрузки ---

def download(url: str, dest: Path, opener=urllib.request.urlopen, label: str = "") -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
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
    os.replace(part, dest)


def ensure_cloudflared(opener=urllib.request.urlopen, which=shutil.which, windows: bool = os.name == "nt") -> str | None:
    found = which("cloudflared")
    if found:
        return found
    local = RUNTIME / ("cloudflared.exe" if windows else "cloudflared")
    if local.exists() and local.stat().st_size > 1_000_000:
        return str(local)
    if not windows:
        return None
    download(CLOUDFLARED_URL, local, opener, "туннель Cloudflare")
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
    p = _ask(ask, "  папка> ").strip('"')
    if ok(p):
        cfg["dota"] = p
        save_config(cfg)
        return Path(p)
    return None


def _running(image: str) -> bool:
    if os.name != "nt":
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {image}", "/NH"], capture_output=True, text=True,
                             timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return image.lower() in out.lower()


def dota_argv(dota: Path) -> list[str]:
    exe = dota / "game" / "bin" / "win64" / "dota2.exe"
    return [str(exe), "-novid", "-tools", "-addon", ADDON, "-condebug", "+dota_launch_custom_game", ADDON, "dota"]


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
    popen(dota_argv(dota), **kw)
    note = "" if (win64 / "resourcecompiler.exe").exists() else (
        " Если кастомка не откроется — поставьте бесплатное дополнение Dota 2 Workshop Tools: Steam → Dota 2 → "
        "Свойства → DLC.")
    return "Дота запускается с кастомкой: возьмите любого героя — вы тренер Света." + note


# --- файл друга и мелочи Windows ---

def make_friend_file(path: Path, secret: str, base: str) -> Path:
    html = (WEB / "friend.html").read_text(encoding="utf-8")
    html = (html.replace("/*__RV_JS__*/", (WEB / "rv.js").read_text(encoding="utf-8"))
            .replace("__RV_BASE__", base).replace("__SECRET__", secret))
    path.write_text(html, encoding="utf-8")
    return path


def copy_text(text: str) -> bool:
    if os.name != "nt":
        return False
    try:
        subprocess.run(["clip"], input=text.encode("utf-16-le"), timeout=5, check=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def reveal(path: Path) -> None:
    if os.name == "nt":
        try:
            subprocess.Popen(["explorer", "/select,", str(path)])
        except OSError:
            pass


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


def main(argv=None, ask=input) -> int:
    args = parse(argv)
    say("=== Тренер Доты: игра вдвоём ===")
    cfg = load_config()
    if args.new_friend or not cfg.get("secret"):
        cfg["secret"] = RV.new_secret()
        save_config(cfg)
    secret = cfg["secret"]

    say("[1/6] Агенты героев")
    key, model = setup_claude(cfg, args, ask)
    if key:
        os.environ["ANTHROPIC_API_KEY"] = key
        backend = make_backend("api", model)
        say(f"  Героев ведёт Claude (быстрая модель), предел {args.max_calls} вызовов на сторону. Платите вы.")
    else:
        backend = make_backend("rules")
        say("  Героев ведут правила (не Claude). Подключить Claude: ИГРАТЬ.bat --ask-key")

    say("[2/6] Кастомка в Доте")
    dota = find_dota(cfg, args, ask, prompt=not args.no_dota)
    if dota:
        try:
            _install_module().install(dota, log=lambda s: None)
            say(f"  Установлена: {dota}")
        except SystemExit as e:
            say(f"  Не установил: {e}")
    else:
        say("  Доту не нашёл — кастомку поставлю, когда скажете путь (ИГРАТЬ.bat --dota \"папка\")")

    say("[3/6] Сервер тренера")
    log = LOGS / f"agents_local_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    try:
        srv = serve("127.0.0.1", GAME_PORT, lambda room: AgentHub(
            {"radiant": backend, "dire": backend}, max_calls=args.max_calls, log_path=log))
    except OSError:
        say("  Порт 8787 занят: похоже, сервер уже запущен в другом окне. Закройте его и запустите снова.")
        return 1
    threading.Thread(target=srv.serve_forever, daemon=True, name="game").start()
    room = srv.hub.room("local")
    keys = load_keys((REMOTE,), new=args.new_friend)
    console = serve_console(srv.hub, "127.0.0.1", CONSOLE_PORT, "local", keys, rv_origin=args.rv)
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
    tunnel = None
    if not args.no_tunnel:
        cf = None
        try:
            cf = ensure_cloudflared()
        except (OSError, urllib.error.URLError) as e:
            say(f"  Не скачал туннель Cloudflare: {e}")
        if cf:
            def on_url(url):
                link = console_url(url, keys[REMOTE])
                pub.set_url(link)
                say(f"  Готово. Ссылка на пульт друга{' (скопирована)' if copy_text(link) else ''}: {link}")
                say(f"  Друг открывает файл {FRIEND_FILE} — пульт откроется сам.")
            tunnel = start_tunnel(CONSOLE_PORT, on_url, cf, on_error=lambda m: say("  " + m))
            if tunnel is not None:
                atexit.register(tunnel.terminate)
                say("  Туннель поднимается — несколько секунд…")
    if tunnel is None:
        say("  Без туннеля: пульт открывается только на этом ПК.")

    say("[5/6] Файл для друга")
    first = not cfg.get("friend_shown") or args.new_friend
    say(f"  {friend}")
    if first:
        say("  Отправьте этот файл другу ОДИН раз (в мессенджере, как документ). Он подходит ко всем следующим играм:")
        say("  друг открывает его двойным щелчком, файл сам находит вашу игру. Показываю файл в Проводнике.")
        reveal(friend)
        cfg["friend_shown"] = True
        save_config(cfg)
    else:
        say("  Друг уже получал этот файл — пусть просто откроет его.")

    say("[6/6] Дота")
    if dota and not args.no_dota:
        say("  " + launch_dota(dota))
    else:
        say(f"  Запустите Доту с инструментами и в её консоли:  dota_launch_custom_game {ADDON} dota")

    say("")
    say("Окно не закрывайте, пока играете. Ctrl+C — закончить игру.")
    try:
        watch(room)
    except KeyboardInterrupt:
        pass
    say("Заканчиваю…")
    pub.close()
    if tunnel is not None:
        tunnel.terminate()
    console.shutdown()
    srv.shutdown()
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
