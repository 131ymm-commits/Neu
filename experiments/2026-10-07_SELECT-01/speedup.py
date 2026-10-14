# SELECT-01: цена ускорения повтора (просьба автора 14.10: «Ускорьтесь, оптимизируйтесь. Посчитайте ошибку ускорения»).
#   python3 speedup.py > speedup.json        (из каталога опыта; данные повтора — только журнал вызовов, правды повтора нет)
# 1) Мощность повтора при досрочной остановке на n полных задачах (PREREG §6: окончательная остановка — решение автора,
#    анализ по полным задачам). Бутстреп n задач из per_task ОСНОВНОЙ выборки; правило зачёта как в analyze.py:
#    Холм по {C_N, D_N} против B_blind, p против A0 ≤ 0,05 (budget.equal принят истинным, как в основной).
#    p — знаковые перестановки, общий набор знаков на все тесты (в analyze.py у perm_p одно зерно 0), M перестановок.
#    Эффект ×1 — как в основной (вероятно, завышен отбором по значимости), ×0,5 — вдвое меньше, ×0 — ложный зачёт.
#    Меньший эффект — сдвиг: D_N + (1 − k)·Δ, Δ = среднее (B_blind − D_N) основной = 0,185; шум разностей тот же.
#    (Не сжатие D_N − B_blind: перестановочный тест к масштабу нечувствителен — ошибка первой версии скрипта, ERRORS № 84.)
# 2) Сколько вызовов оценщиков осталось до n задач (живой журнал, порядок задач — по сидам, PREREG §7).
# 3) Пропускная способность: вызовов на пятичасовое окно (по utilization из rate_limit_event потоков) и в час.
# 4) Когда будет готово (UTC): остаток текущего окна, затем окна по 5 ч подряд — драйвер ждёт сброса внутри запуска
#    и продолжает сразу (если запуск не прерван); вызовов на окно — min / медиана / max по прошлым окнам.
import glob, gzip, json, os, statistics as st
import numpy as np
pt = json.load(open('main_an_wh.json'))['per_task']; T = sorted(pt)
X = {a: np.array([pt[t][a] for t in T]) for a in ('A0', 'B_blind', 'C_N', 'D_N')}
rng = np.random.default_rng(14102026); S, M = 2000, 4000
DELTA = float(np.mean(X['B_blind'] - X['D_N']))

def p_le(d, signs):           # как perm_p: доля перестановок со средним ≤ наблюдаемого, (le + 1) / (M + 1)
    return ((signs @ d / len(d) <= d.mean() + 1e-12).sum() + 1) / (M + 1)

def power(n, k):
    ok = 0
    for _ in range(S):
        i = rng.integers(0, len(T), n); b, a0, c = X['B_blind'][i], X['A0'][i], X['C_N'][i]
        d = X['D_N'][i] + (1 - k) * DELTA
        sg = rng.choice((-1.0, 1.0), size=(M, n))
        pD, pC, p0 = p_le(d - b, sg), p_le(c - b, sg), p_le(d - a0, sg)
        holm = pD <= .025 or (pC <= .025 and pD <= .05)
        ok += holm and p0 <= .05
    return round(ok / S, 3)

L = '../../.cache/select01_live/rep_eval_journal'
fin = {}
for p in glob.glob(f'{L}/WH_*.jsonl'):
    fin[os.path.basename(p)[:-6]] = sum(1 for l in open(p, encoding='utf-8') if json.loads(l).get('final'))
pools = [json.loads(l)['id'].split('|')[0] for l in open('run/rep_eval_jobs.jsonl')]
tasks = sorted(set(pools)); left = lambda n: sum(27 - fin.get(t, 0) for t in tasks[:n])
sd = float(np.std(X['D_N'] - X['B_blind'], ddof=1))

win = {}                       # окно (resetsAt) → [utilization по порядку вызовов]
for f in sorted(glob.glob('../../.cache/select01_streams/*_e*/*/*.gz'), key=os.path.getmtime):
    try:
        for line in gzip.open(f, 'rt'):
            if '"rate_limit_event"' in line:
                w = json.loads(line)['rate_limit_info']['unifiedWindows']['five_hour']; win.setdefault(w['resetsAt'], []).append(w['utilization']); break
    except (EOFError, KeyError):
        pass                   # поток ещё пишется / событие без окна
per_win = {str(r): round(len(u) / (max(u) - min(u))) for r, u in win.items() if len(u) > 100 and max(u) - min(u) > .3}
recs = [json.loads(l) for p in glob.glob(f'{L}/WH_*.jsonl') for l in open(p, encoding='utf-8')]
dur = [r for r in recs if r.get('final')]
from datetime import datetime as D
sec = st.mean((D.fromisoformat(r['finished']) - D.fromisoformat(r['started'])).total_seconds() for r in dur)
from datetime import timezone
def eta(R, Q, rate):
    r_last = max(win); t = D.now(timezone.utc).timestamp(); reset = r_last; q = max(0.0, 1 - win[r_last][-1]) * Q
    while R > 0:
        k = min(R, q, rate * max(0.0, reset - t) / 3600); R -= k; t += k / rate * 3600
        if R > 0:
            t = max(t, reset); reset = t + 5 * 3600; q = Q
    return D.fromtimestamp(t, timezone.utc).strftime('%d.%m %H:%M')
Qs = sorted(per_win.values()); Qs = dict(min=Qs[0], median=st.median(Qs), max=Qs[-1]); rate = 3 * 3600 / sec
out = dict(computed_at=D.now(timezone.utc).strftime('%d.%m %H:%M UTC'), note='до правды повтора; данные повтора — только счёт вызовов', S=S, M=M, sd_DN_minus_Bblind_main=round(sd, 3),
           eval_finals_done=sum(fin.values()), tasks_with_pool=len(tasks),
           rows=[dict(n=n, calls_left=left(n), ci95_halfwidth=round(1.96 * sd / n ** .5, 3),
                      power_x1=power(n, 1.0), power_x05=power(n, 0.5), false_pass_x0=power(n, 0.0),
                      eta_utc={k: eta(left(n), q, rate) for k, q in Qs.items()})
                 for n in (len(tasks), 90, 80, 70, 60, 50, 40)],
           calls_per_window_by_reset=per_win, calls_per_window=Qs, call_seconds_mean=round(sec, 1), calls_per_hour_parallel3=round(3 * 3600 / sec))
print(json.dumps(out, ensure_ascii=False, indent=1))
