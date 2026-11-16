#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-01: ответы и logp одной открытой модели на процессоре раннера GitHub Actions (одно задание — одна голова).
- Задачи и подсказки — из сырого вывода опытов с Pythia, чтобы запросы совпадали побайтно:
  - тест — пять сред OCPOST-01: experiments/2026-11-15_OCPOST-01/run/out/answers.json;
  - пилот — десять сред OCSHIFT-01: experiments/2026-11-15_OCSHIFT-01/run/out/answers.json.
- Запрос, генерация и разбор — как в ocpost_extract.run (сверка по коду, HYPOTHESIS):
  - запрос prompt_head + "a+b=", без чат-шаблона; левое дополнение;
  - жадный вывод, не больше 6 новых токенов;
  - ответ и logp — функция answer_logp, импортом из ocpost_extract.py.
- Отличия от Kaggle: процессор, float32, пакет 16.
- Правда — по коду (ответ == a + b). Ревизия модели — хеш коммита с Hugging Face; пишется в вывод.
- Выборка задач среды — pick_idx: first — первые N (пилот 1; задачи отсортированы по (a, b), выборка смещена — ERRORS № 175);
  random — N случайных с зерном SEED_PICK + 10·X + p (пилот 2). Номера задач пишутся в вывод.
  python3 ocdiv_extract.py --source test|pilot --model REPO [--revision REV] [--envs all|X4_p2,...] [--n N] [--pick first|random] --out DIR [--bs 16]"""
import argparse
import importlib.util
import json
import os
import platform
import shutil
import sys
import tempfile
import time

import numpy as np

X = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X))
SRC = {'test': os.path.join(ROOT, 'experiments/2026-11-15_OCPOST-01/run/out/answers.json'),
       'pilot': os.path.join(ROOT, 'experiments/2026-11-15_OCSHIFT-01/run/out/answers.json')}


def load_ocpost_extract():
    """ocpost_extract.py без torch и без запуска (OCPOST_IMPORT_ONLY=1); модуль при импорте создаёт папку вывода — во временной папке."""
    os.environ['OCPOST_IMPORT_ONLY'] = '1'
    here = os.getcwd()
    os.chdir(tempfile.mkdtemp(prefix='ocpost_import_'))
    try:
        spec = importlib.util.spec_from_file_location('ocpost_extract', os.path.join(ROOT, 'experiments/2026-11-15_OCPOST-01/ocpost_extract.py'))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    finally:
        os.chdir(here)
    return m


OE = load_ocpost_extract()
answer_logp = OE.answer_logp
SEED_PICK = 7_960_000                                       # пилот 2: случайная выборка задач среды, зерно 7 960 000 + 10·X + p


def pick_idx(env, n, pick='first'):
    """Номера задач среды для счёта (одна функция для извлечения, сборки и ответов Pythia). n = 0 или n ≥ размера — все задачи."""
    N = len(env['problems'])
    if not n or n >= N:
        return list(range(N))
    if pick == 'first':
        return list(range(n))
    if pick == 'random':
        g = np.random.default_rng(SEED_PICK + 10 * int(env['X']) + int(env['p']))
        return sorted(int(i) for i in g.choice(N, n, replace=False))
    raise ValueError(f'неизвестная выборка {pick}')


def envs_of(source, names, n, pick='first'):
    d = json.load(open(SRC[source], encoding='utf-8'))
    out = []
    for e in d['envs']:
        if e.get('kind') == 'check':
            continue
        if names != 'all' and e['name'] not in names:
            continue
        idx = pick_idx(e, n, pick)
        out.append(dict(name=e['name'], X=e.get('X'), p=e.get('p'), bound=e['bound'], prompt_head=e['prompt_head'],
                        problems=[e['problems'][i] for i in idx], idx=idx))
    return out


def run(repo, rev, envs, bs, log):
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from huggingface_hub import HfApi
    torch.set_num_threads(os.cpu_count() or 4)
    cache = tempfile.mkdtemp(prefix='hf_')
    t = time.time()
    commit = HfApi().model_info(repo, revision=rev).sha       # хеш коммита модели; грузим ровно его (в transformers 5 поле _commit_hash пусто)
    tok = AutoTokenizer.from_pretrained(repo, revision=commit, cache_dir=cache)
    tok.padding_side = 'left'
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(repo, revision=commit, dtype=torch.float32, cache_dir=cache).eval()
    load_s = round(time.time() - t, 1)
    log(repo, rev, 'загружена за', load_s, 'с; ревизия', commit)
    cols, secs = {}, {}
    for env in envs:
        te = time.time()
        probs = env['problems']
        prompts = [env['prompt_head'] + f"{p['a']}+{p['b']}=" for p in probs]
        c = dict(answer=[], correct=[], logp=[], n_tok=[], text_none={})
        for i in range(0, len(prompts), bs):
            enc = tok(prompts[i:i + bs], return_tensors='pt', padding=True)
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
        acc = {r: round(float(np.mean([x for x, p in zip(c['correct'], probs) if p['range'] == r] or [0])), 4) for r in ('ID', 'OOD')}
        log(env['name'], 'точность', acc, '| без числа', len(c['text_none']), '| время', secs[env['name']], 'с,',
            round(secs[env['name']] / max(len(probs), 1), 3), 'с на задачу')
    del model
    shutil.rmtree(cache, ignore_errors=True)
    return dict(repo=repo, revision=rev, commit=commit, load_seconds=load_s, seconds=round(time.time() - t, 1), seconds_env=secs, cols=cols,
                versions=dict(python=sys.version.split()[0], torch=torch.__version__, transformers=transformers.__version__, numpy=np.__version__),
                cpus=os.cpu_count(), machine=platform.machine())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', choices=('test', 'pilot'), required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--revision', default='main')
    ap.add_argument('--envs', default='all')
    ap.add_argument('--n', type=int, default=0)
    ap.add_argument('--pick', choices=('first', 'random'), default='first')
    ap.add_argument('--out', required=True)
    ap.add_argument('--bs', type=int, default=16)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()

    def log(*x):
        print(f'[{time.time() - t0:7.1f} с]', *x, flush=True)
    names = 'all' if a.envs == 'all' else a.envs.split(',')
    envs = envs_of(a.source, names, a.n, a.pick)
    log('источник', a.source, '| выборка', a.pick, '| сред', len(envs), '| задач', sum(len(e['problems']) for e in envs),
        '| ID', sum(p['range'] == 'ID' for e in envs for p in e['problems']), '| OOD', sum(p['range'] == 'OOD' for e in envs for p in e['problems']))
    dst = os.path.join(a.out, f"answers_{a.model.split('/')[-1]}.json")
    res = dict(source=a.source, source_file=os.path.relpath(SRC[a.source], ROOT), model=a.model, n=a.n, pick=a.pick,
               envs=[dict(name=e['name'], n=len(e['problems']), idx=e['idx']) for e in envs])
    try:
        res.update(run(a.model, a.revision, envs, a.bs, log))
    except Exception as e:                       # не загрузилась или упала — записываем, задание не валим: это данные пилота
        res['error'] = f'{type(e).__name__}: {str(e)[:500]}'
        log('ОШИБКА', res['error'])
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
    log('записано', dst)


if __name__ == '__main__':
    main()
