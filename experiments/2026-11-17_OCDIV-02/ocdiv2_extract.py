#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-02 «ОЦЕНЩИК-ТРУДНЫЙ-СДВИГ»: среды двух семейств сдвига и ответы одной открытой модели на процессоре раннера GitHub Actions
(одно задание — одна голова, одна или несколько сред). Гипотеза — HYPOTHESIS.md (коммит 7187bab5).
- Среды (envs_ocdiv2):
  - a ∈ [100·X, 100·X + 99], b ∈ [10, 99], граница 100·(X + 1); ID — сумма меньше границы;
  - подсказка — ocpost_extract.shots с зерном 7 600 000 + 1000·X + p: два примера ID, два OOD;
  - пары — без примеров обеих подсказок (p = 0 и p = 2); перестановка пар — зерно SPLIT2 + X;
  - пилот — места перестановки 0…399 (p = 0); тест — места 1000…3199 (p = 2). Пилот и тест не пересекаются.
- Семейства: «тысячи» (X = 19…59, a четырёхзначное; 6 новых токенов, как в OCDIV-01) и «длина» (X = 9…99999, a от 3 до 7 цифр;
  сумма вне диапазона на цифру длиннее; 10 новых токенов).
- Запрос, генерация и разбор — как в ocdiv_extract.run (OCDIV-01, регистрация c626aa32): запрос prompt_head + "a+b=", без
  чат-шаблона, левое дополнение, жадный вывод, ответ и logp — ocpost_extract.answer_logp. Отличие одно: число новых токенов —
  из среды (max_new). Равенство с ocdiv_extract.run при max_new = 6 проверяет test_ocdiv2.py --real.
- В лог задания точность и счёт ответов не пишутся (замок ERRORS № 180): только время по средам.
  python3 ocdiv2_extract.py --phase pilot|test --model REPO [--revision REV] --envs NAME,NAME... --out DIR [--bs 16]"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time

import numpy as np

X_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X_DIR))
sys.path.insert(0, os.path.join(ROOT, 'experiments/2026-11-16_OCDIV-01'))
import ocdiv_extract as DX  # noqa: E402   OCDIV-01: ocpost_extract (OE), prompt_sha, cpu_model, pip_freeze
OE = DX.OE
answer_logp = OE.answer_logp

FAMILIES = {'thousands': dict(code='T', X=(19, 29, 39, 49, 59), max_new=6),
            'length': dict(code='L', X=(9, 99, 999, 9999, 99999), max_new=10)}
P_PILOT, P_TEST = 0, 2
N_PILOT, N_TEST, RESERVE = 400, 2200, 1000       # пилот — места 0…399; места 400…999 — запас под второй пилот; тест — с места 1000
SPLIT2 = 8_100_000                                # перестановка пар среды OCDIV-02: зерно 8 100 000 + X (новое)


def env_of(fam, X, p, n_take, start):
    a_range, bound = (100 * X, 100 * X + 99), 100 * (X + 1)
    hd = {q: OE.shots(a_range, bound, OE.SHOTS_BASE + 1000 * X + q) for q in (P_PILOT, P_TEST)}
    ex = set(e for q in hd for e in hd[q][1])                    # примеры обеих подсказок в задачи не идут
    pairs = [(a, b) for a in range(a_range[0], a_range[1] + 1) for b in range(OE.B_RANGE[0], OE.B_RANGE[1] + 1) if (a, b) not in ex]
    perm = np.random.default_rng(SPLIT2 + X).permutation(len(pairs))
    idx = sorted(int(i) for i in perm[start:start + n_take])
    f = FAMILIES[fam]
    return dict(name=f"{f['code']}_X{X}_p{p}", family=fam, X=X, p=p, bound=bound, a=list(a_range), b=list(OE.B_RANGE), max_new=f['max_new'],
                shots_seed=OE.SHOTS_BASE + 1000 * X + p, split_seed=SPLIT2 + X, prompt_head=hd[p][0],
                problems=OE.problems(pairs, idx, bound), idx=idx, n_pairs=len(pairs), place=[start, start + n_take])


def envs_ocdiv2(phase, fams=tuple(FAMILIES)):
    """Все среды фазы: pilot — p = 0, места 0…399; test — p = 2, места 1000…3199."""
    p, n, start = (P_PILOT, N_PILOT, 0) if phase == 'pilot' else (P_TEST, N_TEST, RESERVE)
    return [env_of(fam, X, p, n, start) for fam in fams for X in FAMILIES[fam]['X']]


def env_by_name(phase, names):
    allv = {e['name']: e for e in envs_ocdiv2(phase)}
    miss = [n for n in names if n not in allv]
    if miss:
        raise SystemExit(f'нет таких сред фазы {phase}: {miss}')
    return [allv[n] for n in names]


def run(repo, rev, envs, bs, log):
    """Как ocdiv_extract.run; число новых токенов — env['max_new']; в лог — только время."""
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from huggingface_hub import HfApi
    torch.set_num_threads(os.cpu_count() or 4)
    cache = tempfile.mkdtemp(prefix='hf_')
    t = time.time()
    load_errors = []
    for attempt in (1, 2):                                    # как в OCDIV-01: сбой загрузки — один повтор в том же задании
        try:
            commit = HfApi().model_info(repo, revision=rev).sha
            tok = AutoTokenizer.from_pretrained(repo, revision=commit, cache_dir=cache)
            model = AutoModelForCausalLM.from_pretrained(repo, revision=commit, dtype=torch.float32, cache_dir=cache).eval()
            break
        except Exception as e:                                # noqa: BLE001 — вторая неудача уходит в поле error вывода
            load_errors.append(f'попытка {attempt}: {type(e).__name__}: {str(e)[:300]}')
            log('сбой загрузки', load_errors[-1])
            if attempt == 2:
                raise
            time.sleep(30)
    tok.padding_side = 'left'
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
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
                gen = model.generate(**enc, max_new_tokens=int(env['max_new']), do_sample=False, output_scores=True,
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
        log(env['name'], '| задач', len(probs), '| время', secs[env['name']], 'с,', round(secs[env['name']] / max(len(probs), 1), 3), 'с на задачу')
    del model
    shutil.rmtree(cache, ignore_errors=True)
    return dict(repo=repo, revision=rev, commit=commit, load_seconds=load_s, load_errors=load_errors, seconds=round(time.time() - t, 1), seconds_env=secs,
                cols=cols, versions=dict(python=sys.version.split()[0], torch=torch.__version__, transformers=transformers.__version__, numpy=np.__version__),
                cpus=os.cpu_count(), machine=DX.platform.machine(), cpu_model=DX.cpu_model(), pip_freeze=DX.pip_freeze())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=('pilot', 'test'), required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--revision', default='main')
    ap.add_argument('--envs', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--bs', type=int, default=16)
    ap.add_argument('--limit', type=int, default=0, help='только для сухого прогона: первые N задач каждой среды')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()

    def log(*x):
        print(f'[{time.time() - t0:7.1f} с]', *x, flush=True)
    envs = env_by_name(a.phase, a.envs.split(','))
    if a.limit:
        envs = [dict(e, problems=e['problems'][:a.limit], idx=e['idx'][:a.limit]) for e in envs]
    log('фаза', a.phase, '| сред', len(envs), '| задач', sum(len(e['problems']) for e in envs))
    dst = os.path.join(a.out, f"answers_{a.model.split('/')[-1]}.json")
    res = dict(experiment='OCDIV-02', phase=a.phase, model=a.model, limit=a.limit,
               envs=[dict(name=e['name'], family=e['family'], X=e['X'], p=e['p'], max_new=e['max_new'], n=len(e['problems']), idx=e['idx'],
                          keys=[[q['a'], q['b']] for q in e['problems']], prompt_sha256=DX.prompt_sha(e['prompt_head'])) for e in envs])
    try:
        res.update(run(a.model, a.revision, envs, a.bs, log))
    except Exception as e:                       # не загрузилась или упала — записываем, задание не валим
        res['error'] = f'{type(e).__name__}: {str(e)[:500]}'
        log('ОШИБКА', res['error'])
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
    log('записано', dst)


if __name__ == '__main__':
    main()
