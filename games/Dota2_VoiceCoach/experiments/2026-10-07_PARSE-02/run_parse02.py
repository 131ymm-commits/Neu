"""PARSE-02: прогоны разборщика (заданы в PREREG-PARSE-02.md до первого прогона).

  python3 run_parse02.py new     правда A, нынешний разборщик        → result.json, result_log.txt
  python3 run_parse02.py old     правда A, разборщик до правок 75dc796 → result_prefix.json, result_prefix_log.txt
  python3 run_parse02.py newB    правда B, нынешний разборщик        → result_B.json, result_B_log.txt
  python3 run_parse02.py new --data stub_phrases.jsonl --tag pilot   (сухой прогон на заглушке)
  python3 run_parse02.py old --data ../../coach/tests/heldout_phrases.jsonl --ctx parse01 --tag pilot_parse01_original
                                 (исходный замер PARSE-01 исправленным оценщиком: должно остаться 57/80)

Оценка — функция evaluate() из coach/tests/eval_heldout.py (хеш в PREREG), без изменений. Обёртка
только ловит исключение разборщика: такая фраза получает пустой ответ (commands = [],
unknown = ['<исключение: …>']) и считается неверной; число упавших фраз пишется в json.
Первые строки лога — sha256 файлов кода, на которых шёл прогон. Тексты фраз в лог не пишутся.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                       # games/Dota2_VoiceCoach
COACH = ROOT / "coach"
REPO = ROOT.parents[1]
OLD_COMMIT = "75dc796"                       # разборщик, измеренный в PARSE-01 (до пост-хок правок)
CODE = ["voicecoach/__init__.py", "voicecoach/parser.py", "voicecoach/lexicon.py", "voicecoach/protocol.py",
        "data/heroes.json", "data/items_internal.txt"]
DATA = {"new": COACH / "tests" / "heldout_phrases_02.jsonl",
        "old": COACH / "tests" / "heldout_phrases_02.jsonl",
        "newB": HERE / "labels_B_eval.jsonl"}
OUT = {"new": "result", "old": "result_prefix", "newB": "result_B"}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def old_coach_dir() -> Path:
    """Папка coach из коммита OLD_COMMIT (git archive во временную папку)."""
    tmp = Path(tempfile.mkdtemp(prefix="parse02_old_"))
    raw = subprocess.run(["git", "-C", str(REPO), "archive", OLD_COMMIT, "games/Dota2_VoiceCoach/coach"],
                         check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(raw)) as t:
        try:
            t.extractall(tmp, filter="data")
        except TypeError:                                # Python < 3.12
            t.extractall(tmp)
    return tmp / "games" / "Dota2_VoiceCoach" / "coach"


def check_frozen() -> None:
    """Перед настоящим прогоном: код и данные совпадают с хешами из предрегистрации (frozen_sha256.txt)."""
    bad = []
    for line in (HERE / "frozen_sha256.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        h, rel = line.split(None, 1)
        if sha(ROOT / rel) != h:
            bad.append(rel)
    if bad:
        raise SystemExit(f"не совпадает с предрегистрацией: {bad}")


def safe(parse_fn, result_cls, crashed: list):
    """Исключение разборщика — исход: пустой ответ, фраза неверна, счёт в crashed."""
    def wrapped(text, ctx):
        try:
            return parse_fn(text, ctx)
        except Exception as e:                          # noqa: BLE001
            crashed.append(type(e).__name__)
            return result_cls(text=text, commands=[], unknown=[f"<исключение: {type(e).__name__}>"], confidence=0.0)
    return wrapped


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=sorted(DATA))
    ap.add_argument("--data", help="другой файл фраз (сухой прогон)")
    ap.add_argument("--tag", default="", help="приставка к именам выходных файлов")
    ap.add_argument("--ctx", default="parse02", help="состав матча (для проверки оценщика на PARSE-01 — parse01)")
    a = ap.parse_args(argv)

    coach = old_coach_dir() if a.mode == "old" else COACH
    if a.mode != "old" and not a.tag:
        check_frozen()
    sys.path.insert(0, str(coach))                       # voicecoach — из нужного состояния
    spec = importlib.util.spec_from_file_location("eval_heldout", COACH / "tests" / "eval_heldout.py")
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)                         # оценщик — всегда нынешний (хеш в PREREG)
    import voicecoach
    assert Path(voicecoach.__file__).resolve().parent == (coach / "voicecoach").resolve()

    crashed = []
    ev.parse = safe(ev.parse, voicecoach.ParseResult, crashed)
    data = Path(a.data) if a.data else DATA[a.mode]
    if not data.is_absolute() and not data.exists():
        data = HERE / data
    summary, results = ev.evaluate(data, a.ctx)
    summary["crashed_phrases"] = len(crashed)
    summary["parser_state"] = OLD_COMMIT if a.mode == "old" else "рабочая копия (хеши ниже)"
    summary["code_sha256"] = {c: sha(coach / c) for c in CODE}
    summary["eval_sha256"] = sha(COACH / "tests" / "eval_heldout.py")
    name = (a.tag + "_" if a.tag else "") + OUT[a.mode]
    (HERE / f"{name}.json").write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False,
                                                  indent=1), encoding="utf-8")
    log = [f"{v}  {k}" for k, v in summary["code_sha256"].items()]
    log.append(f"{summary['eval_sha256']}  tests/eval_heldout.py")
    log.append(f"{summary['data_sha256']}  {data.name}")
    log.append(json.dumps({k: v for k, v in summary.items() if k not in ("code_sha256",)}, ensure_ascii=False, indent=1))
    log += [f"#{r['id']} [{r['category']}] неверно" for r in results if not r["ok"]]
    (HERE / f"{name}_log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    print(f"{name}: верных {summary['phrase_ok']} из {summary['phrases']}, упало {len(crashed)}")


if __name__ == "__main__":
    main()
