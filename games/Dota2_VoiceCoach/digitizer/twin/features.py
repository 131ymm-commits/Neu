"""Признаки одного игрока в одном матче из ответа OpenDota /matches/{id}.

Поля OpenDota сверены по тестовым данным odota/core (tests/fixtures) и по
исходникам разборщика odota/parser (actions = CDOTAUserMsg_SpectatorPlayerUnitOrders,
ключ — тип приказа). Отсутствующие поля (старые или неразобранные матчи) дают None,
а не ноль: «нет данных» и «ноль» для профиля — разные вещи.
"""
from __future__ import annotations

from statistics import median

from . import data

# Расходники и мелочь: в «сборку» не входят.
CONSUMABLES = {
    "tango", "tango_single", "flask", "clarity", "ward_observer", "ward_sentry", "ward_dispenser",
    "tpscroll", "smoke_of_deceit", "dust", "enchanted_mango", "faerie_fire", "tome_of_knowledge",
    "blood_grenade", "famango", "great_famango", "greater_famango", "bottle_refill", "courier",
    "flying_courier", "cheese", "aegis", "refresher_shard", "aghanims_shard_roshan", "ultimate_scepter_roshan",
}
CORE_COST = 2000          # предмет от этой цены — «ключевой», его время покупки идёт в тайминги

# Группы типов приказов (номера — DOTA_UNIT_ORDER_*, data/order_types.json).
ORDER_GROUPS = {
    "move": {1, 2, 28, 39},
    "attack": {3, 4},
    "cast": {5, 6, 7, 8, 9, 20, 30, 40},
    "hold_stop": {10, 21},
    "items": {12, 13, 14, 16, 17, 18, 19, 25, 32, 37, 41, 42},
    "other": set(),
}


def find_player(match: dict, account_id: int) -> dict | None:
    for p in match.get("players", []):
        if p.get("account_id") == account_id:
            return p
    return None


def is_radiant(p: dict) -> bool:
    if "isRadiant" in p:
        return bool(p["isRadiant"])
    return p.get("player_slot", 0) < 128


def _total_gold(p: dict, duration_s: int) -> float:
    if p.get("total_gold") is not None:
        return float(p["total_gold"])
    if p.get("gold_t"):
        return float(p["gold_t"][-1])
    return float(p.get("gold_per_min", 0)) * duration_s / 60.0


def estimate_positions(match: dict) -> dict[int, int]:
    """Позиция 1–5 каждого игрока (ключ — player_slot).

    1) Если OpenDota уже посчитала position_est — берём её (алгоритм odota/core
       svc/util/compute.ts estimatePositions; по их проверке 98,9% совпадений на 100 про-матчах).
    2) Иначе — тот же алгоритм заново: ранг фарма по среднему gold_t и lh_t на 10–12-й минуте
       (меньше ранг — больше фарма; ранние варды склоняют к саппорту); три первых — коры
       (lane_role 1/2/3 → позиции 1/2/3, конфликты — по порядку фарма); два последних — саппорты:
       лёгкая линия (lane_role 1) → 5, мид/сложная → 4.
    3) Если ранних рядов нет (старый или неразобранный матч) — запасная эвристика по итоговому золоту.
    Ошибка 06.10.2026 (journal/ERRORS.md): сначала здесь было «OpenDota позицию не отдаёт» — неверно."""
    dur = int(match.get("duration") or 1)
    players = match.get("players", [])
    out: dict[int, int] = {}
    for radiant in (True, False):
        team = [p for p in players if is_radiant(p) == radiant]
        if team and all(p.get("position_est") in (1, 2, 3, 4, 5) for p in team):
            out.update({p["player_slot"]: p["position_est"] for p in team})
            continue
        early = len(team) == 5 and all(
            p.get("gold_t") and len(p["gold_t"]) > 12 and p.get("lh_t") and len(p["lh_t"]) > 12
            and p.get("lane_role") is not None for p in team)
        if early:
            def win(arr):
                return (arr[10] + arr[11] + arr[12]) / 3
            sc = []
            for p in team:
                wards = sum(1 for e in (p.get("purchase_log") or [])
                            if e.get("key") in ("ward_observer", "ward_sentry") and e.get("time", 1e9) <= 720)
                sc.append({"p": p, "gold": win(p["gold_t"]), "lh": win(p["lh_t"]), "wards": wards})
            for key in ("gold", "lh"):
                order = sorted(sc, key=lambda s: -s[key])
                for s in sc:
                    s["rank_" + key] = order.index(s)
            for s in sc:
                s["farm_rank"] = s["rank_gold"] + s["rank_lh"]
            sc.sort(key=lambda s: (s["farm_rank"], s["wards"]))
        else:
            sc = [{"p": p} for p in sorted(team, key=lambda p: -_total_gold(p, dur))]

        def assign(group, wanted, prefer):
            taken, rest = set(), []
            for s in group:
                w = prefer(s["p"])
                if w is not None and w in wanted and w not in taken:
                    out[s["p"]["player_slot"]] = w
                    taken.add(w)
                else:
                    rest.append(s)
            remaining = [w for w in wanted if w not in taken]
            for s, w in zip(rest, remaining):
                out[s["p"]["player_slot"]] = w

        assign(sc[:3], [1, 2, 3], lambda p: p.get("lane_role") if p.get("lane_role") in (1, 2, 3) else None)
        assign(sc[3:], [4, 5], lambda p: 4 if p.get("lane_role") in (2, 3) else (5 if p.get("lane_role") == 1 else None))
    return out


def _at_minute(series, times, minute: int):
    if not series:
        return None
    t = minute * 60
    if times and t in times:
        i = times.index(t)
        return series[i] if i < len(series) else None
    if minute < len(series):          # шаг 60 с без поля times
        return series[minute]
    return None


def _per_min(v, minutes):
    return None if v is None or minutes <= 0 else v / minutes


def match_features(match: dict, account_id: int) -> dict | None:
    p = find_player(match, account_id)
    if p is None:
        return None
    dur = int(match.get("duration") or p.get("duration") or 0)
    minutes = dur / 60.0
    radiant = is_radiant(p)
    team = [q for q in match.get("players", []) if is_radiant(q) == radiant]
    team_kills = sum(q.get("kills") or 0 for q in team)
    team_gold = sum(_total_gold(q, dur) for q in team)
    positions = estimate_positions(match)

    f: dict = {
        "match_id": match.get("match_id"),
        "start_time": match.get("start_time"),
        "patch": match.get("patch"),
        "duration_s": dur,
        "lobby_type": match.get("lobby_type"),
        "game_mode": match.get("game_mode"),
        "hero_id": p.get("hero_id"),
        "hero": data.hero_name(p.get("hero_id", 0)),
        "is_radiant": radiant,
        "win": bool(p.get("win")) if "win" in p else (match.get("radiant_win") == radiant),
        "position": positions.get(p.get("player_slot")),
        "lane_role": p.get("lane_role"),
        "is_roaming": p.get("is_roaming"),
        "rank_tier": p.get("rank_tier"),
        "personaname": p.get("personaname"),
        "pro_name": p.get("name"),
        "kills": p.get("kills"), "deaths": p.get("deaths"), "assists": p.get("assists"),
        "last_hits": p.get("last_hits"), "denies": p.get("denies"),
        "gpm": p.get("gold_per_min"), "xpm": p.get("xp_per_min"),
    }
    for k_out, k_in in (("kills_pm", "kills"), ("deaths_pm", "deaths"), ("assists_pm", "assists"),
                        ("last_hits_pm", "last_hits"), ("hero_damage_pm", "hero_damage"),
                        ("tower_damage_pm", "tower_damage"), ("healing_pm", "hero_healing"),
                        ("stuns_pm", "stuns")):
        f[k_out] = _per_min(p.get(k_in), minutes)

    times = p.get("times")
    f["lh10"] = _at_minute(p.get("lh_t"), times, 10)
    f["dn10"] = _at_minute(p.get("dn_t"), times, 10)
    f["gold10"] = _at_minute(p.get("gold_t"), times, 10)
    f["xp10"] = _at_minute(p.get("xp_t"), times, 10)
    f["lane_efficiency_pct"] = p.get("lane_efficiency_pct")

    actions = p.get("actions") or {}
    n_actions = sum(actions.values()) if actions else 0
    apm = p.get("actions_per_min")
    if not apm and n_actions and minutes > 0:
        apm = n_actions / minutes
    f["apm"] = apm or None
    if n_actions:
        mix = {g: 0 for g in ORDER_GROUPS}
        for k, v in actions.items():
            o = int(k)
            g = next((g for g, s in ORDER_GROUPS.items() if o in s), "other")
            mix[g] += v
        f["action_mix"] = {g: round(v / n_actions, 4) for g, v in mix.items()}
    else:
        f["action_mix"] = None

    tf = p.get("teamfight_participation")
    if tf is None and team_kills:
        tf = ((p.get("kills") or 0) + (p.get("assists") or 0)) / team_kills
    f["teamfight"] = tf
    f["farm_share"] = _total_gold(p, dur) / team_gold if team_gold else None

    obs = p.get("obs_placed")
    if obs is None and p.get("obs_log") is not None:
        obs = len(p["obs_log"])
    sen = p.get("sen_placed")
    if sen is None and p.get("sen_log") is not None:
        sen = len(p["sen_log"])
    f["obs_placed"], f["sen_placed"] = obs, sen
    f["ward_spots"] = [(w.get("x"), w.get("y")) for w in (p.get("obs_log") or []) if "x" in w]
    f["camps_stacked"] = p.get("camps_stacked")
    f["rune_pickups"] = p.get("rune_pickups")
    f["buybacks"] = p.get("buyback_count")
    f["roshan_kills"] = p.get("roshan_kills")
    f["tower_kills"] = p.get("tower_kills")
    pings = p.get("pings")
    f["pings"] = sum(pings.values()) if isinstance(pings, dict) else pings
    f["dead_share"] = (p["life_state_dead"] / dur) if p.get("life_state_dead") is not None and dur else None
    kl = p.get("kills_log")
    f["early_kills"] = sum(1 for k in kl if k.get("time", 1e9) < 600) if kl is not None else None

    # сборка
    plog = p.get("purchase_log")
    if plog is not None:
        seen, build, start = set(), [], []
        for e in plog:
            key, t = e.get("key"), e.get("time", 0)
            if not key or key in CONSUMABLES:
                continue
            if t <= 0:
                start.append(key)
            if key in seen:
                continue
            seen.add(key)
            if data.item_cost(key) >= CORE_COST:
                build.append((t, key))
        # дорогой компонент, собранный в предмет позже или в ту же секунду, в сборку не идёт
        # (рецепты — текущего патча; у старых матчей могут не совпасть)
        first = {k: t for t, k in build}
        all_first = {}
        for e in plog:
            if e.get("key") and e["key"] not in all_first:
                all_first[e["key"]] = e.get("time", 0)
        absorbed = set()
        for k, t in all_first.items():
            for c in data.item_components(k):
                if c in first and first[c] <= t:
                    absorbed.add(c)
        build = [(t, k) for t, k in build if k not in absorbed]
        f["start_items"] = sorted(start)
        f["core_build"] = [k for _, k in sorted(build)]
        f["core_timings"] = {k: t for t, k in build}
    else:
        f["start_items"] = f["core_build"] = f["core_timings"] = None

    ups = p.get("ability_upgrades_arr")
    f["skill_build"] = [data.ability_name(a) for a in ups] if ups else None

    lp = p.get("lane_pos")
    if lp:
        cells = [((int(x), int(y)), n) for x, row in lp.items() for y, n in row.items()]
        cells.sort(key=lambda c: -c[1])
        f["lane_cells"] = [[x, y, n] for (x, y), n in cells[:12]]
    else:
        f["lane_cells"] = None

    bm = p.get("benchmarks") or {}
    f["benchmark_pct"] = {k: v.get("pct") for k, v in bm.items() if isinstance(v, dict) and v.get("pct") is not None} or None

    slot = p.get("player_slot")
    f["chat"] = [c.get("key") for c in (match.get("chat") or [])
                 if c.get("type") == "chat" and c.get("player_slot") == slot and c.get("key")]
    return f


def med(values):
    vals = [v for v in values if v is not None]
    return median(vals) if vals else None
