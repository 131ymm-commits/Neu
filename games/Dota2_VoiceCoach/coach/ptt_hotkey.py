"""Глобальная клавиша «нажми и говори» для Windows — без установки пакетов (ctypes).

Пока клавиша зажата в игре, страница тренера в Chrome слушает микрофон (сервер передаёт ей
событие ptt). Запуск в отдельном окне, не закрывать:

    python ptt_hotkey.py                    боковая кнопка мыши «назад» (XBUTTON1)
    python ptt_hotkey.py --key F8           или любая клавиша: F1–F12, CAPSLOCK, XBUTTON2, …
    python ptt_hotkey.py --team dire        для тренера Тьмы

Работает ли распознавание в фоновой вкладке Chrome — проверить (docs/FIRST_RUN.md).
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.request

VK = {"XBUTTON1": 0x05, "XBUTTON2": 0x06, "MBUTTON": 0x04, "CAPSLOCK": 0x14, "SPACE": 0x20,
      "LALT": 0xA4, "RALT": 0xA5, "LCTRL": 0xA2, "RCTRL": 0xA3}
VK.update({f"F{i}": 0x70 + i - 1 for i in range(1, 13)})


def windows_key_state():
    import ctypes
    user32 = ctypes.windll.user32

    def pressed(vk: int) -> bool:
        return bool(user32.GetAsyncKeyState(vk) & 0x8000)
    return pressed


def run(key: int, send, pressed, sleep=time.sleep, ticks: int | None = None, period: float = 0.02):
    """Опрашивает клавишу и шлёт down/up только на смену состояния. ticks — для тестов."""
    down = False
    n = 0
    while ticks is None or n < ticks:
        now = pressed(key)
        if now != down:
            down = now
            try:
                send("down" if down else "up")
            except OSError as e:
                print(f"сервер тренера не отвечает: {e}")
        sleep(period)
        n += 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Глобальная клавиша «нажми и говори»")
    ap.add_argument("--key", default="XBUTTON1", help="XBUTTON1, XBUTTON2, F1–F12, CAPSLOCK…")
    ap.add_argument("--server", default="http://127.0.0.1:8787")
    ap.add_argument("--room", default="local")
    ap.add_argument("--team", default="radiant", choices=["radiant", "dire"])
    a = ap.parse_args(argv)
    if sys.platform != "win32":
        raise SystemExit("Нужна Windows: клавиша читается через user32.GetAsyncKeyState")
    key = VK.get(a.key.upper())
    if key is None:
        raise SystemExit(f"Не знаю клавишу {a.key}; есть: {', '.join(sorted(VK))}")

    def send(state):
        urllib.request.urlopen(f"{a.server}/api/{a.room}/ptt?team={a.team}&state={state}", timeout=2).read()

    print(f"Держите {a.key.upper()} и говорите. Ctrl+C — выход.")
    try:
        run(key, send, windows_key_state())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
