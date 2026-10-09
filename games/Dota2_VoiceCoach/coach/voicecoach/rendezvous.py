"""«Почтовый ящик» для игры вдвоём (решение Д14): как файл соперника находит игру хоста без ручных ссылок.

Адрес туннеля к пульту (https://….trycloudflare.com) меняется при каждом запуске. Поэтому лаунчер хоста кладёт
текущую ссылку на пульт в общий ящик — тему на ntfy.sh (бесплатный сервис уведомлений, без учётной записи; имя
темы работает как пароль), а файл соперника ДЛЯ_ДРУГА.html читает оттуда самую свежую.

Секрет — 32 случайных байта, общие у хоста (coach/logs/play.json) и файла соперника; на сервис он не уходит.
Из секрета выводятся имя темы и два ключа. Сообщение зашифровано и подписано (HMAC-SHA256 — есть и в Python,
и в браузере через WebCrypto, web/rv.js): сервис и посторонние не прочтут ссылку с ключом пульта и не подсунут
свою, а подделку и старьё файл соперника отбрасывает.

  сообщение = "vc1." + b64(nonce) + "." + b64(шифртекст) + "." + b64(подпись)
  шифртекст = JSON {"url"|"closed", "t"} XOR поток HMAC(k_enc, nonce ‖ номер блока)
  подпись   = HMAC(k_mac, nonce ‖ шифртекст)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.parse
import urllib.request

RV_DEFAULT = "https://ntfy.sh"
TOPIC_PREFIX = "dcoach-"
MAX_AGE = 12 * 3600            # с: старше — не верим (ntfy.sh хранит сообщения недолго, часы)
REFRESH = 20 * 60              # с: хост повторяет ссылку, пока игра идёт
VERSION = "vc1"


def b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _h(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()


def new_secret() -> str:
    return b64e(os.urandom(32))


def topic(secret: str) -> str:
    """Имя темы ящика: из секрета (буквы, цифры, «-», «_»; ntfy принимает до 64 знаков)."""
    return TOPIC_PREFIX + b64e(_h(b64d(secret), b"topic"))[:32]


def _keys(secret: str) -> tuple[bytes, bytes]:
    k = b64d(secret)
    return _h(k, b"enc"), _h(k, b"mac")


def _stream(k_enc: bytes, nonce: bytes, n: int) -> bytes:
    out, i = b"", 0
    while len(out) < n:
        out += _h(k_enc, nonce + i.to_bytes(4, "big"))
        i += 1
    return out[:n]


def seal(secret: str, obj: dict, nonce: bytes | None = None) -> str:
    k_enc, k_mac = _keys(secret)
    nonce = nonce or os.urandom(16)
    pt = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ct = bytes(a ^ b for a, b in zip(pt, _stream(k_enc, nonce, len(pt))))
    return ".".join((VERSION, b64e(nonce), b64e(ct), b64e(_h(k_mac, nonce + ct))))


def unseal(secret: str, text: str) -> dict | None:
    """Сообщение ящика → {"url"|"closed", "t"}; чужое, испорченное или подделанное — None."""
    try:
        ver, n, c, tag = str(text).strip().split(".")
        if ver != VERSION:
            return None
        nonce, ct, tag = b64d(n), b64d(c), b64d(tag)
        k_enc, k_mac = _keys(secret)
        if not hmac.compare_digest(tag, _h(k_mac, nonce + ct)):
            return None
        obj = json.loads(bytes(a ^ b for a, b in zip(ct, _stream(k_enc, nonce, len(ct)))).decode("utf-8"))
        return obj if isinstance(obj, dict) and isinstance(obj.get("t"), (int, float)) else None
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def latest(secret: str, messages, now: float | None = None) -> dict | None:
    """Самое свежее подлинное сообщение не старше MAX_AGE (тексты сообщений темы)."""
    now = time.time() if now is None else now
    best = None
    for m in messages:
        obj = unseal(secret, m)
        if obj and now - obj["t"] <= MAX_AGE and obj["t"] <= now + 300 and (best is None or obj["t"] > best["t"]):
            best = obj
    return best


def publish(base: str, name: str, text: str, opener=urllib.request.urlopen, timeout: float = 10.0) -> bool:
    req = urllib.request.Request(f"{base.rstrip('/')}/{name}", data=text.encode("ascii"), method="POST",
                                 headers={"Content-Type": "text/plain"})
    try:
        with opener(req, timeout=timeout) as r:
            return 200 <= getattr(r, "status", 200) < 300
    except OSError:
        return False


def fetch(base: str, name: str, since: str = "12h", opener=urllib.request.urlopen, timeout: float = 10.0) -> list:
    """Тексты сообщений темы за since (ntfy: /<тема>/json?poll=1&since=…, по JSON-объекту на строку)."""
    url = f"{base.rstrip('/')}/{name}/json?" + urllib.parse.urlencode({"poll": "1", "since": since})
    with opener(url, timeout=timeout) as r:
        body = r.read().decode("utf-8", "replace")
    out = []
    for line in body.splitlines():
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(m, dict) and m.get("event") == "message" and isinstance(m.get("message"), str):
            out.append(m["message"])
    return out


class Publisher:
    """Держит в ящике актуальную ссылку на пульт: при смене адреса и раз в REFRESH секунд; при выходе — «закрыто»."""

    def __init__(self, secret: str, base: str = RV_DEFAULT, opener=urllib.request.urlopen, refresh: float = REFRESH,
                 on_result=None):
        self.secret, self.base, self.opener, self.refresh = secret, base, opener, refresh
        self.name = topic(secret)
        self.url: str | None = None
        self.on_result = on_result or (lambda ok, what: None)
        self.wake = threading.Event()
        self.stopped = False
        self.thread: threading.Thread | None = None

    def send(self, obj: dict) -> bool:
        ok = publish(self.base, self.name, seal(self.secret, {**obj, "t": time.time()}), self.opener)
        self.on_result(ok, obj)
        return ok

    def set_url(self, url: str) -> bool:
        self.url = url
        ok = self.send({"url": url})
        if self.thread is None:
            self.thread = threading.Thread(target=self._loop, daemon=True, name="rendezvous")
            self.thread.start()
        return ok

    def _loop(self):
        while not self.stopped:
            self.wake.wait(self.refresh)
            if self.stopped:
                return
            if self.url:
                self.send({"url": self.url})

    def close(self) -> bool:
        self.stopped = True
        self.wake.set()
        return self.send({"closed": True})
