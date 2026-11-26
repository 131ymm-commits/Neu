#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCSHIFT-01: извлечение на Kaggle (видеокарты T4 × 2, интернет) — ответы голов и logp ответа на свежих диапазонах.
Счёт на задаче — код OCCOR-01 / OCMIX-01 / OCREP-01 без изменений (подсказка из 4 примеров, жадный ответ до 6 новых токенов,
ведущее целое, logp — сумма по токенам ответа; fp16; пакеты по 32, у 6.9b — по 8). Новое — только порядок работы:
  • несколько сред в одном прогоне: диапазон a ∈ [X00, X99], X = 4…8, b ∈ [10, 99]; ID — сумма < (X+1)00, OOD — сумма ≥ (X+1)00;
    у каждого диапазона две подсказки теста (p = 0, 1) и одна подсказка пилота (p = 9), задачи сред не пересекаются;
  • две видеокарты: два процесса (fork до первого обращения к CUDA), у каждого своя карта и свой кэш весов;
  • блок сверки: первые 96 задач пилота OCREP-01 с его подсказкой — ответы и logp должны совпасть с закоммиченным выводом.
Один файл для пилота (MODE = 'pilot') и теста (MODE = 'test'); разбиение задано зёрнами до данных и от моделей не зависит.
Зёрна: подсказка — 7 600 000 + 1000·X + p; разбиение диапазона — 7 610 000 + X. Правда — по коду (ответ == a + b).
Вывод — /kaggle/working/answers.json (сжатые столбцы по голове и среде). Без скрытых состояний, без личных данных."""
import gc
import json
import multiprocessing as mp
import os
import re
import shutil
import subprocess
import sys
import time

MODE = 'test'                        # 'pilot' или 'test' — меняется только эта строка
os.environ.setdefault('PYTORCH_NVML_BASED_CUDA_CHECK', '1')     # проверка «есть ли CUDA» без cuInit: иначе fork небезопасен
T0 = time.time()
OUT = '/kaggle/working' if os.path.isdir('/kaggle/working') else os.path.abspath(f'{MODE}_out')
os.makedirs(OUT, exist_ok=True)


def log(*a):
    print(f'[{time.time() - T0:7.1f} с]', *a, flush=True)


IMPORT_ONLY = os.environ.get('OCSHIFT_IMPORT_ONLY') == '1'     # для тестов разбиения: без torch и без запуска
import numpy as np  # noqa: E402

if not IMPORT_ONLY:
    try:
        import torch
        import transformers
    except Exception:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'torch', 'transformers', 'accelerate'], check=True)
        import torch
        import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer

# Девять голов — как в OCCOR-01, OCMIX-01, OCREP-01 (порядок — канонический для вывода).
HEADS = [('EleutherAI/pythia-1.4b', 'main'), ('EleutherAI/pythia-1.4b-deduped', 'main'),
         ('EleutherAI/pythia-2.8b', 'main'), ('EleutherAI/pythia-2.8b', 'step133000'),
         ('EleutherAI/pythia-2.8b', 'step123000'), ('EleutherAI/pythia-2.8b', 'step113000'),
         ('EleutherAI/pythia-2.8b-deduped', 'main'), ('EleutherAI/pythia-6.9b', 'main'),
         ('EleutherAI/pythia-6.9b-deduped', 'main')]
# Две карты: нагрузка поровну (≈ 0,12 с на задачу у каждой); две большие модели грузятся не одновременно (память).
WORKERS = [[7, 2, 3, 4], [0, 1, 5, 6, 8]]
RANGES = (4, 5, 6, 7, 8)
B_RANGE = (10, 99)
SHOTS_BASE, SPLIT_BASE = 7_600_000, 7_610_000
N_ENV, N_PILOT = 2200, 300
P_TEST, P_PILOT = (0, 1), 9
CHECK_N = 96


def shots(a_range, bound, seed):
    """Подсказка — как prompt_head в ocrep_extract.py: два примера с суммой < bound, два — с суммой ≥ bound, порядок перемешан."""
    g = np.random.default_rng(seed)
    ex = []
    while len(ex) < 4:
        a, b = int(g.integers(a_range[0], a_range[1] + 1)), int(g.integers(B_RANGE[0], B_RANGE[1] + 1))
        need_id = len(ex) < 2
        if (a + b < bound) == need_id and (a, b) not in ex:
            ex.append((a, b))
    order = g.permutation(4)
    return ''.join(f'{ex[i][0]}+{ex[i][1]}={ex[i][0] + ex[i][1]}\n' for i in order), ex


def problems(pairs, idx, bound):
    out = [dict(id=int(i), a=pairs[i][0], b=pairs[i][1], sum=pairs[i][0] + pairs[i][1]) for i in idx]
    for p in out:
        p['range'] = 'ID' if p['sum'] < bound else 'OOD'
    return out


def check_block():
    """Первые CHECK_N задач пилота OCREP-01 — тем же кодом, что ocrep_extract.py (SPLIT = 'pilot')."""
    a_range, bound = (300, 399), 400
    head, ex = shots(a_range, bound, 7_500_000)
    pairs = [(a, b) for a in range(a_range[0], a_range[1] + 1) for b in range(B_RANGE[0], B_RANGE[1] + 1) if (a, b) not in set(ex)]
    perm = np.random.default_rng(7_510_000).permutation(len(pairs))
    part = sorted(perm[:int(round(0.3 * len(pairs)))])[:CHECK_N]
    return dict(name='check_ocrep_pilot', kind='check', a=list(a_range), bound=bound, shots_seed=7_500_000, prompt_head=head,
                problems=problems(pairs, part, bound))


def environments(mode):
    envs = [check_block()]
    for X in RANGES:
        a_range, bound = (100 * X, 100 * X + 99), 100 * (X + 1)
        hd = {p: shots(a_range, bound, SHOTS_BASE + 1000 * X + p) for p in P_TEST + (P_PILOT,)}
        used = set(e for p in hd for e in hd[p][1])                     # примеры всех трёх подсказок в задачи не идут
        pairs = [(a, b) for a in range(a_range[0], a_range[1] + 1) for b in range(B_RANGE[0], B_RANGE[1] + 1) if (a, b) not in used]
        perm = np.random.default_rng(SPLIT_BASE + X).permutation(len(pairs))
        cut = {P_TEST[0]: perm[:N_ENV], P_TEST[1]: perm[N_ENV:2 * N_ENV], P_PILOT: perm[2 * N_ENV:2 * N_ENV + N_PILOT]}
        for p in ((P_PILOT,) if mode == 'pilot' else P_TEST):
            envs.append(dict(name=f'X{X}_p{p}', kind=mode, X=X, p=p, a=list(a_range), bound=bound, shots_seed=SHOTS_BASE + 1000 * X + p,
                             split_seed=SPLIT_BASE + X, prompt_head=hd[p][0], problems=problems(pairs, sorted(cut[p]), bound)))
    return envs


ENVS = environments(MODE)


def answer_logp(tok, ids, lp_rows):
    """Ответ — ведущее целое; logp — сумма по токенам, пока префикс остаётся числом (как в OCGEO-01)."""
    text = tok.decode(ids, skip_special_tokens=True)
    m = re.match(r'\s*(\d+)', text)
    ans = int(m.group(1)) if m else None
    lps, acc = [], ''
    for k, tid in enumerate(ids):
        piece = tok.decode([tid], skip_special_tokens=True)
        if not re.fullmatch(r'\s*\d*', acc + piece) or (k > 0 and not re.fullmatch(r'\s*\d+', acc + piece)):
            break
        acc += piece
        lps.append(float(lp_rows[k][tid]))
    return ans, text[:16], (float(np.sum(lps)) if lps else None), len(lps)


def load(repo, rev, cache, solo):
    kw = dict(revision=rev, torch_dtype=torch.float16, cache_dir=cache)
    if not torch.cuda.is_available():
        return AutoModelForCausalLM.from_pretrained(repo, **kw).eval(), 'cpu'
    try:
        return AutoModelForCausalLM.from_pretrained(repo, device_map={'': 0}, **kw).eval(), 'gpu'
    except torch.cuda.OutOfMemoryError:
        if not solo:
            raise
        gc.collect(); torch.cuda.empty_cache()
        return AutoModelForCausalLM.from_pretrained(repo, device_map='auto', **kw).eval(), 'auto'


def run(repo, rev, w, solo):
    t = time.time()
    cache = os.path.expanduser(f'~/.cache/hf_w{w}')
    tok = AutoTokenizer.from_pretrained(repo, revision=rev, cache_dir=cache)
    tok.padding_side = 'left'
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model, where = load(repo, rev, cache, solo)
    bs = 8 if '6.9b' in repo else 32
    log(f'W{w}', repo, rev, 'загружена', where, round(time.time() - t, 1), 'с')
    dev0 = next(model.parameters()).device
    cols, secs = {}, {}
    for env in ENVS:
        te = time.time()
        probs = env['problems']
        prompts = [env['prompt_head'] + f"{p['a']}+{p['b']}=" for p in probs]
        c = dict(answer=[], correct=[], logp=[], n_tok=[], text_none={})
        for i in range(0, len(prompts), bs):
            enc = tok(prompts[i:i + bs], return_tensors='pt', padding=True).to(dev0)
            with torch.no_grad():
                gen = model.generate(**enc, max_new_tokens=6, do_sample=False, output_scores=True,
                                     return_dict_in_generate=True, pad_token_id=tok.pad_token_id)
            seqs = gen.sequences[:, enc['input_ids'].shape[1]:].tolist()
            lp = torch.stack([torch.log_softmax(s.float(), -1) for s in gen.scores], 1).cpu().numpy()
            for j, ids in enumerate(seqs):
                ans, text, lsum, ntok = answer_logp(tok, ids, lp[j])
                c['answer'].append(ans)
                c['correct'].append(int(ans == probs[i + j]['sum']))
                c['logp'].append(lsum)
                c['n_tok'].append(ntok)
                if ans is None:
                    c['text_none'][str(i + j)] = text
            del gen
        cols[env['name']], secs[env['name']] = c, round(time.time() - te, 1)
    acc = {e['name']: {r: round(float(np.mean([x for x, p in zip(cols[e['name']]['correct'], e['problems']) if p['range'] == r] or [0])), 4)
                       for r in ('ID', 'OOD')} for e in ENVS}
    log(f'W{w}', repo, rev, 'точность', acc, '| время', round(time.time() - t, 1), 'с')
    del model
    gc.collect(); torch.cuda.empty_cache()
    shutil.rmtree(cache, ignore_errors=True)                                # место на диске
    return dict(model=repo.split('/')[-1], repo=repo, revision=rev, where=where, worker=w, seconds=round(time.time() - t, 1),
                seconds_env=secs, cols=cols)


def worker(w, idx, n_gpu):
    if n_gpu > 1:
        os.environ['CUDA_VISIBLE_DEVICES'] = str(w)                         # до первого обращения к CUDA в этом процессе
    info = dict(worker=w, device='cuda' if torch.cuda.is_available() else 'cpu',
                gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
    log(f'W{w}', 'площадка:', info, '| головы', [HEADS[k] for k in idx])
    part = dict(info=info, heads={})
    for k in idx:
        repo, rev = HEADS[k]
        try:
            part['heads'][str(k)] = run(repo, rev, w, solo=n_gpu <= 1)
        except Exception as e:
            log(f'W{w}', 'ОШИБКА', repo, rev, type(e).__name__, str(e)[:300])
            gc.collect()
            part['heads'][str(k)] = dict(model=repo.split('/')[-1], repo=repo, revision=rev, worker=w, error=f'{type(e).__name__}: {str(e)[:300]}')
        json.dump(part, open(os.path.join(OUT, f'part_w{w}.json'), 'w'), ensure_ascii=False)


def gpu_count():
    """Число видеокарт без обращения к CUDA в родительском процессе (иначе fork небезопасен)."""
    try:
        return subprocess.run(['nvidia-smi', '-L'], capture_output=True, text=True, timeout=60).stdout.count('GPU ')
    except Exception:
        return 0


def main():
    n_gpu = gpu_count()
    du = shutil.disk_usage(os.path.expanduser('~'))
    info = dict(mode=MODE, python=sys.version.split()[0], torch=torch.__version__, transformers=transformers.__version__, n_gpu=n_gpu,
                disk_free_gb=round(du.free / 2 ** 30, 1), cpus=os.cpu_count())
    log('площадка:', info, '| сред', len(ENVS), '| задач', sum(len(e['problems']) for e in ENVS))
    for e in ENVS:
        log(' ', e['name'], 'задач', len(e['problems']), 'ID', sum(p['range'] == 'ID' for p in e['problems']),
            'OOD', sum(p['range'] == 'OOD' for p in e['problems']), '| подсказка', repr(e['prompt_head']))
    plan = WORKERS if n_gpu > 1 else [list(range(len(HEADS)))]
    ctx = mp.get_context('fork')
    procs = [ctx.Process(target=worker, args=(w, idx, n_gpu)) for w, idx in enumerate(plan)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    heads, winfo = {}, []

    def collect(w):
        f = os.path.join(OUT, f'part_w{w}.json')
        if os.path.exists(f):
            part = json.load(open(f))
            heads.update(part['heads'])
            winfo.append(part['info'])
            os.remove(f)
    for w in range(len(plan)):
        collect(w)
    failed = [k for k in range(len(HEADS)) if 'cols' not in heads.get(str(k), {})]
    if failed:                                # запасной путь: по одной голове в самом родительском процессе (без fork, карта 0)
        log('повтор без параллели, головы:', [HEADS[k] for k in failed])
        first = {str(k): heads.get(str(k), {}).get('error', 'нет результата (процесс не дошёл)') for k in failed}
        for d in ('~/.cache/hf_w0', '~/.cache/hf_w1'):
            shutil.rmtree(os.path.expanduser(d), ignore_errors=True)
        try:
            worker(9, failed, 1)
        except Exception as e:
            log('ОШИБКА повтора', type(e).__name__, str(e)[:300])
        collect(9)
        for k in failed:
            if str(k) in heads:
                heads[str(k)]['first_error'] = first[str(k)]
    res = dict(info=dict(info, workers=winfo, exit_codes=[p.exitcode for p in procs]), mode=MODE,
               design=dict(ranges=list(RANGES), b=list(B_RANGE), shots_base=SHOTS_BASE, split_base=SPLIT_BASE, n_env=N_ENV, n_pilot=N_PILOT,
                           p_test=list(P_TEST), p_pilot=P_PILOT, check_n=CHECK_N, plan=plan),
               envs=ENVS,
               heads=[heads.get(str(k), dict(model=HEADS[k][0].split('/')[-1], repo=HEADS[k][0], revision=HEADS[k][1], error='нет результата (процесс не дошёл)'))
                      for k in range(len(HEADS))],
               seconds=round(time.time() - T0, 1))
    json.dump(res, open(os.path.join(OUT, 'answers.json'), 'w'), ensure_ascii=False)
    log('готово')


if not IMPORT_ONLY:
    main()
