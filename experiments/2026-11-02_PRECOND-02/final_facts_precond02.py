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
facts = dict(totals=totals, n_tasks=n, t=round(t, 3), p_exact=p_exact, p_exact_sci=f'{p_exact:.1e}', se=round(se, 4), sd=round(st.stdev(g), 4),
             expectations=E, calls=calls, test_out=test_out, streams=dict(streams), order=order, heads_audit=aud, support_bits=bits,
             plan=pl, decision=ia['decision'])
json.dump(facts, open('final_facts.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps({k: facts[k] for k in ('n_tasks', 't', 'p_exact_sci', 'sd', 'test_out', 'streams', 'support_bits', 'decision')}, ensure_ascii=False))
for k, v in facts['calls'].items(): print(k, v)
