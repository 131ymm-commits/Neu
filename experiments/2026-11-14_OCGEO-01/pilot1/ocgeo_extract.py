#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCGEO-01: извлечение на Kaggle (видеокарта, интернет) — ответы голов Pythia и соседи в их представлениях.
Один и тот же файл для пилота (SPLIT = 'pilot') и теста (SPLIT = 'test'); разделение задач задано зерном и не зависит
от модели. Без личных данных.

Задачи: все пары a, b ∈ [10, 99] (8100), кроме двух пар из подсказки; разделение зерном 7 200 000: пилот — 30 %,
тест — 70 %. Внутри части: ID — сумма < 100 (банк калибровки), OOD — сумма ≥ 100 (цели вне диапазона калибровки).
Подсказка — 4 примера пилота 0 (зерно 7 190 000), та же у всех голов.
Головы — EleutherAI/pythia-{1.4b, 1.4b-deduped, 2.8b, 2.8b-deduped, 6.9b}; начальная линия геометрии — pythia-1.4b
ревизии step0 (необученная). Для каждой модели:
  ответ — жадно, до 6 новых токенов; правильность — по коду; logp — сумма логарифмов вероятностей токенов ответа;
  представление — скрытое состояние последнего токена подсказки на слоях L/4, L/2, 3L/4, L;
  соседи — для каждой задачи части 50 ближайших задач банка ID этой части по косинусу (центровка по среднему банка),
  сама задача исключена; сохраняются номера и косинусы.
Вывод — /kaggle/working: answers.json, nbrs_<модель>_<ревизия>.npz."""
import gc
import json
import os
import re
import shutil
import subprocess
import sys
import time

SPLIT = 'pilot'                      # 'pilot' или 'test' — меняется только эта строка
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
from transformers import AutoTokenizer, GPTNeoXForCausalLM

DEV = 'cuda' if torch.cuda.is_available() else 'cpu'
INFO = dict(split=SPLIT, python=sys.version.split()[0], torch=torch.__version__, transformers=transformers.__version__,
            device=DEV, gpu=torch.cuda.get_device_name(0) if DEV == 'cuda' else None)
log('площадка:', INFO)
HEADS = [('pythia-1.4b', 'main'), ('pythia-1.4b-deduped', 'main'), ('pythia-2.8b', 'main'), ('pythia-2.8b-deduped', 'main'),
         ('pythia-6.9b', 'main'), ('pythia-1.4b', 'step0')]
SHOTS_SEED, SPLIT_SEED, K_NB = 7_190_000, 7_200_000, 50


def prompt_head():
    g = np.random.default_rng(SHOTS_SEED)                 # ровно как в пилоте 0
    ex = [(int(g.integers(10, 100)), int(g.integers(10, 100))) for _ in range(2)] + \
         [(int(g.integers(100, 1000)), int(g.integers(100, 1000))) for _ in range(2)]
    order = g.permutation(4)
    return ''.join(f'{ex[i][0]}+{ex[i][1]}={ex[i][0] + ex[i][1]}\n' for i in order), ex


HEAD, EX = prompt_head()
pairs = [(a, b) for a in range(10, 100) for b in range(10, 100) if (a, b) not in set(EX)]
perm = np.random.default_rng(SPLIT_SEED).permutation(len(pairs))
n_pilot = int(round(0.3 * len(pairs)))
part = sorted(perm[:n_pilot]) if SPLIT == 'pilot' else sorted(perm[n_pilot:])
PROBS = [dict(id=int(i), a=pairs[i][0], b=pairs[i][1], sum=pairs[i][0] + pairs[i][1]) for i in part]
for p in PROBS:
    p['range'] = 'ID' if p['sum'] < 100 else 'OOD'
BANK = np.array([j for j, p in enumerate(PROBS) if p['range'] == 'ID'])
PROMPTS = [HEAD + f"{p['a']}+{p['b']}=" for p in PROBS]
log(f'часть {SPLIT}: задач {len(PROBS)}, банк ID {len(BANK)}, OOD {len(PROBS) - len(BANK)} | подсказка {HEAD!r}')


def answer_logp(tok, ids, lp_rows):
    """Ответ — ведущее целое; logp — сумма по токенам, пока префикс остаётся числом."""
    text = tok.decode(ids)
    m = re.match(r'\s*(\d+)', text)
    ans = int(m.group(1)) if m else None
    lps, acc = [], ''
    for k, tid in enumerate(ids):
        piece = tok.decode([tid])
        if not re.fullmatch(r'\s*\d*', acc + piece) or (k > 0 and not re.fullmatch(r'\s*\d+', acc + piece)):
            break
        acc += piece
        lps.append(float(lp_rows[k][tid]))
    return ans, text[:16], (float(np.sum(lps)) if lps else None), len(lps)


def load(name, rev):
    kw = dict(revision=rev, torch_dtype=torch.float16)
    try:
        return GPTNeoXForCausalLM.from_pretrained(f'EleutherAI/{name}', **kw).to(DEV).eval(), 'gpu'
    except torch.cuda.OutOfMemoryError:
        gc.collect(); torch.cuda.empty_cache()
        return GPTNeoXForCausalLM.from_pretrained(f'EleutherAI/{name}', device_map='auto',
                                                  max_memory={0: '13GiB', 'cpu': '26GiB'}, **kw).eval(), 'gpu+cpu'


def run(name, rev):
    t = time.time()
    tok = AutoTokenizer.from_pretrained(f'EleutherAI/{name}', revision=rev)
    tok.padding_side, tok.pad_token = 'left', tok.eos_token
    model, where = load(name, rev)
    L = model.config.num_hidden_layers
    layers = [L // 4, L // 2, 3 * L // 4, L]
    bs = 8 if '6.9b' in name else 32
    log(name, rev, 'загружена', where, round(time.time() - t, 1), 'с; слоёв', L, 'слои', layers)
    rows, H = [], {l: [] for l in layers}
    dev0 = next(model.parameters()).device
    for i in range(0, len(PROMPTS), bs):
        enc = tok(PROMPTS[i:i + bs], return_tensors='pt', padding=True).to(dev0)
        with torch.no_grad():
            out = model(**enc, output_hidden_states=True)
            for l in layers:
                H[l].append(out.hidden_states[l][:, -1, :].float().cpu().numpy())
            gen = model.generate(**enc, max_new_tokens=6, do_sample=False, output_scores=True,
                                 return_dict_in_generate=True, pad_token_id=tok.eos_token_id)
        seqs = gen.sequences[:, enc['input_ids'].shape[1]:].tolist()
        lp = torch.stack([torch.log_softmax(s.float(), -1) for s in gen.scores], 1).cpu().numpy()
        for j, ids in enumerate(seqs):
            p = PROBS[i + j]
            ans, text, lsum, ntok = answer_logp(tok, ids, lp[j])
            rows.append(dict(answer=ans, correct=ans == p['sum'], text=text, logp=lsum, n_tok=ntok))
        del out, gen
    nb = {}
    for l in layers:
        X = np.concatenate(H[l])
        X = X - X[BANK].mean(0)
        X /= np.linalg.norm(X, axis=1, keepdims=True) + 1e-9
        S = X @ X[BANK].T                                  # (задачи, банк)
        own = {int(j): k for k, j in enumerate(BANK)}
        for j, k in own.items():
            S[j, k] = -np.inf                              # сама задача — не сосед
        idx = np.argsort(-S, axis=1)[:, :K_NB]
        nb[f'idx_L{l}'] = idx.astype(np.int16)             # номер в BANK
        nb[f'cos_L{l}'] = np.take_along_axis(S, idx, 1).astype(np.float16)
    np.savez_compressed(os.path.join(OUT, f'nbrs_{name}_{rev}.npz'), **nb)
    acc = {r: float(np.mean([x['correct'] for x, p in zip(rows, PROBS) if p['range'] == r])) for r in ('ID', 'OOD')}
    log(name, rev, 'точность', acc, '| время', round(time.time() - t, 1), 'с')
    del model
    gc.collect(); torch.cuda.empty_cache()
    shutil.rmtree(os.path.expanduser('~/.cache/huggingface/hub'), ignore_errors=True)    # место на диске
    return dict(model=name, revision=rev, layers=layers, n_layers=L, where=where, accuracy=acc, seconds=time.time() - t, rows=rows)


res = dict(info=INFO, split=SPLIT, prompt_head=HEAD, problems=PROBS, bank=BANK.tolist(), k_nb=K_NB, heads=[])
for name, rev in HEADS:
    try:
        res['heads'].append(run(name, rev))
    except Exception as e:
        log('ОШИБКА', name, rev, type(e).__name__, str(e)[:300])
        res['heads'].append(dict(model=name, revision=rev, error=f'{type(e).__name__}: {str(e)[:300]}'))
    json.dump(res, open(os.path.join(OUT, 'answers.json'), 'w'), ensure_ascii=False)
res['seconds'] = time.time() - T0
json.dump(res, open(os.path.join(OUT, 'answers.json'), 'w'), ensure_ascii=False)
log('готово')
