#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCGEO-01, пилот 0 (Kaggle, видеокарта, интернет): трудность сложения для голов Pythia и проверка площадки.
Зёрна пилота — вне теста: задачи 7 100 000 +, примеры в подсказке 7 190 000. Тест будет брать другие зёрна.
Для каждой модели и задачи: жадный ответ (до 6 новых токенов), правильность по коду, логарифмы вероятностей токенов
ответа, скрытые состояния последнего токена подсказки на 5 слоях (0, L/4, L/2, 3L/4, L), float16.
Модели — EleutherAI/pythia-{160m,410m,1b,1.4b,2.8b} (основная ревизия) и pythia-410m ревизии step0 (необученная —
начальная линия геометрии). Вывод — /kaggle/working: results.json, hidden_<модель>.npz. Без личных данных."""
import json
import os
import re
import subprocess
import sys
import time

T0 = time.time()
OUT = '/kaggle/working' if os.path.isdir('/kaggle/working') else os.path.abspath('pilot0_out')
os.makedirs(OUT, exist_ok=True)


def log(*a):
    print(f'[{time.time() - T0:7.1f} с]', *a, flush=True)


try:
    import torch
    import transformers  # noqa: F401
except Exception:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'torch', 'transformers', 'accelerate'], check=True)
    import torch
import numpy as np
from transformers import AutoTokenizer, GPTNeoXForCausalLM

DEV = 'cuda' if torch.cuda.is_available() else 'cpu'
info = dict(python=sys.version.split()[0], torch=torch.__version__, transformers=transformers.__version__ if 'transformers' in dir() else None,
            device=DEV, gpu=torch.cuda.get_device_name(0) if DEV == 'cuda' else None)
import transformers as _tf  # noqa: E402
info['transformers'] = _tf.__version__
log('площадка:', info)

MODELS = [('pythia-160m', 'main'), ('pythia-410m', 'main'), ('pythia-1b', 'main'), ('pythia-1.4b', 'main'),
          ('pythia-2.8b', 'main'), ('pythia-410m', 'step0')]
SHOTS_SEED, PROB_SEED = 7_190_000, 7_100_000


def make_problems():
    g = np.random.default_rng(PROB_SEED)
    P = [dict(set='2d', a=int(g.integers(10, 100)), b=int(g.integers(10, 100))) for _ in range(240)]
    P += [dict(set='3d', a=int(g.integers(100, 1000)), b=int(g.integers(100, 1000))) for _ in range(120)]
    for i, p in enumerate(P):
        p['id'], p['sum'] = i, p['a'] + p['b']
    return P


def make_prompt_head():
    g = np.random.default_rng(SHOTS_SEED)
    ex = [(int(g.integers(10, 100)), int(g.integers(10, 100))) for _ in range(2)] + \
         [(int(g.integers(100, 1000)), int(g.integers(100, 1000))) for _ in range(2)]
    order = g.permutation(4)
    return ''.join(f'{ex[i][0]}+{ex[i][1]}={ex[i][0] + ex[i][1]}\n' for i in order)


PROBS = make_problems()
HEAD = make_prompt_head()
PROMPTS = [HEAD + f"{p['a']}+{p['b']}=" for p in PROBS]
log('задач:', len(PROBS), '| подсказка:', repr(HEAD))


def run_model(name, rev, bs=24):
    t = time.time()
    tok = AutoTokenizer.from_pretrained(f'EleutherAI/{name}', revision=rev)
    tok.padding_side = 'left'
    tok.pad_token = tok.eos_token
    model = GPTNeoXForCausalLM.from_pretrained(f'EleutherAI/{name}', revision=rev, torch_dtype=torch.float16).to(DEV).eval()
    L = model.config.num_hidden_layers
    layers = sorted({0, L // 4, L // 2, 3 * L // 4, L})
    log(name, rev, 'загружена за', round(time.time() - t, 1), 'с; слоёв', L, '; ширина', model.config.hidden_size, '; слои', layers)
    rows, H = [], {l: [] for l in layers}
    for i in range(0, len(PROMPTS), bs):
        batch = PROMPTS[i:i + bs]
        enc = tok(batch, return_tensors='pt', padding=True).to(DEV)
        with torch.no_grad():
            out = model(**enc, output_hidden_states=True)
            for l in layers:
                H[l].append(out.hidden_states[l][:, -1, :].float().cpu().numpy().astype(np.float16))
            gen = model.generate(**enc, max_new_tokens=6, do_sample=False, output_scores=True, return_dict_in_generate=True,
                                 pad_token_id=tok.eos_token_id)
        seqs = gen.sequences[:, enc['input_ids'].shape[1]:]
        logp = torch.stack([torch.log_softmax(s.float(), -1) for s in gen.scores], 1)       # (b, шаги, словарь)
        for j in range(len(batch)):
            ids = seqs[j].tolist()
            text = tok.decode(ids)
            m = re.match(r'\s*(\d+)', text)
            ans = int(m.group(1)) if m else None
            # токены ответа — пока декодированный префикс остаётся числом
            lps, acc = [], ''
            for k, tid in enumerate(ids):
                piece = tok.decode([tid])
                if not re.fullmatch(r'\s*\d+', acc + piece) and k > 0:
                    break
                if not re.fullmatch(r'\s*\d*', acc + piece):
                    break
                acc += piece
                lps.append(float(logp[j, k, tid]))
            p = PROBS[i + j]
            rows.append(dict(id=p['id'], set=p['set'], answer=ans, correct=ans == p['sum'], text=text[:20],
                             logp_sum=float(np.sum(lps)) if lps else None, logp_first=lps[0] if lps else None, n_tok=len(lps)))
    np.savez_compressed(os.path.join(OUT, f'hidden_{name}_{rev}.npz'), **{f'L{l}': np.concatenate(H[l]) for l in layers})
    acc = {s: float(np.mean([r['correct'] for r in rows if r['set'] == s])) for s in ('2d', '3d')}
    log(name, rev, 'точность', acc, '| время', round(time.time() - t, 1), 'с')
    del model
    torch.cuda.empty_cache()
    return dict(model=name, revision=rev, layers=layers, n_layers=L, width=None, rows=rows, accuracy=acc, seconds=time.time() - t)


res = dict(info=info, problems=PROBS, prompt_head=HEAD, models=[])
for name, rev in MODELS:
    try:
        res['models'].append(run_model(name, rev))
    except Exception as e:                       # модель не загрузилась — записать и идти дальше
        log('ОШИБКА', name, rev, type(e).__name__, str(e)[:300])
        res['models'].append(dict(model=name, revision=rev, error=f'{type(e).__name__}: {str(e)[:300]}'))
    json.dump(res, open(os.path.join(OUT, 'results.json'), 'w'), ensure_ascii=False)
res['seconds'] = time.time() - T0
json.dump(res, open(os.path.join(OUT, 'results.json'), 'w'), ensure_ascii=False)
log('готово')
