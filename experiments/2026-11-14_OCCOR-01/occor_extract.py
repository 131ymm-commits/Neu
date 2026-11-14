#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCCOR-01: извлечение на Kaggle (видеокарта, интернет) — ответы голов и logp ответа. Без скрытых состояний, без
личных данных. Один файл для пилота (SPLIT = 'pilot') и теста (SPLIT = 'test'); разделение задач задано зерном до данных
и от моделей не зависит.

Задача — «трёхзначное + двузначное»: все пары a ∈ [100, 199], b ∈ [10, 99] (9000), кроме четырёх пар подсказки.
ID — сумма < 200 (калибровка оценщиков), OOD — сумма ≥ 200 (цели). Разделение зерном 7 310 000: пилот — 30 %, тест — 70 %.
Подсказка — 4 примера той же задачи (зерно 7 300 000: два с суммой < 200 и два с суммой ≥ 200, порядок перемешан),
одна у всех голов.
Ответ — жадно, до 6 новых токенов; ответ головы — ведущее целое; правильность — по коду; logp — сумма логарифмов
вероятностей токенов ответа, пока префикс остаётся числом. Вывод — /kaggle/working/answers.json (Colab — ./<SPLIT>_out)."""
import gc
import json
import os
import re
import shutil
import subprocess
import sys
import time

SPLIT = 'pilot'                      # 'pilot' или 'test' — меняется только эта строка (и список голов теста по PREREG)
T0 = time.time()
OUT = '/kaggle/working' if os.path.isdir('/kaggle/working') else os.path.abspath(f'{SPLIT}_out')
os.makedirs(OUT, exist_ok=True)


def log(*a):
    print(f'[{time.time() - T0:7.1f} с]', *a, flush=True)


try:
    import torch
    import transformers
except Exception:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'torch', 'transformers', 'accelerate'], check=True)
    import torch
    import transformers
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer

DEV = 'cuda' if torch.cuda.is_available() else 'cpu'
INFO = dict(split=SPLIT, python=sys.version.split()[0], torch=torch.__version__, transformers=transformers.__version__,
            device=DEV, gpu=torch.cuda.get_device_name(0) if DEV == 'cuda' else None,
            n_gpu=torch.cuda.device_count() if DEV == 'cuda' else 0)
log('площадка:', INFO)

# Головы пилота: Pythia разных размеров и наборов данных; «клоны» — поздние чекпойнты pythia-2.8b (main = step143000);
# головы других семейств. Список теста закрепляет PREREG.
HEADS = [('EleutherAI/pythia-1.4b', 'main'), ('EleutherAI/pythia-1.4b-deduped', 'main'),
         ('EleutherAI/pythia-2.8b', 'main'), ('EleutherAI/pythia-2.8b', 'step133000'),
         ('EleutherAI/pythia-2.8b', 'step123000'), ('EleutherAI/pythia-2.8b', 'step113000'),
         ('EleutherAI/pythia-2.8b-deduped', 'main'), ('EleutherAI/pythia-6.9b', 'main'),
         ('EleutherAI/pythia-6.9b-deduped', 'main'), ('facebook/opt-2.7b', 'main'), ('EleutherAI/gpt-neo-2.7B', 'main')]
SHOTS_SEED, SPLIT_SEED, PILOT_FRAC = 7_300_000, 7_310_000, 0.3
A_RANGE, B_RANGE, BOUND = (100, 199), (10, 99), 200


def prompt_head():
    g = np.random.default_rng(SHOTS_SEED)
    ex = []
    while len(ex) < 4:
        a, b = int(g.integers(A_RANGE[0], A_RANGE[1] + 1)), int(g.integers(B_RANGE[0], B_RANGE[1] + 1))
        need_id = len(ex) < 2
        if (a + b < BOUND) == need_id and (a, b) not in ex:
            ex.append((a, b))
    order = g.permutation(4)
    return ''.join(f'{ex[i][0]}+{ex[i][1]}={ex[i][0] + ex[i][1]}\n' for i in order), ex


HEAD, EX = prompt_head()
pairs = [(a, b) for a in range(A_RANGE[0], A_RANGE[1] + 1) for b in range(B_RANGE[0], B_RANGE[1] + 1) if (a, b) not in set(EX)]
perm = np.random.default_rng(SPLIT_SEED).permutation(len(pairs))
n_pilot = int(round(PILOT_FRAC * len(pairs)))
part = sorted(perm[:n_pilot]) if SPLIT == 'pilot' else sorted(perm[n_pilot:])
PROBS = [dict(id=int(i), a=pairs[i][0], b=pairs[i][1], sum=pairs[i][0] + pairs[i][1]) for i in part]
for p in PROBS:
    p['range'] = 'ID' if p['sum'] < BOUND else 'OOD'
PROMPTS = [HEAD + f"{p['a']}+{p['b']}=" for p in PROBS]
log(f"часть {SPLIT}: задач {len(PROBS)}, ID {sum(p['range'] == 'ID' for p in PROBS)}, OOD {sum(p['range'] == 'OOD' for p in PROBS)}"
    f" | подсказка {HEAD!r}")


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


def load(repo, rev):
    kw = dict(revision=rev, torch_dtype=torch.float16)
    if DEV != 'cuda':
        return AutoModelForCausalLM.from_pretrained(repo, **kw).eval(), 'cpu'
    try:
        return AutoModelForCausalLM.from_pretrained(repo, device_map={'': 0}, **kw).eval(), 'gpu'
    except torch.cuda.OutOfMemoryError:
        gc.collect(); torch.cuda.empty_cache()
        return AutoModelForCausalLM.from_pretrained(repo, device_map='auto', **kw).eval(), 'auto'


def run(repo, rev):
    t = time.time()
    tok = AutoTokenizer.from_pretrained(repo, revision=rev)
    tok.padding_side = 'left'
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model, where = load(repo, rev)
    bs = 8 if '6.9b' in repo else 32
    log(repo, rev, 'загружена', where, round(time.time() - t, 1), 'с')
    rows = []
    dev0 = next(model.parameters()).device
    for i in range(0, len(PROMPTS), bs):
        enc = tok(PROMPTS[i:i + bs], return_tensors='pt', padding=True).to(dev0)
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=6, do_sample=False, output_scores=True,
                                 return_dict_in_generate=True, pad_token_id=tok.pad_token_id)
        seqs = gen.sequences[:, enc['input_ids'].shape[1]:].tolist()
        lp = torch.stack([torch.log_softmax(s.float(), -1) for s in gen.scores], 1).cpu().numpy()
        for j, ids in enumerate(seqs):
            p = PROBS[i + j]
            ans, text, lsum, ntok = answer_logp(tok, ids, lp[j])
            rows.append(dict(answer=ans, correct=ans == p['sum'], text=text, logp=lsum, n_tok=ntok))
        del gen
    acc = {r: float(np.mean([x['correct'] for x, p in zip(rows, PROBS) if p['range'] == r])) for r in ('ID', 'OOD')}
    log(repo, rev, 'точность', acc, '| время', round(time.time() - t, 1), 'с')
    del model
    gc.collect(); torch.cuda.empty_cache()
    shutil.rmtree(os.path.expanduser('~/.cache/huggingface/hub'), ignore_errors=True)    # место на диске
    return dict(model=repo.split('/')[-1], repo=repo, revision=rev, where=where, accuracy=acc, seconds=time.time() - t, rows=rows)


res = dict(info=INFO, split=SPLIT, task=dict(a=A_RANGE, b=B_RANGE, bound=BOUND, shots_seed=SHOTS_SEED, split_seed=SPLIT_SEED,
                                              pilot_frac=PILOT_FRAC),
           prompt_head=HEAD, problems=PROBS, heads=[])
for repo, rev in HEADS:
    try:
        res['heads'].append(run(repo, rev))
    except Exception as e:
        log('ОШИБКА', repo, rev, type(e).__name__, str(e)[:300])
        res['heads'].append(dict(model=repo.split('/')[-1], repo=repo, revision=rev, error=f'{type(e).__name__}: {str(e)[:300]}'))
    json.dump(res, open(os.path.join(OUT, 'answers.json'), 'w'), ensure_ascii=False)
res['seconds'] = time.time() - T0
json.dump(res, open(os.path.join(OUT, 'answers.json'), 'w'), ensure_ascii=False)
log('готово')
