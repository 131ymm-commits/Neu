# PRECOND-02: производные числа итогового отчёта — для check_report_precond02.py и ledger.py audit (по образцу final_facts_precond.py).
# Арифметика над interim_an.json, журналами драйвера, событием пуша, солью, хешами регистрации и аудитом голов; плюс неокруглённое p
# первичного теста (в interim_an.json p округлено до 6 знаков и стало 0) — тем же t_cdf, что в анализе, по тем же выигрышам.
#   python3 final_facts_precond02.py  →  final_facts.json
import collections, datetime, glob, gzip, hashlib, json, math, os, statistics as st, subprocess
import analyze_precond02 as A, harness_precond02 as HP
from analyze_precond import t_cdf
ia = json.load(open('interim_an.json')); pr = ia['primary']; d = ia['describe']; pl = json.load(open('plan.json'))
# неокруглённое p и t — пересчёт выигрышей тем же кодом; совпадение со средним interim_an.json — проверка
L = A.load('A', 'evals/A.jsonl'); g = A.gains(L); n = len(g); m = st.mean(g); se = st.stdev(g) / math.sqrt(n); t = m / se
assert round(m, 3) == pr['gain']['mean'] and n == ia['n_tasks']
p_exact = 1 - t_cdf(t, n - 1)
# ожидания PREREG §5 (вероятности — §5; E3 при остановке на промежуточном — «механически», в Брайер не идёт)
E = dict(E1=dict(outcome=bool(pr['reject']), p=0.6), E2=dict(outcome=ia['decision'] == 'остановить: эффективность', p=0.3),
         E3=dict(outcome=None, p=0.75, note='механически выполнено: остановка на промежуточном (оценка ≥ 0,086); в Брайер не идёт',
                 value=pr['effect_REFUSE'], holds=pr['effect_REFUSE'] <= -0.045),
         E4=dict(outcome=d['ANCHOR']['refusal_share'] > 0.03, p=0.8, value=d['ANCHOR']['refusal_share']),
         E5=dict(outcome=d['ANCHOR']['out_per_call'] - d['NOREF']['out_per_call'] > 500, p=0.8, value=round(d['ANCHOR']['out_per_call'] - d['NOREF']['out_per_call'], 1)))
# вызовы: итоги, попытки, выход — по журналам (живые журналы совпадают со снимками run/ после последнего снимка)
calls = {}
for j in ('pilot_exec', 'pilot_eval', 'A_exec', 'B_exec', 'A_eval'):
    fin, att, na, out, models = collections.Counter(), 0, 0, 0, set()
    for p in glob.glob(f'run/{j}_journal/WH_*.jsonl'):
        for line in open(p, encoding='utf-8'):
            x = json.loads(line); att += 1; na += x['outcome'] == 'нет ответа'; out += (x.get('usage') or {}).get('out') or 0
            if x.get('final'): fin[x['final']] += 1
            models.update(x.get('model_usage_keys') or [])
    ev = [json.loads(l) for l in open(f'run/{j}_journal/run_log.jsonl', encoding='utf-8') if l.strip()]
    started = {(e['job'], e['attempt']) for e in ev if e['event'] == 'вызов'}
    rec = {(json.loads(l)['job'], json.loads(l)['attempt']) for p in glob.glob(f'run/{j}_journal/WH_*.jsonl') for l in open(p, encoding='utf-8')}
    calls[j] = dict(finals=dict(fin), attempts=att, no_answer_attempts=na, out=out, models=sorted(models), started_unrecorded=len(started - rec),
                    segments=sum(e['event'] == 'старт' for e in ev))
test_out = sum(calls[j]['out'] for j in ('A_exec', 'B_exec', 'A_eval'))
# сырые потоки (вне git): sha256 распакованного потока против журнала
streams = collections.Counter()
for j in ('A_exec', 'B_exec', 'A_eval'):
    for p in glob.glob(f'run/{j}_journal/WH_*.jsonl'):
        for line in open(p, encoding='utf-8'):
            x = json.loads(line); s_ = x.get('stream') or {}; f_ = f'../../.cache/precond02_streams/{j}/{x["task"]}/{s_.get("file")}'
            if not s_.get('file') or not os.path.exists(f_): streams['нет файла'] += 1; continue
            streams['совпал' if hashlib.sha256(gzip.open(f_).read()).hexdigest() == s_.get('sha256') else 'не совпал'] += 1
# порядок: коммит выборов → событие пуша → правда; соль A опубликована и совпала; хеши регистрации
git = lambda *a: subprocess.run(['git', *a], capture_output=True, text=True, check=True).stdout.strip()
pa = json.load(open('A_push_activity.json')); tm = min(os.path.getmtime(p) for p in glob.glob('/root/precond02_secret_A/truth/WH_*.json'))
first = lambda f: git('log', '--diff-filter=A', '--format=%h %cI', '--', f).splitlines()[-1].split()
order = dict(prereg=first('PREREG-PRECOND-02.md'), pools_B=first('pools/WH_9760.json'), jobs_A=first('run/A_eval_jobs.jsonl'), evals_A=first('evals/A.jsonl'),
             push_time=pa['event']['timestamp'], truth_first_mtime=datetime.datetime.fromtimestamp(tm, datetime.timezone.utc).isoformat()[:19],
             interim=first('interim_an.json'), salt_A=first('salts/A_salt.txt'),
             evals_sha_event=pa['evals_sha256'], evals_sha_disk=hashlib.sha256(open('evals/A.jsonl', 'rb').read()).hexdigest(),
             salt_A_sha=hashlib.sha256(open('salts/A_salt.txt', 'rb').read()).hexdigest())
assert order['prereg'][1] < order['jobs_A'][1] < order['evals_A'][1] and order['pools_B'][1] < order['truth_first_mtime']
assert order['evals_A'][1][:19] < order['push_time'][:19] < order['truth_first_mtime'] and order['evals_sha_event'] == order['evals_sha_disk']
assert order['salt_A_sha'] == 'd7885a5f4d4fb15062e763efb089b0b9a186b942ea98215ada6d68ece0939f88'
HP.verify_hashes('A')                                                         # код, план, сиды и конфигурация — как при регистрации
aud = json.load(open('audit_heads_sealed.json')); aud = aud if isinstance(aud, list) else aud.get('rows', aud)
# вес опоры (CLAUDE.md, решение автора 28.10): опыт Neu с регистрацией — log₂(мощность / ложный уровень); мощность — при половине C-041 (§8)
power_half = json.load(open('power_precond02.json'))['designs']['180/360']['by_effect']['половина C-041 (совет 39)']['power']
bits = dict(precond02=round(math.log2(power_half / 0.05), 2), power=power_half, false_level=0.05, base_hypothesis_neu=0.23, old_samples_posthoc=1.0)
bits['total'] = round(bits['base_hypothesis_neu'] + bits['precond02'] + bits['old_samples_posthoc'], 2)
totals = dict(pilot_out=calls['pilot_exec']['out'] + calls['pilot_eval']['out'], pilot_calls=calls['pilot_exec']['attempts'] + calls['pilot_eval']['attempts'],
              heads_calls=sum(h['calls'] for h in aud))                         # суммы для отчёта — здесь, чтобы аудит находил их в данных
# совет 41 (09.11.2026): порог E3 при остановке — по sd плана (PREREG §5, «оценка ≥ 0,086») и по наблюдённому sd (справка после данных);
# вес PRECOND-02 при другой мощности §8; попытки «нет ответа»; одна конфигурация запуска у всех попыток; пулы B — один коммит;
# задания исполнителя без рук; грубая мощность главного эффекта 2×2 — z-приближения совета (двусторонний α 0,05, без промежуточного анализа)
c1 = ia['bounds']['c1']; sd_plan = json.load(open('power_precond02.json'))['sd_plan']
e3_thr = dict(plan=round(c1 * sd_plan / math.sqrt(n), 3), observed=round(c1 * st.stdev(g) / math.sqrt(n), 3), sd_plan=sd_plan)
pw3 = json.load(open('power_precond02.json'))['designs']['180/360']['by_effect']
bits_alt = {k: dict(power=v['power'], bits=round(math.log2(v['power'] / 0.05), 2)) for k, v in pw3.items()}
noans, inits, att_all = collections.Counter(), set(), 0
for j in ('pilot_exec', 'pilot_eval', 'A_exec', 'B_exec', 'A_eval'):
    for p_ in glob.glob(f'run/{j}_journal/WH_*.jsonl'):
        recs = [json.loads(l) for l in open(p_, encoding='utf-8')]
        for x in recs:
            att_all += 1; inits.add(x.get('init_sha256'))
            if x['outcome'] == 'нет ответа':
                u = x.get('usage') or {}; noans['всего'] += 1; noans['usage 0'] += not (u.get('inp') or u.get('out'))
                noans['повтор годный'] += any(y['job'] == x['job'] and y.get('final') == 'годный' and y['attempt'] > x['attempt'] for y in recs)
pools_B = collections.Counter(tuple(git('log', '--format=%h', '--', f'pools/WH_{t}.json').split()) for t in range(9581, 9761))
arm_words = ('REFUSE', 'ANCHOR', 'NOREF', 'D_N', 'C_N', 'отказ')
exec_arm_hits = sum(any(w in l for w in arm_words) for st_ in ('A', 'B') for l in open(f'run/{st_}_exec_jobs.jsonl', encoding='utf-8'))
Phi = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))
next_power = dict(delta=0.045, sd=sd_plan, z=1.96, left_n180=round(Phi(0.045 * math.sqrt(180) / sd_plan - 1.96), 2),
                  engineer_n180=round(Phi(0.045 * math.sqrt(2 * 180) / sd_plan - 1.96), 2), engineer_n360=round(Phi(0.045 * math.sqrt(2 * 360) / sd_plan - 1.96), 2),
                  note='Левое: se = sd/√n; Инженер: se = sd/√(2n) (контраст по двум клеткам 2×2); грубо, считать кодом до PREREG')
council41 = dict(e3_threshold=e3_thr, bits_alt=bits_alt, no_answer=dict(noans), init_hashes=sorted(i[:8] for i in inits), attempts_all=att_all,
                 pools_B=dict(files=sum(pools_B.values()), commits={' '.join(k): v for k, v in pools_B.items()}), exec_jobs_arm_hits=exec_arm_hits, next_power=next_power)
assert noans['всего'] == noans['usage 0'] == noans['повтор годный'] == 5 and len(inits) == 1 and exec_arm_hits == 0 and list(pools_B) == [('d0ac8af',)]
facts = dict(totals=totals, n_tasks=n, t=round(t, 3), p_exact=p_exact, p_exact_sci=f'{p_exact:.1e}', se=round(se, 4), sd=round(st.stdev(g), 4),
             expectations=E, calls=calls, test_out=test_out, streams=dict(streams), order=order, heads_audit=aud, support_bits=bits,
             plan=pl, decision=ia['decision'], council41=council41)
json.dump(facts, open('final_facts.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps({k: facts[k] for k in ('n_tasks', 't', 'p_exact_sci', 'sd', 'test_out', 'streams', 'support_bits', 'decision')}, ensure_ascii=False))
for k, v in facts['calls'].items(): print(k, v)
