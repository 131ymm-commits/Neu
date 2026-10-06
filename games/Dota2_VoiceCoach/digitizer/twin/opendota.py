"""Клиент OpenDota API (только стандартная библиотека).

Адреса и поведение API записаны по документации docs.opendota.com и коду odota/core
(см. research/02_player_digitization.md); из контейнера, где писался код, api.opendota.com
был закрыт, поэтому вживую клиент проверяется у человека: python -m twin.cli check.
Ответы кешируются на диск: матч не меняется, повторный запрос не тратит лимит.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.opendota.com/api"
DEFAULT_CACHE = Path(os.environ.get("TWIN_CACHE", Path.home() / ".dota_twin_cache"))


class OpenDota:
    def __init__(self, api_key: str | None = None, cache_dir: Path | None = DEFAULT_CACHE,
                 min_interval_s: float = 1.1, fetch=None):
        self.api_key = api_key or os.environ.get("OPENDOTA_API_KEY")
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.min_interval_s = min_interval_s     # бесплатный лимит — порядка запроса в секунду
        self._last = 0.0
        self._fetch = fetch or self._http

    # --- низкий уровень ---
    def _http(self, method: str, url: str) -> object:
        wait = self.min_interval_s - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, method=method, headers={"User-Agent": "dota-voice-coach/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read().decode("utf-8")
        finally:
            self._last = time.time()
        return json.loads(body) if body else None

    def _url(self, path: str, params: dict | None = None) -> str:
        params = dict(params or {})
        if self.api_key:
            params["api_key"] = self.api_key
        q = ("?" + urllib.parse.urlencode(params)) if params else ""
        return f"{BASE}{path}{q}"

    def _cached(self, key: str, loader):
        if self.cache_dir is None:
            return loader()
        p = self.cache_dir / f"{key}.json"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        data = loader()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return data

    # --- методы ---
    def player(self, account_id: int) -> dict:
        return self._fetch("GET", self._url(f"/players/{account_id}"))

    def player_matches(self, account_id: int, limit: int = 50, **filters) -> list:
        """Список матчей игрока (краткий). filters: hero_id, lobby_type, date (дней) и т.п."""
        params = {"limit": limit, **filters}
        return self._fetch("GET", self._url(f"/players/{account_id}/matches", params))

    def match(self, match_id: int, use_cache: bool = True) -> dict:
        loader = lambda: self._fetch("GET", self._url(f"/matches/{match_id}"))
        if not use_cache:
            return loader()
        m = self._cached(f"match_{match_id}", loader)
        if m and not is_parsed(m) and self.cache_dir is not None:
            # неразобранный матч в кеше не держим: разбор может появиться позже
            (self.cache_dir / f"match_{match_id}.json").unlink(missing_ok=True)
        return m

    def request_parse(self, match_id: int) -> dict:
        """Попросить OpenDota скачать и разобрать реплей (пока он не удалён Valve)."""
        return self._fetch("POST", self._url(f"/request/{match_id}"))

    def pro_players(self) -> list:
        return self._cached("pro_players", lambda: self._fetch("GET", self._url("/proPlayers")))


def is_parsed(match: dict) -> bool:
    """У разобранного матча есть version и подробные поля игроков (purchase_log и т.п.)."""
    if not match or not match.get("players"):
        return False
    return match.get("version") is not None or any("purchase_log" in p for p in match["players"])


def collect_matches(api: OpenDota, account_id: int, limit: int = 50, request_missing: bool = False,
                    log=print) -> list[dict]:
    """Матчи игрока с подробностями. Неразобранные тоже берутся (герой, KDA, GPM есть и в них),
    но в них нет покупок, позиций на линии, приказов; их можно поставить на разбор."""
    out, missing = [], []
    for row in api.player_matches(account_id, limit=limit):
        mid = row.get("match_id")
        try:
            m = api.match(mid)
        except urllib.error.HTTPError as e:
            log(f"матч {mid}: HTTP {e.code}")
            continue
        if not m or not m.get("players"):
            continue
        out.append(m)
        if not is_parsed(m):
            missing.append(mid)
    log(f"матчей: {len(out)}, из них разобрано: {len(out) - len(missing)}")
    if missing and request_missing:
        for mid in missing:
            try:
                api.request_parse(mid)
            except urllib.error.HTTPError as e:
                log(f"разбор {mid}: HTTP {e.code}")
        log("запросы на разбор отправлены; повторите сбор через несколько минут "
            "(реплеи старше примерно двух недель Valve уже мог удалить — см. research/02)")
    return out
