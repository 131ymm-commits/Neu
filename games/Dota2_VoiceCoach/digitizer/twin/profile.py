"""Профиль игрока («цифровой двойник», уровень 1 — статистика) из его матчей.

Оси стиля 0..1. Где OpenDota дал процентили по герою (benchmarks.pct) — берём их:
это сравнение с популяцией на том же герое. Где нет — фиксированные шкалы SCALES.
Границы шкал — предположение Claude (не калибровано по выборке); калибровка — задача
этапа «Оцифровка» в docs/ROADMAP.md. В профиле записано, на чём построена каждая ось.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean

from .features import match_features, med

SCHEMA = "dota-twin-profile/1"

# (нижняя, верхняя) граница: значение ниже нижней → 0, выше верхней → 1. ПРЕДПОЛОЖЕНИЕ.
SCALES = {
    "ka_pm": (0.10, 0.80),          # (убийства+помощь) в минуту
    "hero_damage_pm": (100, 900),
    "early_kills": (0, 3),
    "farm_share": (0.10, 0.35),
    "last_hits_pm": (1.0, 9.0),
    "deaths_pm": (0.05, 0.30),
    "dead_share": (0.0, 0.25),
    "teamfight": (0.30, 0.80),
    "wards": (0, 20),               # обсы+сентри за игру
    "stacks": (0, 6),
    "apm": (80, 320),
    "lane_eff": (30, 90),
}


def _scale(v, key):
    if v is None:
        return None
    lo, hi = SCALES[key]
    return max(0.0, min(1.0, (v - lo) / (hi - lo)))


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return round(mean(vals), 3) if vals else None


def _mode_seq(seqs, n=6):
    """Самая частая последовательность из первых n элементов (по префиксам)."""
    seqs = [tuple(s[:n]) for s in seqs if s]
    if not seqs:
        return None
    return list(Counter(seqs).most_common(1)[0][0])


def build_profile(matches: list[dict], account_id: int, name: str | None = None,
                  aliases: list[str] | None = None) -> dict:
    feats = [f for f in (match_features(m, account_id) for m in matches) if f]
    warnings = []
    if not feats:
        return {"schema": SCHEMA, "account_id": account_id, "matches_used": 0,
                "warnings": ["игрок не найден ни в одном матче"]}
    if len(feats) < 20:
        warnings.append(f"мало матчей ({len(feats)}): оси стиля шумные, нужно хотя бы 20–50")

    feats.sort(key=lambda f: f.get("start_time") or 0)
    persona = Counter(f["personaname"] for f in feats if f.get("personaname")).most_common(1)
    pro = Counter(f["pro_name"] for f in feats if f.get("pro_name")).most_common(1)
    display = name or (pro[0][0] if pro else None) or (persona[0][0] if persona else str(account_id))

    pos_counts = Counter(f["position"] for f in feats if f.get("position"))
    n = len(feats)
    positions = {str(k): round(v / n, 3) for k, v in sorted(pos_counts.items())}
    main_pos = pos_counts.most_common(1)[0][0] if pos_counts else None

    # герои
    by_hero = defaultdict(list)
    for f in feats:
        by_hero[f["hero"]].append(f)
    pool = []
    heroes = {}
    for hero, fs in sorted(by_hero.items(), key=lambda kv: -len(kv[1])):
        wins = sum(1 for f in fs if f["win"])
        pool.append({"hero": hero, "hero_id": fs[0]["hero_id"], "games": len(fs),
                     "share": round(len(fs) / n, 3), "winrate": round(wins / len(fs), 3)})
        timings = defaultdict(list)
        for f in fs:
            for k, t in (f.get("core_timings") or {}).items():
                timings[k].append(t)
        heroes[hero] = {
            "games": len(fs),
            "core_build": _mode_seq([f.get("core_build") for f in fs]),
            "core_timings_median_s": {k: med(v) for k, v in sorted(timings.items(), key=lambda kv: med(kv[1]))},
            "start_items": _mode_seq([f.get("start_items") for f in fs], n=10),
            "skill_build": _mode_seq([f.get("skill_build") for f in fs], n=18),
            "positions": dict(Counter(f["position"] for f in fs if f.get("position"))),
        }

    def col(k):
        return [f.get(k) for f in feats]

    stats = {k: _avg(col(k)) for k in (
        "kills_pm", "deaths_pm", "assists_pm", "last_hits_pm", "hero_damage_pm", "tower_damage_pm",
        "healing_pm", "stuns_pm", "lh10", "dn10", "gold10", "xp10", "lane_efficiency_pct", "apm",
        "teamfight", "farm_share", "obs_placed", "sen_placed", "camps_stacked", "rune_pickups",
        "buybacks", "dead_share", "early_kills", "gpm", "xpm", "pings")}
    stats["winrate"] = round(sum(1 for f in feats if f["win"]) / n, 3)
    ka = [(f["kills_pm"] or 0) + (f["assists_pm"] or 0) if f.get("kills_pm") is not None else None for f in feats]

    # процентили OpenDota по герою, если есть
    pct = defaultdict(list)
    for f in feats:
        for k, v in (f.get("benchmark_pct") or {}).items():
            pct[k].append(v)
    pct_avg = {k: _avg(v) for k, v in pct.items()}

    style, basis = {}, {}

    def axis(name, bench_keys, fallback):
        vals = [pct_avg.get(k) for k in bench_keys if pct_avg.get(k) is not None]
        if vals and len(pct.get(bench_keys[0], [])) >= max(3, n // 2):
            style[name], basis[name] = round(mean(vals), 3), "opendota_benchmarks_pct"
            return
        fb = [v for v in fallback if v is not None]
        style[name] = round(mean(fb), 3) if fb else None
        basis[name] = "fixed_scales" if fb else "no_data"

    axis("aggression", ["kills_per_min", "hero_damage_per_min"],
         [_scale(_avg(ka), "ka_pm"), _scale(stats["hero_damage_pm"], "hero_damage_pm"),
          _scale(stats["early_kills"], "early_kills")])
    axis("farm_focus", ["last_hits_per_min", "gold_per_min"],
         [_scale(stats["farm_share"], "farm_share"), _scale(stats["last_hits_pm"], "last_hits_pm")])
    axis("risk", [], [_scale(stats["deaths_pm"], "deaths_pm"), _scale(stats["dead_share"], "dead_share")])
    axis("teamfight", [], [_scale(stats["teamfight"], "teamfight")])
    wards = None
    if stats["obs_placed"] is not None or stats["sen_placed"] is not None:
        wards = (stats["obs_placed"] or 0) + (stats["sen_placed"] or 0)
    axis("vision", [], [_scale(wards, "wards")])
    axis("support_play", [], [_scale(wards, "wards"), _scale(stats["camps_stacked"], "stacks")])
    axis("mechanics", [], [_scale(stats["apm"], "apm"), _scale(stats["lane_efficiency_pct"], "lane_eff")])
    roam = [f.get("is_roaming") for f in feats if f.get("is_roaming") is not None]
    style["roaming"] = round(sum(1 for r in roam if r) / len(roam), 3) if roam else None
    basis["roaming"] = "opendota_is_roaming" if roam else "no_data"

    mixes = [f["action_mix"] for f in feats if f.get("action_mix")]
    action_mix = {k: round(mean(m[k] for m in mixes), 4) for k in mixes[0]} if mixes else None

    spots = Counter()
    for f in feats:
        for x, y in f.get("ward_spots") or []:
            spots[(x, y)] += 1
    chat = []
    for f in reversed(feats):
        for line in f.get("chat") or []:
            if 2 <= len(line) <= 80 and line not in chat:
                chat.append(line)
    rank = next((f["rank_tier"] for f in reversed(feats) if f.get("rank_tier")), None)

    return {
        "schema": SCHEMA,
        "account_id": account_id,
        "name": display,
        "aliases": aliases or [],
        "matches_used": n,
        "match_ids": [f["match_id"] for f in feats],
        "first_match_time": feats[0].get("start_time"),
        "last_match_time": feats[-1].get("start_time"),
        "patches": sorted({f["patch"] for f in feats if f.get("patch") is not None}),
        "rank_tier": rank,
        "positions": positions,
        "main_position": main_pos,
        "hero_pool": pool[:15],
        "heroes": heroes,
        "stats": stats,
        "action_mix": action_mix,
        "style": style,
        "style_basis": basis,
        "ward_spots": [[x, y, c] for (x, y), c in spots.most_common(15)],
        "chat_samples": chat[:20],
        "warnings": warnings,
    }
