# Сборка набора «ответ головы ИИ + правда от кода» из всех прогонов Neu — актив для линии «ИИ оценивает ИИ» (EVAL-01).
# Публичная часть (без правды): experiments/2026-09-27_EVAL-01/data/items_public.jsonl — id, источник, семейство, текст задачи, ответ головы как он был дан.
# Правда и метки: /root/eval_secret/truth.json — вне репозитория, чтобы головы-судьи не могли её прочитать.
#   python3 tools/eval_dataset.py            → собрать и напечатать сводку по источникам
import json, math, os, glob, re, sys
NEU = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); EX = os.path.join(NEU, 'experiments')
OUT_DIR = os.path.join(EX, '2026-09-27_EVAL-01', 'data'); SECRET = '/root/eval_secret'
os.makedirs(OUT_DIR, exist_ok=True); os.makedirs(SECRET, exist_ok=True)
items, truth, log = [], {}, []


def J(p): return json.load(open(p))


def num(x):
    try: v = float(x); return v if math.isfinite(v) else None
    except Exception: return None


def add(iid, source, fam, text, answer, t, head='', kind='estimate', extra=None):
    """answer: dict как дала голова; t: правда (число или строка). Метки считаются здесь."""
    if iid in truth: iid = iid + '#' + str(sum(k.startswith(iid) for k in truth))
    items.append(dict(id=iid, source=source, family=fam, kind=kind, head=head, task=text, answer=answer, **(extra or {})))
    lab = dict(truth=t)
    if kind in ('estimate', 'exact'):
        e = num(answer.get('estimate', answer.get('answer'))); tv = num(t)
        if e is not None and tv is not None:
            lab['exact'] = e == tv; lab['log_err'] = abs(math.log(max(e, 1e-9) / max(tv, 1e-9))) if e > 0 and tv > 0 else None
            lab['within_1pct'] = lab['log_err'] is not None and lab['log_err'] <= math.log(1.01); lab['within_10pct'] = lab['log_err'] is not None and lab['log_err'] <= math.log(1.10)
            lo, hi = num(answer.get('lo')), num(answer.get('hi'))
            if lo is not None and hi is not None: lab['covered'] = lo <= tv <= hi; lab['width_log'] = math.log(max(hi, 1e-9) / max(lo, 1e-9)) if lo > 0 else None
        else: lab['exact'] = False; lab['log_err'] = None
    elif kind == 'existence': lab['exact'] = bool(t)
    elif kind == 'trajectory': lab['exact'] = bool(t.get('exact')) if isinstance(t, dict) else bool(t)
    truth[iid] = lab


# ---------- HIVE-01: 5 поколений × 10 вопросов × 4 улья × 3 головы + итоговая проверка 24 вопроса × 6 рук ----------
def hive01():
    d = os.path.join(EX, '2026-09-26_HIVE-01', 'run'); full = J('/root/hive_secret/questions_full.json'); pub = J(os.path.join(d, 'questions_public.json'))
    tmap = {q['id']: q['truth'] for g in full['gens'] for q in g}; tmap.update({q['id']: q['truth'] for q in full['test_conf'] + full['test_ctrl']})
    text = {q['id']: q['text'] for g in pub['gens'] for q in g}; text.update({q['id']: q['text'] for q in pub.get('test', [])})
    n = 0
    for g in range(5):
        p = os.path.join(d, f'raw_ans{g}.json')
        if not os.path.exists(p): continue
        for hive, o in J(p)['out'].items():
            for stage in ('first', 'second'):
                for k, b in enumerate(o.get(stage) or []):
                    for x in (b or {}).get('items', []):
                        if x['id'] in tmap and x['id'] in text:
                            add(f"HIVE01-g{g}-{hive}-h{k + 1}{'r' if stage == 'second' else ''}-{x['id']}", 'HIVE-01', x['id'].split('-')[0], text[x['id']],
                                dict(estimate=x.get('estimate'), lo=x.get('lo'), hi=x.get('hi'), note=x.get('note', '')), tmap[x['id']], head=f'{hive}:h{k + 1}', extra=dict(stage=stage, gen=g)); n += 1
    p = os.path.join(d, 'out_test.json')
    if os.path.exists(p):
        for arm, o in J(p)['out'].items():
            for stage in ('first', 'second'):
                for k, b in enumerate(o.get(stage) or []):
                    for x in (b or {}).get('items', []):
                        if x['id'] in tmap and x['id'] in text:
                            add(f"HIVE01-test-{arm}-h{k + 1}{'r' if stage == 'second' else ''}-{x['id']}", 'HIVE-01', x['id'].split('-')[0], text[x['id']],
                                dict(estimate=x.get('estimate'), lo=x.get('lo'), hi=x.get('hi'), note=x.get('note', '')), tmap[x['id']], head=f'{arm}:h{k + 1}', extra=dict(stage=stage, gen='test')); n += 1
    log.append(('HIVE-01', n))


# ---------- DIV-01 пилот: 5 голов (3 копии, Sonnet, Haiku) × 12 вопросов ----------
def div01():
    d = os.path.join(EX, '2026-09-26_DIV-01', 'pilot'); qs = {q['id']: q for q in J('/root/div_secret/pilot.json')}; o = J(os.path.join(d, 'out.json'))['out']; n = 0
    for head, r in o.items():
        for x in r['items']:
            q = qs[x['id']]; add(f"DIV01-{head}-{x['id']}", 'DIV-01', x['id'].split('-')[0], q['text'], dict(estimate=x['estimate'], lo=x['lo'], hi=x['hi'], note=x.get('note', '')), q['truth'], head=head); n += 1
    log.append(('DIV-01', n))


# ---------- DUEL-01 пилот: 8 задач COL3, по 3 решателя + составитель ----------
def duel():
    p = os.path.join(EX, '2026-09-26_DUEL-01', 'pilot', 'tasks0.json'); n = 0
    for t in J(p):
        if not t.get('params'): continue
        add(f"DUEL-{t['id']}-setter{t['setter']}", 'DUEL-01', 'COL3', t['text'], dict(t['setter_answer'], note=t.get('why', '')), t['truth'], head=t['setter'], extra=dict(role='составитель')); n += 1
        for s, x in (t.get('solvers') or {}).items():
            add(f"DUEL-{t['id']}-{s}", 'DUEL-01', 'COL3', t['text'], dict(x['answer']), t['truth'], head=s, extra=dict(role='решатель')); n += 1
    log.append(('DUEL-01', n))


# ---------- PRED-01 пилот ----------
def pred():
    d = os.path.join(EX, '2026-09-26_PRED-01', 'pilot'); qs = {q['id']: q for q in J(os.path.join(d, 'questions.json'))}; n = 0
    for r in J(os.path.join(d, 'answers.json'))['records']:
        resp = r.get('response') or r.get('result') or {}
        qid = r['label'].split(':', 1)[1] if ':' in r['label'] else None
        if qid in qs and isinstance(resp, dict) and 'estimate' in resp:
            add(f"PRED01-{r['label'].replace(':', '-')}", 'PRED-01', qs[qid]['fam'], qs[qid]['text'], dict(estimate=resp.get('estimate'), lo=resp.get('lo'), hi=resp.get('hi'), note=resp.get('reasoning', '')), qs[qid]['truth'], head=r['label'].split(':')[0]); n += 1
    log.append(('PRED-01', n))


# ---------- CALIB-01 пилоты: точный ответ + уверенность ----------
def calib():
    n = 0
    for sub in ('pilot', 'pilot2'):
        d = os.path.join(EX, '2026-09-26_CALIB-01', sub)
        tp, rp = os.path.join(d, 'tasks.json'), os.path.join(d, 'results_raw.json')
        if not (os.path.exists(tp) and os.path.exists(rp)): continue
        ts = {t['id']: t for t in J(tp)}
        for r in J(rp)['records']:
            resp = r.get('response') or r.get('result') or {}; tid = r['label'].split(':', 1)[1] if ':' in r['label'] else None
            if tid in ts and isinstance(resp, dict) and 'answer' in resp:
                add(f"CALIB01-{sub}-{r['label'].replace(':', '-')}", 'CALIB-01', 'DIGITDP', ts[tid]['text'], dict(answer=resp.get('answer'), confidence=resp.get('confidence'), note=resp.get('reasoning', '')), ts[tid]['answer'], kind='exact', head=r['label'].split(':')[0]); n += 1
    log.append(('CALIB-01', n))


# ---------- PEER-01 пилоты: решение задачи «есть/нет решения», правильность проверена кодом ----------
def peer():
    n = 0
    for sub in ('pilot', 'pilot2'):
        p = os.path.join(EX, '2026-09-26_PEER-01', sub, 'answers.json')
        if not os.path.exists(p): continue
        for a in J(p):
            if 'correct' not in a: continue
            add(f"PEER01-{sub}-{a['task']}", 'PEER-01', a.get('fam', ''), a.get('text', a['task']), dict(status=a.get('status'), solution=a.get('solution'), note=a.get('argument', ''), confidence=a.get('confidence')), bool(a['correct']), kind='existence', head='solver'); n += 1
    log.append(('PEER-01', n))


# ---------- DIV-02 пилоты и LEVEL-04: длинные точные цепочки; правда считается кодом здесь ----------
def collatz_traj(n):
    t = []
    while n != 1: n = n // 2 if n % 2 == 0 else 3 * n + 1; t.append(n)
    return t


def div02():
    d = os.path.join(EX, '2026-09-26_DIV-01', 'pilot'); n = 0
    qs = J('/root/div_secret/div02_pilot.json'); o = J(os.path.join(d, 'div02_out.json'))
    for q, s in zip(qs, o['solo']):
        add(f"DIV02p-solo-{q['id']}", 'DIV-02', 'COLLATZ-steps', f"Сколько шагов нужно числу {q['n']}, чтобы впервые дойти до 1 (n/2 для чётного, 3n+1 для нечётного)?", dict(estimate=s.get('steps'), lo=s.get('lo'), hi=s.get('hi'), note=s.get('note', ''), done=s.get('done')), q['truth'], head='solo'); n += 1
    qs2 = J('/root/div_secret/div02b_pilot.json'); o2 = J(os.path.join(d, 'div02b_out.json'))
    for q in qs2:
        T = [str(x) for x in collatz_traj(q['n'])]; L = len(T); r = o2[q['id']]
        for arm in ('SOLO_LONG', 'SEG1'):
            v = ((r.get(arm) or {}).get('values')) or []; steps = v.index('1') + 1 if '1' in v else None
            add(f"DIV02b-{arm}-{q['id']}", 'DIV-02', 'COLLATZ-traj', f"Пройди путь числа {q['n']} до 1 (n/2 для чётного, 3n+1 для нечётного) и выпиши все значения.", dict(steps=steps, n_values=len(v), last=v[-1] if v else None, note=(r.get(arm) or {}).get('note', '')), dict(L=L, exact=(v[:L] == T and steps == L)), kind='trajectory', head=arm); n += 1
        for k, x in enumerate(r.get('SC') or []):
            v = (x or {}).get('values') or []; steps = v.index('1') + 1 if '1' in v else None
            add(f"DIV02b-SC{k + 1}-{q['id']}", 'DIV-02', 'COLLATZ-traj', f"Пройди путь числа {q['n']} до 1 и выпиши все значения.", dict(steps=steps, n_values=len(v), last=v[-1] if v else None, note=(x or {}).get('note', '')), dict(L=L, exact=(v[:L] == T and steps == L)), kind='trajectory', head=f'SC{k + 1}'); n += 1
    log.append(('DIV-02', n))


def level04():
    d = os.path.join(EX, '2026-09-26_LEVEL-04'); P = 1000000007; n = 0
    cal = J(os.path.join(d, 'pilot', 'cal_out.json')); tr = {i['id']: i for i in J('/root/level_secret/l4_cal.json')}
    for qid, heads in cal.items():
        T = [str(x) for x in tr[qid]['truth']]
        for k, h in enumerate(heads):
            v = [str(x) for x in ((h or {}).get('values') or [])]
            add(f"L04cal-{qid}-h{k + 1}", 'LEVEL-04', 'MODSQ-traj', f"Итерация x → (x² + {tr[qid]['c']}) mod {P}, x₀ = {tr[qid]['x']}; выпиши 30 значений.", dict(n_values=len(v), last=v[-1] if v else None, note=(h or {}).get('note', '')), dict(L=30, exact=(v[:30] == T[:30] and len(v) >= 30)), kind='trajectory', head=f'h{k + 1}'); n += 1
    for tag, outp, secp in (('ph1', 'pilot/phase1_out.json', '/root/level_secret/l4_phase1.json'), ('ph2', 'phase2_out_partial.json', '/root/level_secret/l4_phase2.json')):
        o = J(os.path.join(d, outp)); ch = {c['id']: c for c in J(secp)}
        for rec in o['records']:
            if rec.get('n') is None or not rec.get('values'): continue  # упавшие или пустые звенья
            jid = rec['tag'].rsplit(':', 1)[0]; cid = jid.split(':')[1]; c = ch[cid]
            v = [str(x).strip() for x in rec['values']]; x = int(rec['from']); T = []
            for _ in range(rec['m']): x = (x * x + c['c']) % P; T.append(str(x))
            add(f"L04{tag}-{rec['tag'].replace(':', '-')}", 'LEVEL-04', 'MODSQ-link', f"Итерация x → (x² + {c['c']}) mod {P}, начни с {rec['from']}, сделай ровно {rec['m']} шагов и выпиши значения.", dict(n_values=len(v), last=v[-1], note=rec.get('check') or ''), dict(L=rec['m'], exact=(v[:rec['m']] == T and len(v) >= rec['m'])), kind='trajectory', head=jid); n += 1
    log.append(('LEVEL-04', n))


for f in (hive01, div01, duel, pred, calib, peer, div02, level04):
    try: f()
    except Exception as e: log.append((f.__name__, f'ОШИБКА {type(e).__name__}: {e}'))
# Утечка между элементами: заметка головы может цитировать правду ДРУГОГО вопроса (сводки HIVE показывали правду прошлых поколений).
# Флаг leak_note=True, если в заметке встречается число, равное правде другого элемента набора (целые из ≥ 4 цифр).
tv = {}
for iid, lab in truth.items():
    t = lab.get('truth'); t = t.get('L') if isinstance(t, dict) else t
    if isinstance(t, (int, float)) and not isinstance(t, bool) and float(t).is_integer() and abs(t) >= 1000: tv.setdefault(str(int(t)), set()).add(iid)
for it in items:
    note = str((it.get('answer') or {}).get('note', '')); own = truth[it['id']].get('truth'); own = own.get('L') if isinstance(own, dict) else own
    hits = {n for n in re.findall(r'\d{4,}', note) if n in tv and str(own) != n and not (isinstance(own, (int, float)) and str(int(own)) == n)}
    it['leak_note'] = bool(hits)
with open(os.path.join(OUT_DIR, 'items_public.jsonl'), 'w') as fh:
    for it in items: fh.write(json.dumps(it, ensure_ascii=False) + '\n')
json.dump(truth, open(os.path.join(SECRET, 'truth.json'), 'w'), ensure_ascii=False)
summary = {}
for it in items:
    lab = truth[it['id']]; s = summary.setdefault(it['source'], dict(n=0, exact=0, kinds=set(), fams=set()))
    s['n'] += 1; s['exact'] += int(bool(lab.get('exact'))); s['kinds'].add(it['kind']); s['fams'].add(it['family']); s['leak_note'] = s.get('leak_note', 0) + int(it.get('leak_note', False))
for k, s in summary.items(): s['kinds'] = sorted(s['kinds']); s['fams'] = sorted(s['fams']); s['exact_rate'] = round(s['exact'] / s['n'], 3)
json.dump(dict(sources=summary, total=len(items), log=log), open(os.path.join(OUT_DIR, 'summary.json'), 'w'), ensure_ascii=False, indent=1)
print('всего ответов:', len(items)); [print(f'{k:10s} n={s["n"]:5d} точных {s["exact_rate"]:.2f} виды {s["kinds"]} семейства {s["fams"]}') for k, s in summary.items()]; print('лог:', log)
